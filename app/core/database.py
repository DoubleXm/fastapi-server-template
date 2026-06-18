from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from app.core.config import Settings, settings

engine = create_engine(
    settings.sqlalchemy_database_uri,
    echo=False,
    pool_pre_ping=True,
)


def import_model_modules() -> None:
    """集中导入所有 SQLModel table，保证 metadata 和 Alembic 都能发现模型。"""
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
