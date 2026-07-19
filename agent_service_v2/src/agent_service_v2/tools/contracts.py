from __future__ import annotations

from typing import Any, Literal


ToolOutcome = Literal["success", "neutral", "warning", "failure"]

_SUCCESS_STATUSES = {"available", "published", "ok", "success"}
_NEUTRAL_STATUSES = {"empty", "not_found"}
_WARNING_STATUSES = {"degraded"}
_FAILURE_STATUSES = {
    "rejected",
    "unavailable",
    "delivery_incomplete",
    "delivery_failed",
    "error",
}


def outcome_for_status(status: str | None, *, framework_error: bool = False) -> ToolOutcome:
    if framework_error:
        return "failure"
    normalized = str(status or "success").lower()
    if normalized in _SUCCESS_STATUSES:
        return "success"
    if normalized in _NEUTRAL_STATUSES:
        return "neutral"
    if normalized in _WARNING_STATUSES:
        return "warning"
    if normalized in _FAILURE_STATUSES:
        return "failure"
    return "failure"


def edu_tool_result(
    *,
    status: str,
    reason: str | None = None,
    summary: str | dict[str, Any] | None = None,
    retryable: bool = False,
    data: dict[str, Any] | None = None,
    artifact: dict[str, Any] | None = None,
    sources: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload = dict(data or {})
    result: dict[str, Any] = {
        "outcome": outcome_for_status(status),
        "status": status,
        "reason": reason,
        "summary": summary,
        "retryable": retryable,
        "data": payload,
        **payload,
    }
    if artifact is not None:
        result["artifact"] = artifact
    if sources is not None:
        result["sources"] = sources
    return result


def normalize_tool_result(
    value: dict[str, Any],
    *,
    default_status: str = "success",
) -> dict[str, Any]:
    status = str(value.get("status") or default_status)
    return edu_tool_result(
        status=status,
        reason=value.get("reason"),
        summary=value.get("summary"),
        retryable=bool(value.get("retryable")),
        data={
            key: item
            for key, item in value.items()
            if key not in {"outcome", "status", "reason", "summary", "retryable", "artifact", "sources"}
        },
        artifact=value.get("artifact") if isinstance(value.get("artifact"), dict) else None,
        sources=value.get("sources") if isinstance(value.get("sources"), list) else None,
    )
