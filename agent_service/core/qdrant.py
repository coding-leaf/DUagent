from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance

from agent_service.core.config import settings

_qdrant_client: QdrantClient | None = None


def get_qdrant_client() -> QdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(path=settings.QDRANT_PATH)
    return _qdrant_client


def init_collections():
    client = get_qdrant_client()
    collections = [
        settings.QDRANT_COURSE_KNOWLEDGE_COLLECTION,
        settings.QDRANT_USER_MEMORY_COLLECTION,
    ]
    for collection_name in collections:
        if not client.collection_exists(collection_name):
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=settings.EMBEDDING_DIMENSION, distance=Distance.COSINE),
            )
