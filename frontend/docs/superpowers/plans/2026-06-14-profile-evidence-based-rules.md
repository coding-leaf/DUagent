# Profile Evidence-Based Rules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make student profile fields authoritative, traceable, and rule-based rather than AI-generated, aligning them with the shared KG node aggregation.

**Architecture:** 
1. Fix unique key violation in `user_profiles` writes by doing in-place updates.
2. Extract `_build_node_progress_rows` into a shared backend service `backend/app/services/knowledge_progress.py`.
3. Implement deterministic profile rules (modal preference, learning habits, badge, knowledge progress) directly in backend logic, bypassing the agent for core fields.
4. Update frontend `StudentProfile.jsx` to correctly display the new structured `learning_habits` and `knowledge_progress`.

**Tech Stack:** FastAPI, SQLAlchemy, React, Tailwind CSS

---

### Task 1: Fix Profile Persistence and Extract Shared KG Aggregation

**Files:**
- Create: `backend/app/services/knowledge_progress.py`
- Modify: `backend/app/api/v1/evaluation.py`
- Modify: `backend/app/api/v1/profile.py`

- [ ] **Step 1: Extract `_build_node_progress_rows`**
Move the `_resolve_evaluation_kg` and `_build_node_progress_rows` functions from `backend/app/api/v1/evaluation.py` into a new file `backend/app/services/knowledge_progress.py`. Update the imports.
```python
# Create backend/app/services/knowledge_progress.py
import logging
from collections import defaultdict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.catalog import CourseCatalog, CourseOffering
from app.models.others import CourseKnowledgeGraph, LearningActivity
from app.models.quiz import QuizAnswer, QuizQuestion, QuizSession
from app.services.course_knowledge_graphs import get_active_knowledge_graph

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

async def _build_node_progress_rows(user_id: str, course_id: str, db: AsyncSession) -> list[dict]:
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

    questions_result = await db.execute(
        select(QuizQuestion).where(
            QuizQuestion.course_id == course_id,
            QuizQuestion.knowledge_point.in_(node_names),
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

    attempts: dict[str, dict] = defaultdict(
        lambda: {"correct": 0, "total": 0, "duration": 0, "sessions": set()}
    )
    if session_by_id and question_to_kp:
        answer_result = await db.execute(
            select(QuizAnswer).where(
                QuizAnswer.quiz_id.in_(list(session_by_id.keys())),
                QuizAnswer.question_id.in_(list(question_to_kp.keys())),
                QuizAnswer.is_deleted == False,
            )
        )
        for answer in answer_result.scalars().all():
            knowledge_point = question_to_kp.get(answer.question_id)
            session = session_by_id.get(answer.quiz_id)
            if not knowledge_point or session is None:
                continue
            stats = attempts[knowledge_point]
            stats["total"] += 1
            stats["correct"] += 1 if answer.is_correct else 0
            stats["sessions"].add(session.id)
        for stats in attempts.values():
            stats["duration"] = sum(session_by_id[sid].time_spent or 0 for sid in stats["sessions"])

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

        # Apply mastery rules from spec
        if score is not None:
            # Nodes with questions: minimum evidence is 3 answered questions or all questions if less than 3
            min_evidence = min(3, question_count)
            has_minimum_evidence = attempt_count >= min_evidence
            
            if score >= 80 and has_minimum_evidence:
                assessment_state = "mastered"
                status_text = "已掌握"
                mastery_label = _mastery_label(score)
            elif score < 70 or (attempt_stats.get("latest_score", 100) < 60):
                assessment_state = "weak"
                status_text = "薄弱"
                mastery_label = _mastery_label(score)
            else:
                assessment_state = "learning"
                status_text = "学习中"
                mastery_label = _mastery_label(score)
        elif question_count > 0:
            assessment_state = "pending_practice"
            status_text = "待练习"
            mastery_label = "待练习"
        else:
            activity_stats = activity_by_node.get(node_id, {})
            has_activity = bool(activity_stats.get("duration") or activity_stats.get("activity_count"))
            if has_activity:
                assessment_state = "learning"
                status_text = "学习中"
                mastery_label = "无测评"
            else:
                assessment_state = "unstarted"
                status_text = "未开始"
                mastery_label = "无测评"

        activity_stats = activity_by_node.get(node_id, {})
        activity_duration = int(activity_stats.get("duration") or 0)
        quiz_duration = int(attempt_stats["duration"]) if attempt_stats and attempt_stats["duration"] else 0
        duration = activity_duration or quiz_duration or None
        last_activity_at = activity_stats.get("last_activity_at")
        rows.append(
            {
                "node_id": node_id,
                "node_name": node_name,
                "status": status_text,
                "study_duration_seconds": duration,
                "mastery_score": score,
                "mastery_label": mastery_label,
                "assessment_state": assessment_state,
                "question_count": question_count,
                "attempt_count": attempt_count,
                "resource_visit_count": activity_stats.get("resource_visit_count"),
                "last_activity_at": last_activity_at.isoformat() if last_activity_at else None,
            }
        )
    return rows
```

