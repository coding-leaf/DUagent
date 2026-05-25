from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import datetime, UTC

from qdrant_client.models import PointStruct

from agent_service.core.config import settings
from agent_service.memory.qdrant_store import build_qdrant_store
from agent_service.schemas.memory import ExtractedFact


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
                id=_fact_point_id(user_id=user_id, conversation_id=conversation_id, fact_text=fact.content or ""),
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
        client = self._store.get_client()
        await client.upsert(
            collection_name=self._store.collection_name,
            points=points,
            wait=True,
        )


def _build_qdrant_store():
    return build_qdrant_store(settings.QDRANT_USER_MEMORY_COLLECTION)


def _fact_point_id(*, user_id: str, conversation_id: str, fact_text: str) -> str:
    raw = f"{user_id}::{conversation_id}::{fact_text}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


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
