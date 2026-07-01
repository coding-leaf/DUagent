import asyncio
from pathlib import Path

from agentscope.event import (
    ReplyEndEvent,
    ReplyStartEvent,
    RequireUserConfirmEvent,
    TextBlockDeltaEvent,
)
from agentscope.message import ToolCallBlock

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


def test_workbench_session_streams_agent_events_to_run_bus(tmp_path: Path):
    class FakeAgent:
        async def reply_stream(self, _message):
            yield ReplyStartEvent(session_id="conv1", reply_id="reply1", name="workbench")
            yield TextBlockDeltaEvent(reply_id="reply1", block_id="block1", delta="今天先复习链表。")
            yield ReplyEndEvent(session_id="conv1", reply_id="reply1")

    class FakeFactory:
        def create_agent(self, **_kwargs):
            return FakeAgent()

    bus = WorkbenchRunBus()
    session = WorkbenchSession(
        run_bus=bus,
        workspace_manager=WorkbenchWorkspaceManager(root_dir=tmp_path),
        agent_factory=FakeFactory(),
    )

    async def run_session():
        run = await session.start_async(
            user_id="u1",
            course_id="c1",
            conversation_id="conv1",
            message="我今天应该学什么？",
            context={},
        )
        return run, await _collect(bus, run.run_id)

    run, events = asyncio.run(run_session())

    assert [event.type for event in events] == [
        EduEventType.WORKFLOW_STARTED,
        EduEventType.TEXT_DELTA,
        EduEventType.WORKFLOW_COMPLETED,
    ]
    assert events[1].payload == {"delta": "今天先复习链表。"}


def test_workbench_session_start_async_returns_before_agent_finishes(tmp_path: Path):
    release_agent = asyncio.Event()

    class SlowAgent:
        async def reply_stream(self, _message):
            yield ReplyStartEvent(session_id="conv1", reply_id="reply1", name="workbench")
            await release_agent.wait()
            yield TextBlockDeltaEvent(reply_id="reply1", block_id="block1", delta="完成。")
            yield ReplyEndEvent(session_id="conv1", reply_id="reply1")

    class FakeFactory:
        def create_agent(self, **_kwargs):
            return SlowAgent()

    async def run_session():
        bus = WorkbenchRunBus()
        session = WorkbenchSession(
            run_bus=bus,
            workspace_manager=WorkbenchWorkspaceManager(root_dir=tmp_path),
            agent_factory=FakeFactory(),
        )

        run = await asyncio.wait_for(
            session.start_async(
                user_id="u1",
                course_id="c1",
                conversation_id="conv1",
                message="我今天应该学什么？",
                context={},
            ),
            timeout=0.1,
        )
        first_event = await anext(bus.subscribe(run.run_id))
        release_agent.set()
        events = await _collect(bus, run.run_id)
        return first_event, events

    first_event, events = asyncio.run(run_session())

    assert first_event.type == EduEventType.WORKFLOW_STARTED
    assert [event.type for event in events] == [
        EduEventType.WORKFLOW_STARTED,
        EduEventType.TEXT_DELTA,
        EduEventType.WORKFLOW_COMPLETED,
    ]


def test_workbench_session_closes_run_when_tool_confirmation_is_required(tmp_path: Path):
    class ConfirmingAgent:
        async def reply_stream(self, _message):
            yield RequireUserConfirmEvent(
                reply_id="reply1",
                tool_calls=[
                    ToolCallBlock(
                        id="tool-1",
                        name="unsafe_tool",
                        input="{}",
                    )
                ],
            )

    class FakeFactory:
        def create_agent(self, **_kwargs):
            return ConfirmingAgent()

    bus = WorkbenchRunBus()
    session = WorkbenchSession(
        run_bus=bus,
        workspace_manager=WorkbenchWorkspaceManager(root_dir=tmp_path),
        agent_factory=FakeFactory(),
    )

    run = session.start(
        user_id="u1",
        course_id="c1",
        conversation_id="conv1",
        message="run unsafe tool",
        context={},
    )
    events = asyncio.run(_collect(bus, run.run_id))

    assert [event.type for event in events] == [
        EduEventType.DEBUG_LOG,
        EduEventType.WORKFLOW_FAILED,
    ]
    assert events[0].payload["event"] == "permission.required"
    assert events[0].payload["tool_calls"] == [
        {"id": "tool-1", "name": "unsafe_tool"}
    ]
    assert events[1].payload == {"reason": "user_confirmation_required"}
