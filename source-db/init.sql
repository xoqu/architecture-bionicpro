CREATE SCHEMA IF NOT EXISTS crm;
CREATE SCHEMA IF NOT EXISTS telemetry;

CREATE TABLE crm.customers (
    user_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL,
    prosthesis_id TEXT NOT NULL,
    city TEXT NOT NULL
);

CREATE TABLE telemetry.events (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    prosthesis_id TEXT NOT NULL,
    event_time TIMESTAMPTZ NOT NULL,
    movement TEXT NOT NULL,
    response_time_ms INTEGER NOT NULL,
    battery_level NUMERIC(5, 2) NOT NULL
);

CREATE INDEX telemetry_events_user_time_idx
    ON telemetry.events (user_id, event_time);

INSERT INTO crm.customers (user_id, full_name, email, prosthesis_id, city)
VALUES
    ('prothetic1', 'Пилот Один', 'prothetic1@example.com', 'PR-100', 'Москва'),
    ('prothetic2', 'Пилот Два', 'prothetic2@example.com', 'PR-200', 'Казань');

-- Завершённые сутки: их заберёт Airflow. CURRENT_DATE в контейнере — UTC.
INSERT INTO telemetry.events (user_id, prosthesis_id, event_time, movement, response_time_ms, battery_level)
SELECT
    'prothetic1',
    'PR-100',
    (CURRENT_DATE - d) + make_interval(hours => h),
    (ARRAY['grip', 'open', 'pinch'])[1 + ((h + d) % 3)],
    40 + h + d,
    92 - d * 3
FROM generate_series(1, 5) AS d
CROSS JOIN generate_series(9, 17) AS h;

INSERT INTO telemetry.events (user_id, prosthesis_id, event_time, movement, response_time_ms, battery_level)
SELECT
    'prothetic2',
    'PR-200',
    (CURRENT_DATE - d) + make_interval(hours => h),
    (ARRAY['open', 'grip', 'pinch'])[1 + (h % 3)],
    55 + h,
    88 - d * 2
FROM generate_series(1, 3) AS d
CROSS JOIN generate_series(10, 16) AS h;

-- Текущие сутки Airflow не забирает: отчёт за сегодня должен быть недоступен, пока сутки не закрыты.
INSERT INTO telemetry.events (user_id, prosthesis_id, event_time, movement, response_time_ms, battery_level)
SELECT
    'prothetic1',
    'PR-100',
    CURRENT_DATE + make_interval(hours => h),
    'grip',
    30 + h,
    70
FROM generate_series(8, 12) AS h;
