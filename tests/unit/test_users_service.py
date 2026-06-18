from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api.v1.users.schemas import UserCreate, UserUpdate
from app.api.v1.users.service import (
    create_user,
    delete_user,
    get_user,
    list_users,
    update_user,
)


def test_user_model_is_sqlmodel_table_and_schema_outputs_camel_case() -> None:
    from sqlmodel import SQLModel

    from app.api.v1.users.models import User
    from app.api.v1.users.schemas import UserPublic

    assert issubclass(User, SQLModel)
    assert User.__tablename__ == "users"

    user = User(id=1, username="alice", password_hash="hash")
    public_user = UserPublic.model_validate(user)

    assert public_user.username == "alice"
    assert public_user.model_dump(mode="json", by_alias=True)["isActive"] is True


def test_create_and_list_users(db_session) -> None:
    created_user = create_user(
        db_session,
        UserCreate(username="alice", password="secret123"),
    )

    users, total = list_users(db_session, offset=0, limit=20)

    assert created_user.id is not None
    assert total == 1
    assert users[0].username == "alice"


def test_duplicate_username_raises_conflict(db_session) -> None:
    create_user(db_session, UserCreate(username="alice", password="secret123"))

    with pytest.raises(HTTPException) as exc_info:
        create_user(db_session, UserCreate(username="alice", password="secret456"))

    assert exc_info.value.status_code == 409


def test_update_and_delete_user(db_session) -> None:
    user = create_user(db_session, UserCreate(username="alice", password="secret123"))

    updated = update_user(
        db_session,
        user_id=user.id,
        payload=UserUpdate(username="alice-updated", password="changed456"),
    )

    assert updated.username == "alice-updated"

    persisted = get_user(db_session, updated.id)
    delete_user(db_session, user_id=persisted.id)

    with pytest.raises(HTTPException) as exc_info:
        get_user(db_session, updated.id)

    assert exc_info.value.status_code == 404
