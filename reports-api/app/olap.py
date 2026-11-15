from __future__ import annotations

from datetime import date, datetime, timedelta

import clickhouse_connect
from clickhouse_connect.driver.exceptions import DatabaseError, OperationalError
from pydantic import BaseModel

from app.config import (
    CLICKHOUSE_DATABASE,
    CLICKHOUSE_HOST,
    CLICKHOUSE_PASSWORD,
    CLICKHOUSE_PORT,
    CLICKHOUSE_USER,
)


class OlapUnavailable(Exception):
    pass


class ReportRow(BaseModel):
    user_id: str
    report_date: date
    prosthesis_id: str
    customer_name: str
    city: str
    events_count: int
    avg_response_ms: float
    max_response_ms: int
    avg_battery: float
    grip_count: int
    open_count: int
    pinch_count: int


class ReportResponse(BaseModel):
    user_id: str
    date_from: date
    date_to: date
    processed_until: date | None
    partial: bool
    message: str | None
    rows: list[ReportRow]


def _client():
    try:
        return clickhouse_connect.get_client(
            host=CLICKHOUSE_HOST,
            port=CLICKHOUSE_PORT,
            username=CLICKHOUSE_USER,
            password=CLICKHOUSE_PASSWORD,
            database=CLICKHOUSE_DATABASE,
        )
    except OperationalError as exc:
        raise OlapUnavailable(str(exc)) from exc


def _missing_object(exc: DatabaseError) -> bool:
    message = str(exc)
    return (
        "UNKNOWN_DATABASE" in message
        or "UNKNOWN_TABLE" in message
        or "doesn't exist" in message
        or "does not exist" in message
    )


def _as_date(value: date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    return value


def _processed_until() -> date | None:
    client = _client()
    try:
        rows = client.query(
            """
            SELECT processed_until
            FROM etl_watermark FINAL
            WHERE pipeline = {pipeline:String}
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            parameters={"pipeline": "report_mart"},
        ).result_rows
    except OperationalError as exc:
        raise OlapUnavailable(str(exc)) from exc
    except DatabaseError as exc:
        if _missing_object(exc):
            return None
        raise
    if not rows:
        return None
    return _as_date(rows[0][0])


def _read_mart(user_id: str, date_from: date, date_to: date) -> list[ReportRow]:
    client = _client()
    try:
        result = client.query(
            """
            SELECT
                user_id,
                report_date,
                prosthesis_id,
                customer_name,
                city,
                events_count,
                round(avg_response_ms, 1) AS avg_response_ms,
                max_response_ms,
                round(avg_battery, 1) AS avg_battery,
                grip_count,
                open_count,
                pinch_count
            FROM report_mart
            WHERE user_id = {user_id:String}
              AND report_date >= {date_from:Date}
              AND report_date <= {date_to:Date}
            ORDER BY report_date
            """,
            parameters={
                "user_id": user_id,
                "date_from": date_from,
                "date_to": date_to,
            },
        )
    except OperationalError as exc:
        raise OlapUnavailable(str(exc)) from exc
    except DatabaseError as exc:
        if _missing_object(exc):
            return []
        raise

    rows: list[ReportRow] = []
    for raw in result.result_rows:
        rows.append(
            ReportRow(
                user_id=str(raw[0]),
                report_date=_as_date(raw[1]),
                prosthesis_id=str(raw[2]),
                customer_name=str(raw[3]),
                city=str(raw[4]),
                events_count=int(raw[5]),
                avg_response_ms=float(raw[6]),
                max_response_ms=int(raw[7]),
                avg_battery=float(raw[8]),
                grip_count=int(raw[9]),
                open_count=int(raw[10]),
                pinch_count=int(raw[11]),
            )
        )
    return rows


def build_report(
    user_id: str,
    date_from: date | None,
    date_to: date | None,
) -> ReportResponse:
    today = date.today()
    requested_to = date_to or today
    watermark = _processed_until()

    if watermark is None:
        requested_from = date_from or (today - timedelta(days=6))
        return ReportResponse(
            user_id=user_id,
            date_from=requested_from,
            date_to=requested_to,
            processed_until=None,
            partial=True,
            message="Airflow ещё не собирал витрину. Отчёт за запрошенный период недоступен.",
            rows=[],
        )

    requested_from = date_from or (watermark - timedelta(days=6))
    effective_to = min(requested_to, watermark)
    partial = requested_to > watermark
    rows = (
        []
        if requested_from > effective_to
        else _read_mart(user_id, requested_from, effective_to)
    )
    message = None
    if requested_from > watermark:
        message = (
            "Запрошенный период ещё не обработан Airflow. "
            f"Последние обработанные сутки: {watermark.isoformat()}."
        )
    elif partial:
        message = (
            "В отчёт вошли только сутки по "
            f"{watermark.isoformat()}. Данные после этой даты ещё не обработаны Airflow."
        )
    return ReportResponse(
        user_id=user_id,
        date_from=requested_from,
        date_to=requested_to,
        processed_until=watermark,
        partial=partial,
        message=message,
        rows=rows,
    )
