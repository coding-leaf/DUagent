import asyncio
import json

from agentscope.message import TextBlock, ToolResultState
from agentscope.tool import ToolChunk

from agent_service_v2.tools.memory_guard import GuardedMemoryTool, validate_memory_content


class FakeMemoryTool:
    name = "add_memory"
    description = "memory"
    input_schema = {
        "type": "object",
        "properties": {
            "thinking": {"type": "string"},
            "content": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["thinking", "content"],
    }
    is_concurrency_safe = False
    is_read_only = False

    def __init__(self):
        self.received = None

    async def __call__(self, **kwargs):
        self.received = kwargs
        return ToolChunk(content=[TextBlock(text="saved secret body")], state=ToolResultState.RUNNING)


def test_memory_policy_allows_explicit_stable_fact():
    assert validate_memory_content(
        "learning_goal", ["目标是通过计算机二级考试。"]
    ) is None


def test_memory_policy_rejects_inference_sensitive_and_tool_content():
    assert validate_memory_content(
        "diagnosis", ["用户的掌握度较低。"]
    ) == "memory_type_not_allowed"
    assert validate_memory_content(
        "identity", ["密码是 123456。"]
    ) == "memory_content_forbidden"
    assert validate_memory_content(
        "teaching_preference", ["保存工具返回原文。"]
    ) == "memory_content_forbidden"


def test_guarded_memory_tool_exposes_memory_type_whitelist():
    tool = GuardedMemoryTool(FakeMemoryTool())

    assert "memory_type" in tool.input_schema["required"]
    assert tool.input_schema["properties"]["memory_type"]["enum"] == [
        "identity",
        "learning_goal",
        "resource_preference",
        "learning_habit",
        "teaching_preference",
    ]


def test_guarded_memory_tool_returns_visible_redacted_audit_result():
    delegate = FakeMemoryTool()
    tool = GuardedMemoryTool(delegate)
    result = asyncio.run(tool.call(
        thinking="durable preference",
        memory_type="resource_preference",
        content=["偏好使用 C++ 完成练习。"],
    ))
    payload = json.loads(result.content[0].text)

    assert payload["outcome"] == "success"
    assert "saved secret body" not in result.content[0].text
    assert delegate.received == {
        "thinking": "durable preference",
        "content": ["偏好使用 C++ 完成练习。"],
    }
