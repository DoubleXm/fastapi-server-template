import logging

from loguru import logger

# "uvicorn.access",
_UVICORN_LOGGER_NAMES = ("uvicorn", "uvicorn.error", "uvicorn.asgi")


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
            if "logging" in filename or filename == __file__:
                frame = frame.f_back
                depth += 1
            else:
                break

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def disable_uvicorn_logging() -> None:
    """彻底关闭 Uvicorn 自身 logger，避免 server/access 日志打印。"""
    access_logger = logging.getLogger("uvicorn.access")
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

    logging.getLogger("uvicorn.access").handlers = [InterceptHandler()]
    logging.getLogger("uvicorn.error").handlers = [InterceptHandler()]
