from __future__ import annotations

import logging
import re
from contextvars import ContextVar
from copy import copy
from logging.handlers import RotatingFileHandler
from pathlib import Path

from uvicorn.logging import AccessFormatter, DefaultFormatter

LOG_FORMAT = (
    "%(asctime)s %(levelprefix)s %(display_name)s%(request_id_part)s %(message)s"
)
ACCESS_LOG_FORMAT = (
    "%(asctime)s %(levelprefix)s %(display_name)s"
    '%(request_id_part)s %(client_addr)s - "%(request_line)s" %(status_code)s'
)
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
request_id_context: ContextVar[str] = ContextVar[str]("request_id", default="-")


def prepare_log_record(record: logging.LogRecord) -> None:
    """为所有自定义 formatter 补齐统一的展示字段和 request_id 字段。"""
    # Uvicorn 将 server lifecycle logs 放在 uvicorn.error；
    # 这里只调整 display name，不改 logger routing。
    if not hasattr(record, "display_name"):
        record.display_name = (
            "uvicorn.server" if record.name == "uvicorn.error" else record.name
        )
    if not hasattr(record, "request_id"):
        request_id = request_id_context.get()
        record.request_id = request_id
    if not hasattr(record, "request_id_part"):
        record.request_id_part = (
            f" [request_id={record.request_id}]" if record.request_id != "-" else ""
        )


class RequestContextFilter(logging.Filter):
    """把 ContextVar 中的 request_id 注入到每条 LogRecord。"""

    def filter(self, record: logging.LogRecord) -> bool:
        prepare_log_record(record)
        return True


class SqlAlchemyResultFilter(logging.Filter):
    """只保留 SQL statement，过滤 SQLAlchemy 的事务、列名和行数据噪音。"""

    allowed_sql_prefixes = (
        "ALTER ",
        "CREATE ",
        "DELETE ",
        "DESCRIBE ",
        "DROP ",
        "INSERT ",
        "SELECT ",
        "UPDATE ",
    )

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage().strip()
        upper_message = message.upper()

        return upper_message.startswith(self.allowed_sql_prefixes)


class UvicornAppFormatter(DefaultFormatter):
    """保留 Uvicorn level 颜色，同时追加 app 统一上下文字段。"""

    def __init__(
        self,
        fmt: str | None = None,
        datefmt: str | None = None,
        *,
        use_colors: bool | None = None,
    ):
        super().__init__(
            fmt=fmt,
            datefmt=datefmt or LOG_DATE_FORMAT,
            use_colors=use_colors,
        )

    def format(self, record: logging.LogRecord) -> str:
        prepare_log_record(record)
        return super().format(record)


class UvicornAccessFormatter(AccessFormatter):
    """保留 Uvicorn access log 的 status code 颜色和 request line 格式。"""

    def __init__(
        self,
        fmt: str | None = None,
        datefmt: str | None = None,
        *,
        use_colors: bool | None = None,
    ):
        super().__init__(
            fmt=fmt,
            datefmt=datefmt or LOG_DATE_FORMAT,
            use_colors=use_colors,
        )

    def format(self, record: logging.LogRecord) -> str:
        # access log 必须继续走 AccessFormatter，
        # 才能保留 request line 和 status code 颜色。
        prepare_log_record(record)
        return super().format(record)


class SingleLineUvicornFormatter(UvicornAppFormatter):
    """把多行日志压成 single-line，主要用于 SQLAlchemy statement。"""

    def __init__(
        self,
        fmt: str | None = None,
        datefmt: str | None = None,
        *,
        force_level: int | None = None,
        use_colors: bool | None = None,
    ):
        super().__init__(fmt=fmt, datefmt=datefmt, use_colors=use_colors)
        self.force_level = force_level

    def format(self, record: logging.LogRecord) -> str:
        record_copy = copy(record)
        if self.force_level is not None:
            record_copy.levelno = self.force_level
            record_copy.levelname = logging.getLevelName(self.force_level)
        message = record_copy.getMessage()
        # SQLAlchemy 会输出多行 SQL；压成 single-line 后更适合和 request log 一起检索。
        record_copy.msg = re.sub(r"\s+", " ", message).strip()
        record_copy.args = ()
        return super().format(record_copy)


