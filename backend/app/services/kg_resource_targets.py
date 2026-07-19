from __future__ import annotations

from typing import Any

SUPPORT_BAND_ORDER = ("strong", "good", "weak_but_usable")
UNKNOWN_SUPPORT_BAND = "unknown"


def select_valid_resource_targets(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    """Return every unique KG node that has enough course support."""
    targets_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    skipped: list[dict[str, str]] = []
    has_support_metadata = False

    for index, node in enumerate(nodes):
        node_id = str(node.get("id") or node.get("node_id") or "").strip()
        node_name = str(node.get("name") or node.get("node_name") or "").strip()
        chapter = str(node.get("chapter") or "").strip()
        if not node_id or not node_name or not chapter:
            skipped.append({"node_id": node_id, "reason": "missing_required_fields"})
            continue

        support_band = _support_band(node)
        has_support_metadata = has_support_metadata or support_band != UNKNOWN_SUPPORT_BAND
        if support_band == "unsupported":
            skipped.append({"node_id": node_id, "reason": "unsupported"})
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
        existing = targets_by_key.get(key)
        if existing is not None:
            skipped.append({"node_id": node_id, "reason": "duplicate_chapter_name"})
            if _sort_key(candidate) < _sort_key(existing):
                targets_by_key[key] = candidate
            continue
        targets_by_key[key] = candidate

    targets = [
        _public(item)
        for item in sorted(targets_by_key.values(), key=lambda item: item["_order"])
    ]
    return {
        "targets": targets,
        "skipped": skipped,
        "selection_degraded": bool(targets) and not has_support_metadata,
        "degraded_reason": (
            "node_support_metadata_missing"
            if targets and not has_support_metadata
            else ""
        ),
    }


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
