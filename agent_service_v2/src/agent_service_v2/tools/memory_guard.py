from __future__ import annotations

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


def validate_memory_content(content: list[str]) -> str | None:
    if not content:
        return "memory_content_empty"
    for item in content:
        normalized = item.strip()
        if not normalized:
            return "memory_content_empty"
        if not (normalized.startswith("用户明确") or normalized.lower().startswith("user explicitly")):
            return "memory_must_be_explicit_user_statement"
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
        self.input_schema = delegate.input_schema
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
            reason = validate_memory_content(kwargs.get("content") or [])
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


def _result_text(result: ToolChunk) -> str:
    return "\n".join(block.text for block in result.content if isinstance(block, TextBlock))


def _chunk(payload: dict[str, Any], *, error: bool = False) -> ToolChunk:
    return ToolChunk(
        content=[TextBlock(text=json.dumps(payload, ensure_ascii=False))],
        state=ToolResultState.ERROR if error else ToolResultState.RUNNING,
    )
