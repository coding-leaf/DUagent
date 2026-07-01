from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from agentscope.event import ModelCallEndEvent, ModelCallStartEvent

from agent_service_v2.runtime.edu_events import utc_now_iso

LogSink = Callable[[dict[str, Any]], None]
MAX_PREVIEW_CHARS = 2048
SENSITIVE_KEYS = {"api_key", "authorization", "password", "secret", "token"}


def build_log_record(
    *,
    event: str,
    run_id: str,
    conversation_id: str | None,
    user_id: str,
    course_id: str | None,
    agent: str,
    level: str = "info",
    message: str | None = None,
    duration_ms: float | None = None,
    error: str | None = None,
    error_message: str | None = None,
    trace_id: str | None = None,
    span_id: str | None = None,
    parent_span_id: str | None = None,
    span_kind: str = "event",
    name: str | None = None,
    phase: str | None = None,
    attributes: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    merged_attributes = dict(attributes or {})
    if extra:
        merged_attributes.update(extra)

    record = {
        "event": event,
        "level": level,
        "message": message or name or event,
        "run_id": run_id,
        "conversation_id": conversation_id,
        "user_id": user_id,
        "course_id": course_id,
        "agent": agent,
        "trace_id": trace_id or run_id,
        "span_id": span_id or new_span_id(run_id, event),
        "parent_span_id": parent_span_id,
        "span_kind": span_kind,
        "name": name or event,
        "phase": phase or _phase_from_event(event),
        "timestamp": utc_now_iso(),
        "attributes": merged_attributes,
    }
    if duration_ms is not None:
        record["duration_ms"] = round(duration_ms, 2)
        record["attributes"]["duration_ms"] = record["duration_ms"]
    if error:
        record["error"] = {
            "type": error,
            "message": error_message or error,
        }
        record["error_type"] = error
        record["attributes"]["error_type"] = error
        record["attributes"]["error_message"] = error_message or error
    if extra:
        record.update(extra)
    return record


def new_span_id(run_id: str, name: str) -> str:
    safe_name = name.replace(" ", "_").replace(".", "_").replace(":", "_")
    return f"span_{run_id}_{safe_name}_{uuid4().hex[:8]}"


def input_preview(value: Any) -> str:
    return _truncate(_serialize_preview(value))


def output_preview(value: Any) -> str:
    return _truncate(_serialize_preview(value))


def enum_value(value: Any) -> str:
    return getattr(value, "value", value)


def build_agentscope_event_log(
    event: Any,
    *,
    run_id: str,
    conversation_id: str | None,
    user_id: str,
    course_id: str | None,
    agent: str,
) -> dict[str, Any] | None:
    if isinstance(event, ModelCallStartEvent):
        span_id = f"span_{run_id}_agentscope_model_{event.reply_id}"
        return build_log_record(
            event="agentscope.model.start",
            message=f"model start: {event.model_name}",
            run_id=run_id,
            conversation_id=conversation_id,
            user_id=user_id,
            course_id=course_id,
            agent=agent,
            span_id=span_id,
            span_kind="model",
            name=f"model.call {event.model_name}",
            phase="start",
            attributes={
                "source": "agentscope.event",
                "reply_id": event.reply_id,
                "event_class": event.__class__.__name__,
                "model": event.model_name,
            },
        )
    if isinstance(event, ModelCallEndEvent):
        span_id = f"span_{run_id}_agentscope_model_{event.reply_id}"
        return build_log_record(
            event="agentscope.model.end",
            message=f"model end: {event.input_tokens}/{event.output_tokens} tokens",
            run_id=run_id,
            conversation_id=conversation_id,
            user_id=user_id,
            course_id=course_id,
            agent=agent,
            span_id=span_id,
            span_kind="model",
            name="model.call",
            phase="end",
            attributes={
                "source": "agentscope.event",
                "reply_id": event.reply_id,
                "event_class": event.__class__.__name__,
                "input_tokens": event.input_tokens,
                "output_tokens": event.output_tokens,
            },
        )
    return None


def _serialize_preview(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return _serialize_string_preview(value)
    if isinstance(value, list):
        return "\n".join(_serialize_preview(item) for item in value)
    text = _block_text(value)
    if text is not None:
        return text
    if hasattr(value, "content"):
        return _serialize_preview(getattr(value, "content"))
    if hasattr(value, "output"):
        return _serialize_preview(getattr(value, "output"))
    return str(value)


def _serialize_string_preview(value: str) -> str:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return value
    return json.dumps(_redact(parsed), ensure_ascii=False, separators=(",", ":"))


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "<redacted>" if key.lower() in SENSITIVE_KEYS else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _block_text(value: Any) -> str | None:
    if hasattr(value, "text"):
        return str(getattr(value, "text"))
    if hasattr(value, "data"):
        return _serialize_preview(getattr(value, "data"))
    return None


def _truncate(value: str) -> str:
    if len(value) <= MAX_PREVIEW_CHARS:
        return value
    return f"{value[:MAX_PREVIEW_CHARS]}...[truncated]"


def _phase_from_event(event: str) -> str:
    suffix = event.rsplit(".", maxsplit=1)[-1]
    if suffix in {"start", "end", "error"}:
        return suffix
    return "event"
