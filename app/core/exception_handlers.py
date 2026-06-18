from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from starlette import status

from app.api.schemas import ApiResponse
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger()


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(
        "Request validation failed method={} path={} errors={}",
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
    logger.warning(
        "HTTP exception status_code={} method={} path={} detail={}",
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
    logger.exception(
        "Unhandled exception method={} path={} error={}",
        request.method,
        request.url.path,
        str(exc),
    )
    return ApiResponse.fail(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message="Internal server error",
        data={
            "detail": str(exc)
            if settings.APP_ENV == "local"
            else "Internal server error"
        },
    )


def register_exception_handlers(app):
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)
