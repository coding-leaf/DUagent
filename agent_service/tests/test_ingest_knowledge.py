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
    def __init__(self, ingested_files: set[str] | None = None) -> None:
        self.calls = []
        self._ingested_files = ingested_files or set()

    async def list_ingested_source_files(self, course_id: str) -> set[str]:
        return self._ingested_files

    async def upsert_chunks(self, *, chunks, vectors):
        self.calls.append((chunks, vectors))


async def fake_loader(course_dir: Path, *, ingested_files=None):
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


async def fake_file_loader(course_path: Path, *, ingested_files=None):
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


async def fake_empty_loader(course_dir: Path, *, ingested_files=None):
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


async def fake_loader_respecting_ingested(course_dir: Path, *, ingested_files=None):
    skipped = ingested_files or set()
    if "chapter_01.md" in skipped:
        return []
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


def test_ingest_course_knowledge_skips_already_ingested_files() -> None:
    """重复摄入同一课程目录时，跳过已摄入的源文件，返回 0 chunks。"""
    embedding_provider = FakeEmbeddingProvider()
    store = FakeStore(ingested_files={"chapter_01.md"})

    result = asyncio.run(
        ingest_course_knowledge(
            Path("/tmp/course-1"),
            embedding_provider=embedding_provider,
            store=store,
            chunk_loader=fake_loader_respecting_ingested,
        )
    )

    assert result.course_id == "course-1"
    assert result.chunk_count == 0
    assert embedding_provider.calls == []
    assert store.calls == []


def test_ingest_course_knowledge_passes_ingested_files_to_loader() -> None:
    """确认 ingest_course_knowledge 将已摄入文件集合传递给 chunk loader。"""
    embedding_provider = FakeEmbeddingProvider()
    store = FakeStore(ingested_files={"notes.txt"})

    captured_ingested = {}

    async def tracking_loader(course_dir: Path, *, ingested_files=None):
        captured_ingested["value"] = ingested_files
        return [
            CourseKnowledgeChunk(
                course_id="course-1",
                source_file="chapter_02.md",
                source_type="course_material",
                content="栈是一种后进先出的数据结构",
                doc_id="doc-2",
                chunk_id=0,
                total_chunks=1,
            )
        ]

    asyncio.run(
        ingest_course_knowledge(
            Path("/tmp/course-1"),
            embedding_provider=embedding_provider,
            store=store,
            chunk_loader=tracking_loader,
        )
    )

    assert captured_ingested["value"] == {"notes.txt"}
