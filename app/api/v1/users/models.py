from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel

from app.shared.utils import utc_now


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(
        default=None,
        primary_key=True,
        index=True,
        sa_column_kwargs={"comment": "用户 ID"},
    )
    username: str = Field(
        max_length=50,
        unique=True,
        index=True,
        nullable=False,
        sa_column_kwargs={"comment": "用户名"},
    )
    password_hash: str = Field(
        max_length=255,
        nullable=False,
        sa_column_kwargs={"comment": "密码哈希"},
    )
    is_active: bool = Field(
        default=True,
        nullable=False,
        description="是否启用",
        sa_column_kwargs={"comment": "是否启用"},
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            comment="创建时间",
        ),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            onupdate=utc_now,
            comment="更新时间",
        ),
    )
