"""initial schema

Revision ID: 20260529_0001
Revises:
Create Date: 2026-05-29 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel

from alembic import op

revision: str = "20260529_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False, comment="用户 ID"),
        sa.Column(
            "username",
            sqlmodel.sql.sqltypes.AutoString(length=50),
            nullable=False,
            comment="用户名",
        ),
        sa.Column(
            "password_hash",
            sqlmodel.sql.sqltypes.AutoString(length=255),
            nullable=False,
            comment="密码哈希",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, comment="是否启用"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="更新时间",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)
    op.create_table(
        "refresh_sessions",
        sa.Column("id", sa.Integer(), nullable=False, comment="刷新会话 ID"),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="用户 ID"),
        sa.Column(
            "current_token_hash",
            sqlmodel.sql.sqltypes.AutoString(length=64),
            nullable=False,
            comment="当前 refresh token 哈希",
        ),
        sa.Column(
            "previous_token_hash",
            sqlmodel.sql.sqltypes.AutoString(length=64),
            nullable=True,
            comment="上一枚 refresh token 哈希",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="过期时间",
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="撤销时间",
        ),
        sa.Column(
            "revoke_reason",
            sa.Integer(),
            nullable=True,
            comment=(
                "撤销原因：1=主动退出，2=修改密码后撤销，3=refresh token 复用，"
                "4=管理员强制撤销，5=用户被禁用，6=新登录替换旧会话"
            ),
        ),
        sa.Column(
            "ip_address",
            sqlmodel.sql.sqltypes.AutoString(length=64),
            nullable=True,
            comment="IP 地址",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="更新时间",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_refresh_sessions_current_token_hash"),
        "refresh_sessions",
        ["current_token_hash"],
        unique=True,
    )
    op.create_index(
        op.f("ix_refresh_sessions_id"),
        "refresh_sessions",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_refresh_sessions_previous_token_hash"),
        "refresh_sessions",
        ["previous_token_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_refresh_sessions_user_id"),
        "refresh_sessions",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_refresh_sessions_user_id"), table_name="refresh_sessions")
    op.drop_index(
        op.f("ix_refresh_sessions_previous_token_hash"),
        table_name="refresh_sessions",
    )
    op.drop_index(op.f("ix_refresh_sessions_id"), table_name="refresh_sessions")
    op.drop_index(
        op.f("ix_refresh_sessions_current_token_hash"),
        table_name="refresh_sessions",
    )
    op.drop_table("refresh_sessions")
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_table("users")
