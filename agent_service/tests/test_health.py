import asyncio

from agent_service.agents.health import build_health_data
from agent_service.api.v1.health import health_check


def test_build_health_data_reports_qdrant_and_uptime(monkeypatch) -> None:
    class FakeSettings:
        LLM_PROVIDER = "agentscope_openai"
        LLM_MODEL = "test-model"

    monkeypatch.setattr("agent_service.agents.health.settings", FakeSettings())

    data = build_health_data(qdrant_probe=lambda: True, monotonic_now=lambda: 125.5, started_at=100.0)

    assert data["status"] == "healthy"
    assert data["qdrant_connected"] is True
    assert data["model_loaded"] is True
    assert data["model_name"] == "test-model"
    assert data["uptime_seconds"] == 25


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

    with caplog.at_level("WARNING", logger="agent_service.agents.health"):
        build_health_data(qdrant_probe=failing_probe, monotonic_now=lambda: 101.0, started_at=100.0)

    assert "Health probe failed" in caplog.text
    assert "qdrant unavailable" in caplog.text


def test_build_health_data_returns_empty_model_name_when_unconfigured(monkeypatch) -> None:
    class FakeSettings:
        LLM_PROVIDER = "none"
        LLM_MODEL = None

    monkeypatch.setattr("agent_service.agents.health.settings", FakeSettings())

    data = build_health_data(qdrant_probe=lambda: True, monotonic_now=lambda: 100.0, started_at=100.0)

    assert data["model_loaded"] is False
    assert data["model_name"] == ""


def test_health_data_matches_openapi() -> None:
    from agent_service.schemas.common import HealthData

    schema = HealthData.model_json_schema()
    props = schema["properties"]

    assert set(props.keys()) == {"status", "qdrant_connected", "model_loaded", "model_name", "uptime_seconds"}
    assert props["status"]["type"] == "string"
    assert props["qdrant_connected"]["type"] == "boolean"
    assert props["model_loaded"]["type"] == "boolean"
    assert props["model_name"]["type"] == "string"
    assert props["uptime_seconds"]["type"] == "integer"


def test_health_check_uses_json_wrapper() -> None:
    response = asyncio.run(health_check())
    payload = response.model_dump()

    assert set(payload) == {"code", "message", "data"}
    assert payload["code"] == 200
    assert payload["message"] == "success"
