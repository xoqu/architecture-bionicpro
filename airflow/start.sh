#!/usr/bin/env bash
set -euo pipefail

mkdir -p /opt/airflow/data

airflow db migrate

airflow users create \
  --username airflow \
  --firstname Air \
  --lastname Flow \
  --role Admin \
  --email airflow@example.com \
  --password airflow \
  || true

airflow scheduler &
scheduler_pid=$!

# Новый DAG в Airflow 2 создаётся на паузе. Без снятия паузы расписание 02:00 не запускается.
for _ in 1 2 3 4 5 6 7 8 9 10 11 12; do
  if airflow dags unpause build_report_mart; then
    break
  fi
  sleep 5
done

airflow webserver --port 8080 &
webserver_pid=$!

wait -n "$scheduler_pid" "$webserver_pid"
