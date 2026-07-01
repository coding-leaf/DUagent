from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agent_service_v2.runtime.edu_events import utc_now_iso

LogSink = Callable[[dict[str, Any]], None]


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
