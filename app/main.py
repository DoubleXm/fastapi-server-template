from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import settings
from app.core.database import (
    configure_sql_logging,
    create_db_and_tables,
    should_create_db_and_tables,
)
from app.core.exception_handlers import register_exception_handlers
from app.core.logging import configure_uvicorn_access_file_logging
from app.middlewares.logging import DetailLogMiddleware


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.static_dir_path.mkdir(parents=True, exist_ok=True)
    if should_create_db_and_tables():
        create_db_and_tables()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan,
)

if settings.all_cors_origins:
    allow_all_origins = settings.all_cors_origins == ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.all_cors_origins,
        allow_credentials=not allow_all_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
app.add_middleware(DetailLogMiddleware)

configure_sql_logging()
configure_uvicorn_access_file_logging(
    log_dir=settings.logs_dir_path,
    level=logging.INFO,
    max_bytes=settings.LOG_MAX_BYTES,
    backup_count=settings.LOG_BACKUP_COUNT,
)

app.mount(
    "/static",
    StaticFiles(directory=settings.static_dir_path, check_dir=False),
    name="static",
)

register_exception_handlers(app)
app.include_router(api_router, prefix=settings.API_V1_PREFIX)
