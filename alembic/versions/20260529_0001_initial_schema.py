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
        "todos",
        sa.Column("id", sa.Integer(), nullable=False, comment="待办事项 ID"),
        sa.Column(
            "title",
            sqlmodel.sql.sqltypes.AutoString(length=100),
            nullable=False,
            comment="标题",
        ),
        sa.Column(
            "description",
            sqlmodel.sql.sqltypes.AutoString(length=500),
            nullable=True,
            comment="描述",
        ),
        sa.Column("is_completed", sa.Boolean(), nullable=False, comment="是否完成"),
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
    op.create_index(op.f("ix_todos_id"), "todos", ["id"], unique=False)
    op.create_index(op.f("ix_todos_title"), "todos", ["title"], unique=False)

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


def downgrade() -> None:
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_table("users")
    op.drop_index(op.f("ix_todos_title"), table_name="todos")
    op.drop_index(op.f("ix_todos_id"), table_name="todos")
    op.drop_table("todos")
