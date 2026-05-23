import importlib
import sys
import warnings

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

    settings = Settings()

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
