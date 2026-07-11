import os
import sys
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///./test_oj_sandbox.db",
)

from app.db.session import init_db
from app.main import app
from app.services.oj_execution_service import OJExecutionError, execute_code_in_oj


@pytest.fixture(scope="module", autouse=True)
def _init_db():
    import asyncio
    asyncio.run(init_db())


@pytest.mark.asyncio
async def test_internal_oj_evaluate_requires_token():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/internal/ai-chat/oj/evaluate",
            json={"code": "int main() {}", "language": "c", "stdin": ""},
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_internal_code_problem_creation_requires_token():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/internal/ai-chat/code-problem-validations",
            json={
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
                        {"stdin": "1\n", "is_public": True},
                        {"stdin": "2\n", "is_public": False},
                    ],
                },
            },
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_internal_code_problem_creation_returns_safe_metadata_only():
    from types import SimpleNamespace

    created = SimpleNamespace(
        generation=SimpleNamespace(id="generation-1", status="published"),
        problem=SimpleNamespace(id="problem-1"),
        public_case_count=1,
        hidden_case_count=1,
    )
    with patch("app.api.v1.internal_ai_chat.settings.INTERNAL_AGENT_TOKEN", "secret"):
        with patch(
            "app.api.v1.internal_ai_chat.create_validated_personal_problem_from_ai_chat",
            new_callable=AsyncMock,
        ) as create_problem:
            create_problem.return_value = created
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/internal/ai-chat/code-problem-validations",
                    headers={"X-Internal-Agent-Token": "secret"},
                    json={
                        "user_id": "student-1",
                        "course_id": "course-1",
                        "conversation_id": "conversation-1",
                        "run_id": "run-1",
                        "draft": {
                            "title": "回显",
                            "statement": "读取并输出输入。",
                            "language": "python",
                            "starter_code": "print(input())",
                            "reference_solution": "print(input())  # private",
                            "test_inputs": [
                                {"stdin": "shown\n", "is_public": True},
                                {"stdin": "hidden\n", "is_public": False},
                            ],
                        },
                    },
                )

    assert response.status_code == 200
    assert response.json()["data"] == {
        "generation_id": "generation-1",
        "status": "published",
        "problem_id": "problem-1",
        "language": "python",
        "public_case_count": 1,
        "hidden_case_count": 1,
    }
    assert "private" not in str(response.json())
    assert "hidden\\n" not in str(response.json())


@pytest.mark.asyncio
async def test_internal_code_problem_creation_normalizes_language_alias_before_service_call():
    from types import SimpleNamespace

    created = SimpleNamespace(
        generation=SimpleNamespace(id="generation-1", status="published"),
        problem=SimpleNamespace(id="problem-1"),
        public_case_count=1,
        hidden_case_count=1,
    )
    with patch("app.api.v1.internal_ai_chat.settings.INTERNAL_AGENT_TOKEN", "secret"):
        with patch(
            "app.api.v1.internal_ai_chat.create_validated_personal_problem_from_ai_chat",
            new_callable=AsyncMock,
        ) as create_problem:
            create_problem.return_value = created
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/internal/ai-chat/code-problem-validations",
                    headers={"X-Internal-Agent-Token": "secret"},
                    json={
                        "user_id": "student-1",
                        "course_id": "course-1",
                        "conversation_id": "conversation-1",
                        "run_id": "run-1",
                        "draft": {
                            "title": "Echo",
                            "statement": "Read and write input.",
                            "language": "C++",
                            "starter_code": "int main() { return 0; }",
                            "reference_solution": "int main() { return 0; }",
                            "test_inputs": [
                                {"stdin": "shown\\n", "is_public": True},
                                {"stdin": "hidden\\n", "is_public": False},
                            ],
                        },
                    },
                )

    assert response.status_code == 200
    assert create_problem.await_args.kwargs["draft"].language == "cpp"


