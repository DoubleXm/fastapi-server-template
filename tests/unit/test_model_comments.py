from __future__ import annotations

from app.api.v1.users.models import User


def test_user_model_columns_have_chinese_comments() -> None:
    comments = {column.name: column.comment for column in User.__table__.columns}

    assert comments == {
        "id": "用户 ID",
        "username": "用户名",
        "password_hash": "密码哈希",
        "is_active": "是否启用",
        "created_at": "创建时间",
        "updated_at": "更新时间",
    }
