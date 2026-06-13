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

        async def search_user_memory(self, user_id, vector, limit=3):
            self.calls.append(("user_memory", user_id, vector, limit))
            return [VectorSearchResult(text="用户容易把内外层顺序写反", score=0.8, payload={})]

        async def search_course_knowledge(self, course_id, vector, limit=3):
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


def test_build_tutoring_retrieval_context_with_ai_skips_course_search_for_global_scope() -> None:
    request = TutoringChatRequest(
        user_id="user-1",
        scope="global",
        message="帮我制定学习计划",
        user_profile=TutoringUserProfile(guidance_level="L2", knowledge_weak=["导数"]),
    )

    class FakeEmbeddingProvider:
        async def embed_texts(self, texts):
            return [[0.1, 0.2, 0.3]]

    class FakeVectorStore:
        def __init__(self) -> None:
            self.calls = []

        async def search_user_memory(self, user_id, vector, limit=3):
            self.calls.append(("user_memory", user_id, vector, limit))
            return [VectorSearchResult(text="用户容易把内外层顺序写反", score=0.8, payload={})]

        async def search_course_knowledge(self, course_id, vector, limit=3):
            self.calls.append(("course_knowledge", course_id, vector, limit))
            return []

    vector_store = FakeVectorStore()

    context = asyncio.run(
        build_tutoring_retrieval_context_with_ai(
            request,
            embedding_provider=FakeEmbeddingProvider(),
            vector_store=vector_store,
        )
    )

    assert context.user_memory_facts == ["用户容易把内外层顺序写反"]
    assert context.course_knowledge_chunks == []
    assert len(vector_store.calls) == 1
    assert vector_store.calls[0][0] == "user_memory"


def test_build_tutoring_retrieval_context_with_ai_keeps_user_memory_when_course_search_fails(caplog) -> None:
    request = TutoringChatRequest(
        user_id="user-1",
        course_id="course-1",
        message="链式法则怎么用？",
        user_profile=TutoringUserProfile(guidance_level="L2", knowledge_weak=["导数"]),
    )

    class FakeEmbeddingProvider:
        async def embed_texts(self, texts):
            return [[0.1, 0.2, 0.3]]

    class FakeVectorStore:
        async def search_user_memory(self, user_id, vector, limit=3):
            return [VectorSearchResult(text="用户容易把内外层顺序写反", score=0.8, payload={})]

        async def search_course_knowledge(self, course_id, vector, limit=3):
            raise RuntimeError("qdrant course collection unavailable")

    with caplog.at_level("WARNING", logger="agent_service.memory.tutoring_retrieval"):
        context = asyncio.run(
            build_tutoring_retrieval_context_with_ai(
                request,
                embedding_provider=FakeEmbeddingProvider(),
                vector_store=FakeVectorStore(),
            )
        )

    assert context.user_memory_facts == ["用户容易把内外层顺序写反"]
    assert context.course_knowledge_chunks == []
    assert "Tutoring course knowledge retrieval failed" in caplog.text


def test_build_tutoring_retrieval_context_with_ai_reranks_results() -> None:
    request = TutoringChatRequest(
        user_id="user-1",
        course_id="course-1",
        message="链式法则怎么用？",
        user_profile=TutoringUserProfile(guidance_level="L2", knowledge_weak=["导数"]),
    )

    class FakeEmbeddingProvider:
        async def embed_texts(self, texts):
            return [[0.1, 0.2, 0.3]]

    class FakeRerankerProvider:
        async def score(self, query, documents):
            if documents == ["用户容易把内外层顺序写反", "用户容易漏写中间步骤"]:
                return [0.1, 0.9]
            return [0.2, 0.8]

    class FakeVectorStore:
        async def search_user_memory(self, user_id, vector, limit=3):
            return [
                VectorSearchResult(text="用户容易把内外层顺序写反", score=0.8, payload={}),
                VectorSearchResult(text="用户容易漏写中间步骤", score=0.7, payload={}),
            ]

        async def search_course_knowledge(self, course_id, vector, limit=3):
            return [
                VectorSearchResult(text="链式法则用于复合函数求导", score=0.7, payload={}),
                VectorSearchResult(text="链式法则要乘以内层导数", score=0.6, payload={}),
            ]

    context = asyncio.run(
        build_tutoring_retrieval_context_with_ai(
            request,
            embedding_provider=FakeEmbeddingProvider(),
            reranker_provider=FakeRerankerProvider(),
            vector_store=FakeVectorStore(),
        )
    )

    assert context.user_memory_facts == ["用户容易漏写中间步骤", "用户容易把内外层顺序写反"]
    assert context.course_knowledge_chunks == ["链式法则要乘以内层导数", "链式法则用于复合函数求导"]


