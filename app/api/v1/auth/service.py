from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlmodel import Session

from app.api.v1.auth.schemas import AuthRegister
from app.api.v1.users import repository
from app.api.v1.users.models import User
from app.api.v1.users.schemas import UserCreate
from app.api.v1.users.service import create_user
from app.shared.security import create_access_token, verify_password


@dataclass(frozen=True)
class AuthResult:
    """认证成功后的内部结果，router 负责写入 response data。"""

    user: User
    access_token: str
    expires_in: int
    token_type: str = "Bearer"


def register_user(session: Session, payload: AuthRegister) -> AuthResult:
    user = create_user(
        session,
        UserCreate(username=payload.username, password=payload.password),
    )
    return create_auth_result(user)


def create_auth_result(user: User) -> AuthResult:
    access_token, expires_in = create_access_token(str(user.id))
    return AuthResult(user=user, access_token=access_token, expires_in=expires_in)


def authenticate_user(session: Session, username: str, password: str) -> AuthResult:
    user = repository.get_user_by_username(session, username)
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid username or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive"
        )
    return create_auth_result(user)
