"""Ежедневная сборка витрины отчётов из CRM и телеметрии.

В витрину попадают только уже завершённые сутки (event_time < сегодня, UTC).
Текущий день остаётся в источнике до следующего запуска.
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta

import clickhouse_connect
import psycopg2
from airflow.decorators import dag, task

logger = logging.getLogger(__name__)


def _source_connection():
    return psycopg2.connect(
        host=os.environ["SOURCE_DB_HOST"],
        port=os.environ.get("SOURCE_DB_PORT", "5432"),
        dbname=os.environ.get("SOURCE_DB_NAME", "bionicpro"),
        user=os.environ["SOURCE_DB_USER"],
        password=os.environ["SOURCE_DB_PASSWORD"],
    )


def _clickhouse_client(database: str | None = None):
    return clickhouse_connect.get_client(
        host=os.environ.get("CLICKHOUSE_HOST", "clickhouse"),
        port=int(os.environ.get("CLICKHOUSE_PORT", "8123")),
        username=os.environ.get("CLICKHOUSE_USER", "default"),
        password=os.environ.get("CLICKHOUSE_PASSWORD", ""),
        database=database,
    )


def _ensure_tables() -> None:
    bootstrap = _clickhouse_client()
    bootstrap.command("CREATE DATABASE IF NOT EXISTS reports")
    client = _clickhouse_client("reports")
    client.command(
        """
        CREATE TABLE IF NOT EXISTS crm_customers (
            user_id String,
            full_name String,
            email String,
            prosthesis_id String,
            city String
        ) ENGINE = MergeTree
        ORDER BY user_id
        """
    )
    client.command(
        """
        CREATE TABLE IF NOT EXISTS telemetry_events (
            user_id String,
            prosthesis_id String,
            event_time DateTime,
            movement String,
            response_time_ms Int32,
            battery_level Float64
        ) ENGINE = MergeTree
        ORDER BY (user_id, event_time)
        """
    )
    client.command(
        """
        CREATE TABLE IF NOT EXISTS report_mart (
            user_id String,
            report_date Date,
            prosthesis_id String,
            customer_name String,
            city String,
            events_count UInt32,
            avg_response_ms Float64,
            max_response_ms Int32,
            avg_battery Float64,
            grip_count UInt32,
            open_count UInt32,
            pinch_count UInt32
        ) ENGINE = MergeTree
        ORDER BY (user_id, report_date)
        """
    )
    client.command(
        """
        CREATE TABLE IF NOT EXISTS etl_watermark (
            pipeline String,
            processed_until Date,
            updated_at DateTime
        ) ENGINE = ReplacingMergeTree(updated_at)
        ORDER BY pipeline
        """
    )


@dag(
    dag_id="build_report_mart",
    schedule="0 2 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["reports", "bionicpro"],
    description="Собирает витрину отчётов из CRM и телеметрии за завершённые сутки",
)
def build_report_mart():
    @task
    def extract_crm() -> str:
        _ensure_tables()
        with _source_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT user_id, full_name, email, prosthesis_id, city
                    FROM crm.customers
                    ORDER BY user_id
                    """
                )
                rows = cursor.fetchall()

        client = _clickhouse_client("reports")
        client.command("TRUNCATE TABLE crm_customers")
        if rows:
            client.insert(
                "crm_customers",
                rows,
                column_names=["user_id", "full_name", "email", "prosthesis_id", "city"],
            )
        logger.info("CRM rows loaded: %s", len(rows))
        return f"crm:{len(rows)}"

    @task
    def extract_telemetry() -> str:
        _ensure_tables()
        today = date.today()
        with _source_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT user_id, prosthesis_id, event_time, movement,
                           response_time_ms, battery_level
                    FROM telemetry.events
                    WHERE event_time < %s
                    ORDER BY event_time
                    """,
                    (today,),
                )
                fetched = cursor.fetchall()

        prepared = [
            (
                user_id,
                prosthesis_id,
                event_time.replace(tzinfo=None),
                movement,
                int(response_time_ms),
                float(battery_level),
            )
            for user_id, prosthesis_id, event_time, movement, response_time_ms, battery_level in fetched
        ]
        client = _clickhouse_client("reports")
        client.command("TRUNCATE TABLE telemetry_events")
        if prepared:
            client.insert(
                "telemetry_events",
                prepared,
                column_names=[
                    "user_id",
                    "prosthesis_id",
                    "event_time",
                    "movement",
                    "response_time_ms",
                    "battery_level",
                ],
            )
        logger.info("Telemetry rows loaded for days before %s: %s", today, len(prepared))
        return f"telemetry:{len(prepared)}"

    @task
    def build_mart(crm_status: str, telemetry_status: str) -> str:
        client = _clickhouse_client("reports")
        client.command("TRUNCATE TABLE report_mart")
        client.command(
            """
            INSERT INTO report_mart
            SELECT
                t.user_id,
                toDate(t.event_time) AS report_date,
                any(t.prosthesis_id) AS prosthesis_id,
                any(c.full_name) AS customer_name,
                any(c.city) AS city,
                toUInt32(count()) AS events_count,
                avg(t.response_time_ms) AS avg_response_ms,
                max(t.response_time_ms) AS max_response_ms,
                avg(t.battery_level) AS avg_battery,
                toUInt32(countIf(t.movement = 'grip')) AS grip_count,
                toUInt32(countIf(t.movement = 'open')) AS open_count,
                toUInt32(countIf(t.movement = 'pinch')) AS pinch_count
            FROM telemetry_events AS t
            LEFT JOIN crm_customers AS c ON t.user_id = c.user_id
            GROUP BY t.user_id, report_date
            """
        )
        count = client.query("SELECT count() FROM report_mart").result_rows[0][0]
        logger.info("Mart rows: %s (%s, %s)", count, crm_status, telemetry_status)
        return f"mart:{count}"

    @task
    def update_watermark(mart_status: str) -> str:
        processed_until = date.today() - timedelta(days=1)
        client = _clickhouse_client("reports")
        client.insert(
            "etl_watermark",
            [["report_mart", processed_until, datetime.utcnow()]],
            column_names=["pipeline", "processed_until", "updated_at"],
        )
        logger.info("Watermark %s after %s", processed_until, mart_status)
        return processed_until.isoformat()

    crm_status = extract_crm()
    telemetry_status = extract_telemetry()
    mart_status = build_mart(crm_status, telemetry_status)
    update_watermark(mart_status)


build_report_mart()
