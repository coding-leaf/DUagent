import time
from collections.abc import Callable

from fastapi import APIRouter

from agent_service.core.logging import get_logger
from agent_service.core.qdrant import get_qdrant_client
from agent_service.schemas.common import HealthResponse


router = APIRouter()
STARTED_AT = time.monotonic()
logger = get_logger(__name__)


def build_health_data(
    qdrant_probe: Callable[[], bool] | None = None,
    monotonic_now: Callable[[], float] = time.monotonic,
    started_at: float = STARTED_AT,
) -> dict:
    """构建基础健康检查数据，输入探针函数，输出统一响应中的 data 字段。"""
    probe = qdrant_probe or _probe_qdrant
    qdrant_connected = False
    try:
        qdrant_connected = bool(probe())
    except Exception as exc:
        logger.warning("Health probe failed: %s", exc)
        qdrant_connected = False

    return {
        "status": "healthy" if qdrant_connected else "degraded",
        "qdrant_connected": qdrant_connected,
        "model_loaded": False,
        "model_name": "none",
        "uptime_seconds": max(0, int(monotonic_now() - started_at)),
    }


def _probe_qdrant() -> bool:
    client = get_qdrant_client()
    client.get_collections()
    return True


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint for the Agent Service.
    """
    return HealthResponse(
        code=200,
        message="success",
        data=build_health_data(),
    )
