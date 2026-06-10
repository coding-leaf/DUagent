from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from agent_service.core.ai import EmbeddingProvider
from agent_service.memory.vector_store import QdrantVectorStore, VectorSearchResult

DEFAULT_GROUNDING_THRESHOLD = 0.70
DEFAULT_SEARCH_LIMIT = 5
DEFAULT_PREVIEW_CHARS = 120


@dataclass(frozen=True)
class KgBodyGroundingResult:
    node_id: str
    node_name: str
    body_top1_score: float | None
    chunk_id: str | None
    source_file: str | None
    preview: str
    supported: bool


async def score_kg_body_grounding(
    course_id: str,
    nodes: Sequence[dict[str, Any]],
    embedding_provider: EmbeddingProvider,
    vector_store: QdrantVectorStore | None = None,
    *,
    limit: int = DEFAULT_SEARCH_LIMIT,
    threshold: float = DEFAULT_GROUNDING_THRESHOLD,
    preview_chars: int = DEFAULT_PREVIEW_CHARS,
) -> list[KgBodyGroundingResult]:
    """对 KG 节点做课程正文支撑度评分，输入课程 ID、节点和 embedding，输出每节点只读检索评分。"""
    store = vector_store or QdrantVectorStore()
    results: list[KgBodyGroundingResult] = []

    for node in nodes:
        node_id = _node_id(node)
        node_name = _node_query_text(node)
        vectors = await embedding_provider.embed_texts([node_name])
        query_vector = vectors[0] if vectors else []
        candidates = await store.search_course_knowledge(course_id, query_vector, limit=limit)
        body_candidate = _first_body_candidate(candidates)
        results.append(_build_result(node_id, node_name, body_candidate, threshold, preview_chars))

    return results


def _build_result(
    node_id: str,
    node_name: str,
    candidate: VectorSearchResult | None,
    threshold: float,
    preview_chars: int,
) -> KgBodyGroundingResult:
    if candidate is None:
        return KgBodyGroundingResult(
            node_id=node_id,
            node_name=node_name,
            body_top1_score=None,
            chunk_id=None,
            source_file=None,
            preview="",
            supported=False,
        )

    score = candidate.score
    return KgBodyGroundingResult(
        node_id=node_id,
        node_name=node_name,
        body_top1_score=score,
        chunk_id=_payload_string(candidate.payload, "chunk_id", "id", "point_id"),
        source_file=_payload_string(candidate.payload, "source_file", "file_name", "filename", "source"),
        preview=_preview(candidate.text, preview_chars),
        supported=score is not None and score >= threshold,
    )


def _first_body_candidate(candidates: Sequence[VectorSearchResult]) -> VectorSearchResult | None:
    for candidate in candidates:
        if candidate.text and not _is_toc_like_chunk(candidate.text, candidate.payload):
            return candidate
    return None


def _node_id(node: dict[str, Any]) -> str:
    value = node.get("id") or node.get("node_id") or _node_query_text(node)
    return str(value).strip()


def _node_query_text(node: dict[str, Any]) -> str:
    for key in ("name", "title", "label", "id", "node_id"):
        value = node.get(key)
        if isinstance(value, str) and value.strip():
            return _normalize_space(value)
    return ""


def _payload_string(payload: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _preview(text: str, max_chars: int) -> str:
    normalized = _normalize_space(text)
    if len(normalized) <= max_chars:
        return normalized
    return normalized[:max_chars].rstrip()


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _is_toc_like_chunk(text: str, payload: dict[str, Any]) -> bool:
    normalized = _normalize_space(text)
    if not normalized:
        return True

    marker_text = " ".join(
        str(payload.get(key, ""))
        for key in ("section", "title", "heading", "source_file", "file_name", "filename")
    ).lower()
    if any(marker in marker_text for marker in ("toc", "table of contents", "index", "目录", "索引")):
        return True

    lower = normalized.lower()
    if lower in {"toc", "table of contents", "contents", "index", "目录", "索引"}:
        return True

    if lower.startswith(("目录 ", "索引 ", "table of contents ", "contents ", "index ")):
        return _looks_like_listing(text)

    if len(normalized) <= 40 and not _has_body_punctuation(normalized):
        return True

    return _looks_like_listing(text) and not _has_body_sentence(normalized)


def _looks_like_listing(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) <= 1:
        lines = [part.strip() for part in re.split(r"\s{2,}|[;；]", text) if part.strip()]
    if len(lines) < 3:
        return False
    listed = sum(1 for line in lines if _is_listing_line(line))
    return listed >= 2 and listed / len(lines) >= 0.5


def _is_listing_line(line: str) -> bool:
    return bool(re.match(r"^((第[一二三四五六七八九十百]+章)|(\d+([.、]\d+)*[.、]?)|[-*•])\s*\S+", line))


def _has_body_punctuation(text: str) -> bool:
    return any(char in text for char in "。.!！？?；;，,")


def _has_body_sentence(text: str) -> bool:
    sentence_markers = sum(text.count(char) for char in "。.!！？?")
    return sentence_markers >= 2 or len(text) >= 80
