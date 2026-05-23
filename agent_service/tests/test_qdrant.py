from qdrant_client.models import Distance, VectorParams

from agent_service.core import qdrant as qdrant_module


class FakeQdrantClient:
    def __init__(self) -> None:
        self.existing_collections = set()
        self.created_collections: list[tuple[str, VectorParams]] = []

    def collection_exists(self, collection_name: str) -> bool:
        return collection_name in self.existing_collections

    def create_collection(self, collection_name: str, vectors_config: VectorParams) -> None:
        self.created_collections.append((collection_name, vectors_config))


def test_init_collections_uses_configured_names_and_dimension(monkeypatch) -> None:
    fake_client = FakeQdrantClient()

    class FakeSettings:
        QDRANT_USER_MEMORY_COLLECTION = "user_memory_v1_1024"
        QDRANT_COURSE_KNOWLEDGE_COLLECTION = "course_knowledge_v1_1024"
        EMBEDDING_DIMENSION = 1024

    monkeypatch.setattr(qdrant_module, "settings", FakeSettings())
    monkeypatch.setattr(qdrant_module, "get_qdrant_client", lambda: fake_client)

    qdrant_module.init_collections()

    assert [name for name, _ in fake_client.created_collections] == [
        "course_knowledge_v1_1024",
        "user_memory_v1_1024",
    ]
    for _, vectors_config in fake_client.created_collections:
        assert vectors_config == VectorParams(size=1024, distance=Distance.COSINE)
