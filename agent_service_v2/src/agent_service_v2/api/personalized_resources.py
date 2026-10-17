from __future__ import annotations

import asyncio
import logging
from uuid import uuid4

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse

from agent_service_v2.schemas.personalized_resources import (
    PersonalizedResourceGenerationRequest,
)
from agent_service_v2.generators.personalized_resource_flow import (
    PersonalizedResourceGenerationRunner,
    PersonalizedResourceUnavailable,
)
from agent_service_v2.runtime.event_broadcaster import EventStreamBroadcaster
from agent_service_v2.session.generation_registry import GenerationSessionRegistry

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/agent/v2/personalized-resources",
    tags=["personalized-resources"],
)
GENERATION_AGENT_NAME = "personalized_resource_agent"
_sessions = GenerationSessionRegistry()


@router.post("/generations")
async def start_personalized_resource_generation(request: PersonalizedResourceGenerationRequest):
    """Start one in-memory generation run and stream its events separately."""
    runner = PersonalizedResourceGenerationRunner()
    try:
        runner.preflight()
    except PersonalizedResourceUnavailable as exc:
        return JSONResponse(
            status_code=503,
            content={"code": 503, "message": str(exc), "data": None},
        )

    session_id = f"gen_{uuid4().hex}"
    session = _sessions.create(
        session_id=session_id,
        task_id=request.task_id,
        conversation_id=request.conversation_id,
    )
    broadcaster = EventStreamBroadcaster(
        bus=session.bus,
        run_id=session_id,
        conversation_id=request.conversation_id,
        agent=GENERATION_AGENT_NAME,
    )

    async def run_generation() -> None:
        try:
            await runner.run(request, emit=broadcaster.emit)
        finally:
            broadcaster.complete()

    _sessions.attach_task(session_id, asyncio.create_task(run_generation()))
    return JSONResponse(
        status_code=202,
        content={
            "code": 202,
            "message": "accepted",
            "data": {
                "status": "started",
                "task_id": request.task_id,
                "session_id": session_id,
                "event_path": _event_path(session_id),
            },
        },
    )


@router.get("/generations/{session_id}/events")
async def stream_personalized_resource_events(session_id: str):
    session = _sessions.get(session_id)
    if session is None:
        return JSONResponse(
            status_code=404,
            content={"code": 404, "message": "generation session not found", "data": None},
        )
    broadcaster = EventStreamBroadcaster(
        bus=session.bus,
        run_id=session_id,
        conversation_id=session.conversation_id,
        agent=GENERATION_AGENT_NAME,
    )
    return StreamingResponse(
        broadcaster.sse_events(),
        media_type="text/event-stream",
    )


def _event_path(session_id: str) -> str:
    return f"/agent/v2/personalized-resources/generations/{session_id}/events"


def shutdown_generation_sessions() -> None:
    """Cancel in-flight generation tasks on application shutdown."""
    _sessions.clear()
