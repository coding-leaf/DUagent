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
