from __future__ import annotations

from sqlalchemy import func
from sqlmodel import Session, select

from app.api.v1.users.models import User


def get_user_by_id(session: Session, user_id: int) -> User | None:
    return session.get(User, user_id)


def get_user_by_username(session: Session, username: str) -> User | None:
    statement = select(User).where(User.username == username)
    return session.exec(statement).first()


def list_users(session: Session, *, skip: int, limit: int) -> tuple[list[User], int]:
    total = session.exec(select(func.count()).select_from(User)).one()
    users = session.exec(
        select(User).order_by(User.id.desc()).offset(skip).limit(limit)
    ).all()
    return list(users), total


def create_user(
    session: Session,
    *,
    username: str,
    password_hash: str,
) -> User:
    user = User(username=username, password_hash=password_hash)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def update_user(session: Session, *, user: User, updates: dict) -> User:
    for key, value in updates.items():
        setattr(user, key, value)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def delete_user(session: Session, *, user: User) -> None:
    session.delete(user)
    session.commit()
