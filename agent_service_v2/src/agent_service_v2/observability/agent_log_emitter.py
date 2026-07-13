from __future__ import annotations

from time import perf_counter
from typing import Any

from agent_service_v2.observability.logging import (
    LogSink,
    build_log_record,
    enum_value,
    input_preview,
    output_preview,
)
from agent_service_v2.tools.web_search_mcp import WEB_SEARCH_INTERNAL_TOOL_NAME


class AgentLogEmitter:
    def __init__(
        self,
        *,
        run_id: str,
        conversation_id: str | None,
        user_id: str,
        course_id: str | None,
        sink: LogSink,
    ) -> None:
        self.run_id = run_id
        self.conversation_id = conversation_id
        self.user_id = user_id
        self.course_id = course_id
        self.trace_id = run_id
        self.sink = sink

    def emit(
        self,
        event: str,
        *,
        agent,
        level: str = "info",
        duration_ms: float | None = None,
        error: str | None = None,
        error_message: str | None = None,
        span_id: str | None = None,
        parent_span_id: str | None = None,
        span_kind: str = "event",
        name: str | None = None,
        phase: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        self.sink(
            build_log_record(
                event=event,
                level=level,
                run_id=self.run_id,
                conversation_id=self.conversation_id,
                user_id=self.user_id,
                course_id=self.course_id,
                agent=getattr(agent, "name", "unknown"),
                duration_ms=duration_ms,
                error=error,
                error_message=error_message,
                trace_id=self.trace_id,
                span_id=span_id,
                parent_span_id=parent_span_id,
                span_kind=span_kind,
                name=name,
                phase=phase,
                attributes=attributes,
            )
        )


def elapsed_ms(started_at: float) -> float:
    return (perf_counter() - started_at) * 1000


def tool_call_attributes(tool_call: Any) -> dict[str, Any]:
    if tool_call is None:
        return {}
    internal_tool_name = getattr(tool_call, "name", None)
    attributes = {
        "tool_call_id": getattr(tool_call, "id", None),
        "tool_name": (
            "web_search"
            if internal_tool_name == WEB_SEARCH_INTERNAL_TOOL_NAME
            else internal_tool_name
        ),
        "tool_input_preview": input_preview(getattr(tool_call, "input", None)),
    }
    if internal_tool_name in {
        "search_memory",
        "add_memory",
        WEB_SEARCH_INTERNAL_TOOL_NAME,
    }:
        attributes.pop("tool_input_preview", None)
        if internal_tool_name in {"search_memory", "add_memory"}:
            attributes["memory_content_redacted"] = True
        else:
            attributes["tool_input_redacted"] = True
        attributes["_redact_tool_io"] = True
    return attributes


def model_call_attributes(agent: Any, input_kwargs: dict[str, Any]) -> dict[str, Any]:
    tool_context = getattr(getattr(agent, "state", None), "tool_context", None)
    activated_groups = list(getattr(tool_context, "activated_groups", None) or [])
    tool_names = []
    for schema in input_kwargs.get("tools") or []:
        function = schema.get("function") if isinstance(schema, dict) else None
        name = function.get("name") if isinstance(function, dict) else None
        if isinstance(name, str):
            tool_names.append(
                "web_search" if name == WEB_SEARCH_INTERNAL_TOOL_NAME else name
            )
    return {
        "activated_tool_groups": activated_groups,
        "available_tool_names": tool_names,
        "available_tool_count": len(tool_names),
        "tool_choice": enum_value(input_kwargs.get("tool_choice")),
    }


def tool_result_attributes(result: Any) -> dict[str, Any]:
    if result is None:
        return {}
    return {
        "tool_state": enum_value(getattr(result, "state", None)),
        "tool_output_preview": output_preview(result),
    }
