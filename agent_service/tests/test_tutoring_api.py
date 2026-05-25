import asyncio
import json

from agent_service.api.v1 import tutoring as tutoring_api
from agent_service.memory.tutoring_retrieval import TutoringRetrievalContext
from agent_service.schemas.tutoring import TutoringChatRequest, TutoringUserProfile


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

    monkeypatch.setattr(tutoring_api, "get_ai_providers", lambda: FakeProviders())

    response = asyncio.run(tutoring_api.tutoring_chat(request))
    body = asyncio.run(_consume_response_body(response.body_iterator))

    assert response.media_type == "text/event-stream"
    events = [
        json.loads(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: ")
    ]
    assert [event["type"] for event in events] == ["chunk", "knowledge_points", "suggestion", "done"]
    assert events[-1]["message_id"] == "msg_user-1_new"


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

    monkeypatch.setattr(tutoring_api, "get_ai_providers", lambda: FakeProviders())
    monkeypatch.setattr(tutoring_api, "build_tutoring_retrieval_context_with_ai", fake_build_context)

    response = asyncio.run(tutoring_api.tutoring_chat(request))
    body = asyncio.run(_consume_response_body(response.body_iterator))
    events = [
        json.loads(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: ")
    ]

    assert calls["request"] == request
    assert events[0]["content"].startswith("我会用关键步骤帮你串起来。")
    assert events[1]["knowledge_points"][0]["name"] == "链式法则"


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

    monkeypatch.setattr(tutoring_api, "get_ai_providers", lambda: FakeProviders())
    monkeypatch.setattr(tutoring_api, "build_tutoring_retrieval_context_with_ai", failing_build_context)

    response = asyncio.run(tutoring_api.tutoring_chat(request))
    body = asyncio.run(_consume_response_body(response.body_iterator))
    events = [
        json.loads(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: ")
    ]

    assert [event["type"] for event in events] == ["chunk", "knowledge_points", "suggestion", "done"]
    assert events[0]["content"].startswith("我会先拆成更小的步骤来讲。")
    assert events[1]["knowledge_points"][0]["name"] == "导数"


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

    monkeypatch.setattr(tutoring_api, "get_ai_providers", lambda: FakeProviders())
    monkeypatch.setattr(tutoring_api, "build_tutoring_retrieval_context_with_ai", fake_build_context)

    response = asyncio.run(tutoring_api.tutoring_chat(request))
    body = asyncio.run(_consume_response_body(response.body_iterator))
    events = [
        json.loads(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: ")
    ]

    assert calls["request"].scope == "global"
    assert calls["request"].course_id is None
    assert events[0]["content"].startswith("我会直接给出核心思路和检查点。")
    assert events[1]["knowledge_points"][0]["name"] == "函数"


def test_tutoring_chat_streams_first_chunk_before_slow_retrieval(monkeypatch) -> None:
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

    monkeypatch.setattr(tutoring_api, "get_ai_providers", lambda: FakeProviders())
    monkeypatch.setattr(tutoring_api, "build_tutoring_retrieval_context_with_ai", slow_build_context)

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

    assert first_event["type"] == "chunk"
    assert first_event["content"].startswith("我会先拆成更小的步骤来讲。")
    assert remaining


def test_tutoring_chat_emits_model_chunk_after_first_rule_chunk(monkeypatch) -> None:
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

        async def complete(self, messages):
            calls["messages"] = messages
            return "链式法则用于复合函数求导，要从外层函数开始乘以内层导数。"

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

    monkeypatch.setattr(tutoring_api, "get_ai_providers", lambda: FakeProviders())
    monkeypatch.setattr(tutoring_api, "build_tutoring_retrieval_context_with_ai", fake_build_context)

    response = asyncio.run(tutoring_api.tutoring_chat(request))
    body = asyncio.run(_consume_response_body(response.body_iterator))
    events = [
        json.loads(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: ")
    ]

    assert [event["type"] for event in events] == ["chunk", "chunk", "knowledge_points", "suggestion", "done"]
    assert events[0]["content"].startswith("我会用关键步骤帮你串起来。")
    assert events[1]["content"] == "链式法则用于复合函数求导，要从外层函数开始乘以内层导数。"
    assert calls["messages"][-1].role == "user"


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

        async def complete(self, messages):
            return (
                "链式法则先看外层函数，再乘以内层导数。"
                "\n<agent_result>{\"knowledge_points\":[\"链式法则\",\"复合函数\"],"
                "\"suggestion\":\"先确认外层函数，再检查内层导数。\"}</agent_result>"
            )

    async def fake_build_context(request_arg, embedding_provider, vector_store=None, limit=3):
        return TutoringRetrievalContext(
            user_id="user-1",
            course_id="course-1",
            query_text="链式法则怎么用？",
            include_course_knowledge=True,
            knowledge_points=["导数"],
            user_memory_facts=["用户容易把内外层顺序写反"],
            course_knowledge_chunks=["链式法则用于复合函数求导"],
        )

    monkeypatch.setattr(tutoring_api, "get_ai_providers", lambda: FakeProviders())
    monkeypatch.setattr(tutoring_api, "build_tutoring_retrieval_context_with_ai", fake_build_context)

    response = asyncio.run(tutoring_api.tutoring_chat(request))
    body = asyncio.run(_consume_response_body(response.body_iterator))
    events = [
        json.loads(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: ")
    ]

    assert events[1]["content"] == "链式法则先看外层函数，再乘以内层导数。"
    assert [item["name"] for item in events[2]["knowledge_points"]] == ["链式法则", "复合函数"]
    assert events[3]["suggestion"] == "先确认外层函数，再检查内层导数。"


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

    monkeypatch.setattr(tutoring_api, "get_ai_providers", lambda: FakeProviders())
    monkeypatch.setattr(tutoring_api, "build_tutoring_retrieval_context_with_ai", fake_build_context)

    response = asyncio.run(tutoring_api.tutoring_chat(request))
    body = asyncio.run(_consume_response_body(response.body_iterator))
    events = [
        json.loads(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: ")
    ]

    assert [event["type"] for event in events] == ["chunk", "knowledge_points", "suggestion", "done"]


def test_build_model_response_uses_chat_provider_without_react_agent(monkeypatch) -> None:
    request = TutoringChatRequest(
        user_id="user-1",
        course_id="course-1",
        message="链式法则怎么用？",
        user_profile=TutoringUserProfile(guidance_level="L2", knowledge_weak=["导数"]),
    )
    context = TutoringRetrievalContext(
        user_id="user-1",
        course_id="course-1",
        query_text="链式法则怎么用？",
        include_course_knowledge=True,
        knowledge_points=["导数"],
        user_memory_facts=[],
        course_knowledge_chunks=[],
    )

    class FakeChatProvider:
        model = object()
        formatter = object()

        async def complete(self, messages):
            return (
                '{"model_text":"chat 单路径回答",'
                '"knowledge_points":["链式法则"],'
                '"suggestion":"继续做同类题。"}'
            )

    class FakeProviders:
        chat = FakeChatProvider()

    class FakeReactAgent:
        async def generate(self, user_message):
            return (
                '{"model_text":"react 不应进入默认链路",'
                '"knowledge_points":["ReAct"],'
                '"suggestion":"不应使用。"}'
            )

    monkeypatch.setattr(tutoring_api, "get_ai_providers", lambda: FakeProviders())
    monkeypatch.setattr(tutoring_api, "TutorReActAgent", lambda **kwargs: FakeReactAgent(), raising=False)

    response = asyncio.run(tutoring_api._build_model_response(request, context))

    assert response.model_text == "chat 单路径回答"
    assert response.knowledge_point_names == ["链式法则"]
    assert response.suggestion_text == "继续做同类题。"


async def _consume_response_body(body_iterator) -> str:
    chunks = []
    async for chunk in body_iterator:
        chunks.append(chunk)
    return "".join(chunks)
