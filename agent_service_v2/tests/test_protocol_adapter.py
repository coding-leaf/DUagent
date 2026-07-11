import json

from agentscope.event import (
    DataBlockDeltaEvent,
    ExceedMaxItersEvent,
    ModelCallEndEvent,
    ModelCallStartEvent,
    ReplyEndEvent,
    ReplyStartEvent,
    RequireUserConfirmEvent,
    TextBlockEndEvent,
    TextBlockDeltaEvent,
    TextBlockStartEvent,
    ThinkingBlockEndEvent,
    ThinkingBlockDeltaEvent,
    ThinkingBlockStartEvent,
    ToolCallDeltaEvent,
    ToolCallEndEvent,
    ToolCallStartEvent,
    ToolResultDataDeltaEvent,
    ToolResultEndEvent,
    ToolResultTextDeltaEvent,
    ToolResultStartEvent,
)
from agentscope.message import ToolCallBlock, ToolResultState

from agent_service_v2.artifacts.schemas import PublishedArtifact
from agent_service_v2.runtime.edu_events import EduEventType
from agent_service_v2.runtime.protocol_adapter import EDUProtocolAdapter
from agent_service_v2.runtime.sse import format_sse


class FakeArtifactPublisher:
    def __init__(self):
        self.calls = []

    def publish_new(self, *, seq_start=None):
        self.calls.append(seq_start)
        if len(self.calls) == 1:
            return [
                PublishedArtifact(
                    id="artifact_001_functions",
                    file="001-functions.md",
                    type="Markdown",
                    title="函数资料",
                    sha256="abc",
                    props={"title": "函数资料", "content": "# 函数资料\n"},
                    published_seq=seq_start,
                )
            ]
        return []


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
    assert events[3].payload == {
        "tool_call_id": "tool-1",
        "tool_name": "TaskCreate",
        "state": "success",
    }


def test_protocol_adapter_emits_plan_updated_for_planning_tools():
    adapter = EDUProtocolAdapter(
        run_id="run-1",
        conversation_id="conv-1",
        agent="workbench",
    )

    raw_events = [
        ToolCallStartEvent(reply_id="reply-1", tool_call_id="tool-1", tool_call_name="TaskCreate"),
        ToolCallDeltaEvent(
            reply_id="reply-1",
            tool_call_id="tool-1",
            delta='{"subject":"查询学习状态","description":"读取薄弱点"}',
        ),
        ToolResultTextDeltaEvent(
            reply_id="reply-1",
            tool_call_id="tool-1",
            delta="Task (id=1) created successfully: 查询学习状态",
        ),
        ToolResultEndEvent(reply_id="reply-1", tool_call_id="tool-1", state=ToolResultState.SUCCESS),
        ToolCallStartEvent(reply_id="reply-1", tool_call_id="tool-2", tool_call_name="TaskUpdate"),
        ToolCallDeltaEvent(
            reply_id="reply-1",
            tool_call_id="tool-2",
            delta='{"task_id":"1","status":"in_progress"}',
        ),
        ToolResultEndEvent(reply_id="reply-1", tool_call_id="tool-2", state=ToolResultState.SUCCESS),
    ]

    events = [
        event
        for raw_event in raw_events
        for event in adapter.adapt_many(raw_event)
    ]

    assert [event.type for event in events] == [
        EduEventType.TOOL_STARTED,
        EduEventType.TOOL_COMPLETED,
        EduEventType.PLAN_UPDATED,
        EduEventType.TOOL_STARTED,
        EduEventType.TOOL_COMPLETED,
        EduEventType.PLAN_UPDATED,
    ]
    assert events[2].payload == {
        "tasks": [
            {
                "id": "1",
                "title": "查询学习状态",
                "description": "读取薄弱点",
                "status": "pending",
            }
        ]
    }
    assert events[5].payload["tasks"][0]["status"] == "in_progress"


def test_protocol_adapter_passes_learning_tool_result_summary():
    adapter = EDUProtocolAdapter(run_id="run-1", conversation_id="conv-1")
    start = ToolCallStartEvent(
        reply_id="reply-1",
        tool_call_id="tool-1",
        tool_call_name="read_recent_answers",
    )
    result_text = json.dumps(
        {
            "status": "available",
            "summary": {"returned_count": 3, "has_more": False},
        }
    )
    delta = ToolResultTextDeltaEvent(
        reply_id="reply-1",
        tool_call_id="tool-1",
        delta=result_text,
    )
    end = ToolResultEndEvent(
        reply_id="reply-1",
        tool_call_id="tool-1",
        state=ToolResultState.SUCCESS,
    )

    assert adapter.adapt(start).type.value == "tool_started"
    assert adapter.adapt(delta) is None
    event = adapter.adapt(end)

    assert event.type.value == "tool_completed"
    assert event.payload["tool_name"] == "read_recent_answers"
    assert event.payload["status"] == "available"
    assert event.payload["returned_count"] == 3
    assert "3" in event.payload["output_summary"]


