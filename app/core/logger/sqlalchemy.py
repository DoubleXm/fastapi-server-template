import logging

from loguru import logger

from app.core.config import settings

_SQL_STATEMENT_LOGGER_NAMES = ("sqlalchemy", "sqlalchemy.engine")
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


def configure_sqlalchemy_logging(level: str) -> None:
    log_level = logging.getLevelName(level)
    enable_sql_logs = settings.SQL_ECHO and log_level <= logging.DEBUG

    for logger_name in _SQL_STATEMENT_LOGGER_NAMES:
        stdlib_logger = logging.getLogger(logger_name)
        stdlib_logger.handlers.clear()
        stdlib_logger.propagate = False
        stdlib_logger.setLevel(logging.DEBUG if enable_sql_logs else logging.WARNING)

    if not enable_sql_logs:
        return

    # 不需要为 sqlalchemy 添加, 去除 handler 并且不让冒泡, 从行为上禁止除 SQL 语句外的其他日志产生  # noqa: E501
    # 仅为 sqlalchemy.engine 添加 handler
    logging.getLogger(_SQL_STATEMENT_LOGGER_NAMES[1]).addHandler(SqlAlchemyHandler())
