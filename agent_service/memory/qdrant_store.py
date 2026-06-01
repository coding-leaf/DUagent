import logging

from agent_service.core.config import settings

logger = logging.getLogger(__name__)


def build_qdrant_store(collection_name: str):
    from agentscope.rag import QdrantStore

    location = settings.QDRANT_URL or settings.QDRANT_PATH
    client_kwargs = {"check_compatibility": False}
    if settings.QDRANT_API_KEY:
        client_kwargs["api_key"] = settings.QDRANT_API_KEY

    return QdrantStore(
        location=location,
        collection_name=collection_name,
        dimensions=settings.EMBEDDING_DIMENSION,
        client_kwargs=client_kwargs,
    )


async def ensure_collection_exists(store) -> None:
    """确保 Qdrant collection 存在，不存在则创建。fresh Qdrant 首次写入前调用。

    创建失败时静默跳过（如测试 fake client 不支持 create_collection），依赖 upsert 自身报错。
    """
    from qdrant_client.models import Distance, VectorParams

    client = store.get_client()
    try:
        collections = await client.get_collections()
        names = {c.name for c in collections.collections}
        if store.collection_name in names:
            return
    except Exception as exc:
        logger.warning(
            "Failed to check Qdrant collection '%s': %s",
            store.collection_name,
            exc,
        )
    try:
        await client.create_collection(
            collection_name=store.collection_name,
            vectors_config=VectorParams(
                size=settings.EMBEDDING_DIMENSION,
                distance=Distance.COSINE,
            ),
        )
    except Exception as exc:
        logger.warning(
            "Failed to create Qdrant collection '%s': %s",
            store.collection_name,
            exc,
        )