- [ ] **Step 2: Update imports in `backend/app/api/v1/evaluation.py`**
Remove the definitions of `_mastery_label`, `_resolve_evaluation_kg` and `_build_node_progress_rows` from `evaluation.py`. Import `_build_node_progress_rows` from `app.services.knowledge_progress`.

- [ ] **Step 3: Fix `user_profiles` persistence to be in-place updates**
In `backend/app/api/v1/profile.py`, change `initialize_profile` and `_run_profile_refresh_background` to update the existing row instead of soft-delete and insert.

In `initialize_profile`:
```python
        old_result = await db.execute(
            select(UserProfile).where(
                UserProfile.user_id == current_user.id,
                UserProfile.course_id == req.course_id,
                UserProfile.is_deleted == False,
            )
        )
        pf = old_result.scalars().first()
        answers = req.answers or {}
        now = datetime.now(timezone.utc)
        
        if pf:
            pf.guidance_level_current = answers.get("guidance_level", "L2")
            pf.guidance_level_updated_at = now
            pf.modal_preference = {k: 60 for k in (answers.get("modal_preference") or ["text"])}
            pf.drive_intent = {"type": answers.get("learning_goal", "casual"), "intensity": 50}
            pf.knowledge_coordinates = [{"name": "入门", "status": "learning", "mastered_at": None}]
            pf.generated_at = now
        else:
            pf = UserProfile(
                user_id=current_user.id,
                course_id=req.course_id,
                guidance_level_current=answers.get("guidance_level", "L2"),
                guidance_level_updated_at=now,
                modal_preference={k: 60 for k in (answers.get("modal_preference") or ["text"])},
                drive_intent={"type": answers.get("learning_goal", "casual"), "intensity": 50},
                knowledge_coordinates=[{"name": "入门", "status": "learning", "mastered_at": None}],
                generated_at=now,
            )
            db.add(pf)
```

In `_run_profile_refresh_background`:
```python
                old_result = await db.execute(
                    select(UserProfile).where(
                        UserProfile.user_id == user_id,
                        UserProfile.course_id == course_id,
                        UserProfile.is_deleted == False,
                    )
                )
                pf = old_result.scalars().first()
                if not pf:
                    pf = UserProfile(
                        user_id=user_id,
                        course_id=course_id,
                    )
                    db.add(pf)
                    await db.flush()
                pf.generated_at = now
                # ... (apply data later)
```

### Task 2: Implement Profile Rules Engine

**Files:**
- Create: `backend/app/services/profile_rules.py`

- [ ] **Step 1: Write rule computation logic**
Create `backend/app/services/profile_rules.py` with logic to compute modal preference, learning habits, badge, and knowledge structures based on `LearningActivity`, `QuizSession`, and `_build_node_progress_rows`.

