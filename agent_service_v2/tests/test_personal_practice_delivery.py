import asyncio
import json

from agent_service_v2.tools.backend_learning_client import BackendLearningClientError
from agent_service_v2.tools.personal_practice_delivery import (
    build_resume_personal_practice_tools,
    publish_prepared_practice,
)


class TimeoutThenSuccessClient:
    def __init__(self):
        self.calls = []
        self.finalize_attempts = 0

    async def post_json(self, path, payload):
        self.calls.append((path, payload))
        if path.endswith("/prepare"):
            return {"generation_id": "generation-1", "status": "delivery_pending"}
        self.finalize_attempts += 1
        if self.finalize_attempts == 1:
            raise BackendLearningClientError("backend_timeout")
        return {
            "generation_id": "generation-1",
            "status": "published",
            "artifact": {
                "id": "generation-1",
                "type": "QuizCard",
                "title": "练习",
                "course_id": "course-1",
                "question_ids": ["question-1"],
            },
        }


def test_delivery_retries_finalize_once_after_timeout():
    client = TimeoutThenSuccessClient()
    result = asyncio.run(publish_prepared_practice(
        client=client,
        prepare_payload={
            "user_id": "user-1",
            "course_id": "course-1",
            "conversation_id": "conv-1",
            "run_id": "run-1",
            "practice_type": "choice_quiz",
            "choice_quiz": {},
        },
    ))

    assert result["outcome"] == "success"
    assert client.finalize_attempts == 2


def test_resume_tool_injects_trusted_context():
    class Client:
        async def post_json(self, path, payload):
            assert path.endswith("/resume")
            assert payload == {
                "generation_id": "generation-1",
                "user_id": "user-1",
                "course_id": "course-1",
            }
            return {"generation_id": "generation-1", "status": "published", "artifact": {}}

    tool = build_resume_personal_practice_tools(
        client=Client(),
        user_id="user-1",
        course_id="course-1",
    )[0]
    result = asyncio.run(tool.call(generation_id="generation-1", user_id="attacker"))
    payload = json.loads(result.content[0].text)

    assert payload["status"] == "published"
    assert "user_id" not in tool.input_schema["properties"]
