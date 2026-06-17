import json
import time
from uuid import uuid4

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logger import get_logger, request_id_context

# request/response body 日志最多采样的字符数。
MAX_LOG_BODY_CHARS = 1000
# request header 白名单字段，避免默认输出过多无关 header。
LOGGED_HEADER_NAMES = {
    "authorization",
    "content-length",
    "content-type",
    "host",
    "user-agent",
    "x-forwarded-for",
    "x-real-ip",
    "x-request-id",
}
# 跳过 request body 采样的 content-type。
SKIPPED_REQUEST_BODY_CONTENT_TYPES = {"multipart/form-data"}
# 跳过 response body 采样的 content-type。
SKIPPED_RESPONSE_BODY_CONTENT_TYPES = {"application/octet-stream", "text/event-stream"}

logger = get_logger("app.request")


def format_body_text(body: bytes) -> str:
    """格式化可打印 body：JSON 压缩展示，其他文本只做长度截断。"""
    try:
        body_text = body.decode("utf-8")
    except UnicodeDecodeError:
        return f"<binary> size={len(body)}"

    try:
        parsed_body = json.loads(body_text)
    except json.JSONDecodeError:
        return truncate_body_text(body_text)

    compact_body = json.dumps(parsed_body, ensure_ascii=False, separators=(",", ":"))
    return truncate_body_text(compact_body)


def truncate_body_text(body_text: str) -> str:
    """限制 body 日志长度，避免大 payload 撑爆 console 或 log file。"""
    if len(body_text) <= MAX_LOG_BODY_CHARS:
        return body_text
    omitted_chars = len(body_text) - MAX_LOG_BODY_CHARS
    return f"{body_text[:MAX_LOG_BODY_CHARS]}...<truncated {omitted_chars} chars>"


def format_headers(scope: Scope) -> str:
    headers = {}
    for key, value in scope["headers"]:
        header_name = key.decode("latin-1").lower()
        if header_name in LOGGED_HEADER_NAMES:
            headers[header_name] = value.decode("latin-1")
    return json.dumps(
        headers,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def format_request_line(scope: Scope) -> str:
    """格式化类似 access log 的请求地址和 request line。"""
    client = scope.get("client")
    client_addr = f"{client[0]}:{client[1]}" if client else "-"
    target = scope["path"]
    query_string = scope.get("query_string", b"").decode("latin-1")
    if query_string:
        target = f"{target}?{query_string}"
    http_version = scope.get("http_version", "1.1")
    return f'{client_addr} - "{scope["method"]} {target} HTTP/{http_version}"'


def should_log_response_body(headers: MutableHeaders) -> bool:
    # 流式响应和附件不读取 body，避免阻塞 SSE 或把文件内容写入内存。
    content_disposition = headers.get("content-disposition", "")
    if "attachment" in content_disposition.lower():
        return False

    content_type = headers.get("content-type", "").split(";", maxsplit=1)[0].lower()
    if content_type in SKIPPED_RESPONSE_BODY_CONTENT_TYPES:
        return False

    return "content-length" in headers


def should_log_request_body(scope: Scope) -> bool:
    headers = MutableHeaders(scope=scope)
    content_type = headers.get("content-type", "").split(";", maxsplit=1)[0].lower()
    return content_type not in SKIPPED_REQUEST_BODY_CONTENT_TYPES


class BodySampler:
    """只采样前 N 字节，避免日志中间件缓存完整大 body。"""

    def __init__(
        self,
        max_chars: int = MAX_LOG_BODY_CHARS,
    ) -> None:
        self.max_bytes = max_chars
        self.body = bytearray()
        self.total_size = 0
        self.truncated = False

    def append(self, chunk: bytes) -> None:
        if not chunk:
            return

        self.total_size += len(chunk)
        remaining_bytes = self.max_bytes - len(self.body)
        if remaining_bytes > 0:
            self.body.extend(chunk[:remaining_bytes])
        if len(chunk) > remaining_bytes:
            self.truncated = True

    def text(self) -> str:
        body_text = format_body_text(bytes(self.body))
        if not self.truncated:
            return body_text
        omitted_chars = max(self.total_size - len(self.body), 0)
        return f"{body_text}...<truncated {omitted_chars} chars>"


class LoggingMiddleware:
    """记录 request/response body、耗时和 request_id 的 ASGI 中间件。"""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = self._get_request_id(scope)
        request_id_token = request_id_context.set(request_id)
        start_time = time.time()
        request_sampler = BodySampler()
        response_sampler = BodySampler()
        should_log_request_body_content = should_log_request_body(scope)
        should_log_body = True
        request_body_logged = False

        logger.debug("Request headers: {}", format_headers(scope))
        logger.info(format_request_line(scope))
        if not should_log_request_body_content:
            logger.debug("Request body: <multipart skipped>")
            request_body_logged = True

        async def logging_receive() -> Message:
            nonlocal request_body_logged

            # 包装 receive：业务读取 request body 时顺手采样，不提前消费请求流。
            message = await receive()
            if message["type"] != "http.request":
                return message

            body = message.get("body", b"")
            if should_log_request_body_content:
                request_sampler.append(body)

            if (
                should_log_request_body_content
                and not message.get("more_body", False)
                and request_sampler.total_size
            ):
                logger.debug("Request body: {}", request_sampler.text())
                request_body_logged = True

            return message

        async def logging_send(message: Message) -> None:
            nonlocal should_log_body

            # 包装 send：在 response start 阶段补 request_id，并判断是否记录 body。
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id
                should_log_body = should_log_response_body(headers)

            if message["type"] == "http.response.body":
                body = message.get("body", b"")
                more_body = message.get("more_body", False)
                if should_log_body:
                    response_sampler.append(body)
                if not more_body:
                    duration = (time.time() - start_time) * 1000
                    self._log_response_body(
                        response_sampler,
                        duration=duration,
                        should_log_body=should_log_body,
                    )

            await send(message)

        try:
            await self.app(scope, logging_receive, logging_send)
        finally:
            # 某些 endpoint 不读取 request body，finally 里兜底输出已采样内容。
            if request_sampler.total_size and not request_body_logged:
                logger.debug("Request body: {}", request_sampler.text())
            request_id_context.reset(request_id_token)

    def _get_request_id(self, scope: Scope) -> str:
        for key, value in scope["headers"]:
            if key.lower() == b"x-request-id":
                return value.decode("latin-1")
        return uuid4().hex

    def _log_response_body(
        self, sampler: BodySampler, *, duration: float, should_log_body: bool
    ) -> None:
        if not should_log_body:
            logger.debug(
                "Response body: <streaming skipped> | Duration: {:.2f}ms", duration
            )
            return

        if sampler.total_size:
            logger.debug(
                "Response body: {} | Duration: {:.2f}ms", sampler.text(), duration
            )
            return

        logger.debug("Response body: <empty> | Duration: {:.2f}ms", duration)
