from __future__ import annotations

from datetime import timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import select

from app.api.deps import get_db
from app.api.v1.auth.models import RefreshSession
from app.api.v1.auth.router import router as auth_router
from app.api.v1.users.router import router as users_router
from app.api.v1.users.schemas import UserCreate
from app.api.v1.users.service import create_user
from app.core.exception_handlers import register_exception_handlers
from app.shared.enum import RefreshSessionRevokeReason
from app.shared.security import (
    create_access_token,
    decode_access_token,
    hash_refresh_token,
)


def create_test_app(db_session, *, with_exception_handlers: bool = False) -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[get_db] = lambda: db_session
    if with_exception_handlers:
        register_exception_handlers(app)
    app.include_router(auth_router)
    app.include_router(users_router)
    return app


def test_login_returns_token_in_data_without_authorization_header(db_session) -> None:
    create_user(db_session, UserCreate(username="alice", password="secret123"))

    app = create_test_app(db_session)
    client = TestClient(app)

    response = client.post(
        "/auth/login",
        json={"username": "alice", "password": "secret123"},
    )

    assert response.status_code == 200
    assert "Authorization" not in response.headers
    assert response.json()["data"]["token"]
    assert response.json()["data"]["refreshToken"]
    assert "accessToken" not in response.json()["data"]
    assert "tokenType" not in response.json()["data"]
    assert "expiresIn" not in response.json()["data"]
    assert response.json()["data"]["user"]["username"] == "alice"


def test_login_response_token_decodes(db_session) -> None:
    create_user(db_session, UserCreate(username="alice", password="secret123"))

    app = create_test_app(db_session)
    client = TestClient(app)

    response = client.post(
        "/auth/login",
        json={"username": "alice", "password": "secret123"},
    )

    body_token = response.json()["data"]["token"]
    payload = decode_access_token(body_token)

    assert payload["sub"] == str(response.json()["data"]["user"]["id"])


def test_login_token_can_immediately_access_current_user(db_session) -> None:
    create_user(db_session, UserCreate(username="alice", password="secret123"))

    app = create_test_app(db_session, with_exception_handlers=True)
    client = TestClient(app)

    login_response = client.post(
        "/auth/login",
        json={"username": "alice", "password": "secret123"},
    )
    me_response = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {login_response.json()['data']['token']}"},
    )

    assert me_response.status_code == 200
    assert me_response.json()["data"]["username"] == "alice"


def test_register_returns_body_token_without_authorization_header(db_session) -> None:
    app = create_test_app(db_session)
    client = TestClient(app)

    response = client.post(
        "/auth/register",
        json={"username": "alice", "password": "secret123"},
    )

    assert response.status_code == 201
    assert "Authorization" not in response.headers
    assert response.json()["data"]["token"]
    assert response.json()["data"]["refreshToken"]
    assert "accessToken" not in response.json()["data"]
    assert "tokenType" not in response.json()["data"]
    assert "expiresIn" not in response.json()["data"]
    assert response.json()["data"]["user"]["username"] == "alice"


def test_create_user_requires_authentication(db_session) -> None:
    app = create_test_app(db_session, with_exception_handlers=True)
    client = TestClient(app)

    response = client.post(
        "/users",
        json={"username": "alice", "password": "secret123"},
    )

    assert response.status_code == 401
    assert response.json()["message"] == "Authentication required"


