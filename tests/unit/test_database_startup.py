from __future__ import annotations

from app.core.config import Settings
from app.core.database import should_create_db_and_tables


def make_settings(*, app_env: str, create_db_tables: bool = False) -> Settings:
    return Settings(
        APP_NAME="app",
        APP_ENV=app_env,
        API_V1_PREFIX="/api/v1",
        SECRET_KEY="x" * 32,
        JWT_ALGORITHM="HS256",
        ACCESS_TOKEN_EXPIRE_MINUTES=60,
        BACKEND_CORS_ORIGINS=[],
        LOG_LEVEL="INFO",
        LOG_MAX_BYTES=1024,
        LOG_BACKUP_COUNT=1,
        DB_HOST="127.0.0.1",
        DB_PORT=3306,
        DB_USER="user",
        DB_PASSWORD="password",
        DB_NAME="app",
        SQL_ECHO=False,
        STATIC_DIR="static",
        LOG_DIR="logs",
        CREATE_DB_TABLES=create_db_tables,
    )


def test_production_never_auto_creates_tables() -> None:
    settings = make_settings(app_env="production", create_db_tables=True)

    assert should_create_db_and_tables(settings) is False


def test_local_can_explicitly_auto_create_tables() -> None:
    settings = make_settings(app_env="local", create_db_tables=True)

    assert should_create_db_and_tables(settings) is True
