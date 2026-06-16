from fastapi import APIRouter

from app.api.schemas import ApiResponse, ApiSchema
from app.core.config import settings
from app.core.logger import get_logger

router = APIRouter(prefix="/health", tags=["health"])

logger = get_logger()


class HealthPayload(ApiSchema):
    status: str
    environment: str


@router.get(
    "",
    response_model=ApiResponse[HealthPayload],
    response_model_exclude_none=True,
)
def health_check() -> dict:
    payload = HealthPayload(status="ok", environment=settings.APP_ENV)
    # raise ValueError()
    return ApiResponse.success(
        data=payload.model_dump(by_alias=True),
    )
