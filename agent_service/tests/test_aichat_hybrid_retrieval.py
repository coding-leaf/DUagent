import asyncio

import pytest

from agent_service.memory.tutoring_retrieval import build_tutoring_retrieval_context_with_ai
from agent_service.memory.vector_store import VectorSearchResult
from agent_service.schemas.tutoring import TutoringChatRequest, TutoringUserProfile


class FakeEmbeddingProvider:
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        # Return a dummy vector
        return [[0.1, 0.2, 0.3]] * len(texts)


class FakeRerankerProvider:
    def __init__(self, expected_scores: dict[str, float] = None):
        self.expected_scores = expected_scores or {}

    async def score(self, query: str, documents: list[str]) -> list[float]:
        # Return mocked score or a default
        scores = []
        for doc in documents:
            if doc in self.expected_scores:
                scores.append(self.expected_scores[doc])
            elif any(doc in d for d in self.expected_scores):
                # fuzzy match
                matched_score = 0.0
                for k, v in self.expected_scores.items():
                    if k in doc:
                        matched_score = max(matched_score, v)
                scores.append(matched_score or 0.1)
            else:
                scores.append(0.1)
        return scores


class FakeVectorStore:
    def __init__(self, chunks: list[str] = None):
        self.chunks = chunks or []

    async def search_user_memory(self, user_id: str, vector: list[float], limit: int = 3) -> list[VectorSearchResult]:
        return []

    async def search_course_knowledge(self, course_id: str, vector: list[float], limit: int = 3) -> list[VectorSearchResult]:
        results = []
        for chunk in self.chunks:
            results.append(VectorSearchResult(text=chunk, score=0.8, payload={}))
        return results[:limit]


@pytest.mark.asyncio
async def test_hybrid_retrieval_wild_pointer_sample() -> None:
    request = TutoringChatRequest(
        user_id="user-1",
        course_id="course-c",
        message="什么是野指针？它和悬空指针有什么区别？",
        user_profile=TutoringUserProfile(guidance_level="L2"),
        active_kg_nodes=[
            {"id": "c_1", "name": "指针基础"},
            {"id": "c_2", "name": "野指针"},
            {"id": "c_3", "name": "悬空指针"},
            {"id": "c_4", "name": "内存泄漏"},
            {"id": "c_5", "name": "数组"},
        ],
    )

    reranker = FakeRerankerProvider(
        expected_scores={
            "野指针": 0.95,
            "悬空指针": 0.9,
            "指针基础": 0.6,
            "未初始化指针会导致野指针": 0.85,
            "free 后不置空会导致悬空指针": 0.80,
        }
    )

    vector_store = FakeVectorStore(
        chunks=[
            "未初始化指针会导致野指针，使用前必须分配内存或置为NULL。",
            "free 后不置空会导致悬空指针（Dangling Pointer）。",
        ]
    )

    context = await build_tutoring_retrieval_context_with_ai(
        request,
        embedding_provider=FakeEmbeddingProvider(),
        reranker_provider=reranker,
        vector_store=vector_store,
        limit=3,
    )

    # Assert that matched_kg_nodes contains the expected concepts
    matched_names = [node["name"] for node in context.matched_kg_nodes]
    assert "野指针" in matched_names
    assert "悬空指针" in matched_names
    
    # Assert course_knowledge_chunks is non-empty and contains expected info
    assert len(context.course_knowledge_chunks) == 2
    assert any("野指针" in chunk for chunk in context.course_knowledge_chunks)
    assert any("悬空指针" in chunk for chunk in context.course_knowledge_chunks)


@pytest.mark.asyncio
async def test_hybrid_retrieval_array_vs_pointer_sample() -> None:
    request = TutoringChatRequest(
        user_id="user-2",
        course_id="course-c",
        message="数组和指针有什么区别？",
        user_profile=TutoringUserProfile(guidance_level="L2"),
        active_kg_nodes=[
            {"id": "c_5", "name": "数组"},
            {"id": "c_1", "name": "指针基础"},
            {"id": "c_6", "name": "数组指针与指针数组"},
            {"id": "c_7", "name": "结构体"},
        ],
    )

    reranker = FakeRerankerProvider(
        expected_scores={
            "数组": 0.9,
            "指针基础": 0.85,
            "数组指针与指针数组": 0.8,
            "数组名退化为指针": 0.88,
            "sizeof操作符": 0.7,
        }
    )

    vector_store = FakeVectorStore(
        chunks=[
            "数组名在大多数表达式中会退化为指向其首元素的指针。",
            "sizeof(数组名)返回整个数组的字节数，而sizeof(指针)返回指针本身的大小。",
        ]
    )

    context = await build_tutoring_retrieval_context_with_ai(
        request,
        embedding_provider=FakeEmbeddingProvider(),
        reranker_provider=reranker,
        vector_store=vector_store,
        limit=3,
    )

    # Assert matched kg nodes
    matched_names = [node["name"] for node in context.matched_kg_nodes]
    assert "数组" in matched_names
    assert "指针基础" in matched_names

    # Assert chunks
    assert len(context.course_knowledge_chunks) == 2
    assert any("退化为指向其首元素的指针" in chunk for chunk in context.course_knowledge_chunks)


@pytest.mark.asyncio
async def test_hybrid_retrieval_malloc_sample() -> None:
    request = TutoringChatRequest(
        user_id="user-3",
        course_id="course-c",
        message="如何使用 malloc 动态分配内存？",
        user_profile=TutoringUserProfile(guidance_level="L2"),
        active_kg_nodes=[
            {"id": "c_8", "name": "动态内存分配"},
            {"id": "c_9", "name": "malloc/free"},
            {"id": "c_1", "name": "指针基础"},
            {"id": "c_4", "name": "内存泄漏"},
        ],
    )

    reranker = FakeRerankerProvider(
        expected_scores={
            "malloc/free": 0.95,
            "动态内存分配": 0.9,
            "内存泄漏": 0.8,
            "malloc函数使用": 0.92,
        }
    )

    vector_store = FakeVectorStore(
        chunks=[
            "malloc函数用于在堆上动态分配指定字节数的内存，返回void*指针。",
            "分配的内存必须使用free函数释放，否则会导致内存泄漏。",
        ]
    )

    context = await build_tutoring_retrieval_context_with_ai(
        request,
        embedding_provider=FakeEmbeddingProvider(),
        reranker_provider=reranker,
        vector_store=vector_store,
        limit=3,
    )

    # Assert matched kg nodes
    matched_names = [node["name"] for node in context.matched_kg_nodes]
    assert "malloc/free" in matched_names
    assert "动态内存分配" in matched_names

    # Assert chunks
    assert len(context.course_knowledge_chunks) == 2
    assert any("malloc函数" in chunk for chunk in context.course_knowledge_chunks)
