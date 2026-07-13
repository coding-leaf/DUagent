from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any

from agentscope.message import TextBlock, ToolResultState
from agentscope.permission import PermissionContext, PermissionDecision
from agentscope.tool import ToolBase, ToolChunk

from agent_service_v2.tools.contracts import edu_tool_result


_FORBIDDEN_MEMORY_PATTERNS = (
    r"(?i)api[_ -]?key|access[_ -]?token|authorization|password|secret",
    r"密钥|密码|身份证|银行卡|手机号|电子邮箱",
    r"掌握度|薄弱点|诊断结论|正确率|用户答案|学生答案|答题记录",
    r"(?i)tool[_ -]?result|工具返回|reference_solution|hidden_inputs",
)

_ALLOWED_MEMORY_TYPES = (
    "identity",
    "learning_goal",
    "resource_preference",
    "learning_habit",
    "teaching_preference",
)


def validate_memory_content(memory_type: str | None, content: list[str]) -> str | None:
    if memory_type not in _ALLOWED_MEMORY_TYPES:
        return "memory_type_not_allowed"
    if not content:
        return "memory_content_empty"
    for item in content:
        normalized = item.strip()
        if not normalized:
            return "memory_content_empty"
        if any(re.search(pattern, normalized) for pattern in _FORBIDDEN_MEMORY_PATTERNS):
            return "memory_content_forbidden"
    if len(set(item.strip() for item in content)) != len(content):
        return "memory_content_duplicate"
    return None


class GuardedMemoryTool(ToolBase):
    def __init__(self, delegate: ToolBase) -> None:
        super().__init__()
        self._delegate = delegate
        self.name = delegate.name
        self.description = delegate.description
        self.input_schema = _memory_input_schema(delegate.input_schema) if self.name == "add_memory" else delegate.input_schema
        self.is_concurrency_safe = delegate.is_concurrency_safe
        self.is_read_only = delegate.is_read_only

    async def check_permissions(
        self,
        tool_input: dict[str, Any],
        context: PermissionContext,
    ) -> PermissionDecision:
        return await self._delegate.check_permissions(tool_input, context)

    async def call(self, **kwargs: Any) -> ToolChunk:
        if self.name == "add_memory":
            memory_type = kwargs.pop("memory_type", None)
            reason = validate_memory_content(memory_type, kwargs.get("content") or [])
            if reason:
                return _chunk(edu_tool_result(status="rejected", reason=reason), error=True)
        result = await self._delegate(**kwargs)
        text = _result_text(result)
        state = getattr(result, "state", ToolResultState.SUCCESS)
        if state == ToolResultState.ERROR:
            return _chunk(edu_tool_result(status="error", reason="memory_backend_error"), error=True)
        status = "empty" if self.name == "search_memory" and "no relevant" in text else "success"
        data = {"match_text": text} if self.name == "search_memory" else {}
        return _chunk(edu_tool_result(status=status, summary="memory operation completed", data=data))


def guard_memory_tools(tools: list[ToolBase]) -> list[ToolBase]:
    return [GuardedMemoryTool(tool) if tool.name in {"search_memory", "add_memory"} else tool for tool in tools]


def _memory_input_schema(delegate_schema: dict[str, Any]) -> dict[str, Any]:
    schema = deepcopy(delegate_schema)
    properties = schema.setdefault("properties", {})
    properties["memory_type"] = {
        "type": "string",
        "enum": list(_ALLOWED_MEMORY_TYPES),
        "description": "Whitelisted durable fact category.",
    }
    required = schema.setdefault("required", [])
    if "memory_type" not in required:
        required.append("memory_type")
    return schema


def _result_text(result: ToolChunk) -> str:
    return "\n".join(block.text for block in result.content if isinstance(block, TextBlock))


def _chunk(payload: dict[str, Any], *, error: bool = False) -> ToolChunk:
    return ToolChunk(
        content=[TextBlock(text=json.dumps(payload, ensure_ascii=False))],
        state=ToolResultState.ERROR if error else ToolResultState.RUNNING,
    )
