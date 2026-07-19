import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from app.services.agent_client import AgentServiceError
from app.services.tutoring_stream_adapter import StreamState, TutoringStreamAdapter, _client_artifact


def test_workbench_payload_keeps_offering_and_catalog_ids_separate():
    result = TutoringStreamAdapter._build_workbench_payload(
        {
            "user_id": "student-1",
            "scope": "course",
            "course_id": "offering-1",
            "catalog_id": "catalog-1",
            "conversation_id": "conv-1",
            "message": "练习指针",
        }
    )

    assert result["course_id"] == "offering-1"
    assert result["catalog_id"] == "catalog-1"


def test_stream_adapter_persists_text_and_tool_event_order():
    state = StreamState(conversation_id="conv-1", assistant_message_id="msg-1")

    TutoringStreamAdapter._adapt_data(
        '{"type":"text_delta","payload":{"delta":"before"}}', state
    )
    TutoringStreamAdapter._adapt_data(
        '{"type":"tool_started","payload":{"tool_call_id":"t1","tool_name":"read_profile"}}', state
    )
    TutoringStreamAdapter._adapt_data(
        '{"type":"tool_completed","payload":{"tool_call_id":"t1","state":"success"}}', state
    )
    TutoringStreamAdapter._adapt_data(
        '{"type":"text_delta","payload":{"delta":"after"}}', state
    )

    assert [event["type"] for event in state.meta["event_timeline"]] == [
        "text_delta",
        "tool_started",
        "tool_completed",
        "text_delta",
    ]


@pytest.mark.asyncio
async def test_stream_adapter_forwards_v2_events_with_backend_envelope():
    calls = []

    async def source(path, payload):
        calls.append((path, payload))
        yield b'data: {"type":"workflow_started","run_id":"run-1","conversation_id":"agent-conv","seq":1,"timestamp":"t1","agent":"workbench","payload":{"reply_id":"r1"}}\n\n'
        yield b'data: {"type":"text_delta","run_id":"run-1","conversation_id":"agent-conv","seq":2,"timestamp":"t2","agent":"workbench","payload":{"delta":"hello"}}\n\n'
        yield b'data: {"type":"workflow_completed","run_id":"run-1","conversation_id":"agent-conv","seq":3,"timestamp":"t3","agent":"workbench","payload":{"reply_id":"r1"}}\n\n'

    persisted = AsyncMock()
    recorded_log = AsyncMock()
    adapter = TutoringStreamAdapter(
        stream_sse=source,
        persist_result=persisted,
        record_agent_log=recorded_log,
    )
    events = []
    async for event in adapter.stream(
        payload={
            "user_id": "u1",
            "scope": "course",
            "course_id": "course-1",
            "conversation_id": "conv-1",
            "message": "x",
        },
        conversation_id="conv-1",
        assistant_message_id="msg-1",
    ):
        if json.loads(event["data"])["type"] == "workflow_completed":
            assert persisted.await_count == 1
        events.append(event)

    decoded = [json.loads(event["data"]) for event in events]
    assert calls[0][0] == "/agent/v2/workbench/chat"
    assert calls[0][1]["context"]["message"] == "x"
    assert [item["type"] for item in decoded] == [
        "workflow_started",
        "text_delta",
        "workflow_completed",
    ]
    assert decoded[1]["payload"] == {"delta": "hello"}
    assert decoded[1]["conversation_id"] == "conv-1"
    assert decoded[1]["message_id"] == "msg-1"
    assert decoded[1]["run_id"] == "run-1"
    persisted.assert_awaited_once_with(
        "msg-1", "conv-1", "hello", [], [], {"agent_run_id": "run-1"}
    )
    recorded_log.assert_awaited_once()
    record = recorded_log.await_args.args[0]
    assert record.endpoint == "/agent/v2/workbench/chat"
    assert record.status == "success"
    assert record.tokens_used == 0


