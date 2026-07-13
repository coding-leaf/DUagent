from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.others import LearningActivity
from app.models.quiz import QuizAnswer, QuizQuestion, QuizSession
from app.services.course_knowledge_graphs import get_effective_knowledge_graph
from app.services.knowledge_progress import build_node_progress_rows
from app.services.learning_path_service import LearningPathService

MAX_RECENT_ANSWERS = 10
MAX_PROGRESS_NODES = 100


def _bounded_limit(value: int, *, default: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(parsed, maximum))


def normalize_question_options(options: object) -> list[dict[str, str]]:
    if not isinstance(options, list):
        return []

    normalized: list[dict[str, str]] = []
    for index, option in enumerate(options):
        fallback_key = chr(65 + index)
        if isinstance(option, dict):
            key = str(option.get("key") or fallback_key)
            text = str(option.get("text") or option.get("label") or option.get("key") or "")
            normalized.append({"key": key, "text": text})
        else:
            normalized.append({"key": fallback_key, "text": str(option or "")})
    return normalized


async def resolve_node_knowledge_point(
    db: AsyncSession,
    course_id: str,
    node_id: str,
) -> str | None:
    kg = await get_effective_knowledge_graph(db, course_id)
    nodes = kg.nodes if kg and isinstance(kg.nodes, list) else []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        current_id = str(node.get("id") or node.get("node_id") or "")
        if current_id == node_id:
            name = str(node.get("name") or "").strip()
            return name or None
    return None


def _progress_summary(nodes: list[dict[str, Any]]) -> dict[str, int]:
    completed = sum(1 for node in nodes if node.get("status") == "completed")
    in_progress = sum(1 for node in nodes if node.get("status") == "in_progress")
    weak = sum(
        1
        for node in nodes
        if node.get("assessment_state") == "weak" or node.get("status") == "recommended"
    )
    pending = sum(1 for node in nodes if node.get("status") == "pending")
    total = len(nodes)
    mastery_rate = int((completed / total) * 100) if total else 0
    return {
        "total_nodes": total,
        "completed_count": completed,
        "in_progress_count": in_progress,
        "weak_count": weak,
        "pending_count": pending,
        "mastery_rate": mastery_rate,
    }


def _progress_node_from_path_node(
    node: dict[str, Any],
    progress: dict[str, Any],
) -> dict[str, Any]:
    node_id = str(node.get("id") or node.get("node_id") or progress.get("node_id") or "")
    return {
        "node_id": node_id,
        "node_name": str(node.get("name") or progress.get("node_name") or ""),
        "status": node.get("status") or "pending",
        "assessment_state": progress.get("assessment_state") or "",
        "mastery_score": progress.get("mastery_score"),
        "mastery_label": progress.get("mastery_label") or "",
        "attempt_count": int(progress.get("attempt_count") or 0),
        "wrong_count": int(progress.get("wrong_count") or 0),
        "question_count": int(progress.get("question_count") or 0),
        "study_duration_seconds": progress.get("study_duration_seconds"),
        "resource_visit_count": progress.get("resource_visit_count"),
        "last_activity_at": progress.get("last_activity_at"),
    }


async def build_learning_progress_overview(
    db: AsyncSession,
    *,
    user_id: str,
    course_id: str,
    limit_nodes: int = 50,
) -> dict:
    limit = _bounded_limit(limit_nodes, default=50, maximum=MAX_PROGRESS_NODES)
    path = await LearningPathService(db).get_learning_path(user_id, course_id)
    progress_rows = await build_node_progress_rows(user_id, course_id, db)
    progress_by_id = {str(row.get("node_id") or ""): row for row in progress_rows}

    nodes: list[dict[str, Any]] = []
    path_nodes = path.get("nodes") or []
    source_nodes = path_nodes if path_nodes else progress_rows
    for node in source_nodes[:limit]:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id") or node.get("node_id") or "")
        progress = progress_by_id.get(node_id, node)
        nodes.append(_progress_node_from_path_node(node, progress))

    activity_result = await db.execute(
        select(LearningActivity)
        .where(
            LearningActivity.user_id == user_id,
            LearningActivity.course_id == course_id,
            LearningActivity.is_deleted.is_(False),
        )
        .order_by(LearningActivity.occurred_at.desc())
        .limit(10)
    )
    recent_activity = [
        {
            "activity_type": item.activity_type,
            "node_id": item.node_id,
            "node_name": item.node_name,
            "resource_id": item.resource_id,
            "duration_seconds": item.duration_seconds,
            "occurred_at": item.occurred_at.isoformat() if item.occurred_at else None,
        }
        for item in activity_result.scalars().all()
    ]

    return {
        "status": "available",
        "course_id": course_id,
        "current_position": path.get("current_position"),
        "summary": _progress_summary(nodes),
        "nodes": nodes,
        "recent_activity": recent_activity,
        "source": "backend.learning_progress",
    }