def test_refresh_token_rotates_session_and_returns_new_tokens(db_session) -> None:
    create_user(db_session, UserCreate(username="alice", password="secret123"))

    app = create_test_app(db_session)
    client = TestClient(app)

    login_response = client.post(
        "/auth/login",
        json={"username": "alice", "password": "secret123"},
    )
    old_refresh_token = login_response.json()["data"]["refreshToken"]
    refresh_response = client.post(
        "/auth/refresh",
        json={"refreshToken": old_refresh_token},
    )

    assert refresh_response.status_code == 200
    assert refresh_response.json()["data"]["token"]
    assert refresh_response.json()["data"]["refreshToken"] != old_refresh_token
    assert refresh_response.json()["data"]["user"]["username"] == "alice"

    refresh_session = db_session.get(RefreshSession, 1)
    assert refresh_session.previous_token_hash == hash_refresh_token(old_refresh_token)
    assert refresh_session.current_token_hash == hash_refresh_token(
        refresh_response.json()["data"]["refreshToken"]
    )
    assert refresh_session.revoked_at is None
    assert refresh_session.revoke_reason is None


def test_reused_previous_refresh_token_revokes_current_session(db_session) -> None:
    create_user(db_session, UserCreate(username="alice", password="secret123"))

    app = create_test_app(db_session, with_exception_handlers=True)
    client = TestClient(app)

    login_response = client.post(
        "/auth/login",
        json={"username": "alice", "password": "secret123"},
    )
    old_refresh_token = login_response.json()["data"]["refreshToken"]
    client.post(
        "/auth/refresh",
        json={"refreshToken": old_refresh_token},
    )
    reuse_response = client.post(
        "/auth/refresh",
        json={"refreshToken": old_refresh_token},
    )

    assert reuse_response.status_code == 401
    assert reuse_response.json()["message"] == "Refresh token reuse detected"

    refresh_session = db_session.get(RefreshSession, 1)
    assert refresh_session.revoked_at is not None
    assert refresh_session.revoke_reason == RefreshSessionRevokeReason.TOKEN_REUSE


def test_logout_revokes_current_refresh_session(db_session) -> None:
    create_user(db_session, UserCreate(username="alice", password="secret123"))

    app = create_test_app(db_session)
    client = TestClient(app)

    login_response = client.post(
        "/auth/login",
        json={"username": "alice", "password": "secret123"},
    )
    logout_response = client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {login_response.json()['data']['token']}"},
    )

    assert logout_response.status_code == 200
    assert logout_response.json()["data"] == {"revoked": True}

    refresh_session = db_session.get(RefreshSession, 1)
    assert refresh_session.revoked_at is not None
    assert refresh_session.revoke_reason == RefreshSessionRevokeReason.LOGOUT


def test_logout_requires_authentication(db_session) -> None:
    app = create_test_app(db_session, with_exception_handlers=True)
    client = TestClient(app)

    response = client.post("/auth/logout")

    assert response.status_code == 401
    assert response.json()["message"] == "Authentication required"


def test_reset_password_updates_password_and_revokes_refresh_session(
    db_session,
) -> None:
    create_user(db_session, UserCreate(username="alice", password="secret123"))

    app = create_test_app(db_session, with_exception_handlers=True)
    client = TestClient(app)

    login_response = client.post(
        "/auth/login",
        json={"username": "alice", "password": "secret123"},
    )
    reset_response = client.post(
        "/auth/reset-password",
        json={"oldPassword": "secret123", "newPassword": "new-secret123"},
        headers={"Authorization": f"Bearer {login_response.json()['data']['token']}"},
    )

    assert reset_response.status_code == 200
    assert reset_response.json()["data"] == {"reset": True}

    refresh_session = db_session.get(RefreshSession, 1)
    assert refresh_session.revoked_at is not None
    assert refresh_session.revoke_reason == RefreshSessionRevokeReason.PASSWORD_CHANGED

    old_password_response = client.post(
        "/auth/login",
        json={"username": "alice", "password": "secret123"},
    )
    assert old_password_response.status_code == 400

    new_password_response = client.post(
        "/auth/login",
        json={"username": "alice", "password": "new-secret123"},
    )
    assert new_password_response.status_code == 200

    refresh_response = client.post(
        "/auth/refresh",
        json={"refreshToken": login_response.json()["data"]["refreshToken"]},
    )
    assert refresh_response.status_code == 401