@pytest.mark.asyncio
async def test_internal_code_problem_creation_does_not_report_success_when_commit_fails():
    from sqlalchemy.exc import OperationalError

    from app.api.deps import get_db
    from app.models.code_problem import CodeProblem
    from app.models.personalized_resource_generation import PersonalizedResourceGeneration
    from app.services.code_problem_service import CreatedCodeProblem

    class CommitFailingDB:
        async def commit(self):
            raise OperationalError("INSERT", {}, RuntimeError("column missing"))

        async def rollback(self):
            return None

    created = CreatedCodeProblem(
        problem=CodeProblem(
            id="problem-1",
            course_id="course-1",
            owner_user_id="student-1",
            title="回显",
            statement="读取并输出输入。",
            language="python",
            starter_code="print(input())",
            reference_solution="print(input())",
            validation_report={},
        ),
        generation=PersonalizedResourceGeneration(
            id="generation-1",
            user_id="student-1",
            course_id="course-1",
            source_type="ai_chat",
            goal="读取并输出输入。",
            resource_type="validated_code_problem",
            status="published",
            draft={},
        ),
        public_case_count=1,
        hidden_case_count=1,
    )

    async def override_db():
        yield CommitFailingDB()

    app.dependency_overrides[get_db] = override_db
    try:
        with patch("app.api.v1.internal_ai_chat.settings.INTERNAL_AGENT_TOKEN", "secret"):
            with patch(
                "app.api.v1.internal_ai_chat.create_validated_personal_problem_from_ai_chat",
                new_callable=AsyncMock,
            ) as create_problem:
                create_problem.return_value = created
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    response = await client.post(
                        "/internal/ai-chat/code-problem-validations",
                        headers={"X-Internal-Agent-Token": "secret"},
                        json={
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
                                    {"stdin": "1\n", "is_public": True},
                                    {"stdin": "2\n", "is_public": False},
                                ],
                            },
                        },
                    )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 500
    assert response.json()["detail"]["message"] == "代码题保存失败"


@pytest.mark.asyncio
async def test_internal_oj_evaluate_returns_success():
    with patch("app.api.v1.internal_ai_chat.settings.INTERNAL_AGENT_TOKEN", "secret"):
        with patch(
            "app.api.v1.internal_ai_chat.execute_code_in_oj",
            new_callable=AsyncMock,
        ) as mock_execute:
            mock_execute.return_value = {
                "status": "success",
                "compile_status": "OK",
                "compile_output": "",
                "execution": {
                    "stdout": "hello",
                    "stderr": "",
                    "exit_code": 0,
                    "exit_signal": None,
                    "status_description": "Accepted",
                    "run_time_ms": 10,
                    "memory_kb": 100,
                }
            }
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/internal/ai-chat/oj/evaluate",
                    headers={"X-Internal-Agent-Token": "secret"},
                    json={"code": "printf('hello');", "language": "c", "stdin": ""},
                )
    assert response.status_code == 200
    assert response.json()["code"] == 200
    assert response.json()["data"]["compile_status"] == "OK"
    assert response.json()["data"]["execution"]["stdout"] == "hello"
    mock_execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_internal_oj_evaluate_handles_degradation():
    with patch("app.api.v1.internal_ai_chat.settings.INTERNAL_AGENT_TOKEN", "secret"):
        with patch(
            "app.api.v1.internal_ai_chat.execute_code_in_oj",
            new_callable=AsyncMock,
        ) as mock_execute:
            mock_execute.side_effect = OJExecutionError("oj_unavailable", "Cannot connect to Judge0")
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/internal/ai-chat/oj/evaluate",
                    headers={"X-Internal-Agent-Token": "secret"},
                    json={"code": "printf('hello');", "language": "c", "stdin": ""},
                )
    assert response.status_code == 200
    assert response.json()["code"] == 200
    assert response.json()["data"]["status"] == "degraded"
    assert "LLM静态分析" in response.json()["data"]["message"]


