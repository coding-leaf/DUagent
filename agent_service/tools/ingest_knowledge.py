from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from inspect import signature
from pathlib import Path

from agent_service.core.ai import EmbeddingProvider, get_ai_providers
from agent_service.memory.course_knowledge_ingestion import (
    CourseKnowledgeChunk,
    load_course_knowledge_chunks,
)
from agent_service.memory.course_knowledge_store import QdrantCourseKnowledgeStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class KnowledgeIngestionResult:
    course_id: str
    chunk_count: int
    duration_seconds: float = 0.0


ChunkLoader = Callable[..., Awaitable[list[CourseKnowledgeChunk]]]
_EMBEDDING_BATCH_SIZE = 64


async def ingest_course_knowledge(
    course_dir: Path | str,
    *,
    course_id: str | None = None,
    embedding_provider: EmbeddingProvider | None = None,
    store: QdrantCourseKnowledgeStore | None = None,
    chunk_loader: ChunkLoader | None = None,
) -> KnowledgeIngestionResult:
    """导入本地课程资料，输入课程目录，输出导入的课程 ID 和切片数量。

    已摄入的源文件会被跳过，重复执行对同一课程目录为幂等操作。
    """
    start_time = time.time()
    root = Path(course_dir)
    resolved_course_id = course_id or (root.stem if root.suffix else root.name)
    target_store = store or QdrantCourseKnowledgeStore()
    
    logger.debug(f"Checking previously ingested files for course_id: {resolved_course_id}")
    ingested_files = await target_store.list_ingested_source_files(resolved_course_id)
    
    loader = chunk_loader or load_course_knowledge_chunks
    logger.debug(f"Loading chunks from: {root}")
    chunks = await _load_chunks_with_course_id(
        loader,
        root,
        ingested_files=ingested_files,
        course_id=resolved_course_id,
    )
    if not chunks:
        duration = time.time() - start_time
        return KnowledgeIngestionResult(course_id=resolved_course_id, chunk_count=0, duration_seconds=duration)

    provider = embedding_provider or get_ai_providers().embedding
    logger.debug(f"Embedding {len(chunks)} chunks in batches of {_EMBEDDING_BATCH_SIZE}")
    vectors = await _embed_texts_in_batches(
        provider,
        [chunk.content for chunk in chunks],
        batch_size=_EMBEDDING_BATCH_SIZE,
    )
    
    logger.debug(f"Upserting chunks to Qdrant")
    await target_store.upsert_chunks(chunks=chunks, vectors=vectors)
    
    duration = time.time() - start_time
    return KnowledgeIngestionResult(course_id=resolved_course_id, chunk_count=len(chunks), duration_seconds=duration)


async def _load_chunks_with_course_id(
    loader: ChunkLoader,
    root: Path,
    *,
    ingested_files: set[str],
    course_id: str,
) -> list[CourseKnowledgeChunk]:
    """调用课程资料切片 loader，输入路径和课程 ID，输出可入库切片。"""
    if "course_id" in signature(loader).parameters:
        return await loader(root, ingested_files=ingested_files, course_id=course_id)
    return await loader(root, ingested_files=ingested_files)


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
    parser.add_argument("--verbose", action="store_true", help="Enable verbose debug logging.")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    course_dir = args.course_dir

    if not course_dir.exists():
        logger.error(f"Path does not exist: {course_dir}")
        sys.exit(1)
    
    if course_dir.is_file():
        if course_dir.suffix.lower() not in {".md", ".txt", ".pdf"}:
            logger.error(f"Unsupported file type: {course_dir.suffix}. Only .md, .txt, .pdf are supported.")
            sys.exit(1)
    elif course_dir.is_dir():
        supported = [
            p for p in course_dir.rglob("*") 
            if p.is_file() and p.suffix.lower() in {".md", ".txt", ".pdf"}
        ]
        if not supported:
            logger.error(f"No supported files found in directory: {course_dir}")
            sys.exit(1)
    else:
        logger.error(f"Path is neither a file nor a directory: {course_dir}")
        sys.exit(1)

    try:
        logger.info(f"Starting ingestion for {course_dir}")
        result = asyncio.run(ingest_course_knowledge(course_dir))
        logger.info(
            f"Ingestion completed for course_id={result.course_id}: "
            f"{result.chunk_count} chunks in {result.duration_seconds:.2f}s."
        )
        sys.exit(0)
    except KeyboardInterrupt:
        logger.warning("Ingestion interrupted by user.")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Ingestion failed due to top-level error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
