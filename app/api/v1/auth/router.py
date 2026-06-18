from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import SessionDep
from app.api.schemas import ApiResponse
from app.api.v1.auth import service
from app.api.v1.auth.schemas import AuthLogin, AuthPayload, AuthRegister
from app.api.v1.users.schemas import UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=ApiResponse[AuthPayload],
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    session: SessionDep,
    payload: AuthRegister,
) -> dict:
    auth_result = service.register_user(session, payload)
    return ApiResponse.success(
        data=auth_payload(auth_result),
        code=status.HTTP_201_CREATED,
    )


@router.post(
    "/login", response_model=ApiResponse[AuthPayload], response_model_exclude_none=True
)
def login(
    session: SessionDep,
    payload: AuthLogin,
) -> dict:
    auth_result = service.authenticate_user(
        session,
        username=payload.username,
        password=payload.password,
    )
    return ApiResponse.success(
        data=auth_payload(auth_result),
    )


def auth_payload(auth_result: service.AuthResult) -> dict:
    return AuthPayload(
        token=auth_result.access_token,
        user=UserPublic.model_validate(auth_result.user),
    ).model_dump(mode="json", by_alias=True)