def test_reset_password_rejects_wrong_old_password(db_session) -> None:
    create_user(db_session, UserCreate(username="alice", password="secret123"))

    app = create_test_app(db_session, with_exception_handlers=True)
    client = TestClient(app)

    login_response = client.post(
        "/auth/login",
        json={"username": "alice", "password": "secret123"},
    )
    reset_response = client.post(
        "/auth/reset-password",
        json={"oldPassword": "wrong-password", "newPassword": "new-secret123"},
        headers={"Authorization": f"Bearer {login_response.json()['data']['token']}"},
    )

    assert reset_response.status_code == 400
    assert reset_response.json()["message"] == "Invalid old password"


def test_reset_password_requires_authentication(db_session) -> None:
    app = create_test_app(db_session, with_exception_handlers=True)
    client = TestClient(app)

    response = client.post(
        "/auth/reset-password",
        json={"oldPassword": "secret123", "newPassword": "new-secret123"},
    )

    assert response.status_code == 401
    assert response.json()["message"] == "Authentication required"


def test_login_replaces_existing_active_refresh_session(db_session) -> None:
    create_user(db_session, UserCreate(username="alice", password="secret123"))

    app = create_test_app(db_session)
    client = TestClient(app)

    client.post(
        "/auth/login",
        json={"username": "alice", "password": "secret123"},
    )
    second_login_response = client.post(
        "/auth/login",
        json={"username": "alice", "password": "secret123"},
    )

    refresh_sessions = db_session.exec(select(RefreshSession)).all()
    assert len(refresh_sessions) == 2
    assert refresh_sessions[0].revoked_at is not None
    assert (
        refresh_sessions[0].revoke_reason == RefreshSessionRevokeReason.LOGIN_REPLACED
    )
    assert refresh_sessions[1].revoked_at is None

    refresh_response = client.post(
        "/auth/refresh",
        json={"refreshToken": second_login_response.json()["data"]["refreshToken"]},
    )
    assert refresh_response.status_code == 200


def test_logout_all_endpoint_is_not_registered(db_session) -> None:
    create_user(db_session, UserCreate(username="alice", password="secret123"))

    app = create_test_app(db_session)
    client = TestClient(app)

    login_response = client.post(
        "/auth/login",
        json={"username": "alice", "password": "secret123"},
    )
    response = client.post(
        "/auth/logout-all",
        headers={"Authorization": f"Bearer {login_response.json()['data']['token']}"},
    )

    assert response.status_code == 404


def test_authenticated_user_can_update_other_user(db_session) -> None:
    create_user(db_session, UserCreate(username="admin", password="secret123"))
    other_user = create_user(
        db_session,
        UserCreate(username="bob", password="secret123"),
    )

    app = create_test_app(db_session)
    client = TestClient(app)

    login_response = client.post(
        "/auth/login",
        json={"username": "admin", "password": "secret123"},
    )
    update_response = client.patch(
        f"/users/{other_user.id}",
        json={"username": "bob-updated"},
        headers={"Authorization": f"Bearer {login_response.json()['data']['token']}"},
    )

    assert update_response.status_code == 200
    assert update_response.json()["data"]["username"] == "bob-updated"


def test_expired_token_returns_expired_message(db_session) -> None:
    user = create_user(db_session, UserCreate(username="alice", password="secret123"))
    expired_token, _ = create_access_token(
        str(user.id),
        expires_delta=timedelta(seconds=-1),
    )

    app = create_test_app(db_session, with_exception_handlers=True)
    client = TestClient(app)

    response = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == 401
    assert response.json()["message"] == "Token expired"


def test_malformed_token_returns_invalid_message(db_session) -> None:
    app = create_test_app(db_session, with_exception_handlers=True)
    client = TestClient(app)

    response = client.get(
        "/users/me",
        headers={"Authorization": "Bearer not-a-jwt"},
    )

    assert response.status_code == 401
    assert response.json()["message"] == "Invalid token"
