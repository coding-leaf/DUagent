import logging
from collections import defaultdict
from datetime import datetime
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.catalog import CourseCatalog, CourseOffering
from app.models.others import CourseKnowledgeGraph, LearningActivity
from app.models.quiz import QuizAnswer, QuizQuestion, QuizSession
from app.services.course_knowledge_graphs import get_active_knowledge_graph
from app.services.resource_scope import resolve_course_resource_scope

logger = logging.getLogger(__name__)

def _mastery_label(score: float | None) -> str:
    if score is None:
        return ""
    if score >= 90:
        return "A"
    if score >= 75:
        return "B"
    if score >= 60:
        return "C"
    return "需复习"

async def _resolve_evaluation_kg(db: AsyncSession, course_id: str) -> CourseKnowledgeGraph | None:
    kg = await get_active_knowledge_graph(db, course_id)
    if kg is not None:
        return kg

    offering_result = await db.execute(
        select(CourseOffering).where(
            CourseOffering.id == course_id,
            CourseOffering.is_deleted == False,
        )
    )
    offering = offering_result.scalar_one_or_none()
    if offering is None:
        return None

    catalog_result = await db.execute(
        select(CourseCatalog).where(
            CourseCatalog.id == offering.catalog_id,
            CourseCatalog.is_deleted == False,
        )
    )
    catalog = catalog_result.scalar_one_or_none()
    if catalog is None or not catalog.kg_host_course_id:
        return None
    return await get_active_knowledge_graph(db, catalog.kg_host_course_id)

def evaluate_mastery_state(
    score: float | None, 
    question_count: int, 
    attempt_count: int, 
    latest_score: float | None, 
    has_activity: bool
) -> tuple[str, str, str]:
    """Evaluate mastery state based on score and activity."""
    if score is not None:
        min_evidence = min(3, question_count)
        has_minimum_evidence = attempt_count >= min_evidence
        
        if score >= 80 and has_minimum_evidence:
            return "mastered", "已掌握", _mastery_label(score)
        elif score < 70 or (latest_score is not None and latest_score < 60):
            return "weak", "薄弱", _mastery_label(score)
        else:
            return "learning", "学习中", _mastery_label(score)
    elif question_count > 0:
        return "pending_practice", "待练习", "待练习"
    else:
        if has_activity:
            return "learning", "学习中", "无测评"
        else:
            return "unstarted", "未开始", "无测评"


def summarize_attempt_answers(rows: list[tuple[str, bool, str, int, datetime | None]]) -> dict[str, dict]:
    attempts: dict[str, dict] = defaultdict(
        lambda: {
            "correct": 0,
            "total": 0,
            "duration": 0,
            "sessions": set(),
            "latest_score": None,
            "_latest_time": None,
        }
    )
    session_kp_stats: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"correct": 0, "total": 0, "duration": 0, "created_at": None}
    )

    for knowledge_point, is_correct, session_id, time_spent, created_at in rows:
        if not knowledge_point or not session_id:
            continue
        stats = attempts[knowledge_point]
        stats["total"] += 1
        stats["correct"] += 1 if is_correct else 0
        if session_id not in stats["sessions"]:
            stats["sessions"].add(session_id)
            stats["duration"] += int(time_spent or 0)

        session_stats = session_kp_stats[(knowledge_point, session_id)]
        session_stats["total"] += 1
        session_stats["correct"] += 1 if is_correct else 0
        session_stats["duration"] = int(time_spent or 0)
        session_stats["created_at"] = created_at

    for (knowledge_point, _session_id), session_stats in session_kp_stats.items():
        total = session_stats["total"]
        if not total:
            continue
        latest_time = session_stats["created_at"]
        stats = attempts[knowledge_point]
        previous_time = stats.get("_latest_time")
        if previous_time is None or (latest_time is not None and latest_time >= previous_time):
            stats["_latest_time"] = latest_time
            stats["latest_score"] = round((session_stats["correct"] / total) * 100, 1)

    for stats in attempts.values():
        stats.pop("_latest_time", None)

    return attempts


