import logging

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from starlette import status

from app.api.schemas import ApiResponse
from app.core.config import settings
from app.core.logging import configure_app_logger

error_logger = logging.getLogger("app.error")
log_level = logging.getLevelName(settings.LOG_LEVEL)
error_logger = configure_app_logger(
    error_logger.name,
    log_dir=settings.logs_dir_path,
    level=log_level,
    max_bytes=settings.LOG_MAX_BYTES,
    backup_count=settings.LOG_BACKUP_COUNT,
)


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    error_logger.warning(
        "Request validation failed method=%s path=%s errors=%s",
        request.method,
        request.url.path,
        exc.errors(),
    )
    return ApiResponse.fail(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        message="Request validation failed",
        data={"errors": exc.errors()},
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    error_logger.warning(
        "HTTP exception status_code=%s method=%s path=%s detail=%s",
        exc.status_code,
        request.method,
        request.url.path,
        exc.detail,
    )
    return ApiResponse.fail(
        status_code=exc.status_code,
        message=str(exc.detail),
        data={"detail": exc.detail},
    )


async def global_exception_handler(request: Request, exc: Exception):
    error_logger.error(
        "Unhandled exception method=%s path=%s error=%s",
        request.method,
        request.url.path,
        str(exc),
    )
    return ApiResponse.fail(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message="Internal server error",
        data={"detail": str(exc) if settings.DEBUG else "Internal server error"},
    )


def register_exception_handlers(app):
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)
