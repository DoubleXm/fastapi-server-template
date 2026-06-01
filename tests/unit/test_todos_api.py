from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.api.v1.todos.router import router as todos_router
from app.api.v1.users.router import router as users_router
from app.api.v1.users.schemas import UserCreate
from app.api.v1.users.service import create_user
from app.core.exception_handlers import register_exception_handlers


def make_client(db_session) -> TestClient:
    app = FastAPI()
    app.dependency_overrides[get_db] = lambda: db_session
    register_exception_handlers(app)
    app.include_router(users_router)
    app.include_router(todos_router)
    return TestClient(app)


def login_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/users/login",
        json={"username": "alice", "password": "secret123"},
    )
    token = response.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


def test_todo_routes_require_login(db_session) -> None:
    client = make_client(db_session)

    response = client.get("/todos")

    assert response.status_code == 401
    assert response.json()["message"] == "Authentication required"


def test_todo_crud_routes_return_unified_camel_case_response(db_session) -> None:
    create_user(db_session, UserCreate(username="alice", password="secret123"))
    client = make_client(db_session)
    headers = login_headers(client)

    create_response = client.post(
        "/todos",
        json={"title": "Buy milk", "description": "Two bottles"},
        headers=headers,
    )
    todo_id = create_response.json()["data"]["id"]

    list_response = client.get(
        "/todos",
        params={"pageNum": 1, "pageSize": 20},
        headers=headers,
    )
    detail_response = client.get(f"/todos/{todo_id}", headers=headers)
    update_response = client.patch(
        f"/todos/{todo_id}",
        json={"isCompleted": True},
        headers=headers,
    )
    delete_response = client.delete(f"/todos/{todo_id}", headers=headers)

    assert create_response.status_code == 201
    assert "message" not in create_response.json()
    assert "total" not in create_response.json()
    assert create_response.json()["data"]["isCompleted"] is False
    assert "createdAt" in create_response.json()["data"]
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1
    assert list_response.json()["data"][0]["title"] == "Buy milk"
    assert detail_response.status_code == 200
    assert detail_response.json()["data"]["id"] == todo_id
    assert update_response.status_code == 200
    assert update_response.json()["data"]["isCompleted"] is True
    assert delete_response.status_code == 200
    assert delete_response.json()["data"] == {"id": todo_id, "deleted": True}
