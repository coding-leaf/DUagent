from __future__ import annotations

import asyncio
import json

import httpx

from agent_service_v2.api import personalized_resources as module
from agent_service_v2.main import app
from agent_service_v2.runtime.edu_events import EduEventType
from agent_service_v2.session.generation_registry import GenerationSessionRegistry


def _payload(**overrides):
    payload = {
        "task_id": "task-1",
        "user_id": "student-1",
        "course_id": "course-1",
        "course_title": "C语言",
        "goal": "生成指针讲义",
        "resource_preferences": ["chart_logic"],
    }
    payload.update(overrides)
    return payload


def test_start_generation_returns_in_memory_stream_coordinates(monkeypatch):
    async def fake_run(_self, request, emit):
        emit(EduEventType.WORKFLOW_STARTED, {"task_id": request.task_id})
        emit(
            EduEventType.WORKFLOW_COMPLETED,
            {"task_id": request.task_id, "status": "completed"},
        )
        return {"status": "completed"}

    monkeypatch.setattr(
        module.PersonalizedResourceGenerationRunner,
        "preflight",
        lambda _self: None,
    )
    monkeypatch.setattr(module.PersonalizedResourceGenerationRunner, "run", fake_run)

    async def request_api():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.post(
                "/agent/v2/personalized-resources/generations", json=_payload()
            )

    response = asyncio.run(request_api())

    assert response.status_code == 202
    data = response.json()["data"]
    assert data["status"] == "started"
    assert data["task_id"] == "task-1"
    assert data["session_id"].startswith("gen_")
    assert data["event_path"] == (
        f"/agent/v2/personalized-resources/generations/{data['session_id']}/events"
    )
    assert "team-runtime" not in response.text
    assert "AgentEvent" not in response.text


def test_start_generation_reports_unavailable_pipeline(monkeypatch):
    def fake_preflight(_self):
        raise module.PersonalizedResourceUnavailable("model_not_configured")

    monkeypatch.setattr(
        module.PersonalizedResourceGenerationRunner, "preflight", fake_preflight
    )

    async def request_api():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.post(
                "/agent/v2/personalized-resources/generations", json=_payload()
            )

    response = asyncio.run(request_api())

    assert response.status_code == 503
    assert response.json() == {
        "code": 503,
        "message": "model_not_configured",
        "data": None,
    }


def test_start_then_stream_events_end_to_end(monkeypatch):
    from agent_service_v2.runtime.edu_events import EduEventType as Types

    async def fake_run(_self, request, emit):
        emit(Types.WORKFLOW_STARTED, {"task_id": request.task_id})
        emit(Types.THOUGHT, {"delta": "先检索教材"})
        emit(Types.TEXT_DELTA, {"delta": "已生成"})
        emit(
            Types.TOOL_STARTED,
            {"tool_call_id": "tool-1", "tool_name": "create_personalized_resource_draft"},
        )
        emit(
            Types.TOOL_COMPLETED,
            {"tool_call_id": "tool-1", "tool_name": "create_personalized_resource_draft"},
        )
        emit(Types.WORKFLOW_COMPLETED, {"task_id": request.task_id})
        return {"status": "completed"}

    monkeypatch.setattr(
        module.PersonalizedResourceGenerationRunner, "preflight", lambda _self: None
    )
    monkeypatch.setattr(module.PersonalizedResourceGenerationRunner, "run", fake_run)

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            started = await client.post(
                "/agent/v2/personalized-resources/generations", json=_payload()
            )
            session_id = started.json()["data"]["session_id"]
            # The background task must finish so the stream closes on replay.
            await asyncio.sleep(0)
            response = await client.get(started.json()["data"]["event_path"])
            return session_id, response

    session_id, response = asyncio.run(scenario())

    assert response.status_code == 200
    events = [
        json.loads(line[len("data: ") :])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert [event["type"] for event in events] == [
        "workflow_started",
        "thought",
        "text_delta",
        "tool_started",
        "tool_completed",
        "workflow_completed",
    ]
    assert events[0]["run_id"] == session_id
    assert events[0]["agent"] == "personalized_resource_agent"


def test_event_stream_unknown_session_returns_404():
    async def request_api():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.get(
                "/agent/v2/personalized-resources/generations/gen_missing/events"
            )

    response = asyncio.run(request_api())

    assert response.status_code == 404
    assert response.json()["code"] == 404


def test_event_stream_replays_completed_session_events():
    registry = GenerationSessionRegistry()
    session = registry.create(
        session_id="gen_test",
        task_id="task-1",
        conversation_id="conv-1",
    )
    session.bus.publish(
        session.session_id,
        EduEventType.WORKFLOW_STARTED,
        {"task_id": "task-1"},
    )
    session.bus.complete(session.session_id)
    original = module._sessions
    module._sessions = registry
    try:

        async def request_api():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                return await client.get(
                    "/agent/v2/personalized-resources/generations/gen_test/events"
                )

        response = asyncio.run(request_api())
    finally:
        module._sessions = original

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    lines = [line for line in response.text.splitlines() if line.startswith("data: ")]
    assert len(lines) == 1
    assert json.loads(lines[0][len("data: ") :])["type"] == "workflow_started"
