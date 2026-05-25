import asyncio
from pathlib import Path

from agent_service.memory.course_knowledge_ingestion import CourseKnowledgeChunk
from agent_service.tools.ingest_knowledge import ingest_course_knowledge


class FakeEmbeddingProvider:
    def __init__(self) -> None:
        self.calls = []

    async def embed_texts(self, texts):
        self.calls.append(texts)
        return [[0.1, 0.2] for _ in texts]


class FakeStore:
    def __init__(self) -> None:
        self.calls = []

    async def upsert_chunks(self, *, chunks, vectors):
        self.calls.append((chunks, vectors))


async def fake_loader(course_dir: Path):
    assert course_dir.name == "course-1"
    return [
        CourseKnowledgeChunk(
            course_id="course-1",
            source_file="chapter_01.md",
            source_type="course_material",
            content="链式法则用于复合函数求导",
            doc_id="doc-1",
            chunk_id=0,
            total_chunks=1,
        )
    ]


async def fake_file_loader(course_path: Path):
    assert course_path.name == "data-structures.pdf"
    return [
        CourseKnowledgeChunk(
            course_id="data-structures",
            source_file="data-structures.pdf",
            source_type="course_material",
            content="线性表是数据结构的基本内容",
            doc_id="doc-1",
            chunk_id=0,
            total_chunks=1,
        )
    ]


def test_ingest_course_knowledge_loads_embeds_and_upserts() -> None:
    embedding_provider = FakeEmbeddingProvider()
    store = FakeStore()

    result = asyncio.run(
        ingest_course_knowledge(
            Path("/tmp/course-1"),
            embedding_provider=embedding_provider,
            store=store,
            chunk_loader=fake_loader,
        )
    )

    assert result.course_id == "course-1"
    assert result.chunk_count == 1
    assert embedding_provider.calls == [["链式法则用于复合函数求导"]]
    chunks, vectors = store.calls[0]
    assert chunks[0].course_id == "course-1"
    assert vectors == [[0.1, 0.2]]


def test_ingest_course_knowledge_returns_chunk_course_id_for_single_file() -> None:
    embedding_provider = FakeEmbeddingProvider()
    store = FakeStore()

    result = asyncio.run(
        ingest_course_knowledge(
            Path("/tmp/data-structures.pdf"),
            embedding_provider=embedding_provider,
            store=store,
            chunk_loader=fake_file_loader,
        )
    )

    assert result.course_id == "data-structures"
    assert result.chunk_count == 1
    assert embedding_provider.calls == [["线性表是数据结构的基本内容"]]


async def fake_empty_loader(course_dir: Path):
    return []


def test_ingest_course_knowledge_skips_empty_chunks() -> None:
    embedding_provider = FakeEmbeddingProvider()
    store = FakeStore()

    result = asyncio.run(
        ingest_course_knowledge(
            Path("/tmp/course-1"),
            embedding_provider=embedding_provider,
            store=store,
            chunk_loader=fake_empty_loader,
        )
    )

    assert result.course_id == "course-1"
    assert result.chunk_count == 0
    assert embedding_provider.calls == []
    assert store.calls == []
