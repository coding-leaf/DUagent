from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from agent_service_v2.agents.workbench_factory import WorkbenchAgentFactory
from agent_service_v2.runtime.sse import format_sse
from agent_service_v2.schemas.workbench import WorkbenchChatRequest
from agent_service_v2.session.run_bus import WorkbenchRunBus
from agent_service_v2.session.workbench_session import WorkbenchSession
from agent_service_v2.workspaces.workbench_workspace_manager import (
    WorkbenchWorkspaceManager,
)

router = APIRouter(prefix="/agent/v2/workbench", tags=["workbench"])


@router.post("/chat")
async def workbench_chat(req: WorkbenchChatRequest) -> StreamingResponse:
    run_bus = WorkbenchRunBus()
    session = WorkbenchSession(
        run_bus=run_bus,
        workspace_manager=WorkbenchWorkspaceManager(root_dir=_workspace_root()),
        agent_factory=create_agent_factory(),
    )
    run = await session.start_async(
        user_id=req.user_id,
        course_id=req.course_id if req.scope == "course" else None,
        conversation_id=req.conversation_id,
        message=req.message,
        context=req.context,
    )

    async def event_stream():
        async for event in run_bus.subscribe(run.run_id):
            yield format_sse(event)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[3] / "workspaces"


def create_agent_factory() -> WorkbenchAgentFactory:
    return WorkbenchAgentFactory(model_provider=lambda: None)
