from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime, UTC

from qdrant_client.models import PointStruct

from agent_service.core.config import settings
from agent_service.memory.qdrant_store import build_qdrant_store
from agent_service.schemas.memory import ExtractedFact


_MEMORY_POINT_NAMESPACE = uuid.UUID("b9cf7a5f-0f29-4bd1-9232-6d7ef79bb6c1")


class QdrantUserMemoryStore:
    """写入用户长期记忆，通过 AgentScope QdrantStore 异步 upsert facts。"""

    def __init__(self, store=None) -> None:
        self._store = store or _build_qdrant_store()

    async def upsert_facts(
        self,
        *,
        user_id: str,
        conversation_id: str,
        facts: Sequence[ExtractedFact],
        vectors: Sequence[Sequence[float]],
    ) -> None:
        points = [
            PointStruct(
                id=build_memory_point_id(
                    user_id,
                    conversation_id,
                    fact.fact_type or "",
                    fact.content or "",
                ),
                vector=list(vector),
                payload=_fact_payload(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    fact=fact,
                ),
            )
            for fact, vector in zip(facts, vectors, strict=True)
        ]
        if not points:
            return
        from agent_service.memory.qdrant_store import ensure_collection_exists

        await ensure_collection_exists(self._store)
        client = self._store.get_client()
        await client.upsert(
            collection_name=self._store.collection_name,
            points=points,
            wait=True,
        )


def _build_qdrant_store():
    return build_qdrant_store(settings.QDRANT_USER_MEMORY_COLLECTION)


def build_memory_point_id(user_id: str, conversation_id: str, fact_type: str, content: str) -> str:
    """Return a stable UUID point id for a user memory fact."""
    raw = f"{user_id}|{conversation_id}|{fact_type}|{content}"
    return str(uuid.uuid5(_MEMORY_POINT_NAMESPACE, raw))


def _fact_payload(*, user_id: str, conversation_id: str, fact: ExtractedFact) -> dict[str, object]:
    return {
        "user_id": user_id,
        "conversation_id": conversation_id,
        "fact_text": fact.content,
        "fact_type": fact.fact_type,
        "knowledge_point": fact.knowledge_point,
        "confidence": fact.confidence,
        "source": "memory_compress",
        "created_at": datetime.now(UTC).isoformat(),
    }
