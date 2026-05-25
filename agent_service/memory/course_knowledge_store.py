from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import UTC, datetime

from qdrant_client.models import PointStruct

from agent_service.core.config import settings
from agent_service.memory.course_knowledge_ingestion import CourseKnowledgeChunk
from agent_service.memory.qdrant_store import build_qdrant_store


class QdrantCourseKnowledgeStore:
    """写入课程知识库，通过 AgentScope QdrantStore 异步 upsert 课程切片。"""

    def __init__(self, store=None) -> None:
        self._store = store or _build_qdrant_store()

    async def upsert_chunks(
        self,
        *,
        chunks: Sequence[CourseKnowledgeChunk],
        vectors: Sequence[Sequence[float]],
    ) -> None:
        points = [
            PointStruct(
                id=_chunk_point_id(chunk),
                vector=list(vector),
                payload=_chunk_payload(chunk),
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
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
    return build_qdrant_store(settings.QDRANT_COURSE_KNOWLEDGE_COLLECTION)


def _chunk_point_id(chunk: CourseKnowledgeChunk) -> str:
    raw = (
        f"{chunk.course_id}::{chunk.source_file}::{chunk.doc_id}::"
        f"{chunk.chunk_id}::{chunk.content}"
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _chunk_payload(chunk: CourseKnowledgeChunk) -> dict[str, object]:
    return {
        "course_id": chunk.course_id,
        "source_file": chunk.source_file,
        "source_type": chunk.source_type,
        "content": chunk.content,
        "doc_id": chunk.doc_id,
        "chunk_id": chunk.chunk_id,
        "total_chunks": chunk.total_chunks,
        "source": "knowledge_ingestion",
        "created_at": datetime.now(UTC).isoformat(),
    }
