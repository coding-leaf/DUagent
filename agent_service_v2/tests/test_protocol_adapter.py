import json

from agentscope.event import (
    ExceedMaxItersEvent,
    ReplyEndEvent,
    ReplyStartEvent,
    TextBlockDeltaEvent,
    ToolCallStartEvent,
    ToolResultEndEvent,
)
from agentscope.message import ToolResultState

from agent_service_v2.runtime.edu_events import EduEventType
from agent_service_v2.runtime.protocol_adapter import EDUProtocolAdapter
from agent_service_v2.runtime.sse import format_sse


def test_protocol_adapter_maps_core_agentscope_events():
    adapter = EDUProtocolAdapter(
        run_id="run-1",
        conversation_id="conv-1",
        agent="workbench",
    )

    events = [
        adapter.adapt(ReplyStartEvent(session_id="conv-1", reply_id="reply-1", name="workbench")),
        adapter.adapt(TextBlockDeltaEvent(reply_id="reply-1", block_id="block-1", delta="你好")),
        adapter.adapt(ToolCallStartEvent(reply_id="reply-1", tool_call_id="tool-1", tool_call_name="TaskCreate")),
        adapter.adapt(ToolResultEndEvent(reply_id="reply-1", tool_call_id="tool-1", state=ToolResultState.SUCCESS)),
        adapter.adapt(ReplyEndEvent(session_id="conv-1", reply_id="reply-1")),
        adapter.adapt(ExceedMaxItersEvent(reply_id="reply-2", name="workbench")),
    ]

    assert [event.type for event in events] == [
        EduEventType.WORKFLOW_STARTED,
        EduEventType.TEXT_DELTA,
        EduEventType.TOOL_STARTED,
        EduEventType.TOOL_COMPLETED,
        EduEventType.WORKFLOW_COMPLETED,
        EduEventType.WORKFLOW_FAILED,
    ]
    assert [event.seq for event in events] == [1, 2, 3, 4, 5, 6]
    assert events[1].payload == {"delta": "你好"}
    assert events[2].payload == {"tool_call_id": "tool-1", "tool_name": "TaskCreate"}
    assert events[3].payload == {"tool_call_id": "tool-1", "state": "success"}


def test_format_sse_serializes_edu_event():
    adapter = EDUProtocolAdapter(
        run_id="run-1",
        conversation_id="conv-1",
        agent="workbench",
    )
    event = adapter.adapt(TextBlockDeltaEvent(reply_id="reply-1", block_id="block-1", delta="hi"))

    encoded = format_sse(event)

    assert encoded.startswith("data: ")
    assert encoded.endswith("\n\n")
    payload = json.loads(encoded.removeprefix("data: ").strip())
    assert payload["type"] == "text_delta"
    assert payload["payload"] == {"delta": "hi"}
