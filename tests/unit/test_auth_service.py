from __future__ import annotations

import warnings

import pytest
from fastapi import HTTPException
from jwt.warnings import InsecureKeyLengthWarning

from app.api.v1.auth.schemas import AuthRegister
from app.api.v1.auth.service import authenticate_user, register_user
from app.api.v1.users.schemas import UserCreate
from app.api.v1.users.service import create_user


def test_authenticate_user_returns_token(db_session) -> None:
    create_user(db_session, UserCreate(username="alice", password="secret123"))

    with warnings.catch_warnings(record=True) as captured_warnings:
        warnings.simplefilter("always")
        payload = authenticate_user(db_session, "alice", "secret123")

    assert payload.access_token
    assert payload.user.username == "alice"
    assert payload.token_type == "Bearer"
    assert not any(
        issubclass(warning.category, InsecureKeyLengthWarning)
        for warning in captured_warnings
    )


def test_authenticate_user_rejects_invalid_password(db_session) -> None:
    create_user(db_session, UserCreate(username="alice", password="secret123"))

    with pytest.raises(HTTPException) as exc_info:
        authenticate_user(db_session, "alice", "wrong-password")

    assert exc_info.value.status_code == 400


def test_register_user_creates_user_and_returns_token(db_session) -> None:
    auth_result = register_user(
        db_session,
        AuthRegister(username="alice", password="secret123"),
    )

    assert auth_result.access_token
    assert auth_result.user.username == "alice"
