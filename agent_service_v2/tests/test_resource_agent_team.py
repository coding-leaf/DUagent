import asyncio
import json

import httpx

from agent_service_v2.agents.model_provider import AgentModelSettings
from agent_service_v2.agents.resource_team_leader import ResourceTeamRequest
from agent_service_v2.team.runtime_client import OfficialTeamRuntimeClient


def test_official_runtime_client_provisions_leader_session_and_triggers_chat():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.url.path, json.loads(request.content or b"{}")))
        responses = {
            "/credential/": (201, {"credential_id": "cred-1"}),
            "/agent/": (201, {"agent_id": "leader-1"}),
            "/sessions/": (201, {"session_id": "session-1"}),
            "/chat/": (200, {"status": "started", "session_id": "session-1"}),
        }
        status, body = responses[request.url.path]
        return httpx.Response(status, json=body)

    runtime = OfficialTeamRuntimeClient(
        settings=AgentModelSettings(
            LLM_PROVIDER="agentscope_openai",
            LLM_BASE_URL="https://model.example/v1",
            LLM_API_KEY="secret",
            LLM_MODEL="model-x",
        ),
        transport=httpx.MockTransport(handler),
    )
    result = asyncio.run(
        runtime.start(
            ResourceTeamRequest(
                task_id="task-1",
                user_id="student-1",
                course_id="course-1",
                goal="生成指针讲义和思维导图",
                resource_preferences=["personal_lesson", "diagram"],
            )
        )
    )

    assert [path for path, _ in calls] == [
        "/credential/",
        "/agent/",
        "/sessions/",
        "/chat/",
    ]
    assert result == {
        "status": "started",
        "agent_id": "leader-1",
        "session_id": "session-1",
        "stream_path": "/agent/v2/team-runtime/sessions/session-1/stream",
    }
    leader_prompt = calls[1][1]["system_prompt"]
    assert "resource_generator" in leader_prompt
    assert "resource_reviewer" in leader_prompt
    assert "最多一次返修" in leader_prompt
    assert "warnings" in leader_prompt


def test_product_api_returns_only_edu_runtime_coordinates(monkeypatch):
    from agent_service_v2.api import personalized_resources as module
    from agent_service_v2.main import app

    async def fake_start(_self, _request):
        return {
            "status": "started",
            "agent_id": "leader-1",
            "session_id": "session-1",
            "stream_path": "/agent/v2/team-runtime/sessions/session-1/stream",
        }

    monkeypatch.setattr(module.OfficialTeamRuntimeClient, "start", fake_start)
    async def request_api():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.post(
                "/agent/v2/personalized-resources/generations",
                json={
                    "task_id": "task-1",
                    "user_id": "student-1",
                    "course_id": "course-1",
                    "goal": "生成指针讲义",
                },
            )

    response = asyncio.run(request_api())

    assert response.status_code == 202
    assert response.json()["data"]["status"] == "started"
    assert "AgentEvent" not in response.text
