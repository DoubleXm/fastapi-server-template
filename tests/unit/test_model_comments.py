from __future__ import annotations

from app.api.v1.auth.models import RefreshSession
from app.api.v1.users.models import User
from app.shared.enum import RefreshSessionRevokeReason


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


def test_refresh_session_model_columns_have_chinese_comments() -> None:
    comments = {
        column.name: column.comment for column in RefreshSession.__table__.columns
    }

    assert comments == {
        "id": "刷新会话 ID",
        "user_id": "用户 ID",
        "current_token_hash": "当前 refresh token 哈希",
        "previous_token_hash": "上一枚 refresh token 哈希",
        "expires_at": "过期时间",
        "revoked_at": "撤销时间",
        "revoke_reason": (
            "撤销原因：1=主动退出，2=修改密码后撤销，3=refresh token 复用，"
            "4=管理员强制撤销，5=用户被禁用，6=新登录替换旧会话"
        ),
        "ip_address": "IP 地址",
        "created_at": "创建时间",
        "updated_at": "更新时间",
    }


def test_refresh_session_revoke_reason_values_are_stable() -> None:
    assert RefreshSessionRevokeReason.LOGOUT == 1
    assert RefreshSessionRevokeReason.PASSWORD_CHANGED == 2
    assert RefreshSessionRevokeReason.TOKEN_REUSE == 3
    assert RefreshSessionRevokeReason.ADMIN_REVOKED == 4
    assert RefreshSessionRevokeReason.USER_DISABLED == 5
    assert RefreshSessionRevokeReason.LOGIN_REPLACED == 6
