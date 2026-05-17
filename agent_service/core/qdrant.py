from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance
from core.config import settings

# Using local memory/disk for development
qdrant_client = QdrantClient(path=settings.QDRANT_PATH)

def init_collections():
    """
    Initialize Qdrant collections if they don't exist.
    """
    collections = ["course_knowledge", "user_memory"]
    for collection_name in collections:
        if not qdrant_client.collection_exists(collection_name):
            qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=768, distance=Distance.COSINE),
            )

def get_qdrant_client() -> QdrantClient:
    """
    Dependency to get the Qdrant client.
    """
    return qdrant_client
