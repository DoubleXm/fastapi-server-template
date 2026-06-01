from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api.v1.todos.schemas import TodoCreate, TodoUpdate
from app.api.v1.todos.service import (
    create_todo,
    delete_todo,
    get_todo_or_404,
    list_todos,
    update_todo,
)


def test_create_list_update_and_delete_todo(db_session) -> None:
    todo = create_todo(
        db_session,
        TodoCreate(title="Buy milk", description="Two bottles"),
    )

    todos, total = list_todos(db_session, offset=0, limit=20)

    assert todo.id is not None
    assert total == 1
    assert todos[0].title == "Buy milk"
    assert todos[0].is_completed is False

    persisted = get_todo_or_404(db_session, todo.id)
    updated = update_todo(
        db_session,
        todo=persisted,
        payload=TodoUpdate(title="Buy oat milk", is_completed=True),
    )

    assert updated.title == "Buy oat milk"
    assert updated.is_completed is True

    delete_todo(db_session, todo=updated)
    with pytest.raises(HTTPException) as exc_info:
        get_todo_or_404(db_session, todo.id)

    assert exc_info.value.status_code == 404
