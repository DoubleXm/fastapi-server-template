from __future__ import annotations

import importlib
import logging
import re
from io import StringIO
from logging.handlers import RotatingFileHandler
from pathlib import Path

import yaml
from uvicorn.logging import AccessFormatter, DefaultFormatter

from app.core.database import configure_sql_logging, engine
from app.core.logging import (
    ACCESS_LOG_FORMAT,
    LOG_FORMAT,
    RequestContextFilter,
    SingleLineUvicornFormatter,
    SqlAlchemyResultFilter,
    UvicornAccessFormatter,
    UvicornAppFormatter,
    configure_app_logger,
    configure_rotating_file_handlers,
    configure_uvicorn_access_file_logging,
    request_id_context,
)
from app.middlewares.logging import configure_request_logging


def test_sql_engine_echo_is_disabled_to_avoid_duplicate_console_logs() -> None:
    assert engine.echo is False


def test_sql_logging_uses_app_formatter() -> None:
    access_logger = logging.getLogger("uvicorn.access")
    original_access_handlers = access_logger.handlers[:]
    uvicorn_logger = logging.getLogger("uvicorn.error")
    original_uvicorn_handlers = uvicorn_logger.handlers[:]
    sql_logger = logging.getLogger("sqlalchemy.engine")
    original_sql_handlers = sql_logger.handlers[:]
    original_sql_propagate = sql_logger.propagate
    original_sql_level = sql_logger.level

    try:
        access_handler = logging.StreamHandler(StringIO())
        access_handler.setFormatter(AccessFormatter())
        access_logger.handlers = [access_handler]

        uvicorn_handler = logging.StreamHandler(StringIO())
        uvicorn_handler.setFormatter(DefaultFormatter("%(levelprefix)s %(message)s"))
        uvicorn_logger.handlers = [uvicorn_handler]

        sql_logger.handlers = []

        configure_sql_logging()

        assert len(sql_logger.handlers) == 3
        assert isinstance(sql_logger.handlers[0].formatter, SingleLineUvicornFormatter)
    finally:
        access_logger.handlers = original_access_handlers
        uvicorn_logger.handlers = original_uvicorn_handlers
        sql_logger.handlers = original_sql_handlers
        sql_logger.propagate = original_sql_propagate
        sql_logger.setLevel(original_sql_level)


def test_sql_logging_collapses_multiline_sql() -> None:
    formatter = SingleLineUvicornFormatter(LOG_FORMAT, force_level=logging.DEBUG)
    record = logging.LogRecord(
        name="sqlalchemy.engine",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="SELECT users.id \nFROM users \nWHERE users.username = %(username_1)s",
        args=(),
        exc_info=None,
    )

    formatted = formatter.format(record)

    assert re.match(
        r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} DEBUG:\s+sqlalchemy\.engine ",
        formatted,
    )
    assert "sqlalchemy.engine" in formatted
    assert "request_id=-" not in formatted
    assert (
        "SELECT users.id FROM users WHERE users.username = %(username_1)s" in formatted
    )
    assert "\n" not in formatted


def test_sqlalchemy_result_filter_drops_column_and_row_logs() -> None:
    result_filter = SqlAlchemyResultFilter()
    dropped_messages = [
        "Col ('id', 'password_hash')",
        "Row (1, 'secret-hash')",
        "[raw sql] {}",
        "[generated in 0.00049s] {'username_1': 'curl_register_user'}",
        "BEGIN (implicit)",
        "COMMIT",
        "ROLLBACK",
    ]
    kept_messages = [
        "SELECT DATABASE()",
        "SELECT @@sql_mode",
        "SELECT @@lower_case_table_names",
        "DESCRIBE `fastapi_app`.`users`",
    ]
    statement_record = logging.LogRecord(
        name="sqlalchemy.engine.Engine",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="SELECT users.id FROM users",
        args=(),
        exc_info=None,
    )

    for message in dropped_messages:
        record = logging.LogRecord(
            name="sqlalchemy.engine.Engine",
            level=logging.DEBUG,
            pathname=__file__,
            lineno=1,
            msg=message,
            args=(),
            exc_info=None,
        )
        assert result_filter.filter(record) is False

    for message in kept_messages:
        record = logging.LogRecord(
            name="sqlalchemy.engine.Engine",
            level=logging.DEBUG,
            pathname=__file__,
            lineno=1,
            msg=message,
            args=(),
            exc_info=None,
        )
        assert result_filter.filter(record) is True

    assert result_filter.filter(statement_record) is True


