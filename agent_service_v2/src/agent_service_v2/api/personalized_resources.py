import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from agent_service_v2.agents.model_provider import AgentModelSettings
from agent_service_v2.agents.resource_team_leader import ResourceTeamRequest
from agent_service_v2.team.runtime_client import (
    OfficialTeamRuntimeClient,
    TeamRuntimeUnavailable,
)
from agent_service_v2.team_app import team_runtime_app

router = APIRouter(prefix="/agent/v2/personalized-resources", tags=["personalized-resources"])


@router.post("/generations")
async def start_personalized_resource_generation(request: ResourceTeamRequest):
    runtime = OfficialTeamRuntimeClient(
        settings=AgentModelSettings(),
        transport=httpx.ASGITransport(app=team_runtime_app),
    )
    try:
        data = await runtime.start(request)
    except TeamRuntimeUnavailable as exc:
        return JSONResponse(
            status_code=503,
            content={"code": 503, "message": str(exc), "data": None},
        )
    return JSONResponse(
        status_code=202,
        content={"code": 202, "message": "accepted", "data": data},
    )
