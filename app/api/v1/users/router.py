from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUser, PaginationDep, SessionDep, get_current_user
from app.api.schemas import ApiResponse
from app.api.v1.users import service
from app.api.v1.users.schemas import (
    DeletedUserRes,
    UserCreate,
    UserPublic,
    UserUpdate,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.post(
    "",
    dependencies=[Depends(get_current_user)],
    response_model=ApiResponse[UserPublic],
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
def create_user(session: SessionDep, payload: UserCreate) -> dict:
    user = service.create_user(session, payload)
    return ApiResponse.success(
        data=UserPublic.model_validate(user),
        code=status.HTTP_201_CREATED,
    )


@router.get(
    "/me",
    response_model=ApiResponse[UserPublic],
    response_model_exclude_none=True,
)
def read_current_user(current_user: CurrentUser) -> dict:
    return ApiResponse.success(data=UserPublic.model_validate(current_user))


@router.get(
    "",
    dependencies=[Depends(get_current_user)],
    response_model=ApiResponse[list[UserPublic]],
    response_model_exclude_none=True,
)
def list_users(session: SessionDep, pagination: PaginationDep) -> dict:
    users, total = service.list_users(
        session,
        offset=pagination.offset,
        limit=pagination.limit,
    )
    return ApiResponse.success(
        data=[UserPublic.model_validate(user) for user in users],
        total=total,
    )


@router.get(
    "/{userId}",
    dependencies=[Depends(get_current_user)],
    response_model=ApiResponse[UserPublic],
    response_model_exclude_none=True,
)
def get_user(session: SessionDep, userId: int) -> dict:
    user_id = userId
    user = service.get_user(session, user_id)
    return ApiResponse.success(
        data=UserPublic.model_validate(user),
    )


@router.patch(
    "/{userId}",
    dependencies=[Depends(get_current_user)],
    response_model=ApiResponse[UserPublic],
    response_model_exclude_none=True,
)
def update_user(session: SessionDep, userId: int, payload: UserUpdate) -> dict:
    user_id = userId
    updated_user = service.update_user(session, user_id=user_id, payload=payload)
    return ApiResponse.success(
        data=UserPublic.model_validate(updated_user),
    )


@router.delete(
    "/{userId}",
    dependencies=[Depends(get_current_user)],
    response_model=ApiResponse[DeletedUserRes],
    response_model_exclude_none=True,
)
def delete_user(session: SessionDep, userId: int) -> dict:
    user_id = userId
    service.delete_user(session, user_id=user_id)
    return ApiResponse.success(
        data=DeletedUserRes(id=user_id),
    )
