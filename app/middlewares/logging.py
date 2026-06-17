import json
import time
from typing import Any
from urllib.parse import parse_qsl, quote_plus
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.logger import get_logger, request_id_context

MAX_LOG_BODY_CHARS = 1000
SENSITIVE_BODY_KEYS = {
    "access_token",
    "accesstoken",
    "authorization",
    "cookie",
    "password",
    "refresh_token",
    "refreshtoken",
    "set-cookie",
    "secret",
    "token",
    "x-api-key",
}
logger = get_logger("app.request")


def sanitize_body_text(body_text: str) -> str:
    """清洗可打印 body：JSON 做脱敏和压缩，非 JSON 只做长度截断。"""
    try:
        parsed_body = json.loads(body_text)
    except json.JSONDecodeError:
        return truncate_body_text(body_text)

    # 只对 JSON 做 field-level redaction；plain text 不猜测内容，避免误伤可读性。
    sanitized_body = redact_sensitive_values(parsed_body)
    compact_body = json.dumps(sanitized_body, ensure_ascii=False, separators=(",", ":"))
    return truncate_body_text(compact_body)


def sanitize_headers(headers: dict[str, str]) -> str:
    """清洗 request headers，保留排查所需信息但隐藏认证和 cookie。"""
    sanitized_headers = {
        key.lower(): redact_header_value(key, value) for key, value in headers.items()
    }
    return json.dumps(
        sanitized_headers,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def sanitize_query_string(query_string: str) -> str:
    """清洗 query string 中的敏感参数，避免 token/password 进入 access log。"""
    sanitized_params = []
    for key, value in parse_qsl(query_string, keep_blank_values=True):
        encoded_key = quote_plus(key)
        encoded_value = (
            "***"
            if normalize_sensitive_key(key) in SENSITIVE_BODY_KEYS
            else quote_plus(value)
        )
        sanitized_params.append(f"{encoded_key}={encoded_value}")
    return "&".join(sanitized_params)


def redact_header_value(key: str, value: str) -> str:
    """Authorization 保留 scheme，其他敏感 header 直接隐藏。"""
    lowered_key = key.lower()
    if lowered_key == "authorization":
        parts = value.split()
        if len(parts) <= 1:
            return "***"
        return f"{' '.join(parts[:-1])} ***"
    if lowered_key in SENSITIVE_BODY_KEYS:
        return "***"
    return value


def redact_sensitive_values(value: Any) -> Any:
    """递归脱敏 dict/list 中的敏感字段，避免 password/token 进入日志。"""
    if isinstance(value, dict):
        return {
            key: (
                "***"
                if normalize_sensitive_key(key) in SENSITIVE_BODY_KEYS
                else redact_sensitive_values(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive_values(item) for item in value]
    return value


def normalize_sensitive_key(key: str) -> str:
    return key.lower().replace("_", "").replace("-", "")


def truncate_body_text(body_text: str) -> str:
    """限制 body 日志长度，避免大 payload 撑爆 console 或 log file。"""
    if len(body_text) <= MAX_LOG_BODY_CHARS:
        return body_text
    omitted_chars = len(body_text) - MAX_LOG_BODY_CHARS
    return f"{body_text[:MAX_LOG_BODY_CHARS]}...<truncated {omitted_chars} chars>"


def format_request_line(request: Request) -> str:
    """格式化类似 access log 的请求地址和 request line。"""
    client = request.client
    client_addr = f"{client.host}:{client.port}" if client else "-"
    target = request.url.path
    if request.url.query:
        target = f"{target}?{sanitize_query_string(request.url.query)}"
    http_version = request.scope.get("http_version", "1.1")
    return f'{client_addr} - "{request.method} {target} HTTP/{http_version}"'


class LoggingMiddleware(BaseHTTPMiddleware):
    """记录 request/response body、耗时和 request_id 的调试中间件。"""

    async def dispatch(self, request: Request, call_next):
        """缓存 request body 并重建 response，保证日志记录不影响业务处理。"""
        request_id = request.headers.get("X-Request-ID") or uuid4().hex
        request_id_token = request_id_context.set(request_id)
        try:
            body = await self._read_and_cache_request_body(request)
            self._log_request(request, body)

            start_time = time.time()
            response = await call_next(request)
            duration = (time.time() - start_time) * 1000

            return await self._rebuild_and_log_response(
                response,
                request_id=request_id,
                duration=duration,
            )
        finally:
            request_id_context.reset(request_id_token)

    async def _read_and_cache_request_body(self, request: Request) -> bytes:
        """读取 request body 后回填 receive，避免 route 读取 body 时为空。"""
        body = await request.body()

        async def receive():
            return {"type": "http.request", "body": body}

        request._receive = receive
        return body

    def _log_request(self, request: Request, body: bytes) -> None:
        logger.debug(
            "Request headers: {}",
            sanitize_headers(dict(request.headers)),
        )

        if body:
            self._log_body("Request body", body)

        logger.info(format_request_line(request))

    async def _rebuild_and_log_response(
        self,
        response: Response,
        *,
        request_id: str,
        duration: float,
    ) -> Response:
        # BaseHTTPMiddleware 会消费 response iterator，因此记录后需要重建 response。
        response_body = b"".join([chunk async for chunk in response.body_iterator])
        new_response = Response(
            content=response_body,
            status_code=response.status_code,
            headers=dict[str, str](response.headers),
            media_type=response.media_type,
        )
        new_response.headers["X-Request-ID"] = request_id
        self._log_response(response_body, duration)
        return new_response

    def _log_response(self, body: bytes, duration: float) -> None:
        if body:
            self._log_body("Response body", body, duration=duration)
            return

        logger.debug(
            "Response body: <empty> | Duration: {:.2f}ms",
            duration,
        )

    def _log_body(
        self,
        label: str,
        body: bytes,
        *,
        duration: float | None = None,
    ) -> None:
        try:
            body_text = sanitize_body_text(body.decode("utf-8"))
        except UnicodeDecodeError:
            body_text = f"<binary> size={len(body)}"

        if duration is None:
            logger.debug("{}: {}", label, body_text)
            return

        logger.debug("{}: {} | Duration: {:.2f}ms", label, body_text, duration)