@pytest.mark.asyncio
async def test_public_sandbox_execute_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/sandbox/execute",
            json={"code": "int main() {}", "language": "c", "stdin": ""},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_private_code_problem_detail_requires_authentication():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/code-problems/problem-1")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_private_code_problem_detail_excludes_reference_solution_and_hidden_cases():
    from app.api.deps import get_current_user, get_db
    from app.models.code_problem import CodeProblem, CodeProblemTestCase
    from app.models.user import User

    class FakeResult:
        def __init__(self, item):
            self.item = item

        def scalar_one_or_none(self):
            return self.item

        def scalars(self):
            return self

        def all(self):
            return self.item

    class FakeDB:
        async def execute(self, _statement):
            return FakeResult(results.pop(0))

    problem = CodeProblem(
        id="problem-1",
        owner_user_id="student-1",
        course_id="course-1",
        title="回显",
        statement="读取并输出输入。",
        language="python",
        starter_code="print(input())",
        reference_solution="print(input())  # private",
        validation_report={},
    )
    public_case = CodeProblemTestCase(
        stdin="visible\n",
        expected_output="visible",
        is_public=True,
    )
    results = [problem, [public_case]]
    app.dependency_overrides[get_current_user] = lambda: User(
        id="student-1", username="student", is_active=True
    )

    async def override_db():
        yield FakeDB()

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/code-problems/problem-1")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json()["data"]["public_cases"] == [{"stdin": "visible\n", "expected_output": "visible"}]
    assert "reference_solution" not in str(response.json())
    assert "private" not in str(response.json())


@pytest.mark.asyncio
async def test_private_code_problem_submission_returns_async_task_id():
    from app.api.deps import get_current_user, get_db
    from app.models.user import User

    app.dependency_overrides[get_current_user] = lambda: User(
        id="student-1", username="student", is_active=True
    )

    async def override_db():
        yield object()

    app.dependency_overrides[get_db] = override_db
    try:
        with patch(
            "app.api.v1.code_problems.start_code_problem_submission",
            new_callable=AsyncMock,
        ) as start_submission:
            start_submission.return_value = "task-1"
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/code-problems/problem-1/submissions",
                    json={"code": "print(input())"},
                )
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 202
    assert response.json()["data"] == {"task_id": "task-1"}


@pytest.mark.asyncio
async def test_public_sandbox_execute_success():
    from app.api.deps import get_current_user
    from app.models.user import User
    mock_user = User(id="u1", username="testuser", is_active=True)

    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        with patch(
            "app.api.v1.sandbox.execute_code_in_oj",
            new_callable=AsyncMock,
        ) as mock_execute:
            mock_execute.return_value = {
                "status": "success",
                "compile_status": "OK",
                "compile_output": "",
                "execution": {
                    "stdout": "result",
                    "stderr": "",
                    "exit_code": 0,
                    "exit_signal": None,
                    "status_description": "Accepted",
                    "run_time_ms": 20,
                    "memory_kb": 200,
                }
            }
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/sandbox/execute",
                    json={"code": "int main() {}", "language": "c", "stdin": ""},
                )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    assert response.json()["code"] == 200
    assert response.json()["data"]["execution"]["stdout"] == "result"


class _FakeOJResponse:
    status_code = 200
    text = "{}"

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _FakeOJClient:
    def __init__(self, *args, payload, **kwargs):
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *args, **kwargs):
        return _FakeOJResponse(self._payload)


@pytest.mark.asyncio
async def test_execute_code_in_oj_maps_runtime_error_status():
    payload = {
        "status": {"id": 11, "description": "Runtime Error (SIGSEGV)"},
        "stdout": "",
        "stderr": "Segmentation fault",
        "compile_output": None,
        "time": "0.01",
        "memory": 256,
        "exit_code": 139,
        "exit_signal": 11,
    }

    def fake_client(*args, **kwargs):
        return _FakeOJClient(*args, payload=payload, **kwargs)

    with patch("app.services.oj_execution_service.httpx.AsyncClient", fake_client):
        result = await execute_code_in_oj("int main(){return *(int*)0;}", "c")

    assert result["status"] == "runtime_error"
    assert result["compile_status"] == "OK"
    assert result["execution"]["status_id"] == 11
    assert result["execution"]["status_description"] == "Runtime Error (SIGSEGV)"


