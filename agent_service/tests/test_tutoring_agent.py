import asyncio

from agent_service.agents.tutoring import (
    build_tutoring_generation_result,
    generate_tutoring_model_response,
    parse_tutoring_model_response,
)
from agent_service.memory.tutoring_retrieval import TutoringRetrievalContext
from agent_service.schemas.tutoring import TutoringChatRequest, TutoringUserProfile


def test_parse_tutoring_model_response_extracts_structured_payload() -> None:
    model_output = (
        "链式法则用于复合函数求导，要先看外层函数。"
        "\n<agent_result>{\"knowledge_points\":[\"链式法则\",\"复合函数\"],"
        "\"suggestion\":\"先确认外层，再检查内层导数。\"}</agent_result>"
    )

    parsed = parse_tutoring_model_response(model_output)

    assert parsed.model_text == "链式法则用于复合函数求导，要先看外层函数。"
    assert parsed.knowledge_point_names == ["链式法则", "复合函数"]
    assert parsed.suggestion_text == "先确认外层，再检查内层导数。"
    assert parsed.diagram is None


def test_parse_tutoring_model_response_falls_back_on_invalid_json() -> None:
    model_output = (
        "链式法则用于复合函数求导。"
        "\n<agent_result>{\"knowledge_points\": [}</agent_result>"
    )

    parsed = parse_tutoring_model_response(model_output)

    assert parsed.model_text == "链式法则用于复合函数求导。"
    assert parsed.knowledge_point_names == []
    assert parsed.suggestion_text is None


def test_parse_tutoring_model_response_handles_json_mode_output() -> None:
    """JSON mode response: 模型返回顶层 JSON object。"""
    model_output = (
        '{"model_text": "链式法则先看外层函数，再乘以内层导数。",'
        '"knowledge_points": ["链式法则", "复合函数"],'
        '"suggestion": "先确认外层函数，再检查内层自变量怎么变化。"}'
    )

    parsed = parse_tutoring_model_response(model_output)

    assert parsed.model_text == "链式法则先看外层函数，再乘以内层导数。"
    assert parsed.knowledge_point_names == ["链式法则", "复合函数"]
    assert parsed.suggestion_text == "先确认外层函数，再检查内层自变量怎么变化。"
    assert parsed.diagram is None


def test_parse_tutoring_model_response_json_mode_falls_back_to_xml_regex() -> None:
    """JSON mode 输出为纯文本包裹 + XML 标签时，json.loads 失败后降级为正则提取。"""
    model_output = (
        "链式法则用于复合函数求导。"
        "\n<agent_result>{\"knowledge_points\":[\"链式法则\"],"
        "\"suggestion\":\"先确认外层函数。\"}</agent_result>"
    )

    parsed = parse_tutoring_model_response(model_output)

    assert parsed.model_text == "链式法则用于复合函数求导。"
    assert parsed.knowledge_point_names == ["链式法则"]
    assert parsed.suggestion_text == "先确认外层函数。"


def test_parse_tutoring_model_response_json_mode_returns_raw_on_double_failure() -> None:
    """json.loads 和 XML 正则都失败时，返回原始文本作为 model_text。"""
    model_output = "导数表示函数在某点的变化率。"

    parsed = parse_tutoring_model_response(model_output)

    assert parsed.model_text == "导数表示函数在某点的变化率。"
    assert parsed.knowledge_point_names == []
    assert parsed.suggestion_text is None


def test_parse_tutoring_model_response_json_mode_partial_json_fields() -> None:
    """JSON mode 输出缺少字段时，缺失字段使用默认值。"""
    model_output = '{"model_text": "衍", "knowledge_points": ["导数"]}'

    parsed = parse_tutoring_model_response(model_output)

    assert parsed.model_text == "衍"
    assert parsed.knowledge_point_names == ["导数"]
    assert parsed.suggestion_text is None


def test_build_tutoring_generation_result_collects_single_runtime_object() -> None:
    request = TutoringChatRequest(
        user_id="user-1",
        course_id="course-1",
        message="帮我讲一下链式法则",
        user_profile=TutoringUserProfile(guidance_level="L2", knowledge_weak=["导数"]),
    )
    context = TutoringRetrievalContext(
        user_id="user-1",
        course_id="course-1",
        query_text="帮我讲一下链式法则",
        include_course_knowledge=True,
        knowledge_points=["导数"],
        user_memory_facts=["用户容易混淆复合函数求导顺序"],
        course_knowledge_chunks=["链式法则用于复合函数求导"],
    )
    model_response = parse_tutoring_model_response(
        "链式法则先看外层函数，再乘以内层导数。"
        "\n<agent_result>{\"knowledge_points\":[\"链式法则\"],"
        "\"suggestion\":\"先确认外层函数，再检查内层导数。\"}</agent_result>"
    )

    result = build_tutoring_generation_result(request, context, model_response=model_response)

    assert result.chunk_text == "链式法则先看外层函数，再乘以内层导数。"
    assert [item.name for item in result.knowledge_points] == ["链式法则"]
    assert result.suggestion_text == "先确认外层函数，再检查内层导数。"
    assert result.used_rule_fallback is False


