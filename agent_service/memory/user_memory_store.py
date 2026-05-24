from __future__ import annotations

import hashlib
import asyncio
from collections.abc import Sequence
from datetime import datetime, UTC
from typing import Protocol

from qdrant_client.models import PointStruct

from agent_service.core.config import settings
from agent_service.core.qdrant import get_qdrant_client
from agent_service.schemas.memory import ExtractedFact


class QdrantUpsertClient(Protocol):
    def upsert(self, **kwargs): ...


class QdrantUserMemoryStore:
    """写入用户长期记忆，输入 facts 和 vectors，输出 Qdrant upsert 副作用。"""

    def __init__(self, client: QdrantUpsertClient | None = None) -> None:
        self.client = client or get_qdrant_client()
        self.collection_name = settings.QDRANT_USER_MEMORY_COLLECTION

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
        await asyncio.to_thread(
            self.client.upsert,
            collection_name=self.collection_name,
            points=points,
            wait=True,
        )


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
