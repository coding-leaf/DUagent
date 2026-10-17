from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol

from agent_service_v2.runtime.edu_events import EduEvent, EduEventType, utc_now_iso
from agent_service_v2.runtime.sse import format_sse


class EventBus(Protocol):
    """Minimal in-memory event bus contract required by the broadcaster."""

    def publish(
        self,
        run_id: str,
        event_type: EduEventType,
        payload: dict | None = None,
    ) -> EduEvent: ...

    def publish_event(self, event: EduEvent) -> EduEvent: ...

    def complete(self, run_id: str) -> None: ...

    def subscribe(self, run_id: str) -> AsyncIterator[EduEvent]: ...


class EventStreamBroadcaster:
    """Decouples in-memory agent events from the outer SSE protocol.

    Callers only publish strongly typed `EduEventType` values; this adapter
    owns the event envelope (run id, conversation id, agent, timestamp) and
    the SSE serialization contract that the frontend consumes
    (`frontend/src/utils/chatStreamEvents.js`).
    """

    def __init__(
        self,
        *,
        bus: EventBus,
        run_id: str,
        conversation_id: str | None,
        agent: str = "edu_ai_chat_workbench",
    ) -> None:
        self._bus = bus
        self.run_id = run_id
        self.conversation_id = conversation_id
        self.agent = agent

    def emit(
        self,
        event_type: EduEventType,
        payload: dict[str, Any] | None = None,
    ) -> EduEvent:
        return self._bus.publish_event(
            EduEvent(
                type=event_type,
                run_id=self.run_id,
                conversation_id=self.conversation_id,
                seq=0,
                timestamp=utc_now_iso(),
                agent=self.agent,
                payload=payload or {},
            )
        )

    def thought(self, delta: str) -> EduEvent:
        return self.emit(EduEventType.THOUGHT, {"delta": delta})

    def text(self, delta: str) -> EduEvent:
        return self.emit(EduEventType.TEXT_DELTA, {"delta": delta})

    def fail(self, reason: str) -> EduEvent:
        event = self.emit(EduEventType.WORKFLOW_FAILED, {"reason": reason})
        self.complete()
        return event

    def complete(self) -> None:
        self._bus.complete(self.run_id)

    async def sse_events(self) -> AsyncIterator[str]:
        """Replay buffered events, then follow live events until completion."""
        async for event in self._bus.subscribe(self.run_id):
            yield format_sse(event)