def test_generate_tutoring_model_response_uses_chat_provider_and_prompt_messages() -> None:
    request = TutoringChatRequest(
        user_id="user-1",
        course_id="course-1",
        message="帮我讲一下链式法则",
        user_profile=TutoringUserProfile(guidance_level="L2", knowledge_weak=["导数"]),
    )
    context = TutoringRetrievalContext(
        user_id="user-1",
        course_id="course-1",
        query_text="帮我讲一下链式法则",
        include_course_knowledge=True,
        knowledge_points=["导数"],
        user_memory_facts=["用户容易混淆复合函数求导顺序"],
        course_knowledge_chunks=["链式法则用于复合函数求导"],
    )

    class FakeChatProvider:
        def __init__(self) -> None:
            self.calls = []

        async def complete(self, messages):
            self.calls.append(messages)
            return (
                "链式法则先看外层函数。"
                "\n<agent_result>{\"knowledge_points\":[\"链式法则\"],"
                "\"suggestion\":\"先确认外层函数。\"}</agent_result>"
            )

    provider = FakeChatProvider()

    response = asyncio.run(generate_tutoring_model_response(request, context, provider))

    assert provider.calls
    assert provider.calls[0][-1].role == "user"
    assert response.model_text == "链式法则先看外层函数。"
    assert response.knowledge_point_names == ["链式法则"]
    assert response.suggestion_text == "先确认外层函数。"


def test_generate_tutoring_model_response_uses_structured_output() -> None:
    request = TutoringChatRequest(
        user_id="user-1",
        course_id="course-1",
        message="帮我讲一下链式法则",
        user_profile=TutoringUserProfile(guidance_level="L2", knowledge_weak=["导数"]),
    )
    context = TutoringRetrievalContext(
        user_id="user-1",
        course_id="course-1",
        query_text="帮我讲一下链式法则",
        include_course_knowledge=True,
        knowledge_points=["导数"],
        user_memory_facts=["用户容易混淆复合函数求导顺序"],
        course_knowledge_chunks=["链式法则用于复合函数求导"],
    )

    class FakeChatProvider:
        def __init__(self) -> None:
            self.complete_calls = []

        async def complete(self, messages, structured_model=None):
            self.complete_calls.append(structured_model)
            if structured_model is not None:
                return (
                    '{"model_text":"链式法则先看外层求导。",'
                    '"knowledge_points":["链式法则","复合函数"],'
                    '"suggestion":"先确认外层函数，再逐层求导。"}'
                )
            return "fallback text"

    provider = FakeChatProvider()

    response = asyncio.run(generate_tutoring_model_response(request, context, provider))

    assert len(provider.complete_calls) == 1  # structured success, no fallback needed
    assert provider.complete_calls[0] is not None
    assert response.model_text == "链式法则先看外层求导。"
    assert response.knowledge_point_names == ["链式法则", "复合函数"]
    assert response.suggestion_text == "先确认外层函数，再逐层求导。"


def test_generate_tutoring_model_response_falls_back_on_structured_output_failure() -> None:
    request = TutoringChatRequest(
        user_id="user-1",
        course_id="course-1",
        message="帮我讲一下链式法则",
        user_profile=TutoringUserProfile(guidance_level="L2", knowledge_weak=["导数"]),
    )
    context = TutoringRetrievalContext(
        user_id="user-1",
        course_id="course-1",
        query_text="帮我讲一下链式法则",
        include_course_knowledge=True,
        knowledge_points=["导数"],
        user_memory_facts=[],
        course_knowledge_chunks=[],
    )

    class FakeChatProvider:
        def __init__(self) -> None:
            self.calls = []

        async def complete(self, messages, structured_model=None):
            self.calls.append(structured_model)
            if structured_model is not None:
                raise RuntimeError("structured output not supported")
            return (
                "链式法则先看外层函数。"
                "\n<agent_result>{\"knowledge_points\":[\"链式法则\"],"
                "\"suggestion\":\"先确认外层函数。\"}</agent_result>"
            )

    provider = FakeChatProvider()

    response = asyncio.run(generate_tutoring_model_response(request, context, provider))

    assert len(provider.calls) == 2  # structured failed, then text fallback
    assert provider.calls[0] is not None
    assert provider.calls[1] is None
    assert response.model_text == "链式法则先看外层函数。"
    assert response.knowledge_point_names == ["链式法则"]
    assert response.suggestion_text == "先确认外层函数。"


