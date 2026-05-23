from agent_service.memory.vector_store import QdrantVectorStore, VectorSearchResult


class FakePoint:
    def __init__(self, payload: dict, score: float = 0.9) -> None:
        self.payload = payload
        self.score = score


class FakeQueryResponse:
    def __init__(self, points: list[FakePoint]) -> None:
        self.points = points


class FakeQdrantClient:
    def __init__(self) -> None:
        self.calls = []

    def query_points(self, **kwargs):
        self.calls.append(kwargs)
        return FakeQueryResponse(
            [
                FakePoint({"fact_text": "用户容易混淆链式法则", "user_id": "user-1"}, 0.8),
                FakePoint({"content": "链式法则用于复合函数求导", "course_id": "course-1"}, 0.7),
            ]
        )


def test_search_user_memory_filters_by_user_id_and_maps_payload_text() -> None:
    client = FakeQdrantClient()
    store = QdrantVectorStore(client=client)

    results = store.search_user_memory(user_id="user-1", vector=[0.1, 0.2], limit=2)

    assert results[0] == VectorSearchResult(text="用户容易混淆链式法则", score=0.8, payload=results[0].payload)
    assert client.calls[0]["collection_name"] == "user_memory"
    assert client.calls[0]["limit"] == 2
    assert client.calls[0]["query"] == [0.1, 0.2]
    assert "user_id" in repr(client.calls[0]["query_filter"])


def test_search_course_knowledge_filters_by_course_id_and_maps_content() -> None:
    client = FakeQdrantClient()
    store = QdrantVectorStore(client=client)

    results = store.search_course_knowledge(course_id="course-1", vector=[0.1, 0.2], limit=1)

    assert results[1].text == "链式法则用于复合函数求导"
    assert results[1].score == 0.7
    assert client.calls[0]["collection_name"] == "course_knowledge"
    assert "course_id" in repr(client.calls[0]["query_filter"])
