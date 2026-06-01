from __future__ import annotations

from datetime import timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.api.v1.users.router import router as users_router
from app.api.v1.users.schemas import UserCreate
from app.api.v1.users.service import create_user
from app.core.exception_handlers import register_exception_handlers
from app.shared.security import create_access_token, decode_access_token


def test_login_returns_token_in_data_without_authorization_header(db_session) -> None:
    create_user(db_session, UserCreate(username="alice", password="secret123"))

    app = FastAPI()
    app.dependency_overrides[get_db] = lambda: db_session
    app.include_router(users_router)
    client = TestClient(app)

    response = client.post(
        "/users/login",
        json={"username": "alice", "password": "secret123"},
    )

    assert response.status_code == 200
    assert "Authorization" not in response.headers
    assert response.json()["data"]["token"]
    assert "accessToken" not in response.json()["data"]
    assert "tokenType" not in response.json()["data"]
    assert "expiresIn" not in response.json()["data"]
    assert response.json()["data"]["user"]["username"] == "alice"


def test_login_response_token_decodes(
    db_session,
) -> None:
    create_user(db_session, UserCreate(username="alice", password="secret123"))

    app = FastAPI()
    app.dependency_overrides[get_db] = lambda: db_session
    app.include_router(users_router)
    client = TestClient(app)

    response = client.post(
        "/users/login",
        json={"username": "alice", "password": "secret123"},
    )

    body_token = response.json()["data"]["token"]
    payload = decode_access_token(body_token)

    assert payload["sub"] == str(response.json()["data"]["user"]["id"])


def test_login_token_can_immediately_access_current_user(db_session) -> None:
    create_user(db_session, UserCreate(username="alice", password="secret123"))

    app = FastAPI()
    app.dependency_overrides[get_db] = lambda: db_session
    register_exception_handlers(app)
    app.include_router(users_router)
    client = TestClient(app)

    login_response = client.post(
        "/users/login",
        json={"username": "alice", "password": "secret123"},
    )
    me_response = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {login_response.json()['data']['token']}"},
    )

    assert me_response.status_code == 200
    assert me_response.json()["data"]["username"] == "alice"


def test_register_returns_body_token_without_authorization_header(db_session) -> None:
    app = FastAPI()
    app.dependency_overrides[get_db] = lambda: db_session
    app.include_router(users_router)
    client = TestClient(app)

    response = client.post(
        "/users/register",
        json={"username": "alice", "password": "secret123"},
    )

    assert response.status_code == 201
    assert "Authorization" not in response.headers
    assert response.json()["data"]["token"]
    assert "accessToken" not in response.json()["data"]
    assert "tokenType" not in response.json()["data"]
    assert "expiresIn" not in response.json()["data"]
    assert response.json()["data"]["user"]["username"] == "alice"


def test_authenticated_user_can_update_other_user(db_session) -> None:
    create_user(db_session, UserCreate(username="admin", password="secret123"))
    other_user = create_user(
        db_session,
        UserCreate(username="bob", password="secret123"),
    )

    app = FastAPI()
    app.dependency_overrides[get_db] = lambda: db_session
    app.include_router(users_router)
    client = TestClient(app)

    login_response = client.post(
        "/users/login",
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

    app = FastAPI()
    app.dependency_overrides[get_db] = lambda: db_session
    register_exception_handlers(app)
    app.include_router(users_router)
    client = TestClient(app)

    response = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == 401
    assert response.json()["message"] == "Token expired"


def test_malformed_token_returns_invalid_message(db_session) -> None:
    app = FastAPI()
    app.dependency_overrides[get_db] = lambda: db_session
    register_exception_handlers(app)
    app.include_router(users_router)
    client = TestClient(app)

    response = client.get(
        "/users/me",
        headers={"Authorization": "Bearer not-a-jwt"},
    )

    assert response.status_code == 401
    assert response.json()["message"] == "Invalid token"