@pytest.mark.asyncio
async def test_execute_code_in_oj_maps_time_limit_status():
    payload = {
        "status": {"id": 5, "description": "Time Limit Exceeded"},
        "stdout": "",
        "stderr": "",
        "compile_output": None,
        "time": "5.01",
        "memory": 128,
        "exit_code": None,
        "exit_signal": None,
    }

    def fake_client(*args, **kwargs):
        return _FakeOJClient(*args, payload=payload, **kwargs)

    with patch("app.services.oj_execution_service.httpx.AsyncClient", fake_client):
        result = await execute_code_in_oj("while True: pass", "python")

    assert result["status"] == "time_limit_exceeded"
    assert result["compile_status"] == "OK"
    assert result["execution"]["status_id"] == 5


def test_judge0_headers_preserve_rapidapi_authentication_mode():
    from app.services.oj_execution_service import _judge0_headers

    with patch("app.services.oj_execution_service.settings.JUDGE0_API_KEY", "rapid-key"):
        with patch(
            "app.services.oj_execution_service.settings.JUDGE0_API_URL",
            "https://judge0-ce.p.rapidapi.com",
        ):
            headers = _judge0_headers()

    assert headers["X-RapidAPI-Key"] == "rapid-key"
    assert headers["X-RapidAPI-Host"] == "judge0-ce.p.rapidapi.com"
    assert "X-Auth-Token" not in headers


@pytest.mark.asyncio
async def test_execute_code_batch_in_oj_submits_all_fixed_inputs_without_waiting():
    from app.services.oj_execution_service import execute_code_batch_in_oj

    calls = []

    class BatchResponse:
        status_code = 201
        text = "[]"

        def json(self):
            return [{"token": "token-1"}, {"token": "token-2"}]

    class BatchClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, **kwargs):
            calls.append((url, kwargs))
            return BatchResponse()

    result = await execute_code_batch_in_oj(
        code="print(input())",
        language="python",
        stdins=["first\n", "second\n"],
        client_factory=lambda **_kwargs: BatchClient(),
    )

    assert result == ["token-1", "token-2"]
    assert calls[0][0].endswith("/submissions/batch")
    assert calls[0][1]["json"]["submissions"][0]["stdin"] == "first\n"
    assert "wait" not in calls[0][1].get("params", {})


@pytest.mark.asyncio
async def test_read_code_batch_results_maps_each_judge0_submission():
    from app.services.oj_execution_service import read_code_batch_results_in_oj

    class BatchResponse:
        status_code = 200
        text = "[]"

        def json(self):
            return {
                "submissions": [
                    {"status": {"id": 3, "description": "Accepted"}, "stdout": "3\n", "stderr": ""},
                    {"status": {"id": 7, "description": "Runtime Error"}, "stdout": "", "stderr": "boom"},
                ]
            }

    class BatchClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, *_args, **_kwargs):
            return BatchResponse()

    results = await read_code_batch_results_in_oj(
        tokens=["token-1", "token-2"],
        client_factory=lambda **_kwargs: BatchClient(),
    )

    assert results[0]["status"] == "success"
    assert results[0]["execution"]["stdout"] == "3\n"
    assert results[1]["status"] == "runtime_error"


@pytest.mark.asyncio
async def test_poll_code_batch_results_waits_until_every_submission_is_terminal():
    from app.services.oj_execution_service import poll_code_batch_results_in_oj

    responses = iter(
        [
            [{"status": "queued"}, {"status": "processing"}],
            [{"status": "success"}, {"status": "wrong_answer"}],
        ]
    )
    sleep_calls = []

    async def read_results(**_kwargs):
        return next(responses)

    async def sleep(delay):
        sleep_calls.append(delay)

    results = await poll_code_batch_results_in_oj(
        tokens=["token-1", "token-2"],
        read_results=read_results,
        sleep=sleep,
        interval_seconds=0.1,
    )

    assert [item["status"] for item in results] == ["success", "wrong_answer"]
    assert sleep_calls == [0.1]
