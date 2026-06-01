from __future__ import annotations

from datetime import UTC, datetime

from pydantic import Field, field_serializer

from app.api.schemas import ApiSchema


class TodoBase(ApiSchema):
    title: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class TodoCreate(TodoBase):
    pass


class TodoUpdate(ApiSchema):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    is_completed: bool | None = None


class TodoPublic(TodoBase):
    id: int
    is_completed: bool
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at", when_used="json")
    def serialize_datetime(self, value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


class DeletedTodoPayload(ApiSchema):
    id: int
    deleted: bool = True
