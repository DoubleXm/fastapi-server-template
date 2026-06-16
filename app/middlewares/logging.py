import json
import time
from typing import Any
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.logger import (
    get_logger,
    request_id_context,
)

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
        target = f"{target}?{request.url.query}"
    http_version = request.scope.get("http_version", "1.1")
    return f'{client_addr} - "{request.method} {target} HTTP/{http_version}"'


logger = get_logger()


class LoggingMiddleware(BaseHTTPMiddleware):
    """记录 request/response body、耗时和 request_id 的调试中间件。"""

    async def dispatch(self, request: Request, call_next):
        """缓存 request body 并重建 response，保证日志记录不影响业务处理。"""
        request_id = request.headers.get("X-Request-ID") or uuid4().hex
        request_id_token = request_id_context.set(request_id)
        # 读取 request body 并缓存，避免日志读取后业务 route 拿不到 body。
        body = await request.body()

        async def receive():
            return {"type": "http.request", "body": body}

        request._receive = receive
        logger.debug(
            "Request headers: {}",
            sanitize_headers(dict(request.headers)),
        )

        if body:
            try:
                body_str = sanitize_body_text(body.decode("utf-8"))
                logger.debug("Request body: {}", body_str)
            except UnicodeDecodeError:
                logger.debug("Request body: <binary> size={}", len(body))

        logger.info(format_request_line(request))

        try:
            start_time = time.time()
            response = await call_next(request)
            duration = (time.time() - start_time) * 1000

            # BaseHTTPMiddleware 会消费 response iterator，因此记录后需要重建 response。
            response_body = b""
            async for chunk in response.body_iterator:
                response_body += chunk
            new_response = Response(
                content=response_body,
                status_code=response.status_code,
                headers=dict[str, str](response.headers),
                media_type=response.media_type,
            )
            new_response.headers["X-Request-ID"] = request_id
            if response_body:
                try:
                    body_str = sanitize_body_text(response_body.decode("utf-8"))
                    logger.debug(
                        "Response body: {} | Duration: {:.2f}ms",
                        body_str,
                        duration,
                    )
                except UnicodeDecodeError:
                    logger.debug(
                        "Response body: <binary> size={} | Duration: {:.2f}ms",
                        len(response_body),
                        duration,
                    )
            else:
                logger.debug(
                    "Response body: <empty> | Duration: {:.2f}ms",
                    duration,
                )

            return new_response
        finally:
            request_id_context.reset(request_id_token)
