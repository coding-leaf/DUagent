# Analysis Report: Refactoring Evaluation API to Service Layer

## Overview
This report provides a detailed analysis of `backend/app/api/v1/evaluation.py` and proposes the design and API of a new service file `backend/app/services/evaluation_service.py`. By extracting database queries, lock acquisition, payload assembly, and background task execution into the Service layer, we enforce clean separation of concerns and align the Evaluation module with the project's established design patterns (similar to Profile and Learning Path).

---

## 1. Analysis of `backend/app/api/v1/evaluation.py`
The current implementation of the evaluation router suffers from architectural coupling, specifically:
- **Direct Database Queries**: The router performs heavy querying on models (`User`, `UserProfile`, `CourseOffering`, `CourseCatalog`, `LearningActivity`, `Resource`, `QuizSession`, `QuizAnswer`, `QuizQuestion`, `Evaluation`, and `AsyncTask`) to assemble the payload.
- **Controller-managed Concurrency Locks**: Explicitly manages raw MySQL named locks using `GET_LOCK` and `RELEASE_LOCK` SQL execution.
- **Payload Construction**: Over 150 lines of code inside `_assemble_evaluation_payload` are dedicated to gathering context from various tables.
- **Background Task Execution**: `_run_evaluation_refresh_background` is a private, module-level function within the routing layer, which manages database sessions (`async_session_factory`) and processes agent service calls.

---

## 2. Proposed Service Layer Architecture
We propose introducing `EvaluationService` and a background runner module to `backend/app/services/evaluation_service.py`, and extending the locking utilities in `backend/app/infrastructure/locks.py`.

### 2.1 Concurrency Lock Context Manager
In order to encapsulate MySQL/SQLite locking cleanly, we propose adding `evaluation_lock` to `backend/app/infrastructure/locks.py`:

```python
# app/infrastructure/locks.py additions
@asynccontextmanager
async def evaluation_lock(db: AsyncSession, user_id: str, course_id: str):
    # Base key name
    raw = f"evaluation_{user_id}_{course_id}"
    
    # SQLite fallback
    if db.bind.dialect.name == "sqlite":
        yield raw
        return

    # MySQL named lock key length limit is 64 characters, hash to prevent overflow
    lock_name = hashlib.md5(raw.encode()).hexdigest()[:32]
    
    lock_result = await db.execute(
        text("SELECT GET_LOCK(:key, 5)"),
        params={"key": lock_name}
    )
    acquired = lock_result.scalar()
    if not acquired:
        raise LockAcquisitionTimeout(f"Lock timeout for evaluation of user: {user_id}, course: {course_id}")
        
    try:
        yield lock_name
    finally:
        await db.execute(
            text("SELECT RELEASE_LOCK(:key)"),
            params={"key": lock_name}
        )
```

### 2.2 The Service Class: `EvaluationService`
This class will wrap all database read/write actions for request-level transactions.

```python
class EvaluationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_evaluation(self, user_id: str, course_id: str) -> dict:
        """Retrieves active evaluation for user/course. Constructs response dict."""
        ...

    async def get_processing_refresh_task(self, user_id: str, course_id: str) -> AsyncTask | None:
        """Queries database for any currently processing refresh task."""
        ...

    async def create_refresh_task(self, user_id: str, course_id: str) -> AsyncTask:
        """Creates and flushes a new processing task for evaluation refresh."""
        ...

    async def assemble_payload(self, user_id: str, course_id: str) -> dict:
        """Collects database context and constructs the JSON payload for Agent Service."""
        ...

    async def verify_course_enrollment(self, user_id: str, course_id: str, role: str) -> None:
        """Validates that student users are enrolled in the course."""
        ...
```

### 2.3 The Background Service Runner
`run_evaluation_refresh_background` is a standalone coroutine executing on the event loop (via `asyncio.create_task`). It does not reuse the controller's database session, but rather opens a fresh session using `async_session_factory` to guarantee isolation.

