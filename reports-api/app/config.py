import os


CLICKHOUSE_HOST = os.environ.get("CLICKHOUSE_HOST", "clickhouse")
CLICKHOUSE_PORT = int(os.environ.get("CLICKHOUSE_PORT", "8123"))
CLICKHOUSE_USER = os.environ.get("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.environ.get("CLICKHOUSE_PASSWORD", "")
CLICKHOUSE_DATABASE = os.environ.get("CLICKHOUSE_DATABASE", "reports")

KEYCLOAK_ISSUER = os.environ.get(
    "KEYCLOAK_ISSUER",
    "http://localhost:8080/realms/reports-realm",
)
KEYCLOAK_JWKS_URL = os.environ.get(
    "KEYCLOAK_JWKS_URL",
    "http://keycloak:8080/realms/reports-realm/protocol/openid-connect/certs",
)
CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "http://localhost:3000")
