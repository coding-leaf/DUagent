from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Tuple
from sqlalchemy import func, select, case
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.conversation import Conversation, Message
from app.models.others import LearningActivity, Resource
from app.models.user import User

def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)

def compute_modal_preference(
    activities: List[Tuple],
    ai_interaction_count: int = 0,
) -> Dict[str, int]:
    modal_counts = {
        # 兼容历史存储 key；产品含义已调整为 AI 交互。
        "video_animation": max(0, int(ai_interaction_count or 0)),
        "chart_logic": 0, 
        "text_analysis": 0, 
        "code_practice": 0, 
        "formula_derivation": 0
    }
    
    for item in activities:
        if len(item) == 3:
            res_type, act_type, count = item
        else:
            res_type, count = item
            act_type = None
            
        count = max(0, int(count or 0))
        
        # 1. 优先判定活动类型
        if act_type == "node_practice_submit":
            modal_counts["code_practice"] += count
        # 2. 根据资源类型归类
        elif res_type:
            if res_type in ["mindmap", "diagram"]:
                modal_counts["chart_logic"] += count
            elif res_type in ["lesson", "document", "reading", "personal_lesson"]:
                modal_counts["text_analysis"] += count
            elif res_type in ["example", "code"]:
                modal_counts["code_practice"] += count
            elif res_type == "practice":
                modal_counts["formula_derivation"] += count
            
    max_count = max(modal_counts.values())
    if max_count == 0:
        return {key: 0 for key in modal_counts}
    return {
        key: int((count / max_count) * 100)
        for key, count in modal_counts.items()
    }

def compute_knowledge_progress(node_progress_rows: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    knowledge_coordinates = []
    weak_nodes = []
    
    total_nodes = len(node_progress_rows)
    mastered_nodes = 0
    learning_nodes = 0
    weak_count = 0
    pending_nodes = 0
    unstarted_nodes = 0
    practiced_nodes = 0

    for row in node_progress_rows:
        status = row["assessment_state"]
        score = row["mastery_score"]
        attempt_count = int(row.get("attempt_count") or 0)
        evidence = "quiz" if row.get("attempt_count", 0) > 0 else ("activity" if row.get("study_duration_seconds", 0) else "none")
        
        knowledge_coordinates.append({
            "node_id": row["node_id"],
            "name": row["node_name"],
            "status": status,
            "mastery_score": score,
            "evidence": evidence
        })

        if attempt_count > 0 or status in {"mastered", "weak", "learning"}:
            practiced_nodes += 1
        
        if status == "mastered":
            mastered_nodes += 1
        elif status == "weak":
            weak_count += 1
            severity = "high" if (score is not None and score < 50) else "medium"
            weak_nodes.append({
                "name": row["node_name"],
                "severity": severity,
                "error_count": row.get("wrong_count", 0),
                "source": "quiz"
            })
        elif status == "learning":
            learning_nodes += 1
        elif status == "pending_practice":
            pending_nodes += 1
        elif status == "unstarted":
            unstarted_nodes += 1

    mastery_rate = int((mastered_nodes / total_nodes * 100)) if total_nodes > 0 else 0
    
    knowledge_progress_summary = {
        "total_nodes": total_nodes,
        "mastered_nodes": mastered_nodes,
        "learning_nodes": learning_nodes,
        "weak_nodes": weak_count,
        "pending_nodes": pending_nodes,
        "unstarted_nodes": unstarted_nodes,
        "practiced_nodes": practiced_nodes,
        "mastery_rate": mastery_rate
    }
    
    return knowledge_coordinates, weak_nodes, knowledge_progress_summary

def compute_streak_days(activity_datetimes: List[datetime], now: datetime) -> int:
    if not activity_datetimes:
        return 0

    active_dates = {_as_utc(value).date() for value in activity_datetimes if value}
    current_date = _as_utc(now).date()
    streak = 0

    if current_date in active_dates:
        cursor = current_date
    elif current_date - timedelta(days=1) in active_dates:
        cursor = current_date - timedelta(days=1)
    else:
        return 0

    while cursor in active_dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak

def count_recent_practice_events(
    activity_rows: List[Tuple[str, datetime]],
    now: datetime,
    days: int = 7,
) -> int:
    start = _as_utc(now) - timedelta(days=days)
    return sum(
        1
        for activity_type, occurred_at in activity_rows
        if activity_type == "node_practice_submit"
        and occurred_at
        and _as_utc(occurred_at) >= start
        and _as_utc(occurred_at) <= _as_utc(now)
    )

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
        select(Resource.type, LearningActivity.activity_type, func.count(LearningActivity.id))
        .select_from(LearningActivity)
        .join(Resource, LearningActivity.resource_id == Resource.id, isouter=True)
        .where(
            LearningActivity.user_id == user_id,
            LearningActivity.course_id == course_id,
            LearningActivity.activity_type.in_(["resource_study", "node_practice_submit"]),
            LearningActivity.is_deleted == False
        )
        .group_by(Resource.type, LearningActivity.activity_type)
    )
    activities = list(activities_result.all())
    ai_interactions_result = await db.execute(
        select(func.count(Message.id))
        .select_from(Message)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            Conversation.user_id == user_id,
            Conversation.course_id == course_id,
            Conversation.is_deleted == False,
            Message.role == "user",
            Message.is_deleted == False,
        )
    )
    ai_interaction_count = int(ai_interactions_result.scalar() or 0)
    modal_preference = compute_modal_preference(activities, ai_interaction_count)

    # 2. Knowledge Coordinates and Cognitive Blindspots
    knowledge_coordinates, weak_nodes, knowledge_progress_summary = compute_knowledge_progress(node_progress_rows)

    # 3. Learning Habits
    habit_metrics_result = await db.execute(
        select(
            func.max(LearningActivity.occurred_at),
            func.sum(case((LearningActivity.occurred_at >= seven_days_ago, LearningActivity.duration_seconds), else_=0)),
            func.sum(case((LearningActivity.occurred_at >= thirty_days_ago, LearningActivity.duration_seconds), else_=0)),
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

    activity_events_result = await db.execute(
        select(LearningActivity.activity_type, LearningActivity.occurred_at).where(
            LearningActivity.user_id == user_id,
            LearningActivity.course_id == course_id,
            LearningActivity.occurred_at >= thirty_days_ago,
            LearningActivity.is_deleted == False
        )
    )
    activity_events = list(activity_events_result.all())
    activity_datetimes = [occurred_at for _activity_type, occurred_at in activity_events]
    streak_days = compute_streak_days(activity_datetimes, now)
    practice_count_7d = count_recent_practice_events(activity_events, now, days=7)
    
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
