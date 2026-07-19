import asyncio

from agent_service_v2.runtime.edu_events import EduEventType
from agent_service_v2.session.run_bus import WorkbenchRunBus


async def _collect(bus: WorkbenchRunBus, run_id: str):
    return [event async for event in bus.subscribe(run_id)]


def test_run_bus_buffers_events_for_late_subscriber():
    bus = WorkbenchRunBus()
    run = bus.create_run(conversation_id="conv-1", agent="workbench")

    first = bus.publish(run.run_id, EduEventType.WORKFLOW_STARTED, {"message": "started"})
    second = bus.publish(run.run_id, EduEventType.TEXT_DELTA, {"delta": "hello"})
    bus.complete(run.run_id)

    events = asyncio.run(_collect(bus, run.run_id))

    assert run.run_id.startswith("run_")
    assert [event.seq for event in events] == [1, 2]
    assert events[0] == first
    assert events[1] == second
    assert events[0].conversation_id == "conv-1"


def test_run_bus_failed_run_publishes_workflow_failed_and_closes_stream():
    bus = WorkbenchRunBus()
    run = bus.create_run(conversation_id="conv-2")

    failed = bus.fail(run.run_id, reason="model_not_configured")

    events = asyncio.run(_collect(bus, run.run_id))

    assert failed.type == EduEventType.WORKFLOW_FAILED
    assert failed.payload == {"reason": "model_not_configured"}
    assert events == [failed]
