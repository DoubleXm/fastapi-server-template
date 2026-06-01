from __future__ import annotations

from typing import Any, Generic, TypeVar

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from app.shared.utils import to_camel_case

T = TypeVar("T")


class ApiSchema(BaseModel):
    """API schema 基类：response 字段统一输出为小驼峰。"""

    model_config = ConfigDict(
        alias_generator=to_camel_case,
        populate_by_name=True,
        from_attributes=True,
    )


class ApiResponse(ApiSchema, Generic[T]):
    """API 通用 response envelope。"""

    code: int = 200
    message: str | None = None
    data: T | None = None
    total: int | None = None

    @classmethod
    def success(
        cls,
        *,
        data: Any = None,
        message: str | None = None,
        code: int = 200,
        total: int | None = None,
    ) -> dict[str, Any]:
        payload = cls[Any](
            code=code,
            data=data,
            total=total,
        )
        return jsonable_encoder(payload, by_alias=True, exclude_none=True)

    @classmethod
    def fail(
        cls,
        *,
        message: str,
        status_code: int,
        code: int | None = None,
        data: Any = None,
    ) -> JSONResponse:
        payload = cls[Any](
            code=code or status_code,
            message=message,
            data=data,
        )
        return JSONResponse(
            status_code=status_code,
            content=jsonable_encoder(payload, by_alias=True, exclude_none=True),
        )
