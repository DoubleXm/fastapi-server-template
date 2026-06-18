from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from fastapi import HTTPException, status
from sqlmodel import Session

from app.api.v1.auth import repository as auth_repository
from app.api.v1.auth.schemas import AuthRegister
from app.api.v1.users import repository as users_repository
from app.api.v1.users.models import User
from app.api.v1.users.schemas import UserCreate
from app.api.v1.users.service import create_user
from app.core.config import settings
from app.shared.enum import RefreshSessionRevokeReason
from app.shared.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    hash_refresh_token,
    verify_password,
)
from app.shared.utils import as_utc, utc_now


@dataclass(frozen=True)
class AuthResult:
    """认证成功后的内部结果，router 负责写入 response data。"""

    user: User
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "Bearer"


def register(
    session: Session,
    payload: AuthRegister,
    *,
    ip_address: str | None = None,
) -> AuthResult:
    user = create_user(
        session,
        UserCreate(username=payload.username, password=payload.password),
    )
    return _create_auth_result(session, user, ip_address=ip_address)


def login(
    session: Session,
    username: str,
    password: str,
    *,
    ip_address: str | None = None,
) -> AuthResult:
    user = users_repository.get_user_by_username(session, username)
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid username or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive"
        )
    return _create_auth_result(session, user, ip_address=ip_address)


def refresh(
    session: Session,
    refresh_token: str,
    *,
    ip_address: str | None = None,
) -> AuthResult:
    token_hash = hash_refresh_token(refresh_token)
    refresh_session = auth_repository.get_refresh_session_by_current_hash(
        session,
        token_hash,
    )

    # 命中 current token 时执行正常轮换：签发新的 access token 和 refresh token。
    if refresh_session is not None:
        # 已经因为 登出、重复使用、修改密码、登录重置原因被撤销了
        if refresh_session.revoked_at is not None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )
        # 过期
        if as_utc(refresh_session.expires_at) <= utc_now():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token expired",
            )

        user = users_repository.get_user_by_id(session, refresh_session.user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is inactive",
            )

        access_token, expires_in = create_access_token(str(user.id))
        new_refresh_token = create_refresh_token()
        # 创建一个新的 refresh token 做 current token
        # refresh_session 中的 current token 做 previous token
        auth_repository.rotate_refresh_session(
            session,
            refresh_session=refresh_session,
            new_token_hash=hash_refresh_token(new_refresh_token),
            expires_at=utc_now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            ip_address=ip_address,
        )
        return AuthResult(
            user=user,
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_in=expires_in,
        )

    # 命中 previous token 说明上一枚 refresh token 被重复使用。
    previous_session = auth_repository.get_refresh_session_by_previous_hash(
        session,
        token_hash,
    )
    if previous_session is not None and previous_session.revoked_at is None:
        auth_repository.revoke_refresh_session(
            session,
            refresh_session=previous_session,
            revoked_at=utc_now(),
            revoke_reason=RefreshSessionRevokeReason.TOKEN_REUSE,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token reuse detected",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid refresh token",
    )


def logout(session: Session, *, user: User) -> bool:
    auth_repository.revoke_active_refresh_sessions_by_user_id(
        session,
        user_id=user.id,
        revoked_at=utc_now(),
        revoke_reason=RefreshSessionRevokeReason.LOGOUT,
    )
    return True


def reset_password(
    session: Session,
    *,
    user: User,
    old_password: str,
    new_password: str,
) -> bool:
    if not verify_password(old_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid old password",
        )

    users_repository.update_user(
        session,
        user=user,
        updates={"password_hash": get_password_hash(new_password)},
    )
    auth_repository.revoke_active_refresh_sessions_by_user_id(
        session,
        user_id=user.id,
        revoked_at=utc_now(),
        revoke_reason=RefreshSessionRevokeReason.PASSWORD_CHANGED,
    )
    return True


def _create_auth_result(
    session: Session,
    user: User,
    *,
    ip_address: str | None = None,
) -> AuthResult:
    # 当前模板不区分多端 session，新登录会替换该用户旧的 active refresh session。
    auth_repository.revoke_active_refresh_sessions_by_user_id(
        session,
        user_id=user.id,
        revoked_at=utc_now(),
        revoke_reason=RefreshSessionRevokeReason.LOGIN_REPLACED,
    )
    access_token, expires_in = create_access_token(str(user.id))
    refresh_token = create_refresh_token()
    # 每次注册、登录会增加一条 session 记录
    auth_repository.create_refresh_session(
        session,
        user_id=user.id,
        current_token_hash=hash_refresh_token(refresh_token),
        expires_at=utc_now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        ip_address=ip_address,
    )
    return AuthResult(
        user=user,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )
