from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Tuple
from sqlalchemy import func, select, case
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.others import LearningActivity, Resource
from app.models.user import User

def compute_modal_preference(activities: List[Tuple[str, int]]) -> Dict[str, int]:
    modal_durations = {
        "video_animation": 0, 
        "chart_logic": 0, 
        "text_analysis": 0, 
        "code_practice": 0, 
        "formula_derivation": 0
    }
    total_effective_duration = 0
    
    for res_type, duration in activities:
        duration = int(duration or 0)
        total_effective_duration += duration
        if res_type == "video":
            modal_durations["video_animation"] += duration
        elif res_type in ["mindmap", "diagram"]:
            modal_durations["chart_logic"] += duration
        elif res_type in ["document", "reading"]:
            modal_durations["text_analysis"] += duration
        elif res_type == "code":
            modal_durations["code_practice"] += duration
            
    modal_preference = {}
    if total_effective_duration > 0:
        max_duration = max(modal_durations.values()) if any(modal_durations.values()) else 1
        if max_duration == 0: 
            max_duration = 1
        for k, v in modal_durations.items():
            modal_preference[k] = int((v / max_duration) * 100)
    else:
        modal_preference = {k: 0 for k in modal_durations.keys()}
        
    return modal_preference

def compute_knowledge_progress(node_progress_rows: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    knowledge_coordinates = []
    weak_nodes = []
    
    total_nodes = len(node_progress_rows)
    mastered_nodes = 0
    learning_nodes = 0
    weak_count = 0
    pending_nodes = 0

    for row in node_progress_rows:
        status = row["assessment_state"]
        score = row["mastery_score"]
        evidence = "quiz" if row.get("attempt_count", 0) > 0 else ("activity" if row.get("study_duration_seconds", 0) else "none")
        
        knowledge_coordinates.append({
            "node_id": row["node_id"],
            "name": row["node_name"],
            "status": status,
            "mastery_score": score,
            "evidence": evidence
        })
        
        if status == "mastered":
            mastered_nodes += 1
        elif status == "weak":
            weak_count += 1
            severity = "high" if (score is not None and score < 50) else "medium"
            weak_nodes.append({
                "name": row["node_name"],
                "severity": severity,
                "error_count": 0, # Could be enriched later
                "source": "quiz"
            })
        elif status == "learning":
            learning_nodes += 1
        elif status == "pending_practice":
            pending_nodes += 1

    mastery_rate = int((mastered_nodes / total_nodes * 100)) if total_nodes > 0 else 0
    
    knowledge_progress_summary = {
        "total_nodes": total_nodes,
        "mastered_nodes": mastered_nodes,
        "learning_nodes": learning_nodes,
        "weak_nodes": weak_count,
        "pending_nodes": pending_nodes,
        "mastery_rate": mastery_rate
    }
    
    return knowledge_coordinates, weak_nodes, knowledge_progress_summary

def compute_learning_habits(
    last_activity_at: datetime | None,
    study_duration_7d: int,
    study_duration_30d: int,
    active_days_7d: int,
    streak_days: int,
    practice_count_7d: int,
    total_events: int,
    total_nodes: int,
    now: datetime
) -> Tuple[Dict[str, Any], float]:
    streak_score = min(streak_days / 7.0, 1.0) * 100
    active_7d_score = (active_days_7d / 7.0) * 100
    continuity_score = (streak_score + active_7d_score) / 2.0
    
    study_duration_7d_score = min(study_duration_7d / 7200.0, 1.0) * 100
    study_duration_30d_score = min(study_duration_30d / 28800.0, 1.0) * 100
    effort_score = (study_duration_7d_score + study_duration_30d_score) / 2.0
    
    practice_score = min(practice_count_7d / 5.0, 1.0) * 100
    
    recency_score = 0
    if last_activity_at:
        hours_since = (now - last_activity_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600
        if hours_since <= 24: 
            recency_score = 100
        elif hours_since <= 72: 
            recency_score = 70
        elif hours_since <= 168: 
            recency_score = 40

    learning_habit_score = (continuity_score * 0.35) + (effort_score * 0.35) + (practice_score * 0.20) + (recency_score * 0.10)
    
    if total_events < 2 and total_nodes == 0:
        habit_label = "new"
    elif not last_activity_at or (now - last_activity_at.replace(tzinfo=timezone.utc)).total_seconds() > 7 * 86400 or learning_habit_score < 20:
        habit_label = "inactive"
    elif effort_score >= 70 and continuity_score < 40:
        habit_label = "sprint"
    elif learning_habit_score >= 60 and last_activity_at and (now - last_activity_at.replace(tzinfo=timezone.utc)).total_seconds() <= 7 * 86400:
        habit_label = "stable"
    elif total_events > 0:
        habit_label = "casual"
    else:
        habit_label = "new"

    learning_habits = {
        "label": habit_label,
        "score": int(learning_habit_score),
        "streak_days": streak_days,
        "active_days_7d": active_days_7d,
        "study_duration_7d": study_duration_7d,
        "last_activity_at": last_activity_at.isoformat() if last_activity_at else None
    }
    
    return learning_habits, learning_habit_score

def compute_discipline_badge(
    course_id: str,
    weak_count: int,
    total_nodes: int,
    learning_habit_score: float,
    mastery_rate: int,
    streak_days: int
) -> Dict[str, Any]:
    weak_penalty_score = min(weak_count / max(total_nodes, 1), 1.0) * 100
    badge_score = (learning_habit_score * 0.40) + (mastery_rate * 0.50) - (weak_penalty_score * 0.10)
    badge_score = max(0, min(100, badge_score))
    
    if badge_score < 40 or total_nodes == 0: 
        badge_level = "starter"
    elif badge_score < 70: 
        badge_level = "steady"
    elif badge_score < 85: 
        badge_level = "advanced"
    else: 
        badge_level = "excellent"

    discipline_badge = {
        "subject": course_id,
        "level": badge_level,
        "score": int(badge_score),
        "streak_days": streak_days,
        "reasons": []
    }
    
    return discipline_badge


async def compute_profile_fields(
    user_id: str,
    course_id: str,
    user: User,
    node_progress_rows: list[dict],
    db: AsyncSession
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)

    # 1. Resource/Modal Preference
    activities_result = await db.execute(
        select(Resource.type, func.sum(LearningActivity.duration_seconds))
        .select_from(LearningActivity)
        .join(Resource, LearningActivity.resource_id == Resource.id, isouter=True)
        .where(
            LearningActivity.user_id == user_id,
            LearningActivity.course_id == course_id,
            LearningActivity.activity_type.in_(["resource_study", "node_practice_submit"]),
            LearningActivity.is_deleted == False
        )
        .group_by(Resource.type)
    )
    activities = list(activities_result.all())
    modal_preference = compute_modal_preference(activities)

    # 2. Knowledge Coordinates and Cognitive Blindspots
    knowledge_coordinates, weak_nodes, knowledge_progress_summary = compute_knowledge_progress(node_progress_rows)

    # 3. Learning Habits
    habit_metrics_result = await db.execute(
        select(
            func.max(LearningActivity.occurred_at),
            func.sum(case((LearningActivity.occurred_at >= seven_days_ago, LearningActivity.duration_seconds), else_=0)),
            func.sum(LearningActivity.duration_seconds),
        ).where(
            LearningActivity.user_id == user_id,
            LearningActivity.course_id == course_id,
            LearningActivity.is_deleted == False
        )
    )
    last_activity_at, study_duration_7d, study_duration_30d = habit_metrics_result.first()
    study_duration_7d = int(study_duration_7d or 0)
    study_duration_30d = int(study_duration_30d or 0)
    
    active_dates_result = await db.execute(
        select(func.date(LearningActivity.occurred_at)).where(
            LearningActivity.user_id == user_id,
            LearningActivity.course_id == course_id,
            LearningActivity.occurred_at >= seven_days_ago,
            LearningActivity.is_deleted == False
        ).group_by(func.date(LearningActivity.occurred_at))
    )
    active_days_7d = len(active_dates_result.all())
    
    total_events_result = await db.execute(
        select(func.count(LearningActivity.id)).where(
            LearningActivity.user_id == user_id, 
            LearningActivity.course_id == course_id,
            LearningActivity.is_deleted == False
        )
    )
    total_events = total_events_result.scalar() or 0
    
    streak_days = 0 
    practice_count_7d = 0
    
    learning_habits, learning_habit_score = compute_learning_habits(
        last_activity_at=last_activity_at,
        study_duration_7d=study_duration_7d,
        study_duration_30d=study_duration_30d,
        active_days_7d=active_days_7d,
        streak_days=streak_days,
        practice_count_7d=practice_count_7d,
        total_events=total_events,
        total_nodes=knowledge_progress_summary["total_nodes"],
        now=now
    )

    # 4. Discipline Badge
    discipline_badge = compute_discipline_badge(
        course_id=course_id,
        weak_count=knowledge_progress_summary["weak_nodes"],
        total_nodes=knowledge_progress_summary["total_nodes"],
        learning_habit_score=learning_habit_score,
        mastery_rate=knowledge_progress_summary["mastery_rate"],
        streak_days=streak_days
    )

    return {
        "modal_preference": modal_preference,
        "knowledge_coordinates": knowledge_coordinates,
        "cognitive_blindspots": weak_nodes,
        "learning_habits": learning_habits,
        "discipline_badge": discipline_badge,
        "knowledge_progress_summary": knowledge_progress_summary
    }
