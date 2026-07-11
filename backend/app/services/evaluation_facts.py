from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from math import ceil
from typing import Any, Iterable


def aggregate_quiz_results(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        knowledge_point = str(row.get("knowledge_point") or "未分类")
        stats = grouped.setdefault(
            knowledge_point,
            {
                "chapter": str(row.get("chapter") or ""),
                "answers": [],
                "personalized_count": 0,
            },
        )
        stats["answers"].append(
            (
                _timestamp(row.get("create_time")),
                bool(row.get("is_correct")),
            )
        )
        stats["personalized_count"] += int(bool(row.get("personalized")))

    results: list[dict[str, Any]] = []
    for knowledge_point in sorted(grouped):
        stats = grouped[knowledge_point]
        answers = stats["answers"]
        correct = sum(int(is_correct) for _created_at, is_correct in answers)
        recent = sorted(answers, key=lambda item: item[0], reverse=True)[:10]
        recent_correct = sum(int(is_correct) for _created_at, is_correct in recent)
        results.append(
            {
                "knowledge_point": knowledge_point,
                "chapter": stats["chapter"],
                "score": round(correct / len(answers) * 100, 1),
                "total_answers": len(answers),
                "personalized_count": stats["personalized_count"],
                "recent_trend": round(recent_correct / len(recent) * 100, 1),
            }
        )
    return results


def aggregate_resource_usage(resource_types: Iterable[str | None]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for resource_type in resource_types:
        normalized = str(resource_type or "").strip()
        if normalized:
            counts[normalized] += 1
    return dict(sorted(counts.items()))


def aggregate_chapter_progress(node_rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    chapters: dict[str, dict[str, int]] = {}
    for row in node_rows:
        chapter = str(row.get("chapter") or "").strip()
        if not chapter:
            continue
        stats = chapters.setdefault(
            chapter,
            {"node_count": 0, "mastered_count": 0, "duration_seconds": 0},
        )
        stats["node_count"] += 1
        stats["mastered_count"] += int(row.get("assessment_state") == "mastered")
        stats["duration_seconds"] += int(row.get("study_duration_seconds") or 0)

    return [
        {
            "chapter": chapter,
            "completion_rate": round(
                stats["mastered_count"] / stats["node_count"] * 100,
                1,
            ),
            "time_spent": ceil(stats["duration_seconds"] / 60),
        }
        for chapter, stats in chapters.items()
    ]


def _timestamp(value: Any) -> float:
    if isinstance(value, datetime):
        return value.timestamp()
    return float("-inf")
