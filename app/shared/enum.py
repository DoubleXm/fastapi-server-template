from enum import IntEnum

REFRESH_SESSION_REVOKE_REASON_COMMENT = (
    "撤销原因：1=主动退出，2=修改密码后撤销，3=refresh token 复用，6=新登录替换旧会话"
)


class RefreshSessionRevokeReason(IntEnum):
    """refresh session 撤销原因"""

    LOGOUT = 1  # 主动退出
    PASSWORD_CHANGED = 2  # 修改密码后撤销
    TOKEN_REUSE = 3  # 检测到上一枚 refresh token 被重复使用
    LOGIN_REPLACED = 6  # 新登录替换旧会话
