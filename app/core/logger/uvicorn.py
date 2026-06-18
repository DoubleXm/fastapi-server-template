import logging
import os

from loguru import logger

_UVICORN_LOGGER_NAMES = ("uvicorn.error", "uvicorn", "uvicorn.asgi")
_UVICORN_ACCESS_LOGGER_NAME = "uvicorn.access"


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # 定位堆栈信息到真实的触发位置
        frame = logging.currentframe()
        depth = 0
        while frame:
            filename = frame.f_code.co_filename
            # 只要文件名包含 python 内部的 logging 库、或者是当前处理器的 emit 方法，就继续往上找  # noqa: E501
            if filename == __file__ or f"{os.sep}logging{os.sep}" in filename:
                frame = frame.f_back
                depth += 1
            else:
                break

        logger.bind(display_name=record.name).opt(
            depth=depth,
            exception=record.exc_info,
        ).log(level, record.getMessage())


def configure_uvicorn_logging() -> None:
    # 禁用原生 access log 输出
    # INFO:     127.0.0.1:58932 - "POST /api/v1/auth/register HTTP/1.1" 409 Conflict
    access_logger = logging.getLogger(_UVICORN_ACCESS_LOGGER_NAME)
    access_logger.handlers.clear()
    access_logger.propagate = False
    access_logger.disabled = True

    for logger_name in _UVICORN_LOGGER_NAMES:
        uvicorn_logger = logging.getLogger(logger_name)
        # 清空原有的 Handler（防止双重输出）
        uvicorn_logger.handlers.clear()
        # 挂载我们的拦截器
        uvicorn_logger.addHandler(InterceptHandler())
        # 禁止日志向上冒泡
        uvicorn_logger.propagate = False