def uvicorn_default_handler() -> logging.Handler:
    """复用 Uvicorn console handler 的 stream/color 设置，并替换为 app formatter。"""
    uvicorn_logger = logging.getLogger("uvicorn.error")
    for handler in uvicorn_logger.handlers:
        if isinstance(handler.formatter, DefaultFormatter):
            app_handler = copy(handler)
            app_handler.setFormatter(UvicornAppFormatter(LOG_FORMAT, LOG_DATE_FORMAT))
            app_handler.addFilter(RequestContextFilter())
            return app_handler

    handler = logging.StreamHandler()
    handler.setFormatter(UvicornAppFormatter(LOG_FORMAT, LOG_DATE_FORMAT))
    handler.addFilter(RequestContextFilter())
    return handler


def uvicorn_single_line_handler() -> logging.Handler:
    """创建单行 console handler，用于 SQL 这类天然容易换行的日志。"""
    handler = uvicorn_default_handler()
    handler.setFormatter(
        SingleLineUvicornFormatter(
            LOG_FORMAT,
            LOG_DATE_FORMAT,
            force_level=logging.DEBUG,
        )
    )
    handler.addFilter(SqlAlchemyResultFilter())
    return handler


def configure_rotating_file_handlers(
    logger: logging.Logger,
    *,
    log_dir: Path,
    level: int,
    formatter: logging.Formatter | None = None,
    filters: list[logging.Filter] | None = None,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
) -> None:
    """为业务 logger 追加 app.log 和 error.log 两个 rotating file handler。"""
    log_dir.mkdir(parents=True, exist_ok=True)
    formatter = formatter or UvicornAppFormatter(
        LOG_FORMAT,
        LOG_DATE_FORMAT,
        use_colors=False,
    )

    app_handler = RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    app_handler.setLevel(level)
    app_handler.setFormatter(formatter)
    app_handler.addFilter(RequestContextFilter())
    for log_filter in filters or []:
        app_handler.addFilter(log_filter)

    error_handler = RotatingFileHandler(
        log_dir / "error.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    error_handler.addFilter(RequestContextFilter())
    for log_filter in filters or []:
        error_handler.addFilter(log_filter)

    logger.addHandler(app_handler)
    logger.addHandler(error_handler)


def configure_app_logger(
    name: str,
    *,
    log_dir: Path,
    level: int,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
) -> logging.Logger:
    """统一配置 app.* logger，避免 request/error 等模块重复拼 handler。"""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False
    if logger.handlers:
        return logger

    console_handler = uvicorn_default_handler()
    console_handler.setLevel(level)
    logger.addHandler(console_handler)
    configure_rotating_file_handlers(
        logger,
        log_dir=log_dir,
        level=level,
        max_bytes=max_bytes,
        backup_count=backup_count,
    )
    return logger


def configure_uvicorn_access_file_logging(
    *,
    log_dir: Path,
    level: int,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
) -> None:
    """把 Uvicorn native access log 额外写入 app.log，保留 console 输出不变。"""
    access_logger = logging.getLogger("uvicorn.access")
    app_log_path = (log_dir / "app.log").resolve()

    for handler in access_logger.handlers:
        if (
            isinstance(handler, RotatingFileHandler)
            and Path(handler.baseFilename).resolve() == app_log_path
            and getattr(handler, "_app_access_log_handler", False)
        ):
            handler.setLevel(level)
            return

    log_dir.mkdir(parents=True, exist_ok=True)
    app_handler = RotatingFileHandler(
        app_log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    app_handler.setLevel(level)
    app_handler.setFormatter(
        UvicornAccessFormatter(
            ACCESS_LOG_FORMAT,
            LOG_DATE_FORMAT,
            use_colors=False,
        )
    )
    app_handler.addFilter(RequestContextFilter())
    app_handler._app_access_log_handler = True
    access_logger.addHandler(app_handler)
