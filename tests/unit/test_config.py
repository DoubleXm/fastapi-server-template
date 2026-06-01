from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import BASE_DIR, Settings


def test_settings_require_env_backed_values() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)

    missing_fields = {error["loc"][0] for error in exc_info.value.errors()}

    assert "APP_NAME" in missing_fields
    assert "SECRET_KEY" in missing_fields
    assert "DB_PASSWORD" in missing_fields
    assert "LOG_LEVEL" in missing_fields


def test_settings_keep_database_url_optional() -> None:
    settings = Settings(
        APP_NAME="app",
        APP_ENV="test",
        DEBUG=False,
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
        CREATE_DB_TABLES=False,
        STATIC_DIR="static",
        LOG_DIR="logs",
    )

    assert settings.DATABASE_URL is None


def test_settings_resolve_static_and_log_dirs_from_env_values() -> None:
    settings = Settings(
        APP_NAME="app",
        APP_ENV="test",
        DEBUG=False,
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
        CREATE_DB_TABLES=False,
        STATIC_DIR="assets/static",
        LOG_DIR="runtime/logs",
    )

    assert settings.static_dir_path == BASE_DIR / "assets/static"
    assert settings.logs_dir_path == BASE_DIR / "runtime/logs"


def test_settings_keep_absolute_static_and_log_dirs() -> None:
    static_dir = Path("/tmp/custom-static")
    log_dir = Path("/tmp/custom-logs")

    settings = Settings(
        APP_NAME="app",
        APP_ENV="test",
        DEBUG=False,
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
        CREATE_DB_TABLES=False,
        STATIC_DIR=str(static_dir),
        LOG_DIR=str(log_dir),
    )

    assert settings.static_dir_path == static_dir
    assert settings.logs_dir_path == log_dir
