from __future__ import annotations

import warnings

import pytest
from fastapi import HTTPException
from jwt.warnings import InsecureKeyLengthWarning

from app.api.v1.auth.schemas import AuthRegister
from app.api.v1.auth.service import login, register, reset_password
from app.api.v1.users.schemas import UserCreate
from app.api.v1.users.service import create_user
from app.shared.security import verify_password


def test_login_returns_token(db_session) -> None:
    create_user(db_session, UserCreate(username="alice", password="secret123"))

    with warnings.catch_warnings(record=True) as captured_warnings:
        warnings.simplefilter("always")
        payload = login(db_session, "alice", "secret123")

    assert payload.access_token
    assert payload.refresh_token
    assert payload.user.username == "alice"
    assert payload.token_type == "Bearer"
    assert not any(
        issubclass(warning.category, InsecureKeyLengthWarning)
        for warning in captured_warnings
    )


def test_login_rejects_invalid_password(db_session) -> None:
    create_user(db_session, UserCreate(username="alice", password="secret123"))

    with pytest.raises(HTTPException) as exc_info:
        login(db_session, "alice", "wrong-password")

    assert exc_info.value.status_code == 400


def test_register_creates_user_and_returns_token(db_session) -> None:
    auth_result = register(
        db_session,
        AuthRegister(username="alice", password="secret123"),
    )

    assert auth_result.access_token
    assert auth_result.refresh_token
    assert auth_result.user.username == "alice"


def test_reset_password_updates_user_password(db_session) -> None:
    user = create_user(db_session, UserCreate(username="alice", password="secret123"))

    reset_password(
        db_session,
        user=user,
        old_password="secret123",
        new_password="new-secret123",
    )

    db_session.refresh(user)
    assert verify_password("new-secret123", user.password_hash)


def test_reset_password_rejects_invalid_old_password(db_session) -> None:
    user = create_user(db_session, UserCreate(username="alice", password="secret123"))

    with pytest.raises(HTTPException) as exc_info:
        reset_password(
            db_session,
            user=user,
            old_password="wrong-password",
            new_password="new-secret123",
        )

    assert exc_info.value.status_code == 400
    assert verify_password("secret123", user.password_hash)
