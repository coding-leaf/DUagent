from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

SUPPORT_BAND_ORDER = ("strong", "good", "weak_but_usable")
UNKNOWN_SUPPORT_BAND = "unknown"
DEFAULT_MAX_TARGETS = 10


def select_core_resource_targets(
    nodes: list[dict[str, Any]],
    max_targets: int = DEFAULT_MAX_TARGETS,
) -> dict[str, Any]:
    """Select deterministic KG nodes for resource generation."""
    limit = max(0, int(max_targets))
    if limit == 0:
        return {"targets": [], "selection_degraded": False, "degraded_reason": ""}

    normalized = _dedupe_nodes(nodes)
    has_support_metadata = any(
        item["support_band"] != UNKNOWN_SUPPORT_BAND for item in normalized
    )
    if has_support_metadata:
        targets = _select_with_support_bands(normalized, limit)
        degraded = False
        reason = ""
    else:
        targets = _round_robin_by_chapter(normalized, limit)
        degraded = bool(normalized)
        reason = "node_support_metadata_missing" if normalized else ""

    return {
        "targets": targets,
        "selection_degraded": degraded,
        "degraded_reason": reason,
    }


def _dedupe_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for index, node in enumerate(nodes):
        node_id = str(node.get("id") or node.get("node_id") or "").strip()
        node_name = str(node.get("name") or node.get("node_name") or "").strip()
        chapter = str(node.get("chapter") or "").strip()
        if not node_id or not node_name or not chapter:
            continue

        support_band = _support_band(node)
        if support_band == "unsupported":
            continue

        candidate = {
            "node_id": node_id,
            "node_name": node_name,
            "chapter": chapter,
            "support_band": support_band,
            "body_top1_score": _score(node),
            "_order": index,
        }
        key = (chapter, node_name)
        existing = best_by_key.get(key)
        if existing is None or _sort_key(candidate) < _sort_key(existing):
            best_by_key[key] = candidate

    return [
        _public(item)
        for item in sorted(best_by_key.values(), key=lambda item: item["_order"])
    ]


def _support_band(node: dict[str, Any]) -> str:
    raw = node.get("support_band") or node.get("body_support_band")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()

    score = _score(node)
    if score is None:
        return UNKNOWN_SUPPORT_BAND
    if score >= 0.70:
        return "strong"
    if score >= 0.65:
        return "good"
    if score >= 0.60:
        return "weak_but_usable"
    return "unsupported"


def _score(node: dict[str, Any]) -> float | None:
    raw = node.get("body_top1_score")
    if raw is None:
        raw = node.get("support_score")
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _select_with_support_bands(
    nodes: list[dict[str, Any]], limit: int
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for band in SUPPORT_BAND_ORDER:
        band_nodes = [item for item in nodes if item["support_band"] == band]
        selected.extend(_round_robin_by_chapter(band_nodes, limit - len(selected)))
        if len(selected) >= limit:
            break
    return selected[:limit]


def _round_robin_by_chapter(
    nodes: list[dict[str, Any]], limit: int
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in sorted(nodes, key=_sort_key):
        grouped[item["chapter"]].append(item)

    queues = deque((chapter, deque(items)) for chapter, items in grouped.items())
    selected: list[dict[str, Any]] = []
    while queues and len(selected) < limit:
        chapter, items = queues.popleft()
        selected.append(_public(items.popleft()))
        if items:
            queues.append((chapter, items))
    return selected


def _sort_key(item: dict[str, Any]) -> tuple[int, float, int]:
    band_rank = {
        "strong": 0,
        "good": 1,
        "weak_but_usable": 2,
        UNKNOWN_SUPPORT_BAND: 3,
    }.get(item["support_band"], 4)
    score = item["body_top1_score"]
    score_rank = -score if score is not None else 0.0
    return (band_rank, score_rank, int(item.get("_order", 0)))


def _public(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "node_id": item["node_id"],
        "node_name": item["node_name"],
        "chapter": item["chapter"],
        "support_band": item["support_band"],
        "body_top1_score": item["body_top1_score"],
    }
