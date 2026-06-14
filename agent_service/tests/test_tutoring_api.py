import asyncio
import json

from agent_service.api.v1 import tutoring as tutoring_api
from agent_service.agents.tutoring import TutoringModelResponse
from agent_service.memory.tutoring_retrieval import TutoringRetrievalContext
from agent_service.schemas.tutoring import TutoringChatRequest, TutoringUserProfile


def _patch_providers(monkeypatch, providers) -> None:
    monkeypatch.setattr("agent_service.core.ai.get_ai_providers", lambda: providers)


def _non_status_events(events: list[dict]) -> list[dict]:
    return [event for event in events if event.get("type") != "status"]


def test_tutoring_chat_returns_rule_based_sse_events(monkeypatch) -> None:
    request = TutoringChatRequest(
        user_id="user-1",
        course_id="course-1",
        message="导数怎么理解？",
        user_profile=TutoringUserProfile(
            guidance_level="L1",
            knowledge_mastered=["函数"],
            knowledge_weak=["导数"],
        ),
    )

    class FakeProviders:
        def __init__(self) -> None:
            self.embedding = object()

    _patch_providers(monkeypatch, FakeProviders())

    response = asyncio.run(tutoring_api.tutoring_chat(request))
    body = asyncio.run(_consume_response_body(response.body_iterator))

    assert response.media_type == "text/event-stream"
    events = [
        json.loads(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: ")
    ]
    payload_events = _non_status_events(events)
    assert [event["type"] for event in payload_events] == ["chunk", "knowledge_points", "suggestion", "done"]
    assert payload_events[-1]["message_id"] == "msg_user-1_new"
    assert events[0]["type"] == "status"


def test_tutoring_chat_uses_ai_retrieval_context_in_sse_output(monkeypatch) -> None:
    request = TutoringChatRequest(
        user_id="user-1",
        course_id="course-1",
        message="链式法则怎么用？",
        user_profile=TutoringUserProfile(guidance_level="L2", knowledge_weak=["导数"]),
    )
    calls = {}

    class FakeProviders:
        def __init__(self) -> None:
            self.embedding = object()

    async def fake_build_context(request_arg, embedding_provider, vector_store=None, limit=3):
        calls["request"] = request_arg
        calls["embedding_provider"] = embedding_provider
        return TutoringRetrievalContext(
            user_id="user-1",
            course_id="course-1",
            query_text="链式法则怎么用？",
            include_course_knowledge=True,
            knowledge_points=["链式法则"],
            user_memory_facts=["用户容易把内外层顺序写反"],
            course_knowledge_chunks=["链式法则用于复合函数求导"],
        )

    monkeypatch.setattr(
        "agent_service.memory.tutoring_retrieval.build_tutoring_retrieval_context_with_ai",
        fake_build_context,
    )
    _patch_providers(monkeypatch, FakeProviders())

    response = asyncio.run(tutoring_api.tutoring_chat(request))
    body = asyncio.run(_consume_response_body(response.body_iterator))
    events = [
        json.loads(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: ")
    ]

    assert calls["request"] == request
    payload_events = _non_status_events(events)
    assert "我会用关键步骤帮你串起来。" in payload_events[0]["content"]
    assert payload_events[1]["knowledge_points"][0]["name"] == "链式法则"


def test_tutoring_chat_degrades_when_ai_retrieval_fails(monkeypatch) -> None:
    request = TutoringChatRequest(
        user_id="user-1",
        course_id="course-1",
        message="导数怎么理解？",
        user_profile=TutoringUserProfile(
            guidance_level="L1",
            knowledge_mastered=["函数"],
            knowledge_weak=["导数"],
        ),
    )

    class FakeProviders:
        def __init__(self) -> None:
            self.embedding = object()

    async def failing_build_context(request_arg, embedding_provider, vector_store=None, limit=3):
        raise RuntimeError("retrieval unavailable")

    monkeypatch.setattr(
        "agent_service.memory.tutoring_retrieval.build_tutoring_retrieval_context_with_ai",
        failing_build_context,
    )
    _patch_providers(monkeypatch, FakeProviders())

    response = asyncio.run(tutoring_api.tutoring_chat(request))
    body = asyncio.run(_consume_response_body(response.body_iterator))
    events = [
        json.loads(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: ")
    ]

    payload_events = _non_status_events(events)
    assert [event["type"] for event in payload_events] == ["chunk", "knowledge_points", "suggestion", "done"]
    assert payload_events[0]["content"].startswith("我会先拆成更小的步骤来讲。")
    assert payload_events[1]["knowledge_points"][0]["name"] == "导数"


def test_tutoring_chat_global_scope_does_not_query_course_knowledge(monkeypatch) -> None:
    request = TutoringChatRequest(
        user_id="user-1",
        scope="global",
        message="帮我制定学习计划",
        user_profile=TutoringUserProfile(guidance_level="L3", knowledge_mastered=["函数"]),
    )
    calls = {}

    class FakeProviders:
        def __init__(self) -> None:
            self.embedding = object()

    async def fake_build_context(request_arg, embedding_provider, vector_store=None, limit=3):
        calls["request"] = request_arg
        return TutoringRetrievalContext(
            user_id="user-1",
            course_id=None,
            query_text="帮我制定学习计划",
            include_course_knowledge=False,
            knowledge_points=["函数"],
            user_memory_facts=["用户偏好分步学习"],
            course_knowledge_chunks=[],
        )

    monkeypatch.setattr(
        "agent_service.memory.tutoring_retrieval.build_tutoring_retrieval_context_with_ai",
        fake_build_context,
    )
    _patch_providers(monkeypatch, FakeProviders())

    response = asyncio.run(tutoring_api.tutoring_chat(request))
    body = asyncio.run(_consume_response_body(response.body_iterator))
    events = [
        json.loads(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: ")
    ]

    assert calls["request"].scope == "global"
    assert calls["request"].course_id is None
    payload_events = _non_status_events(events)
    assert "我会直接给出核心思路和检查点。" in payload_events[0]["content"]
    assert payload_events[1]["knowledge_points"][0]["name"] == "函数"


def test_tutoring_chat_streams_status_before_slow_retrieval(monkeypatch) -> None:
    request = TutoringChatRequest(
        user_id="user-1",
        course_id="course-1",
        message="导数怎么理解？",
        user_profile=TutoringUserProfile(
            guidance_level="L1",
            knowledge_mastered=["函数"],
            knowledge_weak=["导数"],
        ),
    )
    gate = asyncio.Event()

    class FakeProviders:
        def __init__(self) -> None:
            self.embedding = object()

    async def slow_build_context(request_arg, embedding_provider, vector_store=None, limit=3):
        await gate.wait()
        return TutoringRetrievalContext(
            user_id="user-1",
            course_id="course-1",
            query_text=request.message,
            include_course_knowledge=True,
            knowledge_points=["链式法则"],
            user_memory_facts=["用户容易把内外层顺序写反"],
            course_knowledge_chunks=["链式法则用于复合函数求导"],
        )

    monkeypatch.setattr(
        "agent_service.memory.tutoring_retrieval.build_tutoring_retrieval_context_with_ai",
        slow_build_context,
    )
    _patch_providers(monkeypatch, FakeProviders())

    async def consume_first_chunk():
        response = await tutoring_api.tutoring_chat(request)
        iterator = response.body_iterator
        first_chunk = await asyncio.wait_for(iterator.__anext__(), timeout=0.1)
        gate.set()
        remaining = []
        async for chunk in iterator:
            remaining.append(chunk)
        return first_chunk, remaining

    first_chunk, remaining = asyncio.run(consume_first_chunk())
    first_event = json.loads(first_chunk.splitlines()[0].removeprefix("data: "))

    assert first_event["type"] == "status"
    assert "检索" in first_event["message"]
    assert remaining


def test_tutoring_chat_emits_only_model_chunk_when_model_succeeds(monkeypatch) -> None:
    request = TutoringChatRequest(
        user_id="user-1",
        course_id="course-1",
        message="链式法则怎么用？",
        user_profile=TutoringUserProfile(guidance_level="L2", knowledge_weak=["导数"]),
    )
    calls = {}

    class FakeProviders:
        def __init__(self) -> None:
            self.embedding = object()
            self.chat = self

        model = object()
        formatter = object()

    async def fake_react(request_arg, retrieval_context, chat_provider, **kwargs):
        calls["request"] = request_arg
        return TutoringModelResponse(
            model_text="链式法则用于复合函数求导，要从外层函数开始乘以内层导数。",
            knowledge_point_names=["链式法则"],
        )

    async def fake_build_context(request_arg, embedding_provider, vector_store=None, limit=3):
        return TutoringRetrievalContext(
            user_id="user-1",
            course_id="course-1",
            query_text="链式法则怎么用？",
            include_course_knowledge=True,
            knowledge_points=["链式法则"],
            user_memory_facts=["用户容易把内外层顺序写反"],
            course_knowledge_chunks=["链式法则用于复合函数求导"],
        )

    monkeypatch.setattr(
        "agent_service.memory.tutoring_retrieval.build_tutoring_retrieval_context_with_ai",
        fake_build_context,
    )
    monkeypatch.setattr("agent_service.agents.tutoring_react_flow.generate_tutoring_react_response", fake_react)
    _patch_providers(monkeypatch, FakeProviders())

    response = asyncio.run(tutoring_api.tutoring_chat(request))
    body = asyncio.run(_consume_response_body(response.body_iterator))
    events = [
        json.loads(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: ")
    ]

    payload_events = _non_status_events(events)
    assert [event["type"] for event in payload_events] == ["chunk", "knowledge_points", "suggestion", "done"]
    assert payload_events[0]["content"] == "链式法则用于复合函数求导，要从外层函数开始乘以内层导数。"
    assert calls["request"] == request


def test_tutoring_chat_uses_model_metadata_from_text_payload(monkeypatch) -> None:
    request = TutoringChatRequest(
        user_id="user-1",
        course_id="course-1",
        message="链式法则怎么用？",
        user_profile=TutoringUserProfile(guidance_level="L2", knowledge_weak=["导数"]),
    )

    class FakeProviders:
        def __init__(self) -> None:
            self.embedding = object()
            self.chat = self

        model = object()
        formatter = object()

    async def fake_react(*args, **kwargs):
        return TutoringModelResponse(
            model_text="链式法则先看外层函数，再乘以内层导数。",
            knowledge_point_names=["链式法则", "复合函数"],
            suggestion_text="先确认外层函数，再检查内层导数。",
        )

    async def fake_build_context(request_arg, embedding_provider, vector_store=None, limit=3):
        return TutoringRetrievalContext(
            user_id="user-1",
            course_id="course-1",
            query_text="链式法则怎么用？",
            include_course_knowledge=True,
            knowledge_points=["链式法则"],
            user_memory_facts=["用户容易把内外层顺序写反"],
            course_knowledge_chunks=["链式法则用于复合函数求导"],
        )

    monkeypatch.setattr(
        "agent_service.memory.tutoring_retrieval.build_tutoring_retrieval_context_with_ai",
        fake_build_context,
    )
    monkeypatch.setattr("agent_service.agents.tutoring_react_flow.generate_tutoring_react_response", fake_react)
    _patch_providers(monkeypatch, FakeProviders())

    response = asyncio.run(tutoring_api.tutoring_chat(request))
    body = asyncio.run(_consume_response_body(response.body_iterator))
    events = [
        json.loads(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: ")
    ]

    payload_events = _non_status_events(events)
    assert payload_events[0]["content"] == "链式法则先看外层函数，再乘以内层导数。"
    assert [item["name"] for item in payload_events[1]["knowledge_points"]] == ["链式法则", "复合函数"]
    assert payload_events[2]["suggestion"] == "先确认外层函数，再检查内层导数。"


def test_tutoring_chat_streams_diagram_event_when_present(monkeypatch) -> None:
    request = TutoringChatRequest(
        user_id="user-1",
        course_id="course-1",
        message="讲讲树",
        user_profile=TutoringUserProfile(guidance_level="L2", knowledge_weak=["二叉树"]),
    )

    class FakeProviders:
        def __init__(self) -> None:
            self.embedding = object()
            self.chat = self

        model = object()
        formatter = object()

    async def fake_react(*args, **kwargs):
        return TutoringModelResponse(
            model_text="这是树",
            knowledge_point_names=["二叉树"],
            suggestion_text="看图",
            diagram="graph TD; A-->B;",
        )

    async def fake_build_context(request_arg, embedding_provider, vector_store=None, limit=3):
        return TutoringRetrievalContext(
            user_id="user-1",
            course_id="course-1",
            query_text="讲讲树",
            include_course_knowledge=True,
            knowledge_points=["二叉树"],
            user_memory_facts=[],
            course_knowledge_chunks=[],
        )

    monkeypatch.setattr(
        "agent_service.memory.tutoring_retrieval.build_tutoring_retrieval_context_with_ai",
        fake_build_context,
    )
    monkeypatch.setattr("agent_service.agents.tutoring_react_flow.generate_tutoring_react_response", fake_react)
    _patch_providers(monkeypatch, FakeProviders())

    response = asyncio.run(tutoring_api.tutoring_chat(request))
    body = asyncio.run(_consume_response_body(response.body_iterator))
    events = [
        json.loads(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: ")
    ]

    payload_events = _non_status_events(events)
    assert [event["type"] for event in payload_events] == ["chunk", "diagram", "knowledge_points", "suggestion", "done"]
    assert payload_events[1]["data"] == "graph TD; A-->B;"


def test_tutoring_chat_degrades_when_chat_fails(monkeypatch) -> None:
    request = TutoringChatRequest(
        user_id="user-1",
        course_id="course-1",
        message="链式法则怎么用？",
        user_profile=TutoringUserProfile(guidance_level="L2", knowledge_weak=["导数"]),
    )

    class FakeProviders:
        def __init__(self) -> None:
            self.embedding = object()
            self.chat = self

        async def complete(self, messages):
            raise RuntimeError("chat unavailable")

    async def fake_build_context(request_arg, embedding_provider, vector_store=None, limit=3):
        return TutoringRetrievalContext(
            user_id="user-1",
            course_id="course-1",
            query_text="链式法则怎么用？",
            include_course_knowledge=True,
            knowledge_points=["链式法则"],
            user_memory_facts=["用户容易把内外层顺序写反"],
            course_knowledge_chunks=["链式法则用于复合函数求导"],
        )

    monkeypatch.setattr(
        "agent_service.memory.tutoring_retrieval.build_tutoring_retrieval_context_with_ai",
        fake_build_context,
    )
    _patch_providers(monkeypatch, FakeProviders())

    response = asyncio.run(tutoring_api.tutoring_chat(request))
    body = asyncio.run(_consume_response_body(response.body_iterator))
    events = [
        json.loads(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: ")
    ]

    payload_events = _non_status_events(events)
    assert [event["type"] for event in payload_events] == ["chunk", "knowledge_points", "suggestion", "done"]


async def _consume_response_body(body_iterator) -> str:
    chunks = []
    async for chunk in body_iterator:
        chunks.append(chunk)
    return "".join(chunks)