```python
from datetime import datetime, timezone, timedelta
from typing import Dict, Any
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.others import LearningActivity
from app.models.quiz import QuizSession
from app.models.user import User

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

    # 1. Resource/Modal Preference (derived from LearningActivity duration)
    from app.models.others import Resource
    activities = await db.execute(
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
    
    modal_durations = {"video_animation": 0, "chart_logic": 0, "text_analysis": 0, "code_practice": 0, "formula_derivation": 0}
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
        if max_duration == 0: max_duration = 1
        for k, v in modal_durations.items():
            modal_preference[k] = int((v / max_duration) * 100)
    else:
        modal_preference = {k: 0 for k in modal_durations.keys()}

    # 2. Knowledge Coordinates and Cognitive Blindspots
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
        evidence = "quiz" if row["attempt_count"] > 0 else ("activity" if row["study_duration_seconds"] else "none")
        
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

    # 3. Learning Habits
    from sqlalchemy import case
    habit_metrics = await db.execute(
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
    last_activity_at, study_duration_7d, study_duration_30d = habit_metrics.first()
    study_duration_7d = int(study_duration_7d or 0)
    study_duration_30d = int(study_duration_30d or 0)
    
    active_days_7d = 0
    streak_days = 0 
    practice_count_7d = 0
    
    active_dates_result = await db.execute(
        select(func.date(LearningActivity.occurred_at)).where(
            LearningActivity.user_id == user_id,
            LearningActivity.course_id == course_id,
            LearningActivity.occurred_at >= seven_days_ago,
            LearningActivity.is_deleted == False
        ).group_by(func.date(LearningActivity.occurred_at))
    )
    active_days_7d = len(active_dates_result.all())
    
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
        if hours_since <= 24: recency_score = 100
        elif hours_since <= 72: recency_score = 70
        elif hours_since <= 168: recency_score = 40

    learning_habit_score = (continuity_score * 0.35) + (effort_score * 0.35) + (practice_score * 0.20) + (recency_score * 0.10)
    
    total_events_r = await db.execute(select(func.count(LearningActivity.id)).where(LearningActivity.user_id == user_id, LearningActivity.course_id == course_id))
    total_events = total_events_r.scalar() or 0
    
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

    # 4. Discipline Badge
    weak_penalty_score = min(weak_count / max(total_nodes, 1), 1.0) * 100
    badge_score = (learning_habit_score * 0.40) + (mastery_rate * 0.50) - (weak_penalty_score * 0.10)
    badge_score = max(0, min(100, badge_score))
    
    if badge_score < 40 or total_nodes == 0: badge_level = "starter"
    elif badge_score < 70: badge_level = "steady"
    elif badge_score < 85: badge_level = "advanced"
    else: badge_level = "excellent"

    discipline_badge = {
        "subject": course_id,
        "level": badge_level,
        "score": int(badge_score),
        "streak_days": streak_days,
        "reasons": []
    }

    return {
        "modal_preference": modal_preference,
        "knowledge_coordinates": knowledge_coordinates,
        "cognitive_blindspots": weak_nodes,
        "learning_habits": learning_habits,
        "discipline_badge": discipline_badge,
        "knowledge_progress_summary": knowledge_progress_summary
    }
```

### Task 3: Apply Rules in Backend Profile API

**Files:**
- Modify: `backend/app/api/v1/profile.py`

- [ ] **Step 1: Rewrite `_run_profile_refresh_background` to bypass Agent API**
In `backend/app/api/v1/profile.py`, remove the `agent_client.post_json("/agent/v1/profile/generate", payload)` call inside `_run_profile_refresh_background`. Call `compute_profile_fields` from `profile_rules.py` instead. Add `from app.models.user import User` and query the user.
Update `UserProfile` fields with the returned computed fields. Make sure `guidance_level_current` takes `user.guidance_level` directly rather than from the agent.

