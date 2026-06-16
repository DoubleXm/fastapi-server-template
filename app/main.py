from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import settings
from app.core.database import (
    create_db_and_tables,
    should_create_db_and_tables,
)
from app.core.exception_handlers import register_exception_handlers
from app.core.logger import setup_logging
from app.middlewares.logging import LoggingMiddleware

setup_logging()


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
    debug=settings.APP_ENV == "local",
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
app.add_middleware(LoggingMiddleware)

app.mount(
    "/static",
    StaticFiles(directory=settings.static_dir_path, check_dir=False),
    name="static",
)

register_exception_handlers(app)
app.include_router(api_router, prefix=settings.API_V1_PREFIX)
