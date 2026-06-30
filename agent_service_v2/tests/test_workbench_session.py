import asyncio
from pathlib import Path

from agent_service_v2.agents.workbench_factory import WorkbenchAgentFactory
from agent_service_v2.runtime.edu_events import EduEventType
from agent_service_v2.session.run_bus import WorkbenchRunBus
from agent_service_v2.session.workbench_session import WorkbenchSession
from agent_service_v2.workspaces.workbench_workspace_manager import (
    WorkbenchWorkspaceManager,
)


async def _collect(bus: WorkbenchRunBus, run_id: str):
    return [event async for event in bus.subscribe(run_id)]


def test_workbench_session_publishes_failed_event_when_model_missing(tmp_path: Path):
    bus = WorkbenchRunBus()
    session = WorkbenchSession(
        run_bus=bus,
        workspace_manager=WorkbenchWorkspaceManager(root_dir=tmp_path),
        agent_factory=WorkbenchAgentFactory(model_provider=lambda: None),
    )

    run = session.start(
        user_id="u1",
        course_id="c1",
        conversation_id="conv1",
        message="我今天应该学什么？",
        context={},
    )

    events = asyncio.run(_collect(bus, run.run_id))

    assert len(events) == 1
    assert events[0].type == EduEventType.WORKFLOW_FAILED
    assert events[0].payload == {"reason": "model_not_configured"}
