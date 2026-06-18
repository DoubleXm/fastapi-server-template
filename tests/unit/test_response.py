from __future__ import annotations

import anyio
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.testclient import TestClient
from starlette.requests import Request

import app.core.exception_handlers as exception_handlers
from app.api.deps import PaginationParams
from app.api.schemas import ApiResponse, ApiSchema
from app.api.v1.users.schemas import UserPublic
from app.core.exception_handlers import register_exception_handlers


class CamelCasePayload(ApiSchema):
    created_at: str
    is_active: bool
    display_name: str


def test_success_response_contains_data() -> None:
    payload = ApiResponse.success(data={"id": 1}, code=201)

    assert payload == {
        "code": 201,
        "data": {"id": 1},
    }


def test_api_schema_outputs_camel_case_and_keeps_python_fields() -> None:
    payload = CamelCasePayload.model_validate(
        {
            "createdAt": "2026-05-29T00:00:00Z",
            "isActive": True,
            "displayName": "Alice",
        }
    )

    assert payload.created_at == "2026-05-29T00:00:00Z"
    assert payload.model_dump(mode="json", by_alias=True) == {
        "createdAt": "2026-05-29T00:00:00Z",
        "isActive": True,
        "displayName": "Alice",
    }


def test_api_response_serializes_nested_schema_with_camel_case() -> None:
    payload = CamelCasePayload(
        created_at="2026-05-29T00:00:00Z",
        is_active=True,
        display_name="Alice",
    )

    response = ApiResponse.success(data=payload)

    assert response == {
        "code": 200,
        "data": {
            "createdAt": "2026-05-29T00:00:00Z",
            "isActive": True,
            "displayName": "Alice",
        },
    }


def test_nested_route_response_uses_camel_case_fields() -> None:
    app = FastAPI()

    @app.get("/users/me", response_model=ApiResponse[UserPublic])
    def current_user() -> dict:
        user = UserPublic.model_validate(
            {
                "id": 1,
                "username": "alice",
                "is_active": True,
                "created_at": "2026-05-29T00:00:00Z",
                "updated_at": "2026-05-29T00:00:00Z",
            }
        )
        return ApiResponse.success(
            data=user.model_dump(mode="json", by_alias=True),
        )

    client = TestClient(app)

    response = client.get("/users/me")

    assert response.status_code == 200
    assert response.json()["data"] == {
        "id": 1,
        "username": "alice",
        "isActive": True,
        "createdAt": "2026-05-29T00:00:00Z",
        "updatedAt": "2026-05-29T00:00:00Z",
    }


def test_success_list_response_contains_data_and_total() -> None:
    payload = ApiResponse.success(data=[{"id": 1}], total=1)

    assert payload == {
        "code": 200,
        "data": [{"id": 1}],
        "total": 1,
    }


def test_success_detail_response_omits_total() -> None:
    payload = ApiResponse.success(data={"id": 1})

    assert "total" not in payload


def test_fail_response_contains_code_message_and_error_data() -> None:
    response = ApiResponse.fail(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        message="Request validation failed",
        data={"errors": [{"msg": "too short"}]},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.body == (
        b'{"code":422,"message":"Request validation failed",'
        b'"data":{"errors":[{"msg":"too short"}]}}'
    )


def test_exception_handlers_use_unified_response_shape() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/http-error")
    def http_error() -> None:
        raise HTTPException(status_code=409, detail="Username already exists")

    @app.get("/validation-error")
    def validation_error(age: int = Query(..., ge=18)) -> dict[str, int]:
        return {"age": age}

    client = TestClient(app)

    http_response = client.get("/http-error")
    validation_response = client.get("/validation-error", params={"age": 17})

    assert http_response.status_code == 409
    assert http_response.json() == {
        "code": 409,
        "message": "Username already exists",
        "data": {"detail": "Username already exists"},
    }
    assert validation_response.status_code == 422
    assert validation_response.json()["code"] == 422
    assert validation_response.json()["message"] == "Request validation failed"
    assert "errors" in validation_response.json()["data"]


def test_global_exception_handler_logs_traceback_context(monkeypatch) -> None:
    records: list[str] = []

    class CapturingLogger:
        def exception(self, message, *args) -> None:
            records.append(message.format(*args))

    monkeypatch.setattr(exception_handlers, "logger", CapturingLogger())

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/error",
            "headers": [],
        }
    )
    response = anyio.run(
        exception_handlers.global_exception_handler,
        request,
        RuntimeError("boom"),
    )

    assert response.status_code == 500
    assert b'"message":"Internal server error"' in response.body
    assert records == [
        "Unhandled exception method=GET path=/error error=boom",
    ]


def test_pagination_params_use_page_num_and_page_size() -> None:
    params = PaginationParams(page_num=3, page_size=15)

    assert params.page_num == 3
    assert params.page_size == 15
    assert params.offset == 30
    assert params.limit == 15


def test_pagination_dependency_exposes_camel_case_query_params() -> None:
    app = FastAPI()

    @app.get("/items")
    def list_items(
        pagination: PaginationParams = Depends(PaginationParams),
    ) -> dict[str, int]:
        return {
            "offset": pagination.offset,
            "limit": pagination.limit,
        }

    client = TestClient(app)

    response = client.get("/items", params={"pageNum": 2, "pageSize": 30})

    assert response.status_code == 200
    assert response.json() == {"offset": 30, "limit": 30}
