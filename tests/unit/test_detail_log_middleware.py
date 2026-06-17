from __future__ import annotations

import logging
from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.responses import StreamingResponse

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
        logging.INFO,
        logging.DEBUG,
        logging.DEBUG,
    ]
    assert any("Request headers" in message for _, message in records)
    assert any("Request body" in message for _, message in records)
    assert any(
        'testclient:50000 - "POST /api/v1/users HTTP/1.1"' in message
        for _, message in records
    )
    assert any("Response body" in message for _, message in records)


def test_detail_log_middleware_logs_only_allowlisted_request_headers(
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
    assert '"host":"testserver"' in combined
    assert '"user-agent":"testclient"' in combined
    assert '"authorization":"Bearer secret-token"' in combined
    assert "x-client-version" not in combined


def test_detail_log_middleware_logs_query_params_without_redaction(monkeypatch) -> None:
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
    assert "GET /search?q=alice&token=secret-token HTTP/1.1" in combined


def test_detail_log_middleware_logs_sensitive_body_fields_without_redaction(
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
    assert "secret123" in combined
    assert "secret-token" in combined
    assert '"password":"secret123"' in combined
    assert '"access_token":"secret-token"' in combined


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


def test_detail_log_middleware_skips_multipart_request_body(monkeypatch) -> None:
    records: list[str] = []

    class CapturingLogger:
        def debug(self, message, *args) -> None:
            records.append(render_loguru_message(message, *args))

        def info(self, message, *args) -> None:
            records.append(render_loguru_message(message, *args))

    monkeypatch.setattr(logging_middleware, "logger", CapturingLogger())

    app = FastAPI()
    app.add_middleware(LoggingMiddleware)

    @app.post("/upload")
    async def upload() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)

    response = client.post(
        "/upload",
        files={"file": ("demo.txt", b"file-secret-content", "text/plain")},
    )

    assert response.status_code == 200
    combined = "\n".join(records)
    assert "Request body: <multipart skipped>" in combined
    assert "file-secret-content" not in combined


def test_detail_log_middleware_does_not_buffer_streaming_response(
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

    def stream() -> Iterator[bytes]:
        yield b"first\n"
        yield b"second\n"

    @app.get("/stream")
    async def streaming() -> StreamingResponse:
        return StreamingResponse(stream(), media_type="text/event-stream")

    client = TestClient(app)

    with client.stream("GET", "/stream") as response:
        assert response.status_code == 200
        assert response.headers["X-Request-ID"]
        assert list(response.iter_text()) == ["first\nsecond\n"]

    combined = "\n".join(records)
    assert "Response body: <streaming skipped>" in combined
    assert "first" not in combined
    assert "second" not in combined
