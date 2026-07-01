import asyncio

from agent_service_v2.observability.agent_middleware import AgentRunLoggingMiddleware


def test_agent_run_logging_middleware_emits_reply_lifecycle_records():
    records = []
    middleware = AgentRunLoggingMiddleware(
        run_id="run-1",
        conversation_id="conv-1",
        user_id="u1",
        course_id="c1",
        sink=records.append,
    )

    class FakeAgent:
        name = "workbench"

    async def next_handler(**_kwargs):
        yield "event-1"

    async def run_middleware():
        return [
            item
            async for item in middleware.on_reply(
                FakeAgent(),
                {"inputs": "hello"},
                next_handler,
            )
        ]

    seen = asyncio.run(run_middleware())

    assert seen == ["event-1"]
    assert [record["event"] for record in records] == [
        "reply.start",
        "reply.end",
    ]
    assert records[0]["run_id"] == "run-1"
    assert records[0]["conversation_id"] == "conv-1"


def test_agent_run_logging_middleware_closes_streaming_model_call_after_consumption():
    records = []
    middleware = AgentRunLoggingMiddleware(
        run_id="run-1",
        conversation_id="conv-1",
        user_id="u1",
        course_id="c1",
        sink=records.append,
    )

    class FakeAgent:
        name = "workbench"

    async def model_stream():
        yield "chunk-1"
        yield "chunk-2"

    async def next_handler(**_kwargs):
        return model_stream()

    async def run_middleware():
        stream = await middleware.on_model_call(
            FakeAgent(),
            {"current_model": None},
            next_handler,
        )
        assert [record["event"] for record in records] == ["model_call.start"]
        return [item async for item in stream]

    seen = asyncio.run(run_middleware())

    assert seen == ["chunk-1", "chunk-2"]
    assert [record["event"] for record in records] == [
        "model_call.start",
        "model_call.end",
    ]
