from __future__ import annotations

import argparse
import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from agent_service.core.ai import EmbeddingProvider, get_ai_providers
from agent_service.memory.course_knowledge_ingestion import (
    CourseKnowledgeChunk,
    load_course_knowledge_chunks,
)
from agent_service.memory.course_knowledge_store import QdrantCourseKnowledgeStore


@dataclass(frozen=True)
class KnowledgeIngestionResult:
    course_id: str
    chunk_count: int


ChunkLoader = Callable[[Path], Awaitable[list[CourseKnowledgeChunk]]]


async def ingest_course_knowledge(
    course_dir: Path | str,
    *,
    embedding_provider: EmbeddingProvider | None = None,
    store: QdrantCourseKnowledgeStore | None = None,
    chunk_loader: ChunkLoader | None = None,
) -> KnowledgeIngestionResult:
    """导入本地课程资料，输入课程目录，输出导入的课程 ID 和切片数量。"""
    root = Path(course_dir)
    loader = chunk_loader or load_course_knowledge_chunks
    chunks = await loader(root)
    if not chunks:
        return KnowledgeIngestionResult(course_id=root.stem if root.is_file() else root.name, chunk_count=0)

    provider = embedding_provider or get_ai_providers().embedding
    vectors = await provider.embed_texts([chunk.content for chunk in chunks])
    target_store = store or QdrantCourseKnowledgeStore()
    await target_store.upsert_chunks(chunks=chunks, vectors=vectors)
    return KnowledgeIngestionResult(course_id=chunks[0].course_id, chunk_count=len(chunks))


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest local course knowledge into Qdrant.")
    parser.add_argument("course_dir", type=Path, help="Path to knowledge_base/<course_id> directory.")
    args = parser.parse_args()
    result = asyncio.run(ingest_course_knowledge(args.course_dir))
    print(f"ingested course_id={result.course_id} chunks={result.chunk_count}")


if __name__ == "__main__":
    main()
