"""Health check agent — owns Qdrant probing, uptime, and status logic."""

import time
from collections.abc import Callable

from agent_service.core.config import settings
from agent_service.core.logging import get_logger
from agent_service.memory.qdrant_store import build_qdrant_store

STARTED_AT = time.monotonic()
logger = get_logger(__name__)


def build_health_data(
    qdrant_probe: Callable[[], bool] | None = None,
    monotonic_now: Callable[[], float] = time.monotonic,
    started_at: float = STARTED_AT,
) -> dict:
    probe = qdrant_probe or _probe_qdrant
    qdrant_connected = False
    try:
        qdrant_connected = bool(probe())
    except Exception as exc:
        logger.warning("Health probe failed: %s", exc)
        qdrant_connected = False

    model_loaded = settings.LLM_PROVIDER != "none" and bool(settings.LLM_MODEL)

    return {
        "status": "healthy" if qdrant_connected else "degraded",
        "qdrant_connected": qdrant_connected,
        "model_loaded": model_loaded,
        "model_name": settings.LLM_MODEL if model_loaded else "",
        "uptime_seconds": max(0, int(monotonic_now() - started_at)),
    }


def _probe_qdrant() -> bool:
    store = build_qdrant_store(settings.QDRANT_USER_MEMORY_COLLECTION)
    store.get_client()
    return True
