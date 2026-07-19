import asyncio
import json
import pytest

from agent_service_v2.tools.oj_execution import build_oj_execution_tools
from agent_service_v2.tools.backend_learning_client import BackendLearningClientError


class FakeClient:
    def __init__(self, should_fail=False):
        self.calls = []
        self.should_fail = should_fail

    async def post_json(self, path, payload):
        self.calls.append((path, payload))
        if self.should_fail:
            raise BackendLearningClientError(reason="connection_refused")
        return {
            "status": "success",
            "compile_status": "OK",
            "compile_output": "",
            "execution": {
                "stdout": f"executed: {payload.get('code')}",
                "stderr": "",
                "exit_code": 0,
            }
        }


def _text(chunk) -> str:
    return chunk.content[0].text


def test_oj_execution_tool_calls_backend():
    client = FakeClient()
    tools = build_oj_execution_tools(client=client)
    tool = next(item for item in tools if item.name == "run_code_in_oj")

    result = asyncio.run(tool.call(code="printf('hello');", language="c", stdin="input_data"))
    data = json.loads(_text(result))

    assert data["status"] == "success"
    assert data["execution"]["stdout"] == "executed: printf('hello');"
    assert client.calls == [
        (
            "/internal/ai-chat/oj/evaluate",
            {
                "code": "printf('hello');",
                "language": "c",
                "stdin": "input_data",
            }
        )
    ]


def test_oj_execution_tool_degrades_when_client_missing():
    tools = build_oj_execution_tools(client=None)
    tool = next(item for item in tools if item.name == "run_code_in_oj")

    result = asyncio.run(tool.call(code="printf('hello');", language="c"))
    data = json.loads(_text(result))

    assert data["status"] == "degraded"
    assert data["reason"] == "backend_learning_client_not_configured"


def test_oj_execution_tool_degrades_on_client_error():
    client = FakeClient(should_fail=True)
    tools = build_oj_execution_tools(client=client)
    tool = next(item for item in tools if item.name == "run_code_in_oj")

    result = asyncio.run(tool.call(code="printf('hello');", language="c"))
    data = json.loads(_text(result))

    assert data["status"] == "degraded"
    assert data["reason"] == "connection_refused"
    assert "不可用" in data["message"]