def test_app_formatter_includes_time_name_and_request_id() -> None:
    formatter = UvicornAppFormatter(LOG_FORMAT, use_colors=False)
    token = request_id_context.set("req-123")
    record = logging.LogRecord(
        name="app.request",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Request body: {}",
        args=(),
        exc_info=None,
    )

    try:
        RequestContextFilter().filter(record)
        formatted = formatter.format(record)
    finally:
        request_id_context.reset(token)

    assert re.match(
        r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} INFO:\s+app\.request ",
        formatted,
    )
    assert "app.request" in formatted
    assert "[request_id=req-123]" in formatted
    assert "Request body: {}" in formatted


def test_app_formatter_preserves_colored_level_prefix() -> None:
    formatter = UvicornAppFormatter(LOG_FORMAT, use_colors=True)
    record = logging.LogRecord(
        name="app.request",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="服务启动",
        args=(),
        exc_info=None,
    )

    formatted = formatter.format(record)

    assert formatted.startswith("20")
    assert "\x1b[" in formatted
    assert "INFO" in formatted
    assert "app.request" in formatted


def test_app_formatter_omits_empty_request_id() -> None:
    formatter = UvicornAppFormatter(LOG_FORMAT)
    record = logging.LogRecord(
        name="app.request",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="服务启动",
        args=(),
        exc_info=None,
    )

    formatted = formatter.format(record)

    assert "request_id=" not in formatted
    assert "服务启动" in formatted


def test_app_formatter_displays_uvicorn_error_as_server_logger() -> None:
    formatter = UvicornAppFormatter(LOG_FORMAT, use_colors=False)
    record = logging.LogRecord(
        name="uvicorn.error",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Application startup complete.",
        args=(),
        exc_info=None,
    )

    formatted = formatter.format(record)

    assert "uvicorn.server" in formatted
    assert "uvicorn.error" not in formatted


def test_access_formatter_preserves_colored_status_code() -> None:
    formatter = UvicornAccessFormatter(ACCESS_LOG_FORMAT, use_colors=True)
    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='%s - "%s %s HTTP/%s" %d',
        args=("127.0.0.1:56197", "POST", "/api/v1/users/register", "1.1", 409),
        exc_info=None,
    )

    formatted = formatter.format(record)

    assert formatted.startswith("20")
    assert "uvicorn.access" in formatted
    assert "\x1b[" in formatted
    assert "409 Conflict" in formatted


def test_app_error_logger_formats_normal_message_arguments() -> None:
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(UvicornAppFormatter(LOG_FORMAT, use_colors=False))
    record = logging.LogRecord(
        name="app.error",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="Request validation failed method=%s path=%s errors=%s",
        args=("POST", "/api/v1/users/register", [{"msg": "too short"}]),
        exc_info=None,
    )

    handler.handle(record)

    output = stream.getvalue()
    assert "app.error" in output
    assert "Request validation failed method=POST path=/api/v1/users/register" in output


def test_exception_error_logger_does_not_reuse_access_formatter() -> None:
    import app.core.exception_handlers as exception_handlers

    access_logger = logging.getLogger("uvicorn.access")
    original_access_handlers = access_logger.handlers[:]
    original_error_handlers = exception_handlers.error_logger.handlers[:]

    try:
        access_handler = logging.StreamHandler(StringIO())
        access_handler.setFormatter(UvicornAccessFormatter(ACCESS_LOG_FORMAT))
        access_logger.handlers = [access_handler]
        exception_handlers.error_logger.handlers = []

        reloaded = importlib.reload(exception_handlers)

        assert reloaded.error_logger.handlers
        assert all(
            not isinstance(handler.formatter, UvicornAccessFormatter)
            for handler in reloaded.error_logger.handlers
        )
    finally:
        access_logger.handlers = original_access_handlers
        exception_handlers.error_logger.handlers = original_error_handlers
        importlib.reload(exception_handlers)


def test_rotating_file_handlers_are_added(tmp_path: Path) -> None:
    logger = logging.getLogger("app.request")
    original_handlers = logger.handlers[:]

    try:
        logger.handlers = []

        configure_rotating_file_handlers(logger, log_dir=tmp_path, level=logging.INFO)

        file_handlers = [
            handler
            for handler in logger.handlers
            if isinstance(handler, RotatingFileHandler)
        ]
        assert len(file_handlers) == 2
        assert {Path(handler.baseFilename).name for handler in file_handlers} == {
            "app.log",
            "error.log",
        }
        assert (tmp_path / "app.log").exists()
        assert (tmp_path / "error.log").exists()
        assert all(
            getattr(handler.formatter, "use_colors", True) is False
            for handler in file_handlers
        )
    finally:
        for handler in logger.handlers:
            handler.close()
        logger.handlers = original_handlers


