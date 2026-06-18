from __future__ import annotations

from fastapi import APIRouter, Request, status

from app.api.deps import CurrentUser, SessionDep, get_client_ip
from app.api.schemas import ApiResponse
from app.api.v1.auth import service
from app.api.v1.auth.schemas import (
    AuthLogin,
    AuthLogoutRes,
    AuthRefresh,
    AuthRegister,
    AuthRes,
)
from app.api.v1.users.schemas import UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=ApiResponse[AuthRes],
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
def register(request: Request, session: SessionDep, payload: AuthRegister) -> dict:
    auth_result = service.register(
        session,
        payload,
        ip_address=get_client_ip(request),
    )
    return ApiResponse.success(
        data=_to_auth_res(auth_result),
        code=status.HTTP_201_CREATED,
    )


@router.post(
    "/login",
    response_model=ApiResponse[AuthRes],
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
)
def login(request: Request, session: SessionDep, payload: AuthLogin) -> dict:
    auth_result = service.login(
        session,
        username=payload.username,
        password=payload.password,
        ip_address=get_client_ip(request),
    )
    return ApiResponse.success(data=_to_auth_res(auth_result))


@router.post(
    "/refresh",
    response_model=ApiResponse[AuthRes],
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
)
def refresh(request: Request, session: SessionDep, payload: AuthRefresh) -> dict:
    auth_result = service.refresh(
        session,
        payload.refresh_token,
        ip_address=get_client_ip(request),
    )
    return ApiResponse.success(data=_to_auth_res(auth_result))


@router.post(
    "/logout",
    response_model=ApiResponse[AuthLogoutRes],
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
)
def logout(session: SessionDep, current_user: CurrentUser) -> dict:
    service.logout(session, user=current_user)
    return ApiResponse.success(data=AuthLogoutRes(revoked=True))


def _to_auth_res(auth_result: service.AuthResult) -> AuthRes:
    return AuthRes(
        token=auth_result.access_token,
        refresh_token=auth_result.refresh_token,
        user=UserPublic.model_validate(auth_result.user),
    )
