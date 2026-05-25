from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from qdrant_client.models import FieldCondition, Filter, MatchValue

from agent_service.core.config import settings
from agent_service.memory.qdrant_store import build_qdrant_store


@dataclass(frozen=True)
class VectorSearchResult:
    text: str
    score: float | None
    payload: dict[str, Any]


class QdrantVectorStore:
    """封装 Qdrant 检索，通过 AgentScope QdrantStore 异步访问用户记忆和课程知识。"""

    def __init__(self, user_memory_store=None, course_knowledge_store=None) -> None:
        self._user_store = user_memory_store or build_qdrant_store(
            settings.QDRANT_USER_MEMORY_COLLECTION,
        )
        self._course_store = course_knowledge_store or build_qdrant_store(
            settings.QDRANT_COURSE_KNOWLEDGE_COLLECTION,
        )

    async def search_user_memory(
        self,
        user_id: str,
        vector: Sequence[float],
        limit: int = 3,
    ) -> list[VectorSearchResult]:
        client = self._user_store.get_client()
        response = await client.query_points(
            collection_name=self._user_store.collection_name,
            query=list(vector),
            query_filter=_match_filter("user_id", user_id),
            limit=limit,
            with_payload=True,
        )
        return _map_query_response(response)

    async def search_course_knowledge(
        self,
        course_id: str,
        vector: Sequence[float],
        limit: int = 3,
    ) -> list[VectorSearchResult]:
        client = self._course_store.get_client()
        response = await client.query_points(
            collection_name=self._course_store.collection_name,
            query=list(vector),
            query_filter=_match_filter("course_id", course_id),
            limit=limit,
            with_payload=True,
        )
        return _map_query_response(response)



def _match_filter(field: str, value: str) -> Filter:
    return Filter(must=[FieldCondition(key=field, match=MatchValue(value=value))])


def _map_query_response(response: Any) -> list[VectorSearchResult]:
    points = getattr(response, "points", response)
    return [_map_point(point) for point in points]


def _map_point(point: Any) -> VectorSearchResult:
    payload = dict(getattr(point, "payload", {}) or {})
    text = _payload_text(payload)
    return VectorSearchResult(
        text=text,
        score=getattr(point, "score", None),
        payload=payload,
    )


def _payload_text(payload: dict[str, Any]) -> str:
    for key in ("fact_text", "content", "chunk_text", "text"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return ""
