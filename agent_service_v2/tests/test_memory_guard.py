import asyncio
import json

from agentscope.message import TextBlock, ToolResultState
from agentscope.tool import ToolChunk

from agent_service_v2.tools.memory_guard import GuardedMemoryTool, validate_memory_content


class FakeMemoryTool:
    name = "add_memory"
    description = "memory"
    input_schema = {"type": "object"}
    is_concurrency_safe = False
    is_read_only = False

    async def __call__(self, **_kwargs):
        return ToolChunk(content=[TextBlock(text="saved secret body")], state=ToolResultState.RUNNING)


def test_memory_policy_allows_explicit_stable_fact():
    assert validate_memory_content(["用户明确表示长期目标是通过计算机二级考试。"] ) is None


def test_memory_policy_rejects_inference_sensitive_and_tool_content():
    assert validate_memory_content(["用户的掌握度较低。"] ) == "memory_must_be_explicit_user_statement"
    assert validate_memory_content(["用户明确表示密码是 123456。"] ) == "memory_content_forbidden"
    assert validate_memory_content(["用户明确要求保存工具返回原文。"] ) == "memory_content_forbidden"


def test_guarded_memory_tool_returns_visible_redacted_audit_result():
    tool = GuardedMemoryTool(FakeMemoryTool())
    result = asyncio.run(tool.call(
        thinking="durable preference",
        content=["用户明确表示偏好使用 C++ 完成练习。"],
    ))
    payload = json.loads(result.content[0].text)

    assert payload["outcome"] == "success"
    assert "saved secret body" not in result.content[0].text