def test_configure_app_logger_adds_console_and_file_handlers(tmp_path: Path) -> None:
    logger = logging.getLogger("app.test_configured")
    original_handlers = logger.handlers[:]
    original_propagate = logger.propagate
    original_level = logger.level

    try:
        logger.handlers = []

        configured_logger = configure_app_logger(
            "app.test_configured",
            log_dir=tmp_path,
            level=logging.INFO,
            max_bytes=1024 * 1024,
            backup_count=1,
        )

        assert configured_logger is logger
        assert configured_logger.propagate is False
        assert configured_logger.level == logging.INFO
        assert len(configured_logger.handlers) == 3
        assert isinstance(configured_logger.handlers[0].formatter, UvicornAppFormatter)
        assert {
            Path(handler.baseFilename).name
            for handler in configured_logger.handlers
            if isinstance(handler, RotatingFileHandler)
        } == {"app.log", "error.log"}
    finally:
        for handler in logger.handlers:
            handler.close()
        logger.handlers = original_handlers
        logger.propagate = original_propagate
        logger.setLevel(original_level)


def test_request_logging_uses_app_formatter() -> None:
    uvicorn_logger = logging.getLogger("uvicorn.error")
    original_uvicorn_handlers = uvicorn_logger.handlers[:]
    request_logger = logging.getLogger("app.request")
    original_request_handlers = request_logger.handlers[:]
    original_request_propagate = request_logger.propagate
    original_request_level = request_logger.level

    try:
        uvicorn_handler = logging.StreamHandler(StringIO())
        uvicorn_handler.setFormatter(DefaultFormatter("%(levelprefix)s %(message)s"))
        uvicorn_logger.handlers = [uvicorn_handler]
        request_logger.handlers = []

        configure_request_logging()

        assert len(request_logger.handlers) == 3
        assert isinstance(request_logger.handlers[0].formatter, UvicornAppFormatter)
    finally:
        uvicorn_logger.handlers = original_uvicorn_handlers
        request_logger.handlers = original_request_handlers
        request_logger.propagate = original_request_propagate
        request_logger.setLevel(original_request_level)


def test_uvicorn_access_file_logging_writes_access_records(tmp_path: Path) -> None:
    access_logger = logging.getLogger("uvicorn.access")
    original_handlers = access_logger.handlers[:]
    original_level = access_logger.level
    original_propagate = access_logger.propagate

    try:
        access_logger.handlers = []
        access_logger.setLevel(logging.INFO)

        configure_uvicorn_access_file_logging(
            log_dir=tmp_path,
            level=logging.INFO,
            max_bytes=1024 * 1024,
            backup_count=1,
        )
        access_logger.info(
            '%s - "%s %s HTTP/%s" %d',
            "127.0.0.1:65109",
            "GET",
            "/api/v1/users/me",
            "1.1",
            401,
        )

        log_content = (tmp_path / "app.log").read_text(encoding="utf-8")

        assert '127.0.0.1:65109 - "GET /api/v1/users/me HTTP/1.1" 401' in log_content
        assert "uvicorn.access" in log_content
        assert re.search(
            r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} INFO:\s+uvicorn\.access",
            log_content,
        )
    finally:
        for handler in access_logger.handlers:
            handler.close()
        access_logger.handlers = original_handlers
        access_logger.setLevel(original_level)
        access_logger.propagate = original_propagate


def test_uvicorn_yaml_log_config_matches_app_format() -> None:
    config_path = Path("uvicorn-log-config.yaml")
    log_config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    assert log_config["formatters"]["default"]["()"] == (
        "app.core.logging.UvicornAppFormatter"
    )
    assert log_config["formatters"]["default"]["fmt"] == LOG_FORMAT
    assert log_config["formatters"]["default"]["datefmt"] == "%Y-%m-%d %H:%M:%S"
    assert log_config["formatters"]["access"]["()"] == (
        "app.core.logging.UvicornAccessFormatter"
    )
    assert log_config["formatters"]["access"]["fmt"] == ACCESS_LOG_FORMAT
    assert log_config["formatters"]["access"]["datefmt"] == "%Y-%m-%d %H:%M:%S"
    assert not Path("uvicorn-log-config.json").exists()
