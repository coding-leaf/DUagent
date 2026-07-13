import asyncio
from types import SimpleNamespace

from agentscope.message import TextBlock, ToolCallBlock
from agentscope.tool import ToolResponse

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
    assert records[0]["trace_id"] == "run-1"
    assert records[0]["span_kind"] == "agent"
    assert records[0]["phase"] == "start"
    assert records[1]["span_id"] == records[0]["span_id"]
    assert records[1]["phase"] == "end"


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
        assert records[0]["span_kind"] == "model"
        assert records[0]["phase"] == "start"
        return [item async for item in stream]

    seen = asyncio.run(run_middleware())

    assert seen == ["chunk-1", "chunk-2"]
    assert [record["event"] for record in records] == [
        "model_call.start",
        "model_call.end",
    ]
    assert records[1]["span_id"] == records[0]["span_id"]
    assert records[1]["phase"] == "end"


def test_agent_run_logging_middleware_records_visible_tool_surface_without_schemas():
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
        state = SimpleNamespace(
            tool_context=SimpleNamespace(activated_groups=["planning", "learning_progress"])
        )

    async def next_handler(**_kwargs):
        return "response"

    tools = [
        {
            "type": "function",
            "function": {
                "name": "TaskCreate",
                "description": "secret schema content",
                "parameters": {"type": "object"},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_learning_progress",
                "parameters": {"type": "object"},
            },
        },
    ]

    result = asyncio.run(
        middleware.on_model_call(
            FakeAgent(),
            {"current_model": None, "tools": tools, "tool_choice": None},
            next_handler,
        )
    )

    assert result == "response"
    attributes = records[0]["attributes"]
    assert attributes["activated_tool_groups"] == ["planning", "learning_progress"]
    assert attributes["available_tool_names"] == ["TaskCreate", "read_learning_progress"]
    assert attributes["available_tool_count"] == 2
    assert attributes["tool_choice"] is None
    assert "secret schema content" not in str(attributes)


def test_agent_run_logging_middleware_emits_tool_arguments_and_result_preview():
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

    tool_call = ToolCallBlock(
        id="tool-1",
        name="read_learning_state",
        input='{"user_id":"u1","api_key":"should-not-leak"}',
    )

    async def next_handler(**_kwargs):
        yield ToolResponse(content=[TextBlock(text="weak points: linked list, recursion")])

    async def run_middleware():
        return [
            item
            async for item in middleware.on_acting(
                FakeAgent(),
                {"tool_call": tool_call},
                next_handler,
            )
        ]

    seen = asyncio.run(run_middleware())

    assert len(seen) == 1
    assert [record["event"] for record in records] == [
        "tool.call.start",
        "tool.call.end",
    ]
    assert records[0]["span_kind"] == "tool"
    assert records[0]["name"] == "execute_tool read_learning_state"
    assert records[0]["phase"] == "start"
    assert records[1]["span_id"] == records[0]["span_id"]
    assert records[1]["phase"] == "end"
    assert records[0]["attributes"]["tool_name"] == "read_learning_state"
    assert records[0]["attributes"]["tool_call_id"] == "tool-1"
    assert "should-not-leak" not in records[0]["attributes"]["tool_input_preview"]
    assert records[0]["attributes"]["tool_input_preview"] == '{"user_id":"u1","api_key":"<redacted>"}'
    assert records[1]["attributes"]["tool_state"] == "success"
    assert records[1]["attributes"]["tool_output_preview"] == "weak points: linked list, recursion"


def test_tool_log_preview_redacts_code_problem_reference_solution_and_hidden_cases():
    from agent_service_v2.observability.logging import input_preview

    preview = input_preview(
        '{"title":"sum","reference_solution":"print(secret)",'
        '"test_inputs":[{"stdin":"123 456","expected_output":"579"}]}'
    )

    assert '"reference_solution":"<redacted>"' in preview
    assert '"test_inputs":"<redacted>"' in preview
    assert "print(secret)" not in preview
    assert "123 456" not in preview
