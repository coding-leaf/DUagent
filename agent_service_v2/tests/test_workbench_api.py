import json

from fastapi.testclient import TestClient

from agent_service_v2.main import app


def test_workbench_chat_returns_sse_failure_when_model_missing():
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
