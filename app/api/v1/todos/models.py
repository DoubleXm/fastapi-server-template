from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel

from app.shared.utils import utc_now


class Todo(SQLModel, table=True):
    __tablename__ = "todos"

    id: int | None = Field(
        default=None,
        primary_key=True,
        index=True,
        sa_column_kwargs={"comment": "待办事项 ID"},
    )
    title: str = Field(
        max_length=100,
        index=True,
        nullable=False,
        sa_column_kwargs={"comment": "标题"},
    )
    description: str | None = Field(
        default=None,
        max_length=500,
        sa_column_kwargs={"comment": "描述"},
    )
    is_completed: bool = Field(
        default=False,
        nullable=False,
        description="是否完成",
        sa_column_kwargs={"comment": "是否完成"},
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
