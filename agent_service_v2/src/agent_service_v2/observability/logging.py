from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

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
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record = {
        "event": event,
        "level": level,
        "message": message or event,
        "run_id": run_id,
        "conversation_id": conversation_id,
        "user_id": user_id,
        "course_id": course_id,
        "agent": agent,
        "timestamp": utc_now_iso(),
    }
    if duration_ms is not None:
        record["duration_ms"] = round(duration_ms, 2)
    if error:
        record["error"] = error
    if extra:
        record.update(extra)
    return record


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
        return build_log_record(
            event="agentscope.model.start",
            message=f"model start: {event.model_name}",
            run_id=run_id,
            conversation_id=conversation_id,
            user_id=user_id,
            course_id=course_id,
            agent=agent,
            extra={
                "source": "agentscope.event",
                "reply_id": event.reply_id,
                "event_class": event.__class__.__name__,
                "model": event.model_name,
            },
        )
    if isinstance(event, ModelCallEndEvent):
        return build_log_record(
            event="agentscope.model.end",
            message=f"model end: {event.input_tokens}/{event.output_tokens} tokens",
            run_id=run_id,
            conversation_id=conversation_id,
            user_id=user_id,
            course_id=course_id,
            agent=agent,
            extra={
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
