from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.deps import PaginationDep, SessionDep, get_current_user
from app.api.schemas import ApiResponse
from app.api.v1.todos import service
from app.api.v1.todos.schemas import (
    DeletedTodoPayload,
    TodoCreate,
    TodoPublic,
    TodoUpdate,
)

router = APIRouter(
    prefix="/todos",
    tags=["todos"],
    dependencies=[Depends(get_current_user)],
)


@router.post(
    "",
    response_model=ApiResponse[TodoPublic],
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
def create_todo(
    session: SessionDep,
    payload: TodoCreate,
) -> dict:
    todo = service.create_todo(session, payload)
    return ApiResponse.success(
        data=TodoPublic.model_validate(todo).model_dump(
            mode="json",
            by_alias=True,
        ),
        code=status.HTTP_201_CREATED,
    )


@router.get(
    "",
    response_model=ApiResponse[list[TodoPublic]],
    response_model_exclude_none=True,
)
def read_todos(
    session: SessionDep,
    pagination: PaginationDep,
) -> dict:
    todos, total = service.list_todos(
        session,
        offset=pagination.offset,
        limit=pagination.limit,
    )
    return ApiResponse.success(
        data=[
            TodoPublic.model_validate(todo).model_dump(
                mode="json",
                by_alias=True,
            )
            for todo in todos
        ],
        total=total,
    )


@router.get(
    "/{todoId}",
    response_model=ApiResponse[TodoPublic],
    response_model_exclude_none=True,
)
def read_todo_by_id(
    session: SessionDep,
    todoId: int,
) -> dict:
    todo_id = todoId
    todo = service.get_todo_or_404(session, todo_id)
    return ApiResponse.success(
        data=TodoPublic.model_validate(todo).model_dump(
            mode="json",
            by_alias=True,
        ),
    )


@router.patch(
    "/{todoId}",
    response_model=ApiResponse[TodoPublic],
    response_model_exclude_none=True,
)
def update_todo(
    session: SessionDep,
    todoId: int,
    payload: TodoUpdate,
) -> dict:
    todo_id = todoId
    todo = service.get_todo_or_404(session, todo_id)
    updated_todo = service.update_todo(session, todo=todo, payload=payload)
    return ApiResponse.success(
        data=TodoPublic.model_validate(updated_todo).model_dump(
            mode="json",
            by_alias=True,
        ),
    )


@router.delete(
    "/{todoId}",
    response_model=ApiResponse[DeletedTodoPayload],
    response_model_exclude_none=True,
)
def delete_todo(
    session: SessionDep,
    todoId: int,
) -> dict:
    todo_id = todoId
    todo = service.get_todo_or_404(session, todo_id)
    service.delete_todo(session, todo=todo)
    return ApiResponse.success(
        data=DeletedTodoPayload(id=todo_id).model_dump(
            mode="json",
            by_alias=True,
        ),
    )