def test_protocol_adapter_emits_artifact_after_artifact_tool_success():
    publisher = FakeArtifactPublisher()
    adapter = EDUProtocolAdapter(
        run_id="run-1",
        conversation_id="conv-1",
        agent="workbench",
        artifact_publisher=publisher,
    )

    raw_events = [
        ToolCallStartEvent(reply_id="reply-1", tool_call_id="tool-1", tool_call_name="write_artifact_file"),
        ToolResultEndEvent(reply_id="reply-1", tool_call_id="tool-1", state=ToolResultState.SUCCESS),
    ]

    events = [event for raw_event in raw_events for event in adapter.adapt_many(raw_event)]

    assert [event.type for event in events] == [
        EduEventType.TOOL_STARTED,
        EduEventType.TOOL_COMPLETED,
        EduEventType.ARTIFACT_CREATED,
    ]
    assert events[2].payload == {
        "artifact": {
            "id": "artifact_001_functions",
            "type": "Markdown",
            "title": "函数资料",
            "props": {"title": "函数资料", "content": "# 函数资料\n"},
        }
    }


def test_protocol_adapter_scans_before_workflow_completed():
    publisher = FakeArtifactPublisher()
    adapter = EDUProtocolAdapter(
        run_id="run-1",
        conversation_id="conv-1",
        agent="workbench",
        artifact_publisher=publisher,
    )

    events = adapter.adapt_many(ReplyEndEvent(session_id="conv-1", reply_id="reply-1"))

    assert [event.type for event in events] == [
        EduEventType.ARTIFACT_CREATED,
        EduEventType.WORKFLOW_COMPLETED,
    ]


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


def test_protocol_adapter_ignores_normal_structural_events():
    adapter = EDUProtocolAdapter(
        run_id="run-1",
        conversation_id="conv-1",
        agent="workbench",
    )

    structural_events = [
        ModelCallStartEvent(reply_id="reply-1", model_name="deepseek"),
        TextBlockStartEvent(reply_id="reply-1", block_id="block-1"),
        TextBlockEndEvent(reply_id="reply-1", block_id="block-1"),
        ToolCallEndEvent(reply_id="reply-1", tool_call_id="tool-1"),
        ToolResultStartEvent(
            reply_id="reply-1",
            tool_call_id="tool-1",
            tool_call_name="TaskCreate",
        ),
        ModelCallEndEvent(reply_id="reply-1", input_tokens=12, output_tokens=8),
    ]

    assert [adapter.adapt(event) for event in structural_events] == [
        None,
        None,
        None,
        None,
        None,
        None,
    ]


def test_protocol_adapter_ignores_additional_streaming_delta_events():
    adapter = EDUProtocolAdapter(
        run_id="run-1",
        conversation_id="conv-1",
        agent="workbench",
    )

    events = [
        ToolCallDeltaEvent(reply_id="reply-1", tool_call_id="tool-1", delta='{"kind"'),
        ToolResultTextDeltaEvent(reply_id="reply-1", tool_call_id="tool-1", delta="partial result"),
        ToolResultDataDeltaEvent(
            reply_id="reply-1",
            tool_call_id="tool-1",
            media_type="application/json",
            data='{"ok":true}',
        ),
        DataBlockDeltaEvent(
            reply_id="reply-1",
            block_id="data-1",
            data='{"artifact":true}',
            media_type="application/json",
        ),
        ThinkingBlockDeltaEvent(reply_id="reply-1", block_id="think-1", delta="internal"),
    ]

    assert [adapter.adapt(event) for event in events] == [
        None,
        None,
        None,
        None,
        None,
    ]


def test_protocol_adapter_ignores_agent_internal_thinking_and_confirmation_events():
    adapter = EDUProtocolAdapter(
        run_id="run-1",
        conversation_id="conv-1",
        agent="workbench",
    )

    events = [
        ThinkingBlockStartEvent(reply_id="reply-1", block_id="think-1"),
        ThinkingBlockEndEvent(reply_id="reply-1", block_id="think-1"),
        RequireUserConfirmEvent(
            reply_id="reply-1",
            tool_calls=[
                ToolCallBlock(
                    id="tool-1",
                    name="read_learning_state",
                    input="{}",
                )
            ],
        ),
    ]

    assert [adapter.adapt(event) for event in events] == [
        None,
        None,
        None,
    ]
