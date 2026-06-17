from fastapi import APIRouter, Request

from app.api.schemas import ApiResponse, ApiSchema
from app.core.config import settings
from app.core.logger import get_logger

router = APIRouter(prefix="/health", tags=["health"])

logger = get_logger()


class HealthPayload(ApiSchema):
    status: str
    environment: str


class UploadDemoPayload(ApiSchema):
    file_size: int
    chunks: int
    content_type: str | None = None


@router.get(
    "",
    response_model=ApiResponse[HealthPayload],
    response_model_exclude_none=True,
)
def health_check() -> dict:
    payload = HealthPayload(status="ok", environment=settings.APP_ENV)
    raise ValueError("boom")
    return ApiResponse.success(
        data=payload.model_dump(by_alias=True),
    )


@router.post(
    "/upload-demo",
    response_model=ApiResponse[UploadDemoPayload],
    response_model_exclude_none=True,
)
async def upload_demo(request: Request) -> dict:
    file_size = 0
    chunks = 0
    async for chunk in request.stream():
        if not chunk:
            continue
        file_size += len(chunk)
        chunks += 1

    payload = UploadDemoPayload(file_size=file_size, chunks=chunks)
    return ApiResponse.success(data=payload.model_dump(by_alias=True))


@router.post(
    "/upload-multipart-demo",
    response_model=ApiResponse[UploadDemoPayload],
    response_model_exclude_none=True,
)
async def upload_multipart_demo(request: Request) -> dict:
    file_size = 0
    chunks = 0
    async for chunk in request.stream():
        if not chunk:
            continue
        file_size += len(chunk)
        chunks += 1

    payload = UploadDemoPayload(
        file_size=file_size,
        chunks=chunks,
        content_type=request.headers.get("content-type"),
    )
    return ApiResponse.success(data=payload.model_dump(by_alias=True))