```python
                user_result = await db.execute(select(User).where(User.id == user_id))
                user = user_result.scalars().first()
                
                from app.services.knowledge_progress import _build_node_progress_rows
                from app.services.profile_rules import compute_profile_fields
                node_progress_rows = await _build_node_progress_rows(user_id, course_id, db)
                computed = await compute_profile_fields(user_id, course_id, user, node_progress_rows, db)

                pf.modal_preference = computed["modal_preference"]
                pf.guidance_level_current = user.guidance_level if user else "L2"
                pf.guidance_level_updated_at = now
                pf.knowledge_coordinates = computed["knowledge_coordinates"]
                pf.cognitive_blindspots = computed["cognitive_blindspots"]
                
                drive_intent = pf.drive_intent or {}
                drive_intent["learning_habits"] = computed["learning_habits"]
                drive_intent["knowledge_progress_summary"] = computed["knowledge_progress_summary"]
                pf.drive_intent = drive_intent
                
                pf.discipline_badge = computed["discipline_badge"]
```

- [ ] **Step 2: Update `_profile_dimensions` to return the new structured values**
In `_profile_dimensions`:
```python
    drive_intent = profile.get("drive_intent") or {}
    learning_habits = drive_intent.get("learning_habits") or {}
    knowledge_progress_summary = drive_intent.get("knowledge_progress_summary") or {}
    # ...
    return [
        # ...
        {
            "key": "knowledge_progress",
            "label": "知识进展",
            "value": knowledge_progress_summary if knowledge_progress_summary else len(knowledge_coordinates),
            "source": "kg_quiz_activity",
        },
        {
            "key": "learning_habits",
            "label": "学习习惯",
            "value": learning_habits,
            "source": "activity",
        },
    ]
```

- [ ] **Step 3: Ensure `get_profile` correctly mirrors `users.guidance_level`**
Update `_profile_data(pf, course_id)` to take `user` argument and use `user.guidance_level` as the source of truth for `guidance_level.current`. Update `get_profile`, `initialize_profile`, and `dialogue_update_profile` to pass `current_user` to `_profile_data`.

### Task 4: Update Frontend `StudentProfile.jsx`

**Files:**
- Modify: `frontend/src/pages/StudentProfile.jsx`

- [ ] **Step 1: Update labels for new fields**
Update `PROFILE_DIMENSION_LABELS` and `PROFILE_EMPTY_TEXT` in `StudentProfile.jsx`:
```javascript
const PROFILE_DIMENSION_LABELS = {
  // ...
  learning_habits: '学习习惯',
};

const PROFILE_EMPTY_TEXT = {
  // ...
  learning_habits: '暂无学习记录',
};
```

- [ ] **Step 2: Update rendering of `knowledge_progress`**
In `formatDimensionValue`, add special formatting for `knowledge_progress`:
```javascript
    if (key === 'knowledge_progress' && value && typeof value === 'object') {
      return `已掌握 ${value.mastered_nodes || 0}/${value.total_nodes || 0}，薄弱 ${value.weak_nodes || 0} 个，待练习 ${value.pending_nodes || 0} 个`;
    }
```

- [ ] **Step 3: Update rendering of `learning_habits`**
In `formatDimensionValue`, add special formatting for `learning_habits`:
```javascript
    if (key === 'learning_habits') {
      if (!value || typeof value !== 'object') return PROFILE_EMPTY_TEXT.learning_habits;
      const labelMap = { new: '新生', inactive: '不活跃', sprint: '突击', stable: '稳定', casual: '随性' };
      const label = labelMap[value.label] || value.label || '未知';
      return `状态：${label} · 习惯分：${value.score || 0}`;
    }
```

- [ ] **Step 4: Update source labels**
```javascript
  const sourceLabel = (source) => ({
    // ...
    kg_quiz_activity: '图谱+行为',
  }[source] || source || '未知来源');
```

- [ ] **Step 5: Run tests to verify**
Start the frontend and backend, manually navigate to `/profile`, switch guidance level, click '同步画像', and verify the UI updates and reflects the rule-derived data.
