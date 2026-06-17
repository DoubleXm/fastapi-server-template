from __future__ import annotations

import logging
import re
from io import StringIO
from pathlib import Path

from loguru import logger

import app.core.logger as logger_core
import app.middlewares.logging as logging_middleware
from app.core.database import engine
from app.core.logger import (
    get_logger,
    logger_manager,
    request_id_context,
    setup_logging,
)
from app.core.logger.sqlalchemy import SqlAlchemyHandler
from app.core.logger.uvicorn import InterceptHandler


def test_sql_engine_echo_is_disabled_to_avoid_duplicate_console_logs() -> None:
    assert engine.echo is False


def test_logger_package_exposes_singleton_manager() -> None:
    assert setup_logging == logger_manager.setup
    assert get_logger == logger_manager.get_logger
    assert logger_manager.normalize_level(logging.DEBUG) == "DEBUG"


def test_get_logger_uses_explicit_name_when_provided(tmp_path: Path) -> None:
    setup_logging(
        log_dir=tmp_path,
        level="INFO",
        max_bytes=1024 * 1024,
        backup_count=1,
    )
    app_logger = get_logger("app.test_configured")

    app_logger.info("service started")

    log_content = (tmp_path / "app.log").read_text(encoding="utf-8")
    assert re.search(r"\d{4}-\d{2}-\d{2} .* \| INFO\s+\|", log_content)
    assert "app.test_configured" in log_content
    assert "service started" in log_content


def test_get_logger_uses_calling_module_name_by_default(tmp_path: Path) -> None:
    setup_logging(
        log_dir=tmp_path,
        level="INFO",
        max_bytes=1024 * 1024,
        backup_count=1,
    )
    app_logger = get_logger()

    app_logger.info("module scoped log")

    log_content = (tmp_path / "app.log").read_text(encoding="utf-8")
    assert re.search(rf"\| INFO\s+\| {__name__}:", log_content)
    assert "module scoped log" in log_content


def test_loguru_formatter_includes_request_id(tmp_path: Path) -> None:
    setup_logging(
        log_dir=tmp_path,
        level="INFO",
        max_bytes=1024 * 1024,
        backup_count=1,
    )
    app_logger = get_logger("app.request")
    token = request_id_context.set("req-123")

    try:
        app_logger.info("Request body: {}", "{}")
    finally:
        request_id_context.reset(token)

    log_content = (tmp_path / "app.log").read_text(encoding="utf-8")
    assert "[request_id=req-123]" in log_content
    assert "app.request" in log_content
    assert "Request body: {}" in log_content


def test_console_logging_uses_color_markup(tmp_path: Path) -> None:
    stream = StringIO()
    setup_logging(
        log_dir=tmp_path,
        level="INFO",
        max_bytes=1024 * 1024,
        backup_count=1,
        console_sink=stream,
    )
    app_logger = get_logger("app.request")

    app_logger.info("colored console log")

    console_output = stream.getvalue()
    assert "\x1b[" in console_output
    assert "INFO" in console_output
    assert "app.request" in console_output
    assert "colored console log" in console_output


def test_uvicorn_error_logs_are_forwarded_and_access_logs_are_disabled(
    tmp_path: Path,
) -> None:
    setup_logging(
        log_dir=tmp_path,
        level="INFO",
        max_bytes=1024 * 1024,
        backup_count=1,
    )

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.asgi"):
        uvicorn_logger = logging.getLogger(logger_name)
        assert uvicorn_logger.disabled is False
        assert len(uvicorn_logger.handlers) == 1
        assert isinstance(uvicorn_logger.handlers[0], InterceptHandler)
        assert uvicorn_logger.propagate is False

    access_logger = logging.getLogger("uvicorn.access")
    assert access_logger.disabled is True
    assert access_logger.handlers == []
    assert access_logger.propagate is False

    logging.getLogger("uvicorn.error").critical("Application startup complete.")
    logging.getLogger("uvicorn.access").critical(
        '%s - "%s %s HTTP/%s" %d',
        "127.0.0.1:65109",
        "GET",
        "/api/v1/users/me",
        "1.1",
        401,
    )
    log_content = (tmp_path / "app.log").read_text(encoding="utf-8")
    assert "uvicorn.error" in log_content
    assert "Application startup complete." in log_content
    assert "uvicorn.access" not in log_content


def test_error_traceback_uses_compact_loguru_output(tmp_path: Path) -> None:
    setup_logging(
        log_dir=tmp_path,
        level="INFO",
        max_bytes=1024 * 1024,
        backup_count=1,
    )
    app_logger = get_logger("app.error")

    try:
        raise ValueError("boom")
    except ValueError:
        app_logger.exception("Unhandled exception")

    error_content = (tmp_path / "error.log").read_text(encoding="utf-8")
    assert "Traceback (most recent call last):" in error_content
    assert "ValueError: boom" in error_content
    assert "└" not in error_content
    assert "│" not in error_content


def test_sql_logging_keeps_multiline_statement_and_filters_result_noise(
    tmp_path: Path,
) -> None:
    setup_logging(
        log_dir=tmp_path,
        level="DEBUG",
        max_bytes=1024 * 1024,
        backup_count=1,
    )
    sql_logger = logging.getLogger("sqlalchemy.engine")
    assert len(sql_logger.handlers) == 1
    assert isinstance(sql_logger.handlers[0], SqlAlchemyHandler)

    sql_logger.debug("SELECT users.id \nFROM users \nWHERE users.username = %(name)s")
    sql_logger.debug("Row (1, 'secret-hash')")

    log_content = (tmp_path / "app.log").read_text(encoding="utf-8")
    assert "SELECT users.id \nFROM users \nWHERE users.username = %(name)s" in (
        log_content
    )
    assert "secret-hash" not in log_content
    assert "sqlalchemy.engine" in log_content


def test_error_logs_are_written_to_error_log(tmp_path: Path) -> None:
    setup_logging(
        log_dir=tmp_path,
        level="INFO",
        max_bytes=1024 * 1024,
        backup_count=1,
    )
    error_logger = get_logger("app.error")

    error_logger.error("Unhandled exception path={}", "/api/v1/users/me")

    error_content = (tmp_path / "error.log").read_text(encoding="utf-8")
    assert "app.error" in error_content
    assert "Unhandled exception path=/api/v1/users/me" in error_content


def test_logger_is_defined_without_extra_configure_function(
    tmp_path: Path,
) -> None:
    setup_logging(
        log_dir=tmp_path,
        level="DEBUG",
        max_bytes=1024 * 1024,
        backup_count=1,
    )

    assert not hasattr(logging_middleware, "configure_request_logging")
    logging_middleware.logger.debug("Request body: {}", '{"name":"alice"}')

    log_content = (tmp_path / "app.log").read_text(encoding="utf-8")
    assert "app.request" in log_content
    assert 'Request body: {"name":"alice"}' in log_content


def test_sqlalchemy_bridge_is_not_a_module_level_handler_class() -> None:
    assert not hasattr(logger_core, "_SqlAlchemyLogHandler")


def test_logger_logic_lives_in_core_logger_package() -> None:
    assert Path("app/core/logger/__init__.py").exists()
    assert Path("app/core/logger/sqlalchemy.py").exists()
    assert Path("app/core/logger/uvicorn.py").exists()
    assert not Path("app/core/logging.py").exists()


def test_uvicorn_yaml_log_config_is_not_required() -> None:
    assert not Path("uvicorn-log-config.yaml").exists()


def teardown_module() -> None:
    logger.remove()
