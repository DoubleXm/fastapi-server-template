import logging
from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from app.core.config import Settings, settings
from app.core.logging import (
    LOG_DATE_FORMAT,
    LOG_FORMAT,
    SingleLineUvicornFormatter,
    SqlAlchemyResultFilter,
    configure_rotating_file_handlers,
    uvicorn_single_line_handler,
)


def configure_sql_logging():
    """Configure SQLAlchemy logs with Uvicorn's default console style."""
    sql_logger = logging.getLogger("sqlalchemy.engine")
    log_level = logging.getLevelName(settings.LOG_LEVEL)
    enable_sql_logs = settings.SQL_ECHO and log_level <= logging.DEBUG
    sql_logger.setLevel(logging.DEBUG if enable_sql_logs else logging.WARNING)
    sql_logger.propagate = False
    if not sql_logger.handlers:
        console_handler = uvicorn_single_line_handler()
        console_handler.setLevel(logging.DEBUG)
        sql_logger.addHandler(console_handler)
        configure_rotating_file_handlers(
            sql_logger,
            log_dir=settings.logs_dir_path,
            level=logging.DEBUG,
            formatter=SingleLineUvicornFormatter(
                LOG_FORMAT,
                LOG_DATE_FORMAT,
                force_level=logging.DEBUG,
                use_colors=False,
            ),
            filters=[SqlAlchemyResultFilter()],
            max_bytes=settings.LOG_MAX_BYTES,
            backup_count=settings.LOG_BACKUP_COUNT,
        )


engine = create_engine(
    settings.sqlalchemy_database_uri,
    echo=False,
    pool_pre_ping=True,
)


def import_model_modules() -> None:
    """集中导入所有 SQLModel table，保证 metadata 和 Alembic 都能发现模型。"""
    import app.api.v1.todos.models  # noqa: F401
    import app.api.v1.users.models  # noqa: F401


def get_db() -> Generator[Session, None, None]:
    with Session(engine, expire_on_commit=False) as db:
        yield db


def should_create_db_and_tables(app_settings: Settings = settings) -> bool:
    """判断是否允许启动时自动建表，生产环境必须通过 Alembic 迁移。"""
    return app_settings.CREATE_DB_TABLES and app_settings.APP_ENV != "production"


def create_db_and_tables() -> None:
    import_model_modules()
    SQLModel.metadata.create_all(bind=engine)