```python
async def run_evaluation_refresh_background(
    task_id: str,
    user_id: str,
    course_id: str,
    payload: dict
) -> None:
    """Executes agent call, handles MySQL locking, updates models, and manages task completion/failure."""
    ...
```

---

## 3. Implementation Blueprint of `evaluation_service.py`

Below is the complete proposed code for `backend/app/services/evaluation_service.py`:

```python
import logging
from datetime import datetime, timezone
from sqlalchemy import func, select, update, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models.catalog import CourseCatalog, CourseOffering
from app.models.course import CourseEnrollment
from app.models.others import AsyncTask, Evaluation, LearningActivity, Resource, UserProfile
from app.models.quiz import QuizAnswer, QuizQuestion, QuizSession
from app.models.user import User
from app.services.agent_client import AgentServiceError, agent_client
from app.services.course_knowledge_graphs import get_active_knowledge_graph
from app.services.resource_scope import resolve_course_resource_scope, resource_scope_clause
from app.services.knowledge_progress import build_node_progress_rows
from app.infrastructure.locks import evaluation_lock, LockAcquisitionTimeout

logger = logging.getLogger(__name__)

_empty_table = {"columns": [], "rows": []}

class EvaluationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def verify_course_enrollment(self, user_id: str, course_id: str, role: str) -> None:
        """Verify student enrollment in a course. Raises HTTPException on failure."""
        from fastapi import HTTPException, status
        if role == "student":
            check = await self.db.execute(
                select(CourseEnrollment).where(
                    CourseEnrollment.student_id == user_id,
                    CourseEnrollment.course_id == course_id,
                    CourseEnrollment.is_deleted == False,
                )
            )
            if not check.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"code": 40300, "message": "未加入该课程", "data": None},
                )

    async def get_evaluation(self, user_id: str, course_id: str) -> dict:
        """Get the latest evaluation, format the response structure."""
        node_progress = await build_node_progress_rows(user_id, course_id, self.db)
        
        result = await self.db.execute(
            select(Evaluation)
            .where(
                Evaluation.user_id == user_id,
                Evaluation.course_id == course_id,
                Evaluation.is_deleted == False,
            )
            .order_by(Evaluation.generated_at.desc())
        )
        ev = result.scalars().first()

        if ev is None:
            return {
                "course_id": course_id,
                "progress_table": _empty_table,
                "mastery_table": _empty_table,
                "resource_usage_table": _empty_table,
                "node_progress": node_progress,
                "summary_text": "",
                "generated_at": None,
            }

        progress_table = ev.progress_table or _empty_table
        return {
            "course_id": ev.course_id,
            "progress_table": progress_table,
            "mastery_table": ev.mastery_table or _empty_table,
            "resource_usage_table": ev.resource_usage_table or _empty_table,
            "node_progress": node_progress,
            "summary_text": ev.summary_text or "",
            "generated_at": ev.generated_at.isoformat() if ev.generated_at else None,
        }

    async def get_processing_refresh_task(self, user_id: str, course_id: str) -> AsyncTask | None:
        """Find if there is a running evaluation refresh task for the user/course."""
        result = await self.db.execute(
            select(AsyncTask)
            .where(
                AsyncTask.task_type == "evaluation_refresh",
                AsyncTask.user_id == user_id,
                AsyncTask.course_id == course_id,
                AsyncTask.status == "processing",
                AsyncTask.is_deleted == False,
            )
            .order_by(AsyncTask.create_time.desc(), AsyncTask.id.desc())
        )
        return result.scalars().first()

    async def create_refresh_task(self, user_id: str, course_id: str) -> AsyncTask:
        """Create and persist a new async task tracking the evaluation refresh."""
        task = AsyncTask(
            task_type="evaluation_refresh",
            status="processing",
            user_id=user_id,
            course_id=course_id,
        )
        self.db.add(task)
        await self.db.flush()
        await self.db.refresh(task)
        return task

    async def assemble_payload(self, user_id: str, course_id: str) -> dict:
        """Assembles the full context dictionary expected by the agent service."""
        payload: dict = {"user_id": user_id, "course_id": course_id}
        resource_scope = await resolve_course_resource_scope(self.db, course_id)
        node_progress = await build_node_progress_rows(user_id, course_id, self.db)

        # 1. Student Info
        user_result = await self.db.execute(
            select(User).where(User.id == user_id, User.is_deleted == False)
        )
        user = user_result.scalar_one_or_none()
        if user:
            payload["student_profile"] = {
                "major": user.major,
                "grade": user.grade,
                "guidance_level": user.guidance_level,
            }

        # 2. User Profile Info
        profile_result = await self.db.execute(
            select(UserProfile)
            .where(
                UserProfile.user_id == user_id,
                UserProfile.course_id == course_id,
                UserProfile.is_deleted == False,
            )
            .order_by(UserProfile.generated_at.desc())
        )
        profile = profile_result.scalars().first()
        if profile:
            payload["profile_context"] = {
                "modal_preference": profile.modal_preference,
                "knowledge_coordinates": profile.knowledge_coordinates,
                "cognitive_blindspots": profile.cognitive_blindspots,
                "drive_intent": profile.drive_intent,
                "discipline_badge": profile.discipline_badge,
                "generated_at": profile.generated_at.isoformat() if profile.generated_at else None,
            }

        # 3. Knowledge Graph Context
        kg = await get_active_knowledge_graph(self.db, course_id)
        if kg is None:
            offering_result = await self.db.execute(
                select(CourseOffering).where(
                    CourseOffering.id == course_id,
                    CourseOffering.is_deleted == False,
                )
            )
            offering = offering_result.scalar_one_or_none()
            if offering:
                catalog_result = await self.db.execute(
                    select(CourseCatalog).where(
                        CourseCatalog.id == offering.catalog_id,
                        CourseCatalog.is_deleted == False,
                    )
                )
                catalog = catalog_result.scalar_one_or_none()
                if catalog and catalog.kg_host_course_id:
                    kg = await get_active_knowledge_graph(self.db, catalog.kg_host_course_id)
        payload["kg_context"] = {
            "nodes": kg.nodes if kg and isinstance(kg.nodes, list) else [],
            "node_progress": node_progress,
        }

        # 4. Learning Activity Stats
        activity_result = await self.db.execute(
            select(
                func.count(LearningActivity.id),
                func.coalesce(func.sum(LearningActivity.duration_seconds), 0),
                func.count(func.distinct(func.date(LearningActivity.occurred_at))),
                func.max(LearningActivity.occurred_at),
            ).where(
                LearningActivity.user_id == user_id,
                LearningActivity.course_id == course_id,
                LearningActivity.is_deleted == False,
            )
        )
        activity_count, total_duration, active_days, last_activity_at = activity_result.one()
        payload["learning_activity"] = {
            "total_events": int(activity_count or 0),
            "total_duration_seconds": int(total_duration or 0),
            "active_days": int(active_days or 0),
            "last_activity_at": last_activity_at.isoformat() if last_activity_at else None,
        }

        # 5. Resource Chapter Progression
        chapters_r = await self.db.execute(
            select(Resource.chapter, func.count(Resource.id))
            .where(resource_scope_clause(course_id, resource_scope.catalog_id), Resource.is_deleted == False)
            .group_by(Resource.chapter)
        )
        chapter_progress = [
            {"chapter": row[0] or "默认", "completion_rate": 0.0, "time_spent": 0}
            for row in chapters_r
        ]
        payload["learning_progress"] = {"chapter_progress": chapter_progress}

        # 6. Quiz Results by Knowledge Point
        qz_r = await self.db.execute(
            select(QuizSession)
            .where(QuizSession.user_id == user_id, QuizSession.course_id == course_id, QuizSession.is_deleted == False)
            .order_by(QuizSession.create_time.desc())
            .limit(50)
        )
        quizzes = qz_r.scalars().all()
        quiz_ids = [q.id for q in quizzes]

        kp_stats: dict[str, dict] = {}
        if quiz_ids:
            qa_result = await self.db.execute(
                select(
                    QuizAnswer.is_correct,
                    QuizAnswer.create_time,
                    QuizQuestion.knowledge_point,
                    QuizQuestion.chapter,
                    QuizQuestion.personalized,
                )
                .join(QuizQuestion, QuizAnswer.question_id == QuizQuestion.id)
                .where(
                    QuizAnswer.quiz_id.in_(quiz_ids),
                    QuizAnswer.is_deleted == False,
                    QuizQuestion.is_deleted == False,
                )
                .order_by(QuizAnswer.create_time.asc())
            )
            for row in qa_result.all():
                kp = row.knowledge_point or "未分类"
                if kp not in kp_stats:
                    kp_stats[kp] = {
                        "chapter": row.chapter or "",
                        "total": 0,
                        "correct": 0,
                        "personalized_count": 0,
                        "recent_scores": [],
                    }
                kp_stats[kp]["total"] += 1
                if row.is_correct:
                    kp_stats[kp]["correct"] += 1
                if row.personalized:
                    kp_stats[kp]["personalized_count"] += 1
                if len(kp_stats[kp]["recent_scores"]) < 10:
                    kp_stats[kp]["recent_scores"].append(1 if row.is_correct else 0)

        payload["quiz_results"] = [
            {
                "knowledge_point": kp,
                "chapter": stats["chapter"],
                "score": round(stats["correct"] / stats["total"] * 100, 1) if stats["total"] > 0 else 0.0,
                "total_answers": stats["total"],
                "personalized_count": stats["personalized_count"],
                "recent_trend": round(sum(stats["recent_scores"]) / len(stats["recent_scores"]) * 100, 1)
                                if stats["recent_scores"] else 0.0,
            }
            for kp, stats in kp_stats.items()
        ]

        # 7. Resource Usage Breakdown
        types = ["document", "mindmap", "reading", "code", "video"]
        by_type: dict = {}
        for t in types:
            c_r = await self.db.execute(
                select(func.count(Resource.id)).where(
                    resource_scope_clause(course_id, resource_scope.catalog_id),
                    Resource.type == t,
                    Resource.is_deleted == False,
                )
            )
            by_type[t] = c_r.scalar() or 0
        payload["resource_usage"] = {"by_type": by_type}

        return payload


async def run_evaluation_refresh_background(
    task_id: str,
    user_id: str,
    course_id: str,
    payload: dict,
) -> None:
    """Background evaluation generation execution coroutine. Uses isolated Session."""
    async with async_session_factory() as db:
        try:
            # 1. Request evaluation generation from the Agent Service client
            data = await agent_client.post_json("/agent/v1/evaluation/generate", payload)

            # 2. Acquire serialization lock inside database context
            async with evaluation_lock(db, user_id, course_id):
                now = datetime.now(timezone.utc)
                
                # Fetch node progress to combine into progress_table rows
                node_progress = await build_node_progress_rows(user_id, course_id, db)
                
                progress_table = data.get("progress_table", _empty_table)
                if not isinstance(progress_table, dict):
                    progress_table = _empty_table
                progress_table = {
                    "columns": progress_table.get("columns") or [],
                    "rows": node_progress,
                }

                # 3. Soft-delete old evaluation logs
                old_result = await db.execute(
                    select(Evaluation).where(
                        Evaluation.user_id == user_id,
                        Evaluation.course_id == course_id,
                        Evaluation.is_deleted == False,
                    )
                )
                for old in old_result.scalars().all():
                    old.is_deleted = True

                # 4. Insert new evaluation entry
                ev = Evaluation(
                    user_id=user_id,
                    course_id=course_id,
                    progress_table=progress_table,
                    mastery_table=data.get("mastery_table", _empty_table),
                    resource_usage_table=data.get("resource_usage_table", _empty_table),
                    summary_text=data.get("summary_text", ""),
                    generated_at=now,
                )
                db.add(ev)

                # 5. Transition task status to 'completed'
                await db.execute(
                    update(AsyncTask)
                    .where(AsyncTask.id == task_id)
                    .values(
                        status="completed",
                        result={"updated_at": now.isoformat()},
                        completed_at=now,
                    )
                )
                await db.commit()
                logger.info(
                    "Evaluation refresh background: completed task_id=%s user_id=%s course_id=%s",
                    task_id, user_id, course_id,
                )
        except LockAcquisitionTimeout as exc:
            await db.rollback()
            logger.warning(
                "Evaluation refresh background: lock timeout task_id=%s user_id=%s course_id=%s message=%s",
                task_id, user_id, course_id, str(exc),
            )
            await db.execute(
                update(AsyncTask)
                .where(AsyncTask.id == task_id)
                .values(
                    status="failed",
                    error_code="lock_timeout",
                    error_message="服务繁忙，请稍后重试",
                    completed_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()
        except AgentServiceError as exc:
            await db.rollback()
            logger.error(
                "Evaluation refresh background: AgentServiceError task_id=%s user_id=%s course_id=%s status=%s code=%s message=%s",
                task_id, user_id, course_id, exc.status_code, exc.agent_code, exc.message,
            )
            await db.execute(
                update(AsyncTask)
                .where(AsyncTask.id == task_id)
                .values(
                    status="failed",
                    error_code=str(exc.agent_code or "agent_error"),
                    error_message=exc.message,
                    completed_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()
        except Exception as exc:
            await db.rollback()
            logger.error(
                "Evaluation refresh background: unexpected error task_id=%s user_id=%s course_id=%s type=%s message=%s",
                task_id, user_id, course_id, type(exc).__name__, str(exc),
                exc_info=True
            )
            await db.execute(
                update(AsyncTask)
                .where(AsyncTask.id == task_id)
                .values(
                    status="failed",
                    error_code="internal_error",
                    error_message=str(exc)[:500],
                    completed_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()
```

