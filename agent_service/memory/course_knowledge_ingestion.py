from __future__ import annotations

from collections.abc import Awaitable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from agentscope.rag import PDFReader, TextReader


@dataclass(frozen=True)
class CourseKnowledgeChunk:
    course_id: str
    source_file: str
    source_type: str
    content: str
    doc_id: str
    chunk_id: int
    total_chunks: int


class AgentScopeReader(Protocol):
    def __call__(self, source: str) -> Awaitable[list[Any]]:
        """读取课程资料文件，输入文件路径或文本，输出 AgentScope Document 列表。"""


async def load_course_knowledge_chunks(
    course_dir: Path | str,
    *,
    reader: AgentScopeReader | None = None,
) -> list[CourseKnowledgeChunk]:
    """读取课程资料目录或单个课程文件，输入路径，输出可写入课程知识库的切片。"""
    root = Path(course_dir)
    if not root.exists():
        raise ValueError(f"course path does not exist: {root}")

    course_id = root.stem if root.is_file() else root.name
    source_root = root.parent if root.is_file() else root
    chunks: list[CourseKnowledgeChunk] = []
    for source_path in _iter_supported_sources(root):
        if not source_path.is_file() or source_path.suffix.lower() not in {".md", ".txt", ".pdf"}:
            continue
        file_reader = reader or _build_reader_for_file(source_path)
        documents = await file_reader(str(source_path))
        chunks.extend(
            _documents_to_chunks(
                course_id=course_id,
                root=source_root,
                source_path=source_path,
                documents=documents,
            )
        )
    return chunks


def _iter_supported_sources(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    if not root.is_dir():
        return []
    return sorted(root.rglob("*"))


def _build_reader_for_file(source_path: Path) -> AgentScopeReader:
    if source_path.suffix.lower() == ".pdf":
        return PDFReader(chunk_size=512, split_by="char")
    return TextReader(chunk_size=512, split_by="char")


def _documents_to_chunks(
    *,
    course_id: str,
    root: Path,
    source_path: Path,
    documents: list[Any],
) -> list[CourseKnowledgeChunk]:
    relative_path = source_path.relative_to(root).as_posix()
    chunks: list[CourseKnowledgeChunk] = []
    for index, document in enumerate(documents):
        metadata = getattr(document, "metadata", None)
        content = _metadata_text(metadata)
        if not content:
            continue
        chunks.append(
            CourseKnowledgeChunk(
                course_id=course_id,
                source_file=relative_path,
                source_type="course_material",
                content=content,
                doc_id=str(getattr(metadata, "doc_id", None) or getattr(document, "id", "")),
                chunk_id=int(getattr(metadata, "chunk_id", index)),
                total_chunks=int(getattr(metadata, "total_chunks", len(documents))),
            )
        )
    return chunks


def _metadata_text(metadata: Any) -> str:
    content = getattr(metadata, "content", None)
    if isinstance(content, dict):
        text = content.get("text")
        return text.strip() if isinstance(text, str) else ""
    text = getattr(content, "text", None)
    return text.strip() if isinstance(text, str) else ""
