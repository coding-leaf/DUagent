import asyncio
import json

from agent_service_v2.tools.learning_progress import build_learning_progress_tools


class FakeClient:
    def __init__(self):
        self.calls = []

    async def post_json(self, path, payload):
        self.calls.append((path, payload))
        return {"status": "available", "path": path, "payload": payload}


def _text(chunk) -> str:
    return chunk.content[0].text


def test_read_learning_progress_tool_injects_user_and_course():
    client = FakeClient()
    tools = build_learning_progress_tools(client=client, user_id="u1", course_id="c1")
    tool = next(item for item in tools if item.name == "read_learning_progress")

    result = asyncio.run(tool.call(limit_nodes=20))

    assert json.loads(_text(result))["status"] == "available"
    assert client.calls == [
        ("/internal/ai-chat/learning-progress", {"user_id": "u1", "course_id": "c1", "limit_nodes": 20})
    ]


def test_read_recent_answers_tool_does_not_accept_user_id_from_model():
    client = FakeClient()
    tools = build_learning_progress_tools(client=client, user_id="u1", course_id="c1")
    tool = next(item for item in tools if item.name == "read_recent_answers")

    asyncio.run(tool.call(scope="node", node_id="n-avl", user_id="attacker", limit=10))

    path, payload = client.calls[0]
    assert path == "/internal/ai-chat/recent-answers"
    assert payload["user_id"] == "u1"
    assert payload["course_id"] == "c1"
    assert payload["node_id"] == "n-avl"
    assert payload["limit"] == 10
    assert payload["scope"] == "node"
    assert "attacker" not in payload.values()


def test_learning_tools_return_unavailable_when_client_missing():
    tools = build_learning_progress_tools(client=None, user_id="u1", course_id="c1")
    tool = next(item for item in tools if item.name == "read_learning_progress")

    result = asyncio.run(tool.call())

    assert "backend_learning_client_not_configured" in _text(result)
