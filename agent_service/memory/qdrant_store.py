from agent_service.core.config import settings


def build_qdrant_store(collection_name: str):
    from agentscope.rag import QdrantStore

    return QdrantStore(
        location=None,
        collection_name=collection_name,
        dimensions=settings.EMBEDDING_DIMENSION,
        client_kwargs={"path": settings.QDRANT_PATH, "check_compatibility": False},
    )
