from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from uuid import uuid4

from agent_service_v2.runtime.edu_events import EduEvent, EduEventType, utc_now_iso


@dataclass(frozen=True)
class WorkbenchRun:
    run_id: str
    conversation_id: str | None
    agent: str


@dataclass
class _RunState:
    run: WorkbenchRun
    events: list[EduEvent] = field(default_factory=list)
    closed: bool = False
    waiters: list[asyncio.Event] = field(default_factory=list)


class WorkbenchRunBus:
    def __init__(self) -> None:
        self._runs: dict[str, _RunState] = {}

    def create_run(
        self,
        *,
        conversation_id: str | None,
        agent: str = "edu_ai_chat_workbench",
    ) -> WorkbenchRun:
        run = WorkbenchRun(
            run_id=f"run_{uuid4().hex}",
            conversation_id=conversation_id,
            agent=agent,
        )
        self._runs[run.run_id] = _RunState(run=run)
        return run

    def publish(
        self,
        run_id: str,
        event_type: EduEventType,
        payload: dict | None = None,
    ) -> EduEvent:
        state = self._get_run(run_id)
        event = EduEvent(
            type=event_type,
            run_id=run_id,
            conversation_id=state.run.conversation_id,
            seq=len(state.events) + 1,
            timestamp=utc_now_iso(),
            agent=state.run.agent,
            payload=payload or {},
        )
        state.events.append(event)
        self._notify(state)
        return event

    def publish_event(self, event: EduEvent) -> EduEvent:
        state = self._get_run(event.run_id)
        next_seq = len(state.events) + 1
        if event.seq != next_seq:
            event = EduEvent(
                type=event.type,
                run_id=event.run_id,
                conversation_id=event.conversation_id,
                seq=next_seq,
                timestamp=event.timestamp,
                agent=event.agent,
                payload=event.payload,
            )
        state.events.append(event)
        self._notify(state)
        return event

    def complete(self, run_id: str) -> None:
        state = self._get_run(run_id)
        state.closed = True
        self._notify(state)

    def fail(self, run_id: str, *, reason: str) -> EduEvent:
        event = self.publish(run_id, EduEventType.WORKFLOW_FAILED, {"reason": reason})
        self.complete(run_id)
        return event

    async def subscribe(self, run_id: str):
        state = self._get_run(run_id)
        index = 0
        while True:
            while index < len(state.events):
                event = state.events[index]
                index += 1
                yield event
            if state.closed:
                break
            waiter = asyncio.Event()
            state.waiters.append(waiter)
            await waiter.wait()

    def _get_run(self, run_id: str) -> _RunState:
        try:
            return self._runs[run_id]
        except KeyError as exc:
            raise KeyError(f"unknown run_id: {run_id}") from exc

    def _notify(self, state: _RunState) -> None:
        waiters = state.waiters
        state.waiters = []
        for waiter in waiters:
            waiter.set()
