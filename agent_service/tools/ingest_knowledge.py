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


ChunkLoader = Callable[..., Awaitable[list[CourseKnowledgeChunk]]]
_EMBEDDING_BATCH_SIZE = 64


async def ingest_course_knowledge(
    course_dir: Path | str,
    *,
    embedding_provider: EmbeddingProvider | None = None,
    store: QdrantCourseKnowledgeStore | None = None,
    chunk_loader: ChunkLoader | None = None,
) -> KnowledgeIngestionResult:
    """导入本地课程资料，输入课程目录，输出导入的课程 ID 和切片数量。

    已摄入的源文件会被跳过，重复执行对同一课程目录为幂等操作。
    """
    root = Path(course_dir)
    course_id = root.stem if root.suffix else root.name
    target_store = store or QdrantCourseKnowledgeStore()
    ingested_files = await target_store.list_ingested_source_files(course_id)
    loader = chunk_loader or load_course_knowledge_chunks
    chunks = await loader(root, ingested_files=ingested_files)
    if not chunks:
        return KnowledgeIngestionResult(course_id=course_id, chunk_count=0)

    provider = embedding_provider or get_ai_providers().embedding
    vectors = await _embed_texts_in_batches(
        provider,
        [chunk.content for chunk in chunks],
        batch_size=_EMBEDDING_BATCH_SIZE,
    )
    await target_store.upsert_chunks(chunks=chunks, vectors=vectors)
    return KnowledgeIngestionResult(course_id=course_id, chunk_count=len(chunks))


async def _embed_texts_in_batches(
    provider: EmbeddingProvider,
    texts: list[str],
    *,
    batch_size: int,
) -> list[list[float]]:
    """向量化文本列表，输入切片文本，输出与输入顺序一致的 embedding 向量。"""
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        vectors.extend(await provider.embed_texts(batch))
    return vectors


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest local course knowledge into Qdrant.")
    parser.add_argument("course_dir", type=Path, help="Path to knowledge_base/<course_id> directory.")
    args = parser.parse_args()
    result = asyncio.run(ingest_course_knowledge(args.course_dir))
    print(f"ingested course_id={result.course_id} chunks={result.chunk_count}")


if __name__ == "__main__":
    main()