def test_generate_tutoring_model_response_ignores_legacy_disabled_structured_output() -> None:
    request = TutoringChatRequest(
        user_id="user-1",
        course_id="course-1",
        message="帮我讲一下链式法则",
        user_profile=TutoringUserProfile(guidance_level="L2", knowledge_weak=["导数"]),
    )
    context = TutoringRetrievalContext(
        user_id="user-1",
        course_id="course-1",
        query_text="帮我讲一下链式法则",
        include_course_knowledge=True,
        knowledge_points=["导数"],
        user_memory_facts=[],
        course_knowledge_chunks=[],
    )

    class FakeChatProvider:
        async def complete_structured(self, messages, structured_model):
            raise AssertionError("structured output should be skipped")

        async def complete(self, messages):
            return (
                "链式法则先看外层函数。"
                "\n<agent_result>{\"knowledge_points\":[\"链式法则\"],"
                "\"suggestion\":\"先确认外层函数。\"}</agent_result>"
            )

    response = asyncio.run(generate_tutoring_model_response(request, context, FakeChatProvider()))

    assert response.model_text == "链式法则先看外层函数。"
    assert response.knowledge_point_names == ["链式法则"]
    assert response.suggestion_text == "先确认外层函数。"


def test_parse_tutoring_model_response_extracts_diagram_from_json_mode() -> None:
    model_output = (
        '{"model_text": "这是一个树。\\n",'
        '"knowledge_points": ["二叉树"],'
        '"suggestion": "先看图。",'
        '"diagram": "graph TD; A-->B;"}'
    )

    parsed = parse_tutoring_model_response(model_output)

    assert parsed.model_text == "这是一个树。"
    assert parsed.diagram == "graph TD; A-->B;"


def test_parse_tutoring_model_response_extracts_diagram_from_xml_mode() -> None:
    model_output = (
        "这是一个图。"
        "\n<agent_result>{\"knowledge_points\":[\"图\"],"
        "\"suggestion\":\"看图。\", \"diagram\":\"graph TD; A-->B;\"}</agent_result>"
    )

    parsed = parse_tutoring_model_response(model_output)

    assert parsed.model_text == "这是一个图。"
    assert parsed.diagram == "graph TD; A-->B;"


def test_generate_tutoring_sse_events_maintains_old_order_without_diagram() -> None:
    from agent_service.agents.tutoring import generate_tutoring_sse_events

    request = TutoringChatRequest(
        user_id="user-1",
        course_id="course-1",
        message="讲讲导数",
        user_profile=TutoringUserProfile(guidance_level="L2", knowledge_weak=["导数"]),
    )

    class FakeProviders:
        class FakeChat:
            async def complete(self, messages, **kwargs):
                return '{"model_text":"导数好啊","knowledge_points":["导数"],"suggestion":"看看视频"}'
        chat = FakeChat()
        embedding = None
        reranker = None

    async def _collect():
        events = []
        async for evt in generate_tutoring_sse_events(request, providers=FakeProviders()):
            events.append(evt)
        return events

    events = asyncio.run(_collect())
    # fallback chunk, model chunk, knowledge_points, suggestion, done
    types = []
    for evt in events:
        import json
        payload = json.loads(evt.replace("data: ", "").strip())
        types.append(payload["type"])
    assert types == ["chunk", "chunk", "knowledge_points", "suggestion", "done"]


def test_generate_tutoring_sse_events_inserts_diagram_when_present() -> None:
    from agent_service.agents.tutoring import generate_tutoring_sse_events

    request = TutoringChatRequest(
        user_id="user-1",
        course_id="course-1",
        message="讲讲树",
        user_profile=TutoringUserProfile(guidance_level="L2", knowledge_weak=["二叉树"]),
    )

    class FakeProviders:
        class FakeChat:
            async def complete(self, messages, **kwargs):
                return '{"model_text":"这是树","knowledge_points":["二叉树"],"suggestion":"看图","diagram":"graph TD; A-->B;"}'
        chat = FakeChat()
        embedding = None
        reranker = None

    async def _collect():
        events = []
        async for evt in generate_tutoring_sse_events(request, providers=FakeProviders()):
            events.append(evt)
        return events

    events = asyncio.run(_collect())
    # fallback chunk, model chunk, diagram, knowledge_points, suggestion, done
    types = []
    for evt in events:
        import json
        payload = json.loads(evt.replace("data: ", "").strip())
        types.append(payload["type"])
    assert types == ["chunk", "chunk", "diagram", "knowledge_points", "suggestion", "done"]
    
    diagram_event = json.loads(events[2].replace("data: ", "").strip())
    assert diagram_event["data"] == "graph TD; A-->B;"
