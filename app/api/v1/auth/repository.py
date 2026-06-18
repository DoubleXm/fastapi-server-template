from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, select

from app.api.v1.auth.models import RefreshSession


def create_refresh_session(
    session: Session,
    *,
    user_id: int,
    current_token_hash: str,
    expires_at: datetime,
    ip_address: str | None,
) -> RefreshSession:
    refresh_session = RefreshSession(
        user_id=user_id,
        current_token_hash=current_token_hash,
        expires_at=expires_at,
        ip_address=ip_address,
    )
    session.add(refresh_session)
    session.commit()
    session.refresh(refresh_session)
    return refresh_session


def get_refresh_session_by_current_hash(
    session: Session,
    token_hash: str,
) -> RefreshSession | None:
    return session.exec(
        select(RefreshSession).where(RefreshSession.current_token_hash == token_hash)
    ).first()


def get_refresh_session_by_previous_hash(
    session: Session,
    token_hash: str,
) -> RefreshSession | None:
    return session.exec(
        select(RefreshSession).where(RefreshSession.previous_token_hash == token_hash)
    ).first()


def rotate_refresh_session(
    session: Session,
    *,
    refresh_session: RefreshSession,
    new_token_hash: str,
    expires_at: datetime,
    ip_address: str | None,
) -> RefreshSession:
    refresh_session.previous_token_hash = refresh_session.current_token_hash
    refresh_session.current_token_hash = new_token_hash
    refresh_session.expires_at = expires_at
    refresh_session.ip_address = ip_address
    session.add(refresh_session)
    session.commit()
    session.refresh(refresh_session)
    return refresh_session


def revoke_refresh_session(
    session: Session,
    *,
    refresh_session: RefreshSession,
    revoked_at: datetime,
    revoke_reason: int,
) -> RefreshSession:
    refresh_session.revoked_at = revoked_at
    refresh_session.revoke_reason = revoke_reason
    session.add(refresh_session)
    session.commit()
    session.refresh(refresh_session)
    return refresh_session


def revoke_active_refresh_sessions_by_user_id(
    session: Session,
    *,
    user_id: int,
    revoked_at: datetime,
    revoke_reason: int,
) -> int:
    refresh_sessions = session.exec(
        select(RefreshSession).where(
            RefreshSession.user_id == user_id,
            RefreshSession.revoked_at.is_(None),
        )
    ).all()
    for refresh_session in refresh_sessions:
        refresh_session.revoked_at = revoked_at
        refresh_session.revoke_reason = revoke_reason
        session.add(refresh_session)
    session.commit()
    return len(refresh_sessions)
