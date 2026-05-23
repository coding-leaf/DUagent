import asyncio

from agent_service.memory.tutoring_retrieval import (
    build_tutoring_retrieval_context,
    build_tutoring_retrieval_context_with_ai,
)
from agent_service.memory.vector_store import VectorSearchResult
from agent_service.schemas.tutoring import TutoringChatRequest, TutoringUserProfile


def test_build_tutoring_retrieval_context_uses_course_scope_collections() -> None:
    request = TutoringChatRequest(
        user_id="user-1",
        course_id="course-1",
        message="导数怎么理解？",
        user_profile=TutoringUserProfile(guidance_level="L2", knowledge_weak=["导数"]),
    )

    context = build_tutoring_retrieval_context(request)

    assert context.user_id == "user-1"
    assert context.course_id == "course-1"
    assert context.include_course_knowledge is True
    assert context.query_text == "导数怎么理解？"
    assert [item.name for item in context.knowledge_points] == ["导数"]
    assert context.user_memory_facts == []
    assert context.course_knowledge_chunks == []


def test_build_tutoring_retrieval_context_skips_course_collection_for_global_scope() -> None:
    request = TutoringChatRequest(
        user_id="user-1",
        scope="global",
        message="帮我制定学习计划",
        user_profile=TutoringUserProfile(guidance_level="L3", knowledge_mastered=["函数"]),
    )

    context = build_tutoring_retrieval_context(request)

    assert context.course_id is None
    assert context.include_course_knowledge is False
    assert [item.name for item in context.knowledge_points] == ["函数"]


def test_build_tutoring_retrieval_context_with_ai_queries_memory_and_course_knowledge() -> None:
    request = TutoringChatRequest(
        user_id="user-1",
        course_id="course-1",
        message="链式法则怎么用？",
        user_profile=TutoringUserProfile(guidance_level="L2", knowledge_weak=["导数"]),
    )

    class FakeEmbeddingProvider:
        async def embed_texts(self, texts):
            assert texts == ["链式法则怎么用？"]
            return [[0.1, 0.2, 0.3]]

    class FakeVectorStore:
        def __init__(self) -> None:
            self.calls = []

        def search_user_memory(self, user_id, vector, limit=3):
            self.calls.append(("user_memory", user_id, vector, limit))
            return [VectorSearchResult(text="用户容易把内外层顺序写反", score=0.8, payload={})]

        def search_course_knowledge(self, course_id, vector, limit=3):
            self.calls.append(("course_knowledge", course_id, vector, limit))
            return [VectorSearchResult(text="链式法则用于复合函数求导", score=0.7, payload={})]

    vector_store = FakeVectorStore()

    context = asyncio.run(
        build_tutoring_retrieval_context_with_ai(
            request,
            embedding_provider=FakeEmbeddingProvider(),
            vector_store=vector_store,
        )
    )

    assert context.user_memory_facts == ["用户容易把内外层顺序写反"]
    assert context.course_knowledge_chunks == ["链式法则用于复合函数求导"]
    assert vector_store.calls == [
        ("user_memory", "user-1", [0.1, 0.2, 0.3], 3),
        ("course_knowledge", "course-1", [0.1, 0.2, 0.3], 3),
    ]


def test_build_tutoring_retrieval_context_with_ai_degrades_on_retrieval_failure(caplog) -> None:
    request = TutoringChatRequest(
        user_id="user-1",
        course_id="course-1",
        message="链式法则怎么用？",
        user_profile=TutoringUserProfile(guidance_level="L2", knowledge_weak=["导数"]),
    )

    class FailingEmbeddingProvider:
        async def embed_texts(self, texts):
            raise RuntimeError("embedding unavailable")

    with caplog.at_level("WARNING", logger="agent_service.memory.tutoring_retrieval"):
        context = asyncio.run(
            build_tutoring_retrieval_context_with_ai(
                request,
                embedding_provider=FailingEmbeddingProvider(),
                vector_store=None,
            )
        )

    assert context.user_memory_facts == []
    assert context.course_knowledge_chunks == []
    assert "Tutoring retrieval failed" in caplog.text
