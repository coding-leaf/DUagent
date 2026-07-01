import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from app.services.agent_client import AgentServiceError
from app.services.tutoring_stream_adapter import TutoringStreamAdapter


@pytest.mark.asyncio
async def test_stream_adapter_forwards_v2_events_with_backend_envelope():
    calls = []

    async def source(path, payload):
        calls.append((path, payload))
        yield b'data: {"type":"workflow_started","run_id":"run-1","conversation_id":"agent-conv","seq":1,"timestamp":"t1","agent":"workbench","payload":{"reply_id":"r1"}}\n\n'
        yield b'data: {"type":"text_delta","run_id":"run-1","conversation_id":"agent-conv","seq":2,"timestamp":"t2","agent":"workbench","payload":{"delta":"hello"}}\n\n'
        yield b'data: {"type":"workflow_completed","run_id":"run-1","conversation_id":"agent-conv","seq":3,"timestamp":"t3","agent":"workbench","payload":{"reply_id":"r1"}}\n\n'

    persisted = AsyncMock()
    adapter = TutoringStreamAdapter(
        stream_sse=source,
        persist_result=persisted,
    )
    events = [
        event
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
        )
    ]

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
    persisted.assert_awaited_once_with("msg-1", "conv-1", "hello", [], [])


@pytest.mark.asyncio
async def test_stream_adapter_does_not_filter_tool_source_or_artifact_events():
    async def source(path, payload):
        yield b'data: {"type":"tool_started","run_id":"run-1","seq":1,"timestamp":"t1","agent":"workbench","payload":{"tool_call_id":"tool-1","tool_name":"TaskCreate"}}\n\n'
        yield b'data: {"type":"tool_completed","run_id":"run-1","seq":2,"timestamp":"t2","agent":"workbench","payload":{"tool_call_id":"tool-1","state":"success"}}\n\n'
        yield b'data: {"type":"source_refs","run_id":"run-1","seq":3,"timestamp":"t3","agent":"workbench","payload":{"sources":[{"title":"Array"}]}}\n\n'
        yield b'data: {"type":"artifact_created","run_id":"run-1","seq":4,"timestamp":"t4","agent":"workbench","payload":{"artifact":{"id":"a1","type":"Markdown","props":{"content":"# Plan"}}}}\n\n'

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
    persisted.assert_awaited_once_with("msg-1", "conv-1", "", [], [])


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

    persisted.assert_awaited_once_with("msg-1", "conv-1", "partial", [], [])


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
    persisted.assert_awaited_once_with("msg-1", "conv-1", "", [], [])


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
    persisted.assert_awaited_once_with("msg-1", "conv-1", "", [], [])
