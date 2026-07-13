import asyncio
import json

from agent_service_v2.tools.learner_profile import build_learner_profile_tools


class FakeClient:
    def __init__(self):
        self.calls = []

    async def post_json(self, path, payload):
        self.calls.append((path, payload))
        return {"outcome": "success", "result": "updated"}


def _payload(result):
    return json.loads(result.content[0].text)


def test_profile_tools_hide_identity_and_inject_run_scope():
    client = FakeClient()
    tools = build_learner_profile_tools(
        client=client,
        user_id="user-1",
        course_id="course-1",
        conversation_id="conv-1",
        run_id="run-1",
    )
    update = next(tool for tool in tools if tool.name == "update_learner_profile_from_dialogue")

    result = asyncio.run(update.call(
        learning_goal="掌握图算法",
        user_id="attacker",
        course_id="other",
    ))

    assert _payload(result)["outcome"] == "success"
    path, payload = client.calls[0]
    assert path == "/internal/ai-chat/learner-profile/update"
    assert payload["user_id"] == "user-1"
    assert payload["course_id"] == "course-1"
    assert payload["conversation_id"] == "conv-1"
    assert payload["run_id"] == "run-1"
    assert "user_id" not in update.input_schema["properties"]
    assert "course_id" not in update.input_schema["properties"]


def test_profile_update_schema_limits_allowed_facts():
    tools = build_learner_profile_tools(
        client=None,
        user_id="user-1",
        course_id="course-1",
        conversation_id="conv-1",
        run_id="run-1",
    )
    update = next(tool for tool in tools if tool.name == "update_learner_profile_from_dialogue")
    properties = update.input_schema["properties"]

    assert properties["resource_preferences"]["anyOf"][0]["items"]["enum"] == [
        "text_reading", "chart_logic", "code_practice", "practice_reinforcement"
    ]
    assert properties["guidance_level"]["anyOf"][0]["enum"] == ["L1", "L2", "L3"]
    assert "weak_points" not in properties
    assert "mastery_score" not in properties
