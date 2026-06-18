from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel

from app.shared.enum import REFRESH_SESSION_REVOKE_REASON_COMMENT
from app.shared.utils import utc_now


class RefreshSession(SQLModel, table=True):
    __tablename__ = "refresh_sessions"

    id: int | None = Field(
        default=None,
        primary_key=True,
        index=True,
        sa_column_kwargs={"comment": "刷新会话 ID"},
    )
    user_id: int = Field(
        foreign_key="users.id",
        index=True,
        nullable=False,
        sa_column_kwargs={"comment": "用户 ID"},
    )
    current_token_hash: str = Field(
        max_length=64,
        unique=True,
        index=True,
        nullable=False,
        sa_column_kwargs={"comment": "当前 refresh token 哈希"},
    )
    previous_token_hash: str | None = Field(
        default=None,
        max_length=64,
        index=True,
        nullable=True,
        sa_column_kwargs={"comment": "上一枚 refresh token 哈希"},
    )
    expires_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            comment="过期时间",
        ),
    )
    revoked_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=True,
            comment="撤销时间",
        ),
    )
    revoke_reason: int | None = Field(
        default=None,
        nullable=True,
        description="refresh session 撤销原因",
        sa_column_kwargs={"comment": REFRESH_SESSION_REVOKE_REASON_COMMENT},
    )
    ip_address: str | None = Field(
        default=None,
        max_length=64,
        nullable=True,
        sa_column_kwargs={"comment": "IP 地址"},
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
