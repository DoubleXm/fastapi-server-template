from __future__ import annotations

from pydantic import Field

from app.api.schemas import ApiSchema
from app.api.v1.users.schemas import UserPublic


class AuthRegister(ApiSchema):
    username: str = Field(
        ..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$"
    )
    password: str = Field(..., min_length=6, max_length=128)


class AuthLogin(ApiSchema):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)


class AuthPayload(ApiSchema):
    token: str
    user: UserPublic
