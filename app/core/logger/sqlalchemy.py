import logging

from loguru import logger

from app.core.config import settings

_SQL_LOGGER_NAMES = ("sqlalchemy", "sqlalchemy.engine")
_SQL_PREFIXES = (
    "ALTER ",
    "CREATE ",
    "DELETE ",
    "DESCRIBE ",
    "DROP ",
    "INSERT ",
    "SELECT ",
    "UPDATE ",
)


class SqlAlchemyHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        message = record.getMessage()
        # 防止事务和结果行等噪声进入日志，尤其避免打印 password_hash 等敏感字段。
        if not message.strip().upper().startswith(_SQL_PREFIXES):
            return

        logger.bind(display_name=record.name).opt(
            exception=record.exc_info,
        ).debug(message)


def _normalize_level(level: str | int) -> str:
    if isinstance(level, int):
        return logging.getLevelName(level)
    return level


def configure_sqlalchemy_logging(level: str | int) -> None:
    """配置 SQLAlchemy logger，只保留 SQL statement 并交给 Loguru 输出。"""
    log_level = logging.getLevelName(_normalize_level(level))
    enable_sql_logs = settings.SQL_ECHO and log_level <= logging.DEBUG

    for logger_name in _SQL_LOGGER_NAMES:
        stdlib_logger = logging.getLogger(logger_name)
        stdlib_logger.handlers.clear()
        stdlib_logger.propagate = False
        stdlib_logger.disabled = False
        stdlib_logger.setLevel(logging.DEBUG if enable_sql_logs else logging.WARNING)

    if not enable_sql_logs:
        return

    logging.getLogger("sqlalchemy.engine").addHandler(SqlAlchemyHandler())
