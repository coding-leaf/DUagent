from dataclasses import dataclass
from typing import Any, Protocol, Sequence

from qdrant_client.models import FieldCondition, Filter, MatchValue

from agent_service.core.qdrant import get_qdrant_client


@dataclass(frozen=True)
class VectorSearchResult:
    text: str
    score: float | None
    payload: dict[str, Any]


class QdrantLikeClient(Protocol):
    def query_points(self, **kwargs: Any) -> Any:
        """执行 Qdrant 向量查询，输入 query_points 参数，输出 Qdrant 查询响应。"""


class QdrantVectorStore:
    """封装 tutoring 需要的 Qdrant 检索，输入用户/课程范围和向量，输出结构化文本结果。"""

    def __init__(self, client: QdrantLikeClient | None = None) -> None:
        self.client = client or get_qdrant_client()

    def search_user_memory(self, user_id: str, vector: Sequence[float], limit: int = 3) -> list[VectorSearchResult]:
        response = self.client.query_points(
            collection_name="user_memory",
            query=list(vector),
            query_filter=_match_filter("user_id", user_id),
            limit=limit,
            with_payload=True,
        )
        return _map_query_response(response)

    def search_course_knowledge(
        self,
        course_id: str,
        vector: Sequence[float],
        limit: int = 3,
    ) -> list[VectorSearchResult]:
        response = self.client.query_points(
            collection_name="course_knowledge",
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
