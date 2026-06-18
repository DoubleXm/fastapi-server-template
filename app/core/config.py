from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BeforeValidator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


def parse_cors(value: Any) -> list[str] | str:
    if isinstance(value, str) and value and not value.startswith("["):
        return [origin.strip() for origin in value.split(",") if origin.strip()]
    if isinstance(value, list | str):
        return value
    raise ValueError(value)


def resolve_base_dir_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return BASE_DIR / path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str
    APP_ENV: Literal["local", "test", "production"]
    API_V1_PREFIX: str

    SECRET_KEY: str = Field(..., min_length=16)
    JWT_ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(..., ge=1)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, ge=1)

    BACKEND_CORS_ORIGINS: Annotated[list[str] | str, BeforeValidator(parse_cors)]
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    LOG_MAX_BYTES: int = Field(..., ge=1024)
    LOG_BACKUP_COUNT: int = Field(..., ge=1)

    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str
    DATABASE_URL: str | None = None
    SQL_ECHO: bool
    CREATE_DB_TABLES: bool

    STATIC_DIR: str
    LOG_DIR: str

    @property
    def all_cors_origins(self) -> list[str]:
        if isinstance(self.BACKEND_CORS_ORIGINS, str):
            return [self.BACKEND_CORS_ORIGINS] if self.BACKEND_CORS_ORIGINS else []
        return self.BACKEND_CORS_ORIGINS

    @property
    def sqlalchemy_database_uri(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )

    @property
    def static_dir_path(self) -> Path:
        return resolve_base_dir_path(self.STATIC_DIR)

    @property
    def logs_dir_path(self) -> Path:
        return resolve_base_dir_path(self.LOG_DIR)


@lru_cache
def get_settings() -> Settings:
    env_file = os.getenv("ENV_FILE")
    if env_file:
        return Settings(_env_file=env_file)

    app_env = os.getenv("APP_ENV", "local")
    env_map = {
        "local": ".env",
        "test": ".env.test",
        "production": ".env.prod",
    }
    return Settings(_env_file=env_map.get(app_env, ".env"))


settings = get_settings()