async def build_node_progress_rows(user_id: str, course_id: str, db: AsyncSession) -> list[dict]:
    kg = await _resolve_evaluation_kg(db, course_id)
    nodes = kg.nodes if kg and isinstance(kg.nodes, list) else []
    if not nodes:
        return []

    node_names = [
        str(node.get("name") or node.get("id") or "").strip()
        for node in nodes
        if isinstance(node, dict)
    ]
    node_names = [name for name in node_names if name]
    if not node_names:
        return []

    resource_scope = await resolve_course_resource_scope(db, course_id)
    location_conditions = [and_(QuizQuestion.catalog_id.is_(None), QuizQuestion.course_id == course_id)]
    if resource_scope.catalog_id:
        location_conditions.append(QuizQuestion.catalog_id == resource_scope.catalog_id)

    questions_result = await db.execute(
        select(QuizQuestion).where(
            or_(*location_conditions),
            QuizQuestion.knowledge_point.in_(node_names),
            or_(
                QuizQuestion.source.in_(["common", "baseline"]),
                and_(
                    QuizQuestion.source == "personalized",
                    QuizQuestion.owner_user_id == user_id,
                ),
            ),
            QuizQuestion.is_deleted == False,
        )
    )
    questions = questions_result.scalars().all()
    question_counts: dict[str, int] = defaultdict(int)
    question_to_kp: dict[str, str] = {}
    for question in questions:
        knowledge_point = question.knowledge_point or ""
        question_counts[knowledge_point] += 1
        question_to_kp[question.id] = knowledge_point

    session_result = await db.execute(
        select(QuizSession).where(
            QuizSession.user_id == user_id,
            QuizSession.course_id == course_id,
            QuizSession.is_deleted == False,
        )
    )
    sessions = session_result.scalars().all()
    session_by_id = {session.id: session for session in sessions}

    attempts: dict[str, dict] = {}
    if session_by_id and question_to_kp:
        answer_result = await db.execute(
            select(QuizAnswer).where(
                QuizAnswer.quiz_id.in_(list(session_by_id.keys())),
                QuizAnswer.question_id.in_(list(question_to_kp.keys())),
                QuizAnswer.is_deleted == False,
            )
        )
        attempt_rows = []
        for answer in answer_result.scalars().all():
            knowledge_point = question_to_kp.get(answer.question_id)
            session = session_by_id.get(answer.quiz_id)
            if not knowledge_point or session is None:
                continue
            attempt_rows.append(
                (
                    knowledge_point,
                    bool(answer.is_correct),
                    session.id,
                    int(session.time_spent or 0),
                    session.create_time,
                )
            )
        attempts = summarize_attempt_answers(attempt_rows)

    node_ids = [
        str(node.get("id") or node.get("node_id") or f"node_{index}")
        for index, node in enumerate(nodes)
        if isinstance(node, dict)
    ]
    activity_by_node: dict[str, dict] = {}
    if node_ids:
        activity_result = await db.execute(
            select(
                LearningActivity.node_id,
                func.coalesce(func.sum(LearningActivity.duration_seconds), 0),
                func.count(LearningActivity.id),
                func.max(LearningActivity.occurred_at),
            ).where(
                LearningActivity.user_id == user_id,
                LearningActivity.course_id == course_id,
                LearningActivity.node_id.in_(node_ids),
                LearningActivity.is_deleted == False,
            ).group_by(LearningActivity.node_id)
        )
        for node_id, duration, activity_count, last_activity_at in activity_result.all():
            if node_id:
                activity_by_node[str(node_id)] = {
                    "duration": int(duration or 0),
                    "activity_count": int(activity_count or 0),
                    "last_activity_at": last_activity_at,
                }

        resource_visit_result = await db.execute(
            select(
                LearningActivity.node_id,
                func.count(LearningActivity.id),
            ).where(
                LearningActivity.user_id == user_id,
                LearningActivity.course_id == course_id,
                LearningActivity.node_id.in_(node_ids),
                LearningActivity.activity_type == "resource_view",
                LearningActivity.is_deleted == False,
            ).group_by(LearningActivity.node_id)
        )
        for node_id, visit_count in resource_visit_result.all():
            if node_id:
                activity_by_node.setdefault(str(node_id), {})["resource_visit_count"] = int(visit_count or 0)

    rows: list[dict] = []
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id") or node.get("node_id") or f"node_{index}")
        node_name = str(node.get("name") or node_id)
        question_count = question_counts.get(node_name, 0)
        attempt_stats = attempts.get(node_name)
        attempt_count = int(attempt_stats["total"]) if attempt_stats else 0
        score = (
            round((attempt_stats["correct"] / attempt_stats["total"]) * 100, 1)
            if attempt_stats and attempt_stats["total"]
            else None
        )

        activity_stats = activity_by_node.get(node_id, {})
        has_activity = bool(activity_stats.get("duration") or activity_stats.get("activity_count"))
        latest_score = attempt_stats.get("latest_score", 100) if attempt_stats else None
        
        assessment_state, status_text, mastery_label = evaluate_mastery_state(
            score=score,
            question_count=question_count,
            attempt_count=attempt_count,
            latest_score=latest_score,
            has_activity=has_activity
        )

        activity_stats = activity_by_node.get(node_id, {})
        activity_duration = int(activity_stats.get("duration") or 0)
        quiz_duration = int(attempt_stats["duration"]) if attempt_stats and attempt_stats["duration"] else 0
        duration = activity_duration or quiz_duration or None
        last_activity_at = activity_stats.get("last_activity_at")
        correct_count = int(attempt_stats["correct"]) if attempt_stats else 0
        wrong_count = attempt_count - correct_count
        rows.append(
            {
                "node_id": node_id,
                "node_name": node_name,
                "chapter": str(node.get("chapter") or ""),
                "status": status_text,
                "study_duration_seconds": duration,
                "mastery_score": score,
                "mastery_label": mastery_label,
                "assessment_state": assessment_state,
                "question_count": question_count,
                "attempt_count": attempt_count,
                "wrong_count": wrong_count,
                "resource_visit_count": activity_stats.get("resource_visit_count"),
                "last_activity_at": last_activity_at.isoformat() if last_activity_at else None,
            }
        )
    return rows
