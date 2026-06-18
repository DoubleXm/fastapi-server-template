from __future__ import annotations

from datetime import UTC, datetime

from pydantic import Field, field_serializer

from app.api.schemas import ApiSchema


class UserBase(ApiSchema):
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_.-]+$",
    )


class UserCreate(UserBase):
    password: str = Field(
        ...,
        min_length=6,
        max_length=128,
    )


class UserUpdate(ApiSchema):
    username: str | None = Field(
        default=None,
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_.-]+$",
    )
    password: str | None = Field(default=None, min_length=6, max_length=128)


class UserPublic(ApiSchema):
    id: int
    username: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at", when_used="json")
    def serialize_datetime(self, value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


class DeletedUserPayload(ApiSchema):
    id: int
    deleted: bool = True
