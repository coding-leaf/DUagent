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
        from agent_service.memory.qdrant_store import ensure_collection_exists

        await ensure_collection_exists(self._store)
        client = self._store.get_client()
        await client.upsert(
            collection_name=self._store.collection_name,
            points=points,
            wait=True,
        )

    async def list_ingested_source_files(self, course_id: str) -> set[str]:
        """返回已摄入的源文件集合，输入课程 ID，输出该课程下所有 source_file 的去重集合。"""
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        client = self._store.get_client()
        source_files: set[str] = set()
        offset = None
        while True:
            points, offset = await client.scroll(
                collection_name=self._store.collection_name,
                scroll_filter=Filter(
                    must=[FieldCondition(key="course_id", match=MatchValue(value=course_id))]
                ),
                with_payload=["source_file"],
                limit=256,
                offset=offset,
            )
            for point in points:
                payload = point.payload or {}
                source_file = payload.get("source_file")
                if isinstance(source_file, str) and source_file:
                    source_files.add(source_file)
            if offset is None:
                break
        return source_files


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
