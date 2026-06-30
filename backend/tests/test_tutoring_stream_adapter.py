import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from app.services.agent_client import AgentServiceError
from app.services.tutoring_stream_adapter import TutoringStreamAdapter


@pytest.mark.asyncio
async def test_stream_adapter_buffers_split_utf8_and_sse_lines():
    calls = []

    async def source(path, payload):
        calls.append((path, payload))
        encoded = 'data: {"type":"chunk","content":"指针"}\n\n'.encode()
        yield encoded[:19]
        yield encoded[19:23]
        yield encoded[23:]
        yield b'data: {"type":"done","message_id":"agent-id"}\n\n'

    persisted = AsyncMock()
    adapter = TutoringStreamAdapter(
        stream_sse=source,
        persist_result=persisted,
    )
    events = [
        event
        async for event in adapter.stream(
            payload={"message": "x"},
            conversation_id="conv-1",
            assistant_message_id="msg-1",
        )
    ]

    decoded = [json.loads(event["data"]) for event in events]
    assert calls == [
        (
            "/agent/v2/workbench/chat",
            {
                "user_id": "",
                "scope": "global",
                "course_id": None,
                "conversation_id": None,
                "message": "x",
                "context": {"message": "x"},
            },
        )
    ]
    assert decoded[0] == {"type": "chunk", "content": "指针"}
    assert decoded[1]["conversation_id"] == "conv-1"
    assert decoded[1]["message_id"] == "msg-1"
    persisted.assert_awaited_once_with("msg-1", "conv-1", "指针", [], [])


@pytest.mark.asyncio
async def test_stream_adapter_accumulates_compatible_knowledge_point_fields():
    async def source(path, payload):
        yield b'data: {"type":"diagram","data":"graph TD"}\n\n'
        yield b'data: {"type":"knowledge_points","points":["array"]}\n\n'
        yield b'data: {"type":"done","message_id":"agent-id"}\n\n'

    persisted = AsyncMock()
    adapter = TutoringStreamAdapter(stream_sse=source, persist_result=persisted)
    events = [
        event
        async for event in adapter.stream(
            payload={},
            conversation_id="c",
            assistant_message_id="m",
        )
    ]

    assert len(events) == 3
    persisted.assert_awaited_once_with(
        "m",
        "c",
        "",
        ["graph TD"],
        ["array"],
    )


@pytest.mark.asyncio
async def test_stream_adapter_persists_partial_content_when_closed():
    blocker = asyncio.Event()

    async def source(path, payload):
        yield b'data: {"type":"chunk","content":"partial"}\n\n'
        await blocker.wait()

    persisted = AsyncMock()
    adapter = TutoringStreamAdapter(stream_sse=source, persist_result=persisted)
    stream = adapter.stream(
        payload={},
        conversation_id="c",
        assistant_message_id="m",
    )
    first = await anext(stream)
    assert json.loads(first["data"])["content"] == "partial"
    await stream.aclose()

    persisted.assert_awaited_once_with("m", "c", "partial", [], [])


@pytest.mark.asyncio
async def test_stream_adapter_emits_existing_done_error_on_agent_failure():
    async def source(path, payload):
        if False:
            yield b""
        raise AgentServiceError("offline", status_code=503)

    persisted = AsyncMock()
    adapter = TutoringStreamAdapter(stream_sse=source, persist_result=persisted)
    events = [
        event
        async for event in adapter.stream(
            payload={},
            conversation_id="c",
            assistant_message_id="m",
        )
    ]

    assert events[0]["event"] == "done"
    assert json.loads(events[0]["data"])["error"] == "Agent 服务暂时不可用"
    persisted.assert_awaited_once_with("m", "c", "", [], [])


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
            conversation_id="c",
            assistant_message_id="m",
        )
    ]

    assert events == [{"event": "message", "data": "not-json"}]
    persisted.assert_awaited_once_with("m", "c", "", [], [])


@pytest.mark.asyncio
async def test_stream_adapter_converts_v2_workbench_events_to_client_events():
    async def source(path, payload):
        assert path == "/agent/v2/workbench/chat"
        assert payload["context"]["message"] == "x"
        yield b'data: {"type":"workflow_started","payload":{"reply_id":"r1"}}\n\n'
        yield b'data: {"type":"text_delta","payload":{"delta":"hello"}}\n\n'
        yield b'data: {"type":"text_delta","payload":{"delta":" world"}}\n\n'
        yield b'data: {"type":"workflow_completed","payload":{"reply_id":"r1"}}\n\n'

    persisted = AsyncMock()
    adapter = TutoringStreamAdapter(stream_sse=source, persist_result=persisted)
    events = [
        event
        async for event in adapter.stream(
            payload={"message": "x"},
            conversation_id="c",
            assistant_message_id="m",
        )
    ]

    decoded = [json.loads(event["data"]) for event in events]
    assert decoded == [
        {"type": "chunk", "content": "hello"},
        {"type": "chunk", "content": " world"},
        {"type": "done", "conversation_id": "c", "message_id": "m"},
    ]
    persisted.assert_awaited_once_with("m", "c", "hello world", [], [])


@pytest.mark.asyncio
async def test_stream_adapter_converts_v2_failure_to_done_error():
    async def source(path, payload):
        yield b'data: {"type":"workflow_failed","payload":{"reason":"model_not_configured"}}\n\n'

    persisted = AsyncMock()
    adapter = TutoringStreamAdapter(stream_sse=source, persist_result=persisted)
    events = [
        event
        async for event in adapter.stream(
            payload={"message": "x"},
            conversation_id="c",
            assistant_message_id="m",
        )
    ]

    decoded = [json.loads(event["data"]) for event in events]
    assert decoded == [
        {
            "type": "done",
            "conversation_id": "c",
            "message_id": "m",
            "error": "model_not_configured",
        }
    ]
    persisted.assert_awaited_once_with("m", "c", "", [], [])