@pytest.mark.asyncio
async def test_stream_adapter_does_not_filter_tool_source_or_artifact_events():
    async def source(path, payload):
        yield b'data: {"type":"tool_started","run_id":"run-1","seq":1,"timestamp":"t1","agent":"workbench","payload":{"tool_call_id":"tool-1","tool_name":"TaskCreate"}}\n\n'
        yield b'data: {"type":"tool_completed","run_id":"run-1","seq":2,"timestamp":"t2","agent":"workbench","payload":{"tool_call_id":"tool-1","state":"success"}}\n\n'
        yield b'data: {"type":"source_refs","run_id":"run-1","seq":3,"timestamp":"t3","agent":"workbench","payload":{"sources":[{"title":"Array"}]}}\n\n'
        yield (
            'data: {"type":"artifact_created","run_id":"run-1","seq":4,"timestamp":"t4","agent":"workbench","payload":{"artifact":{"id":"a1","type":"Markdown","props":{"title":"函数资料","content":"# Plan"}}}}\n\n'
        ).encode("utf-8")

    persisted = AsyncMock()
    adapter = TutoringStreamAdapter(stream_sse=source, persist_result=persisted)
    events = [
        event
        async for event in adapter.stream(
            payload={"message": "x"},
            conversation_id="conv-1",
            assistant_message_id="msg-1",
        )
    ]

    decoded = [json.loads(event["data"]) for event in events]
    assert [item["type"] for item in decoded] == [
        "tool_started",
        "tool_completed",
        "source_refs",
        "artifact_created",
    ]
    assert decoded[0]["payload"]["tool_name"] == "TaskCreate"
    assert decoded[3]["payload"]["artifact"]["type"] == "Markdown"
    assert decoded[3]["payload"]["artifact"]["props"]["title"] == "函数资料"
    persisted.assert_awaited_once_with(
        "msg-1",
        "conv-1",
        "",
        [],
        [],
            {
                "agent_run_id": "run-1",
                "tool_events": [
                {
                    "type": "tool_started",
                    "payload": {
                        "tool_call_id": "tool-1",
                        "tool_name": "TaskCreate",
                    },
                },
                {
                    "type": "tool_completed",
                    "payload": {
                        "tool_call_id": "tool-1",
                        "state": "success",
                    },
                },
                ],
                "sources": [{"title": "Array"}],
                "artifacts": [
                {
                    "id": "a1",
                    "type": "Markdown",
                    "props": {"title": "函数资料", "content": "# Plan"},
                }
            ]
        },
    )


@pytest.mark.asyncio
async def test_stream_adapter_persists_partial_text_delta_when_closed():
    blocker = asyncio.Event()

    async def source(path, payload):
        yield b'data: {"type":"text_delta","payload":{"delta":"partial"}}\n\n'
        await blocker.wait()

    persisted = AsyncMock()
    adapter = TutoringStreamAdapter(stream_sse=source, persist_result=persisted)
    stream = adapter.stream(
        payload={},
        conversation_id="conv-1",
        assistant_message_id="msg-1",
    )
    first = await anext(stream)
    assert json.loads(first["data"])["payload"]["delta"] == "partial"
    await stream.aclose()

    persisted.assert_awaited_once_with("msg-1", "conv-1", "partial", [], [], {})


@pytest.mark.asyncio
async def test_stream_adapter_emits_workflow_failed_on_agent_service_error():
    async def source(path, payload):
        if False:
            yield b""
        raise AgentServiceError("offline", status_code=503)

    persisted = AsyncMock()
    adapter = TutoringStreamAdapter(stream_sse=source, persist_result=persisted)
    events = [
        event
        async for event in adapter.stream(
            payload={"message": "x"},
            conversation_id="conv-1",
            assistant_message_id="msg-1",
        )
    ]

    decoded = [json.loads(event["data"]) for event in events]
    assert decoded == [
        {
            "type": "workflow_failed",
            "run_id": None,
            "conversation_id": "conv-1",
            "message_id": "msg-1",
            "seq": None,
            "timestamp": decoded[0]["timestamp"],
            "agent": "backend_proxy",
            "payload": {
                "reason": "agent_service_unavailable",
                "message": "Agent 服务暂时不可用",
            },
        }
    ]
    persisted.assert_awaited_once_with("msg-1", "conv-1", "", [], [], {})


@pytest.mark.asyncio
async def test_stream_adapter_forwards_invalid_json_without_accumulating_it():
    async def source(path, payload):
        yield b"data: not-json\n\n"

    persisted = AsyncMock()
    adapter = TutoringStreamAdapter(stream_sse=source, persist_result=persisted)
    events = [
        event
        async for event in adapter.stream(
            payload={},
            conversation_id="conv-1",
            assistant_message_id="msg-1",
        )
    ]

    assert events == [{"event": "message", "data": "not-json"}]
    persisted.assert_awaited_once_with("msg-1", "conv-1", "", [], [], {})


