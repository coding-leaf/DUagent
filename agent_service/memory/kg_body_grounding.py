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
    query_expansion: bool = False,
    edges: Sequence[dict[str, Any]] | None = None,
) -> list[KgBodyGroundingResult]:
    """对 KG 节点做课程正文支撑度评分，输入课程 ID、节点和 embedding，输出每节点只读检索评分。"""
    store = vector_store or QdrantVectorStore()
    neighbor_names = _neighbor_names_by_node_id(nodes, edges or []) if query_expansion else {}
    results: list[KgBodyGroundingResult] = []

    for node in nodes:
        node_id = _node_id(node)
        node_name = _node_query_text(node)
        query_texts = _node_query_texts(node, node_name, neighbor_names.get(node_id, []), query_expansion)
        vectors = await embedding_provider.embed_texts(query_texts)
        body_candidate = await _best_body_candidate(store, course_id, vectors, limit)
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


async def _best_body_candidate(
    store: QdrantVectorStore,
    course_id: str,
    vectors: Sequence[Sequence[float]],
    limit: int,
) -> VectorSearchResult | None:
    best: VectorSearchResult | None = None
    for vector in vectors:
        candidates = await store.search_course_knowledge(course_id, vector, limit=limit)
        candidate = _first_body_candidate(candidates)
        if _candidate_score(candidate) > _candidate_score(best):
            best = candidate
    return best


def _candidate_score(candidate: VectorSearchResult | None) -> float:
    if candidate is None or candidate.score is None:
        return float("-inf")
    return candidate.score


def _node_id(node: dict[str, Any]) -> str:
    value = node.get("id") or node.get("node_id") or _node_query_text(node)
    return str(value).strip()


def _node_query_text(node: dict[str, Any]) -> str:
    for key in ("name", "title", "label", "id", "node_id"):
        value = node.get(key)
        if isinstance(value, str) and value.strip():
            return _normalize_space(value)
    return ""


def _node_query_texts(
    node: dict[str, Any],
    node_name: str,
    neighbor_names: Sequence[str],
    query_expansion: bool,
) -> list[str]:
    queries = [node_name]
    if query_expansion:
        queries.append(_expanded_query_text(node, node_name, neighbor_names))
    return _unique_texts(queries)


def _expanded_query_text(node: dict[str, Any], node_name: str, neighbor_names: Sequence[str]) -> str:
    parts: list[str] = []
    chapter = node.get("chapter")
    if isinstance(chapter, str) and chapter.strip():
        parts.append(_normalize_space(chapter))
    parts.append(node_name)
    parts.extend(neighbor_names)
    return _dedupe_query_parts(parts)


def _neighbor_names_by_node_id(
    nodes: Sequence[dict[str, Any]],
    edges: Sequence[dict[str, Any]],
) -> dict[str, list[str]]:
    names = {_node_id(node): _node_query_text(node) for node in nodes}
    neighbors: dict[str, list[str]] = {node_id: [] for node_id in names}

    for edge in edges:
        source = _edge_endpoint(edge, "from", "source", "source_id")
        target = _edge_endpoint(edge, "to", "target", "target_id")
        if source in names and target in names:
            neighbors[source].append(names[target])
            neighbors[target].append(names[source])

    return {node_id: _unique_texts(values) for node_id, values in neighbors.items()}


def _edge_endpoint(edge: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = edge.get(key)
        if value is not None:
            return str(value).strip()
    return ""


def _dedupe_query_parts(parts: Sequence[str]) -> str:
    return " ".join(_unique_texts(parts))


def _unique_texts(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = _normalize_space(value)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


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

    if _has_dotted_page_listing(text):
        return True

    if _looks_like_appendix_listing(text):
        return True

    if len(normalized) <= 40 and not _has_body_punctuation(normalized):
        return True

    return _looks_like_listing(text) and not _has_body_sentence(normalized)


def _has_dotted_page_listing(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return False

    dotted_page_lines = sum(1 for line in lines if _is_dotted_page_line(line))
    return dotted_page_lines >= 2 and dotted_page_lines / len(lines) >= 0.5


def _is_dotted_page_line(line: str) -> bool:
    return bool(re.search(r"\S\s*[.·•]{3,}\s*\d{1,4}\s*$", line))


def _looks_like_appendix_listing(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 3:
        return False

    appendix_markers = sum(1 for line in lines if re.match(r"^(附录|appendix\b|[A-Z]\.\d+)", line, re.IGNORECASE))
    return appendix_markers >= 2 and _looks_like_listing(text)


def _looks_like_listing(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) <= 1:
        lines = [part.strip() for part in re.split(r"\s{2,}|[;；]", text) if part.strip()]
    if len(lines) < 3:
        return False
    listed = sum(1 for line in lines if _is_listing_line(line))
    return listed >= 2 and listed / len(lines) >= 0.5


def _is_listing_line(line: str) -> bool:
    return bool(re.match(r"^((第[一二三四五六七八九十百]+章)|(附录[一二三四五六七八九十A-Z\d]*)|([A-Z]\.\d+)|(\d+([.、]\d+)*[.、]?)|[-*•])\s*\S+", line))


def _has_body_punctuation(text: str) -> bool:
    return any(char in text for char in "。.!！？?；;，,")


def _has_body_sentence(text: str) -> bool:
    sentence_markers = sum(text.count(char) for char in "。.!！？?")
    return sentence_markers >= 2 or len(text) >= 80
