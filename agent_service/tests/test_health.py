import asyncio

from agent_service.api.v1.health import build_health_data, health_check


def test_build_health_data_reports_qdrant_and_uptime(monkeypatch) -> None:
    class FakeSettings:
        LLM_PROVIDER = "agentscope_openai"
        LLM_BASE_URL = "https://llm.example.com/v1"
        LLM_API_KEY = "sk-test"
        LLM_MODEL = "test-model"
        EMBEDDING_PROVIDER = "agentscope_openai"
        EMBEDDING_BASE_URL = "https://emb.example.com/v1"
        EMBEDDING_API_KEY = "sk-test"
        EMBEDDING_MODEL = "test-emb"
        RERANKER_PROVIDER = "none"
        RERANKER_BASE_URL = None
        RERANKER_API_KEY = None
        RERANKER_MODEL = None
        QDRANT_USER_MEMORY_COLLECTION = "user_memory_v1_1024"

    monkeypatch.setattr("agent_service.api.v1.health.settings", FakeSettings())

    data = build_health_data(qdrant_probe=lambda: True, monotonic_now=lambda: 125.5, started_at=100.0)

    assert data["status"] == "healthy"
    assert data["qdrant_connected"] is True
    assert data["model_loaded"] is True
    assert data["model_name"] == "test-model"
    assert data["uptime_seconds"] == 25
    assert data["llm_configured"] is True
    assert data["embedding_configured"] is True
    assert data["reranker_configured"] is False
    assert data["qdrant_collection"] == "user_memory_v1_1024"


def test_build_health_data_marks_degraded_when_qdrant_probe_fails() -> None:
    def failing_probe() -> bool:
        raise RuntimeError("qdrant unavailable")

    data = build_health_data(qdrant_probe=failing_probe, monotonic_now=lambda: 101.0, started_at=100.0)

    assert data["status"] == "degraded"
    assert data["qdrant_connected"] is False
    assert data["uptime_seconds"] == 1


def test_build_health_data_logs_probe_failure(caplog) -> None:
    def failing_probe() -> bool:
        raise RuntimeError("qdrant unavailable")

    with caplog.at_level("WARNING", logger="agent_service.api.v1.health"):
        build_health_data(qdrant_probe=failing_probe, monotonic_now=lambda: 101.0, started_at=100.0)

    assert "Health probe failed" in caplog.text
    assert "qdrant unavailable" in caplog.text


def test_health_check_uses_json_wrapper() -> None:
    response = asyncio.run(health_check())
    payload = response.model_dump()

    assert set(payload) == {"code", "message", "data"}
    assert payload["code"] == 200
    assert payload["message"] == "success"
