from collections.abc import Callable
from typing import Any

from agent_service.core.ai import ChatMessage
from agent_service.core.config import settings
from agent_service.memory.qdrant_store import build_qdrant_store


def _configured(settings_obj, provider_name: str, fields: list[str]) -> bool:
    provider = getattr(settings_obj, provider_name, "none")
    if provider == "none":
        return False
    return all(bool(getattr(settings_obj, field, None)) for field in fields)


def _check_template(configured: bool) -> dict[str, Any]:
    return {
        "configured": configured,
        "provider_built": False,
        "live_checked": False,
        "ok": True,
        "error": None,
    }


async def build_readiness_report(
    *,
    settings_obj=settings,
    live: bool = False,
    chat_provider=None,
    embedding_provider=None,
    reranker_provider=None,
    qdrant_probe: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    checks = {
        "llm": await _check_llm(settings_obj, chat_provider, live),
        "embedding": await _check_embedding(settings_obj, embedding_provider, live),
        "reranker": await _check_reranker(settings_obj, reranker_provider, live),
        "qdrant": _check_qdrant(settings_obj, qdrant_probe),
    }
    status = "ready" if all(item["ok"] for item in checks.values()) else "degraded"
    return {"status": status, "live": live, "checks": checks}


async def _check_llm(settings_obj, provider, live: bool) -> dict[str, Any]:
    check = _check_template(_configured(settings_obj, "LLM_PROVIDER", ["LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"]))
    check["provider_built"] = provider is not None
    if check["configured"] and provider is None:
        check["ok"] = False
        check["error"] = "LLM is configured but provider could not be built"
        return check
    if live and provider is not None:
        check["live_checked"] = True
        try:
            await provider.complete([ChatMessage(role="user", content="ping")])
        except Exception as exc:
            check["ok"] = False
            check["error"] = str(exc)
    return check


async def _check_embedding(settings_obj, provider, live: bool) -> dict[str, Any]:
    check = _check_template(_configured(settings_obj, "EMBEDDING_PROVIDER", ["EMBEDDING_BASE_URL", "EMBEDDING_API_KEY", "EMBEDDING_MODEL"]))
    check["provider_built"] = provider is not None
    if check["configured"] and provider is None:
        check["ok"] = False
        check["error"] = "Embedding is configured but provider could not be built"
        return check
    if live and provider is not None:
        check["live_checked"] = True
        try:
            await provider.embed_texts(["ping"])
        except Exception as exc:
            check["ok"] = False
            check["error"] = str(exc)
    return check


async def _check_reranker(settings_obj, provider, live: bool) -> dict[str, Any]:
    check = _check_template(_configured(settings_obj, "RERANKER_PROVIDER", ["RERANKER_BASE_URL", "RERANKER_API_KEY", "RERANKER_MODEL"]))
    check["provider_built"] = provider is not None
    if check["configured"] and provider is None:
        check["ok"] = False
        check["error"] = "Reranker is configured but provider could not be built"
        return check
    if live and provider is not None:
        check["live_checked"] = True
        try:
            await provider.score("ping", ["ping document"])
        except Exception as exc:
            check["ok"] = False
            check["error"] = str(exc)
    return check


def _check_qdrant(settings_obj, qdrant_probe: Callable[[], bool] | None) -> dict[str, Any]:
    check = {
        "configured": True,
        "provider_built": True,
        "live_checked": True,
        "ok": True,
        "error": None,
        "collection": getattr(settings_obj, "QDRANT_USER_MEMORY_COLLECTION", None),
    }
    try:
        probe = qdrant_probe or _probe_qdrant
        check["ok"] = bool(probe())
    except Exception as exc:
        check["ok"] = False
        check["error"] = str(exc)
    return check


def _probe_qdrant() -> bool:
    from qdrant_client import QdrantClient

    if settings.QDRANT_URL:
        client_kwargs = {"url": settings.QDRANT_URL}
        if settings.QDRANT_API_KEY:
            client_kwargs["api_key"] = settings.QDRANT_API_KEY
        client = QdrantClient(**client_kwargs)
    else:
        client = QdrantClient(path=settings.QDRANT_PATH)
    client.get_collections()
    return True
