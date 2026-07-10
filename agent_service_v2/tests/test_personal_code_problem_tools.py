import asyncio
import json

from agent_service_v2.tools.personal_code_problem import build_personal_code_problem_tools


class FakeClient:
    def __init__(self):
        self.calls = []

    async def post_json(self, path, payload):
        self.calls.append((path, payload))
        return {
            "problem_id": "problem-1",
            "language": "python",
            "public_case_count": 1,
            "hidden_case_count": 1,
        }


def _text(chunk) -> str:
    return chunk.content[0].text


def test_personal_code_problem_tool_delegates_validation_and_storage_to_backend():
    client = FakeClient()
    tool = build_personal_code_problem_tools(
        client=client,
        user_id="student-1",
        course_id="course-1",
        conversation_id="conversation-1",
        run_id="run-1",
    )[0]

    response = asyncio.run(
        tool.call(
            title="回显",
            statement="读取并输出输入。",
            language="python",
            starter_code="print(input())",
            reference_solution="print(input())",
            public_inputs=["shown\n"],
            hidden_inputs=["hidden\n"],
        )
    )
    data = json.loads(_text(response))

    assert data == {
        "status": "created",
        "problem_id": "problem-1",
        "language": "python",
        "public_case_count": 1,
        "hidden_case_count": 1,
    }
    assert client.calls == [
        (
            "/internal/ai-chat/code-problems",
            {
                "user_id": "student-1",
                "course_id": "course-1",
                "conversation_id": "conversation-1",
                "run_id": "run-1",
                "draft": {
                    "title": "回显",
                    "statement": "读取并输出输入。",
                    "language": "python",
                    "starter_code": "print(input())",
                    "reference_solution": "print(input())",
                    "test_inputs": [
                        {"stdin": "shown\n", "is_public": True},
                        {"stdin": "hidden\n", "is_public": False},
                    ],
                },
            },
        )
    ]
