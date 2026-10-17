from __future__ import annotations

import asyncio
import json

from agent_service_v2.runtime.edu_events import EduEventType
from agent_service_v2.runtime.event_broadcaster import EventStreamBroadcaster
from agent_service_v2.session.generation_registry import GenerationSessionRegistry
from agent_service_v2.session.run_bus import WorkbenchRunBus


def test_broadcaster_serializes_standard_sse_event_types():
    bus = WorkbenchRunBus()
    bus.create_run(run_id="gen_1", conversation_id="conv-1")
    broadcaster = EventStreamBroadcaster(
        bus=bus,
        run_id="gen_1",
        conversation_id="conv-1",
        agent="personalized_resource_agent",
    )

    broadcaster.emit(EduEventType.WORKFLOW_STARTED, {"task_id": "task-1"})
    broadcaster.thought("先检索教材")
    broadcaster.text("指针保存地址")
    broadcaster.emit(
        EduEventType.TOOL_STARTED,
        {"tool_call_id": "tool-1", "tool_name": "review_personalized_resource"},
    )
    broadcaster.emit(
        EduEventType.TOOL_COMPLETED,
        {
            "tool_call_id": "tool-1",
            "tool_name": "review_personalized_resource",
            "status": "completed",
        },
    )
    broadcaster.emit(EduEventType.WORKFLOW_COMPLETED, {"message_id": "msg-1"})
    broadcaster.complete()

    async def collect() -> list[dict]:
        payloads = []
        async for chunk in broadcaster.sse_events():
            assert chunk.startswith("data: ")
            assert chunk.endswith("\n\n")
            payloads.append(json.loads(chunk[len("data: ") :]))
        return payloads

    events = asyncio.run(collect())

    assert [event["type"] for event in events] == [
        "workflow_started",
        "thought",
        "text_delta",
        "tool_started",
        "tool_completed",
        "workflow_completed",
    ]
    assert [event["seq"] for event in events] == [1, 2, 3, 4, 5, 6]
    assert events[1]["payload"] == {"delta": "先检索教材"}
    assert events[2]["payload"] == {"delta": "指针保存地址"}
    assert all(event["run_id"] == "gen_1" for event in events)
    assert all(event["conversation_id"] == "conv-1" for event in events)
    assert all(event["agent"] == "personalized_resource_agent" for event in events)


def test_broadcaster_fail_closes_stream_with_workflow_failed():
    bus = WorkbenchRunBus()
    bus.create_run(run_id="gen_2", conversation_id=None)
    broadcaster = EventStreamBroadcaster(
        bus=bus,
        run_id="gen_2",
        conversation_id=None,
    )

    broadcaster.fail("model_not_configured")

    async def collect() -> list[dict]:
        return [
            json.loads(chunk[len("data: ") :])
            async for chunk in broadcaster.sse_events()
        ]

    events = asyncio.run(collect())

    assert [event["type"] for event in events] == ["workflow_failed"]
    assert events[0]["payload"] == {"reason": "model_not_configured"}


def test_generation_registry_tracks_and_evicts_sessions():
    registry = GenerationSessionRegistry(max_sessions=2)
    first = registry.create(session_id="gen_a", task_id="t1", conversation_id=None)
    registry.create(session_id="gen_b", task_id="t2", conversation_id=None)
    registry.create(session_id="gen_c", task_id="t3", conversation_id=None)

    assert registry.get("gen_a") is None
    assert registry.get(first.session_id) is None
    assert registry.get("gen_b") is not None
    assert registry.get("gen_c") is not None


def test_generation_registry_creates_buffered_run_bus():
    registry = GenerationSessionRegistry()
    session = registry.create(
        session_id="gen_x",
        task_id="task-9",
        conversation_id="conv-9",
    )

    event = session.bus.publish(
        session.session_id,
        EduEventType.WORKFLOW_STARTED,
        {"task_id": "task-9"},
    )

    assert event.run_id == "gen_x"
    assert event.conversation_id == "conv-9"
    assert event.agent == "personalized_resource_agent"


def test_generation_registry_cancel_marks_task_cancelled():
    registry = GenerationSessionRegistry()
    session = registry.create(
        session_id="gen_y",
        task_id="task-y",
        conversation_id=None,
    )

    async def scenario() -> bool:
        task = asyncio.create_task(asyncio.sleep(30))
        registry.attach_task(session.session_id, task)
        cancelled = await registry.cancel(session.session_id)
        try:
            await task
        except asyncio.CancelledError:
            pass
        return cancelled

    assert asyncio.run(scenario()) is True