@pytest.mark.asyncio
async def test_stream_adapter_persists_content_safety_review_meta():
    async def source(path, payload):
        yield b'data: {"type":"text_delta","run_id":"run-1","seq":1,"timestamp":"t1","agent":"workbench","payload":{"delta":"hello"}}\n\n'
        yield b'data: {"type":"content_safety_reviewed","run_id":"run-1","seq":2,"timestamp":"t2","agent":"workbench","payload":{"passed":false,"risk_level":"high","categories":["illegal_instruction"],"reason":"risk","action":"flag","confidence":0.8,"scope":"content_safety_only","knowledge_reviewed":false,"reviewer":"external_model"}}\n\n'
        yield b'data: {"type":"workflow_completed","run_id":"run-1","seq":3,"timestamp":"t3","agent":"workbench","payload":{"reply_id":"r1"}}\n\n'

    persisted = AsyncMock()
    adapter = TutoringStreamAdapter(stream_sse=source, persist_result=persisted)
    events = [
        event
        async for event in adapter.stream(
            payload={"message": "x"},
            conversation_id="conv-1",
            assistant_message_id="msg-1",
        )
    ]

    decoded = [json.loads(event["data"]) for event in events]
    assert [item["type"] for item in decoded] == [
        "text_delta",
        "content_safety_reviewed",
        "workflow_completed",
    ]
    persisted.assert_awaited_once_with(
        "msg-1",
        "conv-1",
        "hello",
        [],
        [],
            {
                "agent_run_id": "run-1",
                "content_safety_review": {
                "passed": False,
                "risk_level": "high",
                "categories": ["illegal_instruction"],
                "reason": "risk",
                "action": "flag",
                "confidence": 0.8,
                "scope": "content_safety_only",
                "knowledge_reviewed": False,
                "reviewer": "external_model",
            }
        },
    )


@pytest.mark.asyncio
async def test_stream_adapter_discards_partial_content_when_safety_blocks():
    async def source(path, payload):
        yield b'data: {"type":"text_delta","run_id":"run-1","seq":1,"timestamp":"t1","agent":"workbench","payload":{"delta":"partial safe prefix"}}\n\n'
        yield b'data: {"type":"content_safety_reviewed","run_id":"run-1","seq":2,"timestamp":"t2","agent":"workbench","payload":{"passed":false,"risk_level":"critical","categories":["dangerous_instructions"],"reason":"operational_harm_request","action":"block","confidence":0.96,"scope":"content_safety_only","knowledge_reviewed":false,"reviewer":"semantic_model","match_count":1}}\n\n'
        yield 'data: {"type":"text_delta","run_id":"run-1","seq":3,"timestamp":"t3","agent":"workbench","payload":{"delta":"抱歉，我无法回答你的问题。"}}\n\n'.encode()
        yield b'data: {"type":"workflow_completed","run_id":"run-1","seq":4,"timestamp":"t4","agent":"workbench","payload":{}}\n\n'

    persisted = AsyncMock()
    adapter = TutoringStreamAdapter(
        stream_sse=source,
        persist_result=persisted,
        record_agent_log=AsyncMock(),
    )

    events = [
        event
        async for event in adapter.stream(
            payload={"message": "x"},
            conversation_id="conv-1",
            assistant_message_id="msg-1",
        )
    ]

    assert len(events) == 4
    persisted.assert_awaited_once()
    assert persisted.await_args.args[2] == "抱歉，我无法回答你的问题。"
    meta = persisted.await_args.args[5]
    assert meta["content_safety_review"]["action"] == "block"
    assert "partial safe prefix" not in str(meta)


def test_backend_artifact_descriptor_is_recovered_for_conversation_history():
    assert _client_artifact({
        "id": "generation-1",
        "type": "CodeSandboxCard",
        "title": "回显",
        "problem_id": "problem-1",
        "language": "python",
    }) == {
        "id": "generation-1",
        "type": "CodeSandboxCard",
        "title": "回显",
        "props": {"problem_id": "problem-1", "language": "python"},
    }
