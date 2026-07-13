import asyncio
import json

from agent_service_v2.tools.personalized_resources import build_personalized_resource_tools


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def post_json(self, path, payload):
        self.calls.append((path, payload))
        return self.responses.pop(0)


def _json(result):
    return json.loads(result.content[0].text)


def test_recommendation_tool_emits_resource_card_and_hides_identity():
    client = FakeClient([{"status": "available", "items": [{
        "id": "r1", "title": "AVL 图解", "type": "diagram",
        "summary": "旋转过程", "reason": "匹配当前知识点",
    }]}])
    tools = build_personalized_resource_tools(
        client=client, user_id="u1", course_id="c1", conversation_id="conv1", run_id="run1"
    )
    tool = next(item for item in tools if item.name == "recommend_personalized_resources")

    payload = _json(asyncio.run(tool.call(target="AVL 树", user_id="attacker")))

    assert payload["artifact"]["type"] == "PersonalizedResourceCard"
    assert client.calls[0][1]["user_id"] == "u1"
    assert "user_id" not in tool.input_schema["properties"]


def test_generation_tool_starts_at_most_one_task_per_run():
    client = FakeClient([{"status": "processing", "task_id": "task1", "course_id": "c1"}])
    tools = build_personalized_resource_tools(
        client=client, user_id="u1", course_id="c1", conversation_id="conv1", run_id="run1"
    )
    tool = next(item for item in tools if item.name == "generate_personalized_resource")

    first = _json(asyncio.run(tool.call(goal="AVL 树图解", resource_type="diagram")))
    second = _json(asyncio.run(tool.call(goal="另一个讲义", resource_type="reading")))

    assert first["artifact"]["props"]["task_id"] == "task1"
    assert second["artifact"]["props"]["task_id"] == "task1"
    assert len(client.calls) == 1

