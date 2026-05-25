import asyncio

from agent_service.memory import vector_store as vector_store_module
from agent_service.memory.vector_store import QdrantVectorStore, VectorSearchResult


class FakePoint:
    def __init__(self, payload: dict, score: float = 0.9) -> None:
        self.payload = payload
        self.score = score


class FakeQueryResponse:
    def __init__(self, points: list[FakePoint]) -> None:
        self.points = points


class FakeAsyncQdrantClient:
    def __init__(self) -> None:
        self.calls = []

    async def query_points(self, **kwargs):
        self.calls.append(kwargs)
        return FakeQueryResponse(
            [
                FakePoint({"fact_text": "用户容易混淆链式法则", "user_id": "user-1"}, 0.8),
                FakePoint({"content": "链式法则用于复合函数求导", "course_id": "course-1"}, 0.7),
            ]
        )


class FakeQdrantStore:
    def __init__(self, collection_name: str) -> None:
        self.collection_name = collection_name
        self._client = FakeAsyncQdrantClient()
        self.calls = self._client.calls

    def get_client(self):
        return self._client


def test_search_user_memory_filters_by_user_id_and_maps_payload_text() -> None:
    user_store = FakeQdrantStore("user_memory_v1_1024")
    course_store = FakeQdrantStore("course_knowledge_v1_1024")
    store = QdrantVectorStore(user_memory_store=user_store, course_knowledge_store=course_store)

    results = asyncio.run(store.search_user_memory(user_id="user-1", vector=[0.1, 0.2], limit=2))

    assert results[0] == VectorSearchResult(text="用户容易混淆链式法则", score=0.8, payload=results[0].payload)
    assert user_store.calls[0]["collection_name"] == "user_memory_v1_1024"
    assert user_store.calls[0]["limit"] == 2
    assert user_store.calls[0]["query"] == [0.1, 0.2]
    assert "user_id" in repr(user_store.calls[0]["query_filter"])


def test_search_course_knowledge_filters_by_course_id_and_maps_content() -> None:
    user_store = FakeQdrantStore("user_memory_v1_1024")
    course_store = FakeQdrantStore("course_knowledge_v1_1024")
    store = QdrantVectorStore(user_memory_store=user_store, course_knowledge_store=course_store)

    results = asyncio.run(store.search_course_knowledge(course_id="course-1", vector=[0.1, 0.2], limit=1))

    assert results[1].text == "链式法则用于复合函数求导"
    assert results[1].score == 0.7
    assert course_store.calls[0]["collection_name"] == "course_knowledge_v1_1024"
    assert "course_id" in repr(course_store.calls[0]["query_filter"])
