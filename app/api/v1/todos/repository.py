from __future__ import annotations

from sqlalchemy import func
from sqlmodel import Session, select

from app.api.v1.todos.models import Todo


def get_todo_by_id(session: Session, todo_id: int) -> Todo | None:
    return session.get(Todo, todo_id)


def list_todos(session: Session, *, skip: int, limit: int) -> tuple[list[Todo], int]:
    total = session.exec(select(func.count()).select_from(Todo)).one()
    todos = session.exec(
        select(Todo).order_by(Todo.id.desc()).offset(skip).limit(limit)
    ).all()
    return list(todos), total


def create_todo(
    session: Session,
    *,
    title: str,
    description: str | None,
) -> Todo:
    todo = Todo(title=title, description=description)
    session.add(todo)
    session.commit()
    session.refresh(todo)
    return todo


def update_todo(session: Session, *, todo: Todo, updates: dict) -> Todo:
    for key, value in updates.items():
        setattr(todo, key, value)
    session.add(todo)
    session.commit()
    session.refresh(todo)
    return todo


def delete_todo(session: Session, *, todo: Todo) -> None:
    session.delete(todo)
    session.commit()
