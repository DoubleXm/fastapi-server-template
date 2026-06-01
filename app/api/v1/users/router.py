from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUser, PaginationDep, SessionDep, get_current_user
from app.api.schemas import ApiResponse
from app.api.v1.users import service
from app.api.v1.users.schemas import (
    AuthPayload,
    DeletedUserPayload,
    UserCreate,
    UserLogin,
    UserPublic,
    UserRegister,
    UserUpdate,
)
from app.core.config import settings
from app.core.logging import configure_app_logger

auth_logger = configure_app_logger(
    "app.auth",
    log_dir=settings.logs_dir_path,
    level=logging.getLevelName(settings.LOG_LEVEL),
    max_bytes=settings.LOG_MAX_BYTES,
    backup_count=settings.LOG_BACKUP_COUNT,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.post(
    "",
    response_model=ApiResponse[UserPublic],
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    session: SessionDep,
    payload: UserCreate,
) -> dict:
    user = service.create_user(session, payload)
    return ApiResponse.success(
        data=UserPublic.model_validate(user).model_dump(
            mode="json",
            by_alias=True,
        ),
        code=status.HTTP_201_CREATED,
    )


@router.post(
    "/register",
    response_model=ApiResponse[AuthPayload],
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    session: SessionDep,
    payload: UserRegister,
) -> dict:
    user = service.create_user(session, UserCreate(**payload.model_dump()))
    auth_result = service.create_auth_result(user)
    return ApiResponse.success(
        data=auth_payload(auth_result),
        code=status.HTTP_201_CREATED,
    )


@router.post(
    "/login",
    response_model=ApiResponse[AuthPayload],
    response_model_exclude_none=True,
)
def login(
    session: SessionDep,
    payload: UserLogin,
) -> dict:
    auth_result = service.authenticate_user(
        session,
        username=payload.username,
        password=payload.password,
    )
    return ApiResponse.success(
        data=auth_payload(auth_result),
    )


@router.get(
    "/me",
    response_model=ApiResponse[UserPublic],
    response_model_exclude_none=True,
)
def read_current_user(current_user: CurrentUser) -> dict:
    return ApiResponse.success(
        data=UserPublic.model_validate(current_user).model_dump(
            mode="json",
            by_alias=True,
        ),
    )


@router.get(
    "",
    dependencies=[Depends(get_current_user)],
    response_model=ApiResponse[list[UserPublic]],
    response_model_exclude_none=True,
)
def read_users(
    session: SessionDep,
    pagination: PaginationDep,
) -> dict:
    users, total = service.list_users(
        session,
        offset=pagination.offset,
        limit=pagination.limit,
    )
    return ApiResponse.success(
        data=[
            UserPublic.model_validate(user).model_dump(
                mode="json",
                by_alias=True,
            )
            for user in users
        ],
        total=total,
    )


@router.get(
    "/{userId}",
    dependencies=[Depends(get_current_user)],
    response_model=ApiResponse[UserPublic],
    response_model_exclude_none=True,
)
def read_user_by_id(
    session: SessionDep,
    userId: int,
) -> dict:
    user_id = userId
    user = service.get_user_or_404(session, user_id)
    return ApiResponse.success(
        data=UserPublic.model_validate(user).model_dump(
            mode="json",
            by_alias=True,
        ),
    )


@router.patch(
    "/{userId}",
    dependencies=[Depends(get_current_user)],
    response_model=ApiResponse[UserPublic],
    response_model_exclude_none=True,
)
def update_user(
    session: SessionDep,
    userId: int,
    payload: UserUpdate,
) -> dict:
    user_id = userId
    user = service.get_user_or_404(session, user_id)
    updated_user = service.update_user(session, user=user, payload=payload)
    return ApiResponse.success(
        data=UserPublic.model_validate(updated_user).model_dump(
            mode="json",
            by_alias=True,
        ),
    )


@router.delete(
    "/{userId}",
    dependencies=[Depends(get_current_user)],
    response_model=ApiResponse[DeletedUserPayload],
    response_model_exclude_none=True,
)
def delete_user(
    session: SessionDep,
    userId: int,
) -> dict:
    user_id = userId
    user = service.get_user_or_404(session, user_id)
    service.delete_user(session, user=user)
    return ApiResponse.success(
        data=DeletedUserPayload(id=user_id).model_dump(
            mode="json",
            by_alias=True,
        ),
    )


def auth_payload(auth_result: service.AuthResult) -> dict:
    return AuthPayload(
        token=auth_result.access_token,
        user=UserPublic.model_validate(auth_result.user),
    ).model_dump(mode="json", by_alias=True)
