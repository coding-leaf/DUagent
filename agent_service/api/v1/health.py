from fastapi import APIRouter

from agent_service.agents.health import build_health_data
from agent_service.schemas.common import HealthResponse


router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(
        code=200,
        message="success",
        data=build_health_data(),
    )
