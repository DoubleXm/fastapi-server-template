from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from loguru import logger

from app.core.config import settings
from app.core.logger.sqlalchemy import setup_sqlalchemy_logging
from app.core.logger.uvicorn import disable_uvicorn_logging

request_id_context: ContextVar[str] = ContextVar[str]("request_id", default="-")


def _normalize_level(level: str | int) -> str:
    if isinstance(level, int):
        return logging.getLevelName(level)
    return level


def _patch_loguru_record(record: dict[str, Any]) -> None:
    message_parts = []
    extra = record["extra"]
    display_name = extra.get("display_name")
    if display_name:
        message_parts.append(str(display_name))
    request_id = extra.get("request_id") or request_id_context.get()
    if request_id != "-":
        message_parts.append(f"[request_id={request_id}]")
    if message_parts:
        record["message"] = f"{' '.join(message_parts)} {record['message']}"


def setup_logging(
    *,
    log_dir: Path | None = None,
    level: str | int | None = None,
    max_bytes: int | None = None,
    backup_count: int | None = None,
    console_sink: Any | None = None,
) -> None:
    """统一配置 Loguru sinks、SQLAlchemy 日志和 Uvicorn 日志关闭策略。"""
    log_dir = log_dir or settings.logs_dir_path
    level = level or settings.LOG_LEVEL
    max_bytes = max_bytes or settings.LOG_MAX_BYTES
    backup_count = backup_count or settings.LOG_BACKUP_COUNT

    log_dir.mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.configure(patcher=_patch_loguru_record)

    normalized_level = _normalize_level(level)
    logger.add(
        console_sink or sys.stderr,
        level=normalized_level,
        colorize=True,
    )
    logger.add(
        log_dir / "app.log",
        level=normalized_level,
        rotation=max_bytes,
        retention=backup_count,
        encoding="utf-8",
        colorize=False,
    )
    logger.add(
        log_dir / "error.log",
        level="ERROR",
        rotation=max_bytes,
        retention=backup_count,
        encoding="utf-8",
        colorize=False,
    )
    setup_sqlalchemy_logging(level)
    disable_uvicorn_logging()


def get_logger(name: str | None = None):
    """返回 Loguru logger；传入 name 时附加稳定展示名。"""
    if name is None:
        return logger
    return logger.bind(display_name=name)
