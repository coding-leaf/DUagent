import importlib
import asyncio
import sys
import warnings
from types import SimpleNamespace

from pydantic.warnings import PydanticDeprecatedSince20


def test_settings_import_has_no_pydantic_v2_config_warning() -> None:
    sys.modules.pop("agent_service.core.config", None)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        importlib.import_module("agent_service.core.config")

    pydantic_config_warnings = [
        warning for warning in caught if issubclass(warning.category, PydanticDeprecatedSince20)
    ]
    assert pydantic_config_warnings == []


def test_settings_exposes_ai_provider_defaults() -> None:
    from agent_service.core.config import Settings

    settings = Settings(_env_file=None)

    assert settings.AGENTSCOPE_STUDIO_URL is None
    assert settings.QDRANT_PATH == "./qdrant_data"
    assert settings.QDRANT_USER_MEMORY_COLLECTION == "user_memory_v1_1024"
    assert settings.QDRANT_COURSE_KNOWLEDGE_COLLECTION == "course_knowledge_v1_1024"
    assert settings.AI_PROVIDER == "none"
    assert settings.EMBEDDING_PROVIDER == "none"
    assert settings.EMBEDDING_MODEL is None
    assert settings.EMBEDDING_BASE_URL is None
    assert settings.EMBEDDING_API_KEY is None
    assert settings.EMBEDDING_DIMENSION == 1024
    assert settings.RERANKER_PROVIDER == "none"
    assert settings.RERANKER_MODEL is None
    assert settings.RERANKER_BASE_URL is None
    assert settings.RERANKER_API_KEY is None
    assert settings.LLM_PROVIDER == "none"
    assert settings.LLM_MODEL is None
    assert settings.LLM_BASE_URL is None
    assert settings.LLM_API_KEY is None
    assert settings.LLM_STRUCTURED_OUTPUT_ENABLED is False
    assert settings.LLM_JSON_MODE_ENABLED is None


def test_settings_default_env_file_is_service_local() -> None:
    from pathlib import Path

    from agent_service.core.config import _SERVICE_ENV_FILE

    assert _SERVICE_ENV_FILE == Path(__file__).resolve().parents[1] / ".env"


def test_init_agentscope_studio_skips_when_url_missing(monkeypatch) -> None:
    from agent_service import main as main_module

    monkeypatch.setattr(main_module.settings, "AGENTSCOPE_STUDIO_URL", None)

    calls: list[dict] = []

    class FakeAgentScope:
        @staticmethod
        def init(**kwargs):
            calls.append(kwargs)

    monkeypatch.setitem(sys.modules, "agentscope", FakeAgentScope())

    main_module._init_agentscope_studio_if_configured()

    assert calls == []


def test_init_agentscope_studio_uses_configured_url(monkeypatch) -> None:
    from agent_service import main as main_module

    monkeypatch.setattr(main_module.settings, "AGENTSCOPE_STUDIO_URL", "http://localhost:8090")
    monkeypatch.setattr(main_module.settings, "PROJECT_NAME", "EduAgent Agent Service API")

    calls: list[dict] = []

    class FakeAgentScope:
        @staticmethod
        def init(**kwargs):
            calls.append(kwargs)

    monkeypatch.setitem(sys.modules, "agentscope", FakeAgentScope())

    main_module._init_agentscope_studio_if_configured()

    assert calls == [
        {
            "project": "EduAgent Agent Service API",
            "name": "agent_service",
            "studio_url": "http://localhost:8090",
        }
    ]


def test_lifespan_initializes_studio_before_qdrant_store(monkeypatch) -> None:
    from agent_service import main as main_module

    events: list[tuple[str, str]] = []

    monkeypatch.setattr(
        main_module,
        "_init_agentscope_studio_if_configured",
        lambda: events.append(("studio", "init")),
    )
    monkeypatch.setattr(
        main_module,
        "build_qdrant_store",
        lambda collection: events.append(("qdrant", collection)),
    )
    monkeypatch.setattr(
        main_module.settings,
        "QDRANT_COURSE_KNOWLEDGE_COLLECTION",
        "course_collection",
    )
    monkeypatch.setattr(
        main_module.settings,
        "QDRANT_USER_MEMORY_COLLECTION",
        "user_collection",
    )

    async def run() -> None:
        async with main_module.lifespan(SimpleNamespace()):
            pass

    asyncio.run(run())

    assert events == [
        ("studio", "init"),
        ("qdrant", "course_collection"),
        ("qdrant", "user_collection"),
    ]