def test_build_tutoring_retrieval_context_with_ai_keeps_original_order_when_reranker_fails(caplog) -> None:
    request = TutoringChatRequest(
        user_id="user-1",
        course_id="course-1",
        message="链式法则怎么用？",
        user_profile=TutoringUserProfile(guidance_level="L2", knowledge_weak=["导数"]),
    )

    class FakeEmbeddingProvider:
        async def embed_texts(self, texts):
            return [[0.1, 0.2, 0.3]]

    class FailingRerankerProvider:
        async def score(self, query, documents):
            raise RuntimeError("reranker unavailable")

    class FakeVectorStore:
        async def search_user_memory(self, user_id, vector, limit=3):
            return [
                VectorSearchResult(text="用户容易把内外层顺序写反", score=0.8, payload={}),
                VectorSearchResult(text="用户容易漏写中间步骤", score=0.7, payload={}),
            ]

        async def search_course_knowledge(self, course_id, vector, limit=3):
            return [
                VectorSearchResult(text="链式法则用于复合函数求导", score=0.7, payload={}),
                VectorSearchResult(text="链式法则要乘以内层导数", score=0.6, payload={}),
            ]

    with caplog.at_level("WARNING", logger="agent_service.memory.tutoring_retrieval"):
        context = asyncio.run(
            build_tutoring_retrieval_context_with_ai(
                request,
                embedding_provider=FakeEmbeddingProvider(),
                reranker_provider=FailingRerankerProvider(),
                vector_store=FakeVectorStore(),
            )
        )

    assert context.user_memory_facts == ["用户容易把内外层顺序写反", "用户容易漏写中间步骤"]
    assert context.course_knowledge_chunks == ["链式法则用于复合函数求导", "链式法则要乘以内层导数"]
    assert "Tutoring rerank failed" in caplog.text


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


def test_build_tutoring_retrieval_context_with_ai_matches_kg_nodes() -> None:
    request = TutoringChatRequest(
        user_id="user-1",
        course_id="course-1",
        message="什么是二叉树？",
        user_profile=TutoringUserProfile(guidance_level="L2"),
        active_kg_nodes=[
            {"id": "1", "name": "图论"},
            {"id": "2", "name": "二叉树"},
            {"id": "3", "name": "平衡树"},
            {"id": "4", "name": "链表"},
        ],
    )

    class FakeEmbeddingProvider:
        async def embed_texts(self, texts):
            return [[0.1, 0.2, 0.3]]

    class FakeRerankerProvider:
        async def score(self, query, documents):
            scores = []
            for doc in documents:
                if doc == "二叉树":
                    scores.append(0.9)
                elif doc == "平衡树":
                    scores.append(0.8)
                elif doc == "图论":
                    scores.append(0.2)
                else:
                    scores.append(0.1)
            return scores

    class FakeVectorStore:
        async def search_user_memory(self, user_id, vector, limit=3):
            return []
        async def search_course_knowledge(self, course_id, vector, limit=3):
            return []

    context = asyncio.run(
        build_tutoring_retrieval_context_with_ai(
            request,
            embedding_provider=FakeEmbeddingProvider(),
            reranker_provider=FakeRerankerProvider(),
            vector_store=FakeVectorStore(),
        )
    )

    assert [node["name"] for node in context.matched_kg_nodes] == ["二叉树", "平衡树"]
    assert len(context.matched_kg_nodes) == 2
