import asyncio
import json

from agentscope.workspace import LocalWorkspace

from agent_service_v2.tools.backend_learning_client import BackendLearningClientError
from agent_service_v2.tools.personal_code_problem import build_personal_code_problem_tools


class FakeClient:
    def __init__(self):
        self.calls = []

    async def post_json(self, path, payload):
        self.calls.append((path, payload))
        return {
            "generation_id": "generation-1",
            "status": "published",
            "problem_id": "problem-1",
            "language": "python",
            "public_case_count": 1,
            "hidden_case_count": 1,
            "artifact": {
                "id": "generation-1",
                "type": "CodeSandboxCard",
                "title": payload["draft"]["title"],
                "problem_id": "problem-1",
                "language": "python",
            },
        }


class RejectingClient:
    async def post_json(self, _path, _payload):
        raise BackendLearningClientError(
            "backend_rejected",
            status_code=400,
            detail_reason="conversation_ownership_check_failed",
        )


def _text(chunk) -> str:
    return chunk.content[0].text


def test_personal_code_problem_tool_returns_published_private_problem(tmp_path):
    client = FakeClient()
    workspace = LocalWorkspace(workdir=str(tmp_path), workspace_id="ws")
    tool = build_personal_code_problem_tools(
        client=client,
        user_id="student-1",
        course_id="course-1",
        conversation_id="conversation-1",
        run_id="run-1",
        workspace=workspace,
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

    assert data["outcome"] == "success"
    assert data["status"] == "published"
    assert data["problem_id"] == "problem-1"
    assert data["artifact"]["type"] == "CodeSandboxCard"
    assert client.calls == [
        (
            "/internal/ai-chat/code-problem-validations",
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


def test_personal_code_problem_publication_creates_matching_card_without_leaking_draft(tmp_path):
    workspace = LocalWorkspace(workdir=str(tmp_path), workspace_id="ws")
    tool = build_personal_code_problem_tools(
        client=FakeClient(),
        user_id="student-1",
        course_id="course-1",
        conversation_id="conversation-1",
        run_id="run-1",
        workspace=workspace,
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
    assert data["status"] == "published"
    assert data["generation_id"] == "generation-1"
    assert data["problem_id"] == "problem-1"
    assert data["artifact"]["type"] == "CodeSandboxCard"
    assert "reference_solution" not in data
    assert not list(tmp_path.rglob("*.json"))


def test_personal_code_problem_tool_does_not_require_agent_workspace():
    tool = build_personal_code_problem_tools(
        client=FakeClient(),
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
    assert data["status"] == "published"
    assert data["artifact"]["type"] == "CodeSandboxCard"


def test_personal_code_problem_tool_reports_backend_validation_as_rejected(tmp_path):
    tool = build_personal_code_problem_tools(
        client=RejectingClient(),
        user_id="student-1",
        course_id="course-1",
        conversation_id="conversation-1",
        run_id="run-1",
        workspace=LocalWorkspace(workdir=str(tmp_path), workspace_id="ws"),
    )[0]

    response = asyncio.run(
        tool.call(
            title="Echo",
            statement="Read and write input.",
            language="cpp",
            starter_code="int main() { return 0; }",
            reference_solution="int main() { return 0; }",
            public_inputs=["shown\n"],
            hidden_inputs=["hidden\n"],
        )
    )

    data = json.loads(_text(response))
    assert data["outcome"] == "failure"
    assert data["status"] == "rejected"
    assert data["reason"] == "conversation_ownership_check_failed"
