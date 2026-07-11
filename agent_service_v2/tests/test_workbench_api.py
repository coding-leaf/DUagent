import json

from agentscope.event import ReplyEndEvent, ReplyStartEvent, TextBlockDeltaEvent
from fastapi.testclient import TestClient

from agent_service_v2.main import app
from agent_service_v2.api import workbench
from agent_service_v2.agents.workbench_factory import WorkbenchAgentFactory
from agent_service_v2.schemas.workbench import WorkbenchChatRequest


def test_workbench_request_accepts_offering_and_catalog_ids():
    request = WorkbenchChatRequest(
        user_id="u1",
        course_id="offering-1",
        catalog_id="catalog-1",
        conversation_id="conv1",
        message="创建代码练习",
    )

    assert request.course_id == "offering-1"
    assert request.catalog_id == "catalog-1"


def test_workbench_chat_returns_sse_failure_when_model_missing(monkeypatch):
    monkeypatch.setattr(
        workbench,
        "create_agent_factory",
        lambda: WorkbenchAgentFactory(model_provider=lambda: None),
    )
    client = TestClient(app)

    response = client.post(
        "/agent/v2/workbench/chat",
        json={
            "user_id": "u1",
            "course_id": "c1",
            "conversation_id": "conv1",
            "message": "我今天应该学什么？",
            "context": {},
        },
    )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    lines = [line for line in response.text.splitlines() if line.startswith("data: ")]
    payload = json.loads(lines[0].removeprefix("data: "))
    assert payload["type"] == "workflow_failed"
    assert payload["payload"] == {"reason": "model_not_configured"}


def test_workbench_chat_streams_agent_events(monkeypatch):
    class FakeAgent:
        async def reply_stream(self, _message):
            yield ReplyStartEvent(session_id="conv1", reply_id="reply1", name="workbench")
            yield TextBlockDeltaEvent(reply_id="reply1", block_id="block1", delta="先复习链表。")
            yield ReplyEndEvent(session_id="conv1", reply_id="reply1")

    class FakeFactory:
        def create_agent(self, **_kwargs):
            return FakeAgent()

    monkeypatch.setattr(workbench, "create_agent_factory", lambda: FakeFactory())
    client = TestClient(app)

    response = client.post(
        "/agent/v2/workbench/chat",
        json={
            "user_id": "u1",
            "course_id": "c1",
            "conversation_id": "conv1",
            "message": "我今天应该学什么？",
            "context": {},
        },
    )

    payloads = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert [payload["type"] for payload in payloads] == [
        "workflow_started",
        "text_delta",
        "workflow_completed",
        "content_safety_reviewed",
    ]
    assert payloads[1]["payload"] == {"delta": "先复习链表。"}
