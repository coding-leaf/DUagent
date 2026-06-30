from __future__ import annotations

from typing import Any

from agentscope.event import (
    ExceedMaxItersEvent,
    ModelCallEndEvent,
    ModelCallStartEvent,
    ReplyEndEvent,
    ReplyStartEvent,
    TextBlockEndEvent,
    TextBlockDeltaEvent,
    TextBlockStartEvent,
    ToolCallEndEvent,
    ToolCallStartEvent,
    ToolResultEndEvent,
    ToolResultStartEvent,
)

from agent_service_v2.runtime.edu_events import EduEvent, EduEventType, utc_now_iso


class EDUProtocolAdapter:
    def __init__(
        self,
        *,
        run_id: str,
        conversation_id: str | None,
        agent: str = "edu_ai_chat_workbench",
    ) -> None:
        self.run_id = run_id
        self.conversation_id = conversation_id
        self.agent = agent
        self._seq = 0

    def adapt(self, event: Any) -> EduEvent | None:
        mapped = self._map_event(event)
        if mapped is None:
            return None
        event_type, payload = mapped
        self._seq += 1
        return EduEvent(
            type=event_type,
            run_id=self.run_id,
            conversation_id=self.conversation_id,
            seq=self._seq,
            timestamp=utc_now_iso(),
            agent=self.agent,
            payload=payload,
        )

    def _map_event(self, event: Any) -> tuple[EduEventType, dict[str, Any]] | None:
        if isinstance(event, ReplyStartEvent):
            return EduEventType.WORKFLOW_STARTED, {
                "reply_id": event.reply_id,
                "session_id": event.session_id,
            }
        if isinstance(event, TextBlockDeltaEvent):
            return EduEventType.TEXT_DELTA, {"delta": event.delta}
        if isinstance(event, ToolCallStartEvent):
            return EduEventType.TOOL_STARTED, {
                "tool_call_id": event.tool_call_id,
                "tool_name": event.tool_call_name,
            }
        if isinstance(event, ToolResultEndEvent):
            return EduEventType.TOOL_COMPLETED, {
                "tool_call_id": event.tool_call_id,
                "state": getattr(event.state, "value", event.state),
            }
        if isinstance(event, ReplyEndEvent):
            return EduEventType.WORKFLOW_COMPLETED, {"reply_id": event.reply_id}
        if isinstance(event, ExceedMaxItersEvent):
            return EduEventType.WORKFLOW_FAILED, {
                "reply_id": event.reply_id,
                "reason": "exceed_max_iters",
            }
        if isinstance(
            event,
            (
                ModelCallStartEvent,
                ModelCallEndEvent,
                TextBlockStartEvent,
                TextBlockEndEvent,
                ToolCallEndEvent,
                ToolResultStartEvent,
            ),
        ):
            return None
        return EduEventType.WORKFLOW_FAILED, {
            "reason": "unsupported_agentscope_event",
            "event_class": event.__class__.__name__,
        }
