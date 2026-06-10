from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class GroundingMatch:
    node_id: str
    score: float
    chunk_id: str
    content_preview: str


_TOC_MARKERS = ("目录", "table of contents", "contents")
_TOC_LINE_PATTERNS = (
    re.compile(r"^\s*(第\s*[一二三四五六七八九十百千万\d]+\s*[章节篇部])\b"),
    re.compile(r"^\s*(chapter|section)\s+\d+", re.IGNORECASE),
    re.compile(r".*(?:\.{2,}|…{2,})\s*\d+\s*$"),
    re.compile(r"^\s*\d+(?:\.\d+)+\s+\S.{0,80}\s+\d+\s*$"),
)


def is_toc_like_chunk(content: str) -> bool:
    stripped = content.strip()
    if not stripped:
        return True

    non_empty_lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    first_lines = non_empty_lines[:3]
    if any(_is_toc_heading(line) for line in first_lines):
        return True

    if len(non_empty_lines) < 3:
        return False

    toc_like_count = sum(
        1
        for line in non_empty_lines
        if any(pattern.match(line) for pattern in _TOC_LINE_PATTERNS)
    )
    return toc_like_count / len(non_empty_lines) >= 0.6


def _is_toc_heading(line: str) -> bool:
    normalized = re.sub(r"[\s:：\-—_]+", " ", line.strip().lower()).strip()
    if len(normalized) > 32:
        return False
    return normalized in _TOC_MARKERS


def filter_supported_knowledge_graph(
    nodes: Iterable[dict[str, Any]],
    edges: Iterable[dict[str, Any]],
    matches: Iterable[GroundingMatch],
    threshold: float = 0.70,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    node_list = list(nodes)
    edge_list = list(edges)
    match_by_node_id: dict[str, GroundingMatch] = {}
    for match in matches:
        current_match = match_by_node_id.get(match.node_id)
        if current_match is None or match.score > current_match.score:
            match_by_node_id[match.node_id] = match

    kept_nodes: list[dict[str, Any]] = []
    pruned_nodes: list[dict[str, Any]] = []

    for node in node_list:
        node_id = str(node.get("id", ""))
        match = match_by_node_id.get(node_id)
        if match is not None and match.score >= threshold:
            kept_nodes.append(dict(node))
            continue

        pruned_nodes.append(
            {
                "node_id": node_id,
                "node_name": node.get("name", ""),
                "chapter": node.get("chapter", ""),
                "body_top1_score": match.score if match is not None else None,
                "chunk_id": match.chunk_id if match is not None else None,
                "content_preview": match.content_preview if match is not None else "",
            }
        )

    kept_node_ids = {str(node.get("id", "")) for node in kept_nodes}
    kept_edges = [
        dict(edge)
        for edge in edge_list
        if str(edge.get("from", "")) in kept_node_ids
        and str(edge.get("to", "")) in kept_node_ids
    ]

    candidate_node_count = len(node_list)
    kept_node_count = len(kept_nodes)
    pass_ratio = (
        kept_node_count / candidate_node_count if candidate_node_count > 0 else 0.0
    )
    metrics = {
        "body_top1_threshold": threshold,
        "candidate_node_count": candidate_node_count,
        "kept_node_count": kept_node_count,
        "pruned_node_count": len(pruned_nodes),
        "body_support_pass_ratio": pass_ratio,
        "pruned_nodes": pruned_nodes,
    }

    return kept_nodes, kept_edges, metrics
