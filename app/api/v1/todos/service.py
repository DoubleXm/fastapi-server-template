from __future__ import annotations

from fastapi import HTTPException, status
from sqlmodel import Session

from app.api.v1.todos import repository
from app.api.v1.todos.models import Todo
from app.api.v1.todos.schemas import TodoCreate, TodoUpdate


def list_todos(
    session: Session,
    *,
    offset: int,
    limit: int,
) -> tuple[list[Todo], int]:
    return repository.list_todos(session, skip=offset, limit=limit)


def get_todo_or_404(session: Session, todo_id: int) -> Todo:
    todo = repository.get_todo_by_id(session, todo_id)
    if todo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Todo not found",
        )
    return todo


def create_todo(session: Session, payload: TodoCreate) -> Todo:
    return repository.create_todo(
        session,
        title=payload.title,
        description=payload.description,
    )


def update_todo(
    session: Session,
    *,
    todo: Todo,
    payload: TodoUpdate,
) -> Todo:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return todo
    return repository.update_todo(session, todo=todo, updates=updates)


def delete_todo(session: Session, *, todo: Todo) -> None:
    repository.delete_todo(session, todo=todo)
