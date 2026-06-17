import logging
import sys
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from loguru import logger

from app.core.config import settings
from app.core.logger.sqlalchemy import configure_sqlalchemy_logging
from app.core.logger.uvicorn import configure_uvicorn_logging

request_id_context: ContextVar[str] = ContextVar[str]("request_id", default="-")


class LoggerManager:
    """统一封装 Loguru、SQLAlchemy 和 Uvicorn 日志配置。"""

    def normalize_level(self, level: str | int) -> str:
        if isinstance(level, int):
            return logging.getLevelName(level)
        return level

    def patch_loguru_record(self, record: dict[str, Any]) -> None:
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

    def setup(
        self,
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
        # 规范日志输出的格式
        logger.configure(patcher=self.patch_loguru_record)

        normalized_level = self.normalize_level(level)
        file_logger_config = {
            "rotation": max_bytes,
            "retention": backup_count,
            "encoding": "utf-8",
            "colorize": False,
            "backtrace": False,
            "diagnose": False,
        }

        logger.add(
            console_sink or sys.stderr,
            level=normalized_level,
            colorize=True,
            backtrace=False,
            diagnose=False,
        )
        logger.add(log_dir / "app.log", level=normalized_level, **file_logger_config)
        logger.add(log_dir / "error.log", level="ERROR", **file_logger_config)

        configure_sqlalchemy_logging(normalized_level)
        configure_uvicorn_logging()

        # 获取所有的 logger 实例
        # print(logging.getLogger().manager.loggerDict.keys())

    def get_logger(self, name: str | None = None):
        """返回 Loguru logger；传入 name 时附加稳定展示名。"""
        if name is None:
            return logger
        return logger.bind(display_name=name)


logger_manager = LoggerManager()
setup_logging = logger_manager.setup
get_logger = logger_manager.get_logger
