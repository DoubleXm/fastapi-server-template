from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.middlewares.logging as logging_middleware
from app.middlewares.logging import LoggingMiddleware


def render_loguru_message(message: str, *args) -> str:
    return message.format(*args) if args else message


def test_logging_middleware_name_matches_file_name() -> None:
    assert hasattr(logging_middleware, "LoggingMiddleware")
    assert not hasattr(logging_middleware, "DetailLogMiddleware")


def test_detail_log_middleware_returns_request_id_header() -> None:
    app = FastAPI()
    app.add_middleware(LoggingMiddleware)

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)

    response = client.get("/ping", headers={"X-Request-ID": "req-123"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-123"


def test_detail_log_middleware_logs_bodies_at_debug_level(
    monkeypatch,
) -> None:
    records: list[tuple[int, str]] = []

    class CapturingLogger:
        def debug(self, message, *args) -> None:
            records.append((logging.DEBUG, render_loguru_message(message, *args)))

        def info(self, message, *args) -> None:
            records.append((logging.INFO, render_loguru_message(message, *args)))

    monkeypatch.setattr(logging_middleware, "logger", CapturingLogger())

    app = FastAPI()
    app.add_middleware(LoggingMiddleware)

    @app.post("/api/v1/users")
    async def echo(payload: dict) -> dict:
        return payload

    client = TestClient(app)

    response = client.post("/api/v1/users", json={"name": "alice"})

    assert response.status_code == 200
    assert records
    assert [level for level, _ in records] == [
        logging.DEBUG,
        logging.DEBUG,
        logging.INFO,
        logging.DEBUG,
    ]
    assert any("Request headers" in message for _, message in records)
    assert any("Request body" in message for _, message in records)
    assert any(
        'testclient:50000 - "POST /api/v1/users HTTP/1.1"' in message
        for _, message in records
    )
    assert any("Response body" in message for _, message in records)


def test_detail_log_middleware_logs_request_headers_with_redaction(
    monkeypatch,
) -> None:
    records: list[str] = []

    class CapturingLogger:
        def debug(self, message, *args) -> None:
            records.append(render_loguru_message(message, *args))

        def info(self, message, *args) -> None:
            records.append(render_loguru_message(message, *args))

    monkeypatch.setattr(logging_middleware, "logger", CapturingLogger())

    app = FastAPI()
    app.add_middleware(LoggingMiddleware)

    @app.get("/headers")
    async def headers() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)

    response = client.get(
        "/headers",
        headers={
            "Authorization": "Bearer secret-token",
            "X-Client-Version": "1.2.3",
        },
    )

    assert response.status_code == 200
    combined = "\n".join(records)
    assert "Request headers" in combined
    assert '"authorization":"Bearer ***"' in combined
    assert '"x-client-version":"1.2.3"' in combined
    assert "secret-token" not in combined


def test_detail_log_middleware_redacts_authorization_without_scheme(
    monkeypatch,
) -> None:
    records: list[str] = []

    class CapturingLogger:
        def debug(self, message, *args) -> None:
            records.append(render_loguru_message(message, *args))

        def info(self, message, *args) -> None:
            records.append(render_loguru_message(message, *args))

    monkeypatch.setattr(logging_middleware, "logger", CapturingLogger())

    app = FastAPI()
    app.add_middleware(LoggingMiddleware)

    @app.get("/headers")
    async def headers() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)

    response = client.get("/headers", headers={"Authorization": "raw-secret-token"})

    assert response.status_code == 200
    combined = "\n".join(records)
    assert '"authorization":"***"' in combined
    assert "raw-secret-token" not in combined


def test_detail_log_middleware_redacts_sensitive_query_params(monkeypatch) -> None:
    records: list[str] = []

    class CapturingLogger:
        def debug(self, message, *args) -> None:
            records.append(render_loguru_message(message, *args))

        def info(self, message, *args) -> None:
            records.append(render_loguru_message(message, *args))

    monkeypatch.setattr(logging_middleware, "logger", CapturingLogger())

    app = FastAPI()
    app.add_middleware(LoggingMiddleware)

    @app.get("/search")
    async def search() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)

    response = client.get("/search?q=alice&token=secret-token")

    assert response.status_code == 200
    combined = "\n".join(records)
    assert "GET /search?q=alice&token=*** HTTP/1.1" in combined
    assert "secret-token" not in combined


def test_detail_log_middleware_keeps_nested_authorization_scheme(monkeypatch) -> None:
    records: list[str] = []

    class CapturingLogger:
        def debug(self, message, *args) -> None:
            records.append(render_loguru_message(message, *args))

        def info(self, message, *args) -> None:
            records.append(render_loguru_message(message, *args))

    monkeypatch.setattr(logging_middleware, "logger", CapturingLogger())

    app = FastAPI()
    app.add_middleware(LoggingMiddleware)

    @app.get("/headers")
    async def headers() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)

    response = client.get(
        "/headers",
        headers={"Authorization": "Bearer Bearer secret-token"},
    )

    assert response.status_code == 200
    combined = "\n".join(records)
    assert '"authorization":"Bearer Bearer ***"' in combined
    assert "secret-token" not in combined


def test_detail_log_middleware_redacts_sensitive_body_fields(monkeypatch) -> None:
    records: list[str] = []

    class CapturingLogger:
        def debug(self, message, *args) -> None:
            records.append(render_loguru_message(message, *args))

        def info(self, message, *args) -> None:
            records.append(render_loguru_message(message, *args))

    monkeypatch.setattr(logging_middleware, "logger", CapturingLogger())

    app = FastAPI()
    app.add_middleware(LoggingMiddleware)

    @app.post("/login")
    async def login(payload: dict) -> dict:
        return {
            "access_token": "secret-token",
            "nested": {"password": payload["password"]},
        }

    client = TestClient(app)

    response = client.post(
        "/login",
        json={"username": "alice", "password": "secret123"},
    )

    assert response.status_code == 200
    combined = "\n".join(records)
    assert "secret123" not in combined
    assert "secret-token" not in combined
    assert '"password":"***"' in combined
    assert '"access_token":"***"' in combined


def test_detail_log_middleware_redacts_camel_case_access_token(monkeypatch) -> None:
    records: list[str] = []

    class CapturingLogger:
        def debug(self, message, *args) -> None:
            records.append(render_loguru_message(message, *args))

        def info(self, message, *args) -> None:
            records.append(render_loguru_message(message, *args))

    monkeypatch.setattr(logging_middleware, "logger", CapturingLogger())

    app = FastAPI()
    app.add_middleware(LoggingMiddleware)

    @app.get("/auth")
    async def auth() -> dict[str, str]:
        return {"token": "secret-token"}

    client = TestClient(app)

    response = client.get("/auth")

    assert response.status_code == 200
    combined = "\n".join(records)
    assert "secret-token" not in combined
    assert '"token":"***"' in combined


def test_detail_log_middleware_truncates_large_bodies(monkeypatch) -> None:
    records: list[str] = []

    class CapturingLogger:
        def debug(self, message, *args) -> None:
            records.append(render_loguru_message(message, *args))

        def info(self, message, *args) -> None:
            records.append(render_loguru_message(message, *args))

    monkeypatch.setattr(logging_middleware, "logger", CapturingLogger())

    app = FastAPI()
    app.add_middleware(LoggingMiddleware)

    @app.post("/echo")
    async def echo(payload: dict) -> dict:
        return payload

    client = TestClient(app)
    large_value = "x" * 5000

    response = client.post("/echo", json={"payload": large_value})

    assert response.status_code == 200
    assert any("<truncated" in message for message in records)
    assert all(len(message) < 1500 for message in records)
