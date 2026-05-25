import asyncio
from pathlib import Path

from agentscope.rag import TextReader

from agent_service.memory.course_knowledge_ingestion import (
    CourseKnowledgeChunk,
    load_course_knowledge_chunks,
)


class FakeMetadata:
    def __init__(self) -> None:
        self.content = {"type": "text", "text": "PDF 中提取的课程内容"}
        self.doc_id = "pdf-doc-1"
        self.chunk_id = 0
        self.total_chunks = 1


class FakeDocument:
    def __init__(self) -> None:
        self.metadata = FakeMetadata()


class FakeReader:
    def __init__(self) -> None:
        self.sources = []

    async def __call__(self, source: str):
        self.sources.append(source)
        return [FakeDocument()]


def test_load_course_knowledge_chunks_uses_agentscope_text_reader(tmp_path: Path) -> None:
    course_dir = tmp_path / "course-1"
    course_dir.mkdir()
    source_file = course_dir / "chapter_01.md"
    source_file.write_text("链式法则用于复合函数求导。先求外层，再乘以内层导数。", encoding="utf-8")

    chunks = asyncio.run(
        load_course_knowledge_chunks(
            course_dir,
            reader=TextReader(chunk_size=10, split_by="char"),
        )
    )

    assert chunks
    assert chunks[0] == CourseKnowledgeChunk(
        course_id="course-1",
        source_file="chapter_01.md",
        source_type="course_material",
        content="链式法则用于复合函数",
        doc_id=chunks[0].doc_id,
        chunk_id=0,
        total_chunks=3,
    )
    assert chunks[0].doc_id


def test_load_course_knowledge_chunks_skips_unsupported_files(tmp_path: Path) -> None:
    course_dir = tmp_path / "course-1"
    course_dir.mkdir()
    (course_dir / "notes.txt").write_text("导数描述函数变化率。", encoding="utf-8")
    (course_dir / "image.png").write_bytes(b"not text")

    chunks = asyncio.run(
        load_course_knowledge_chunks(
            course_dir,
            reader=TextReader(chunk_size=20, split_by="char"),
        )
    )

    assert [chunk.source_file for chunk in chunks] == ["notes.txt"]


def test_load_course_knowledge_chunks_accepts_pdf_files(tmp_path: Path) -> None:
    course_dir = tmp_path / "course-1"
    course_dir.mkdir()
    pdf_file = course_dir / "chapter_01.pdf"
    pdf_file.write_bytes(b"%PDF-1.4")
    reader = FakeReader()

    chunks = asyncio.run(load_course_knowledge_chunks(course_dir, reader=reader))

    assert reader.sources == [str(pdf_file)]
    assert chunks[0].source_file == "chapter_01.pdf"
    assert chunks[0].content == "PDF 中提取的课程内容"
    assert chunks[0].doc_id == "pdf-doc-1"


def test_load_course_knowledge_chunks_accepts_single_pdf_file(tmp_path: Path) -> None:
    pdf_file = tmp_path / "data-structures.pdf"
    pdf_file.write_bytes(b"%PDF-1.4")
    reader = FakeReader()

    chunks = asyncio.run(load_course_knowledge_chunks(pdf_file, reader=reader))

    assert reader.sources == [str(pdf_file)]
    assert chunks[0].course_id == "data-structures"
    assert chunks[0].source_file == "data-structures.pdf"
    assert chunks[0].content == "PDF 中提取的课程内容"


def test_load_course_knowledge_chunks_rejects_missing_directory(tmp_path: Path) -> None:
    missing_dir = tmp_path / "missing"

    try:
        asyncio.run(load_course_knowledge_chunks(missing_dir))
    except ValueError as exc:
        assert "course path does not exist" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_load_course_knowledge_chunks_skips_ingested_files(tmp_path: Path) -> None:
    course_dir = tmp_path / "course-1"
    course_dir.mkdir()
    (course_dir / "chapter_01.md").write_text("链式法则", encoding="utf-8")
    (course_dir / "chapter_02.md").write_text("偏导数", encoding="utf-8")

    chunks = asyncio.run(
        load_course_knowledge_chunks(
            course_dir,
            reader=FakeReader(),
            ingested_files={"chapter_01.md"},
        )
    )

    source_files = [chunk.source_file for chunk in chunks]
    assert "chapter_01.md" not in source_files
    assert "chapter_02.md" in source_files
