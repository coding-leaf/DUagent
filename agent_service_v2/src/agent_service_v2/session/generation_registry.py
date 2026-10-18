from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from agent_service_v2.session.run_bus import WorkbenchRunBus


MAX_TRACKED_SESSIONS = 200
DEFAULT_GENERATION_AGENT = "personalized_resource_agent"


@dataclass
class GenerationSession:
    """One in-memory personalized-resource generation session."""

    session_id: str
    task_id: str
    conversation_id: str | None
    bus: WorkbenchRunBus = field(default_factory=WorkbenchRunBus)
    task: asyncio.Task | None = None


class GenerationSessionRegistry:
    """In-memory registry backing the generation SSE endpoints.

    Sessions live in the Agent Service process only; the Backend stays the
    durable source of truth. Finished sessions are evicted oldest-first so a
    long-running service cannot grow without bound.
    """

    def __init__(self, *, max_sessions: int = MAX_TRACKED_SESSIONS) -> None:
        self._sessions: dict[str, GenerationSession] = {}
        self._max_sessions = max_sessions

    def create(
        self,
        *,
        session_id: str,
        task_id: str,
        conversation_id: str | None,
        agent: str = DEFAULT_GENERATION_AGENT,
    ) -> GenerationSession:
        session = GenerationSession(
            session_id=session_id,
            task_id=task_id,
            conversation_id=conversation_id,
        )
        session.bus.create_run(
            run_id=session_id,
            conversation_id=conversation_id,
            agent=agent,
        )
        self._sessions[session_id] = session
        self._evict_if_needed()
        return session

    def get(self, session_id: str) -> GenerationSession | None:
        return self._sessions.get(session_id)

    def attach_task(self, session_id: str, task: asyncio.Task) -> None:
        session = self._sessions.get(session_id)
        if session is not None:
            session.task = task
            task.add_done_callback(
                lambda _task, current=session_id: self._release(current)
            )

    async def cancel(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if session is None or session.task is None or session.task.done():
            return False
        session.task.cancel()
        return True

    def clear(self) -> None:
        for session in list(self._sessions.values()):
            if session.task is not None and not session.task.done():
                session.task.cancel()
        self._sessions.clear()

    def _release(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session is not None:
            session.task = None

    def _evict_if_needed(self) -> None:
        while len(self._sessions) > self._max_sessions:
            oldest_id = next(iter(self._sessions))
            oldest = self._sessions.pop(oldest_id)
            if oldest.task is not None and not oldest.task.done():
                oldest.task.cancel()
