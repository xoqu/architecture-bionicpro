# Инструкция по запуску и проверкам

## Запуск

```bash
docker compose up -d --build
```

- Отчёты: http://localhost:3000
- API: http://localhost:8000
- Airflow: http://localhost:8088 (`airflow` / `airflow`)
- Пользователи: `prothetic1` / `prothetic123` и `prothetic2` / `prothetic123`

## Проверки

1. Ручной прогон витрины, не дожидаясь расписания 02:00 UTC. После первой команды нужно дождаться `state=success` в выводе второй команды:

```bash
docker compose exec airflow airflow dags trigger build_report_mart
docker compose exec airflow airflow dags list-runs -d build_report_mart
```

2. Без токена API отвечает `401`:

```bash
curl -i http://localhost:8000/reports
```

3. Войти под пользователем `prothetic1`. Чужой отчёт:

```bash
curl -i -H "Authorization: Bearer <token prothetic1>" \
  "http://localhost:8000/reports?user_id=prothetic2"
```

Ожидается `403`. Тот же токен без `user_id` возвращает `200` и только строки `prothetic1`.