---

## 4. Refactoring the Controller Layer (`evaluation.py`)
With the logic moved, `backend/app/api/v1/evaluation.py` simplifies to an orchestration point:

```python
import asyncio
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.ai_features import RefreshRequest
from app.services.evaluation_service import EvaluationService, run_evaluation_refresh_background

router = APIRouter(prefix="/api/v1/evaluation", tags=["evaluation"])

@router.get("")
async def get_evaluation(
    course_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = EvaluationService(db)
    data = await service.get_evaluation(current_user.id, course_id)
    return {
        "code": 200,
        "message": "success",
        "data": data,
    }

@router.post("/refresh")
async def refresh_evaluation(
    req: RefreshRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    course_id = req.course_id
    service = EvaluationService(db)

    # 1. Verify that user is authorized to access the course evaluation
    await service.verify_course_enrollment(current_user.id, course_id, current_user.role)

    # 2. Check for active execution tasks to prevent overlapping updates
    existing_task = await service.get_processing_refresh_task(current_user.id, course_id)
    if existing_task:
        return JSONResponse(
            status_code=202,
            content={"code": 202, "message": "accepted", "data": {"task_id": existing_task.id}},
        )

    # 3. Assemble data payload synchronously in API request thread
    payload = await service.assemble_payload(current_user.id, course_id)

    # 4. Record new task processing state
    task = await service.create_refresh_task(current_user.id, course_id)
    await db.commit()

    # 5. Dispatch task execution context asynchronously to event loop
    asyncio.create_task(run_evaluation_refresh_background(
        task_id=task.id,
        user_id=current_user.id,
        course_id=course_id,
        payload=payload,
    ))

    return JSONResponse(
        status_code=202,
        content={"code": 202, "message": "accepted", "data": {"task_id": task.id}},
    )
```