async def query_recent_answers(
    db: AsyncSession,
    *,
    user_id: str,
    course_id: str,
    scope: str = "course",
    node_id: str | None = None,
    knowledge_point: str | None = None,
    limit: int = 10,
    only_wrong: bool = True,
) -> dict:
    bounded_limit = _bounded_limit(limit, default=10, maximum=MAX_RECENT_ANSWERS)
    warnings: list[str] = []
    resolved_knowledge_point = str(knowledge_point or "").strip() or None
    result_scope = "course"

    if scope == "node" and node_id:
        node_knowledge_point = await resolve_node_knowledge_point(db, course_id, node_id)
        if node_knowledge_point is None:
            return {
                "status": "not_found",
                "scope": "node",
                "query": {
                    "node_id": node_id,
                    "resolved_knowledge_point": None,
                    "only_wrong": only_wrong,
                    "limit": bounded_limit,
                },
                "items": [],
                "summary": {"returned_count": 0, "has_more": False},
                "warnings": ["node_not_found"],
            }
        if resolved_knowledge_point and resolved_knowledge_point != node_knowledge_point:
            warnings.append("node_id resolved knowledge_point overrides provided knowledge_point")
        resolved_knowledge_point = node_knowledge_point
        result_scope = "node"
    elif scope == "knowledge_point" and resolved_knowledge_point:
        result_scope = "knowledge_point"

    stmt = (
        select(QuizAnswer, QuizSession, QuizQuestion)
        .join(QuizSession, QuizAnswer.quiz_id == QuizSession.id)
        .join(QuizQuestion, QuizAnswer.question_id == QuizQuestion.id)
        .where(
            QuizSession.user_id == user_id,
            QuizSession.course_id == course_id,
            QuizAnswer.is_deleted.is_(False),
            QuizSession.is_deleted.is_(False),
            QuizQuestion.is_deleted.is_(False),
        )
        .order_by(QuizAnswer.create_time.desc())
        .limit(bounded_limit + 1)
    )
    if resolved_knowledge_point:
        stmt = stmt.where(QuizQuestion.knowledge_point == resolved_knowledge_point)
    if only_wrong:
        stmt = stmt.where(QuizAnswer.is_correct.is_(False))

    rows = (await db.execute(stmt)).all()
    visible_rows = rows[:bounded_limit]
    items = [
        {
            "quiz_id": session.id,
            "question_id": question.id,
            "answered_at": answer.create_time.isoformat() if answer.create_time else None,
            "chapter": question.chapter,
            "knowledge_point": question.knowledge_point,
            "type": question.type,
            "difficulty": question.difficulty,
            "source": question.source,
            "personalized": bool(question.personalized),
            "content": question.content,
            "options": normalize_question_options(question.options),
            "user_answer": answer.user_answer,
            "correct_answer": answer.correct_answer,
            "is_correct": bool(answer.is_correct),
            "explanation": answer.explanation or "",
        }
        for answer, session, question in visible_rows
    ]

    return {
        "status": "available" if items else "empty",
        "scope": result_scope,
        "query": {
            "node_id": node_id,
            "resolved_knowledge_point": resolved_knowledge_point,
            "only_wrong": only_wrong,
            "limit": bounded_limit,
        },
        "items": items,
        "summary": {"returned_count": len(items), "has_more": len(rows) > bounded_limit},
        "warnings": warnings,
    }
