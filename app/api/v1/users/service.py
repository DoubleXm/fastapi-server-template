from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlmodel import Session

from app.api.v1.users import repository
from app.api.v1.users.models import User
from app.api.v1.users.schemas import UserCreate, UserUpdate
from app.shared.security import (
    create_access_token,
    get_password_hash,
    verify_password,
)


@dataclass(frozen=True)
class AuthResult:
    """认证成功后的内部结果，router 负责写入 response data。"""

    user: User
    access_token: str
    expires_in: int
    token_type: str = "Bearer"


def list_users(
    session: Session,
    *,
    offset: int,
    limit: int,
) -> tuple[list[User], int]:
    return repository.list_users(
        session,
        skip=offset,
        limit=limit,
    )


def get_user_or_404(session: Session, user_id: int) -> User:
    user = repository.get_user_by_id(session, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user


def create_user(session: Session, payload: UserCreate) -> User:
    existing_user = repository.get_user_by_username(session, payload.username)
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )
    return repository.create_user(
        session,
        username=payload.username,
        password_hash=get_password_hash(payload.password),
    )


def create_auth_result(user: User) -> AuthResult:
    access_token, expires_in = create_access_token(str(user.id))
    return AuthResult(
        user=user,
        access_token=access_token,
        expires_in=expires_in,
    )


def authenticate_user(session: Session, username: str, password: str) -> AuthResult:
    user = repository.get_user_by_username(session, username)
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid username or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )
    return create_auth_result(user)


def update_user(
    session: Session,
    *,
    user: User,
    payload: UserUpdate,
) -> User:
    updates: dict[str, str] = {}

    if payload.username and payload.username != user.username:
        existing_user = repository.get_user_by_username(session, payload.username)
        if existing_user is not None and existing_user.id != user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already exists",
            )
        updates["username"] = payload.username

    if payload.password:
        updates["password_hash"] = get_password_hash(payload.password)

    if not updates:
        return user

    return repository.update_user(session, user=user, updates=updates)


def delete_user(session: Session, *, user: User) -> None:
    repository.delete_user(session, user=user)
