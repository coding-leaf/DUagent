from __future__ import annotations

from typing import Any

from agent_service_v2.runtime.edu_events import EduEvent, EduEventType, utc_now_iso


class TeamEventAdapter:
    def __init__(self, *, run_id: str, conversation_id: str | None) -> None:
        self.run_id = run_id
        self.conversation_id = conversation_id
        self._seq = 0
        self._current_agent = "resource_team_leader"
        self._tool_names: dict[str, str] = {}

    def adapt(self, raw: dict[str, Any]) -> EduEvent | None:
        event_type = str(raw.get("type") or "").upper()
        if event_type == "REPLY_START":
            self._current_agent = _safe_agent_name(raw.get("name"))
            return self._event(
                EduEventType.AGENT_STARTED,
                {"role": self._current_agent},
            )
        if event_type == "TEXT_BLOCK_DELTA":
            return self._event(
                EduEventType.AGENT_MESSAGE,
                {"role": self._current_agent, "delta": str(raw.get("delta") or "")},
            )
        if event_type == "TOOL_CALL_START":
            tool_call_id = str(raw.get("tool_call_id") or "")
            tool_name = str(raw.get("tool_call_name") or "")
            self._tool_names[tool_call_id] = tool_name
            return self._event(
                EduEventType.TOOL_STARTED,
                {"tool_call_id": tool_call_id, "tool_name": tool_name},
            )
        if event_type == "TOOL_RESULT_END":
            tool_call_id = str(raw.get("tool_call_id") or "")
            tool_name = self._tool_names.get(tool_call_id, "")
            mapped_type = (
                EduEventType.CRITIC_COMPLETED
                if tool_name == "review_personalized_resource"
                else EduEventType.TOOL_COMPLETED
            )
            return self._event(
                mapped_type,
                {
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_name,
                    "state": str(raw.get("state") or "unknown"),
                },
            )
        if event_type == "REPLY_END":
            return self._event(EduEventType.WORKFLOW_COMPLETED, {})
        if event_type == "EXCEED_MAX_ITERS":
            return self._event(
                EduEventType.WORKFLOW_FAILED,
                {"reason": "exceed_max_iters"},
            )
        return None

    def _event(self, event_type: EduEventType, payload: dict[str, Any]) -> EduEvent:
        self._seq += 1
        return EduEvent(
            type=event_type,
            run_id=self.run_id,
            conversation_id=self.conversation_id,
            seq=self._seq,
            timestamp=utc_now_iso(),
            agent=self._current_agent,
            payload=payload,
        )


def _safe_agent_name(value: Any) -> str:
    name = str(value or "resource_team_leader")
    allowed = {"resource_team_leader", "resource_generator", "resource_reviewer"}
    return name if name in allowed else "resource_team_member"
