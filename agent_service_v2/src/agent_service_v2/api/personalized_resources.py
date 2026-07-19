import json

import httpx
from agentscope.app.message_bus import MessageBusKeys
from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse

from agent_service_v2.agents.model_provider import AgentModelSettings
from agent_service_v2.agents.team_permissions import build_leader_permission_context
from agent_service_v2.agents.resource_team_leader import ResourceTeamRequest
from agent_service_v2.team.runtime_client import (
    OfficialTeamRuntimeClient,
    TeamRuntimeUnavailable,
)
from agent_service_v2.team_app import team_runtime_app
from agent_service_v2.runtime.team_event_adapter import TeamEventAdapter

router = APIRouter(prefix="/agent/v2/personalized-resources", tags=["personalized-resources"])
_TEAM_RUN_REGISTRY = "eduagent:resource_team_runs"


@router.post("/generations")
async def start_personalized_resource_generation(request: ResourceTeamRequest):
    async def grant_permissions(user_id: str, agent_id: str, session_id: str) -> None:
        storage = team_runtime_app.state.storage
        session = await storage.get_session(user_id, agent_id, session_id)
        state = session.state.model_copy(
            update={"permission_context": build_leader_permission_context()}
        )
        await storage.upsert_session(
            user_id=user_id,
            agent_id=agent_id,
            config=session.config,
            state=state,
            session_id=session_id,
            source=session.source,
            source_schedule_id=session.source_schedule_id,
        )

    runtime = OfficialTeamRuntimeClient(
        settings=AgentModelSettings(),
        transport=httpx.ASGITransport(app=team_runtime_app),
        grant_permissions=grant_permissions,
    )
    try:
        data = await runtime.start(request)
    except TeamRuntimeUnavailable as exc:
        return JSONResponse(
            status_code=503,
            content={"code": 503, "message": str(exc), "data": None},
        )
    session_id = data["session_id"]
    await team_runtime_app.state.message_bus.registry_set(
        _TEAM_RUN_REGISTRY,
        session_id,
        json.dumps(
            {
                "run_id": request.task_id,
                "conversation_id": request.conversation_id or "",
            }
        ),
        ttl_secs=86400,
    )
    product_data = {
        **data,
        "event_path": f"/agent/v2/personalized-resources/generations/{session_id}/events",
    }
    return JSONResponse(
        status_code=202,
        content={"code": 202, "message": "accepted", "data": product_data},
    )


@router.get("/generations/{session_id}/events")
async def stream_personalized_resource_events(session_id: str):
    stored_runs = await team_runtime_app.state.message_bus.registry_getall(
        _TEAM_RUN_REGISTRY
    )
    raw_run = stored_runs.get(session_id)
    if raw_run is None:
        return JSONResponse(
            status_code=404,
            content={"code": 404, "message": "generation session not found", "data": None},
        )
    run = json.loads(raw_run)
    adapter = TeamEventAdapter(
        run_id=run["run_id"],
        conversation_id=run["conversation_id"] or None,
    )
    message_bus = team_runtime_app.state.message_bus

    async def events():
        key = MessageBusKeys.session_events(session_id)
        for _entry_id, raw in await message_bus.log_read(
            key, max_count=MessageBusKeys.SESSION_REPLAY_MAX_LEN
        ):
            event = adapter.adapt(raw)
            if event:
                yield _sse(event.to_dict())
        async for raw in message_bus.subscribe(key):
            event = adapter.adapt(raw)
            if event:
                yield _sse(event.to_dict())

    return StreamingResponse(events(), media_type="text/event-stream")


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
