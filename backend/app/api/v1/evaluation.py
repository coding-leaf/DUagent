import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.course import CourseEnrollment
from app.models.others import AsyncTask, Evaluation, Resource
from app.models.quiz import QuizSession
from app.models.user import User
from app.services.agent_client import AgentServiceError, agent_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/evaluation", tags=["evaluation"])

_empty_table = {"columns": [], "rows": []}


async def _acquire_evaluation_lock(db: AsyncSession, user_id: str, course_id: str) -> str:
    """Acquire a MySQL named lock for serializing evaluation writes."""
    lock_name = f"evaluation_{user_id}_{course_id}"
    lock_result = await db.execute(text("SELECT GET_LOCK(:name, 5)"), {"name": lock_name})
    if not lock_result.scalar():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": 50300, "message": "服务繁忙，请稍后重试", "data": None},
        )
    return lock_name


async def _release_evaluation_lock(db: AsyncSession, lock_name: str) -> None:
    """Release a previously acquired MySQL named lock for evaluation writes."""
    await db.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": lock_name})


@router.get("")
async def get_evaluation(
    course_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Evaluation)
        .where(
            Evaluation.user_id == current_user.id,
            Evaluation.course_id == course_id,
            Evaluation.is_deleted == False,
        )
        .order_by(Evaluation.generated_at.desc())
    )
    ev = result.scalars().first()

    if ev is None:
        return {
            "code": 200,
            "message": "success",
            "data": {
                "course_id": course_id,
                "progress_table": _empty_table,
                "mastery_table": _empty_table,
                "resource_usage_table": _empty_table,
                "summary_text": "",
                "generated_at": None,
            },
        }

    return {
        "code": 200,
        "message": "success",
        "data": {
            "course_id": ev.course_id,
            "progress_table": ev.progress_table or _empty_table,
            "mastery_table": ev.mastery_table or _empty_table,
            "resource_usage_table": ev.resource_usage_table or _empty_table,
            "summary_text": ev.summary_text or "",
            "generated_at": ev.generated_at.isoformat() if ev.generated_at else None,
        },
    }


async def _assemble_evaluation_payload(
    user_id: str, course_id: str, db: AsyncSession,
) -> dict:
    """组装调用 Agent /evaluation/generate 所需的 payload。"""
    payload: dict = {"user_id": user_id, "course_id": course_id}

    # learning_progress (简化：按课程资源章节统计)
    chapters_r = await db.execute(
        select(Resource.chapter, func.count(Resource.id))
        .where(Resource.course_id == course_id, Resource.is_deleted == False)
        .group_by(Resource.chapter)
    )
    chapter_progress = [
        {"chapter": row[0] or "默认", "completion_rate": 0.0, "time_spent": 0}
        for row in chapters_r
    ]
    payload["learning_progress"] = {"chapter_progress": chapter_progress}

    # quiz_results
    qz_r = await db.execute(
        select(QuizSession)
        .where(QuizSession.user_id == user_id, QuizSession.course_id == course_id, QuizSession.is_deleted == False)
        .order_by(QuizSession.create_time.desc())
        .limit(50)
    )
    quizzes = qz_r.scalars().all()
    payload["quiz_results"] = [
        {
            "chapter": q.chapter,
            "score": q.score,
            "created_at": q.create_time.isoformat() if q.create_time else "",
        }
        for q in quizzes
    ]

    # resource_usage
    types = ["document", "mindmap", "reading", "code", "video"]
    by_type: dict = {}
    for t in types:
        c_r = await db.execute(
            select(func.count(Resource.id)).where(
                Resource.course_id == course_id, Resource.type == t, Resource.is_deleted == False
            )
        )
        by_type[t] = c_r.scalar() or 0
    payload["resource_usage"] = {"by_type": by_type}

    return payload


@router.post("/refresh")
async def refresh_evaluation(
    course_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """请求刷新学习效果评估。调用 Agent /evaluation/generate，成功后写入 Evaluation。"""
    if current_user.role == "student":
        check = await db.execute(
            select(CourseEnrollment).where(
                CourseEnrollment.student_id == current_user.id,
                CourseEnrollment.course_id == course_id,
                CourseEnrollment.is_deleted == False,
            )
        )
        if not check.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": 40300, "message": "未加入该课程", "data": None},
            )

    task = AsyncTask(
        task_type="evaluation_refresh",
        status="processing",
        user_id=current_user.id,
        course_id=course_id,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)
    await db.commit()

    try:
        payload = await _assemble_evaluation_payload(current_user.id, course_id, db)
        data = await agent_client.post_json("/agent/v1/evaluation/generate", payload)

        lock_name = await _acquire_evaluation_lock(db, current_user.id, course_id)
        try:
            now = datetime.now(timezone.utc)
            old_result = await db.execute(
                select(Evaluation).where(
                    Evaluation.user_id == current_user.id,
                    Evaluation.course_id == course_id,
                    Evaluation.is_deleted == False,
                )
            )
            for old in old_result.scalars().all():
                old.is_deleted = True

            ev = Evaluation(
                user_id=current_user.id,
                course_id=course_id,
                progress_table=data.get("progress_table", _empty_table),
                mastery_table=data.get("mastery_table", _empty_table),
                resource_usage_table=data.get("resource_usage_table", _empty_table),
                summary_text=data.get("summary_text", ""),
                generated_at=now,
            )
            db.add(ev)

            task.status = "completed"
            task.result = {"updated_at": now.isoformat()}
            task.completed_at = now
            await db.flush()
            await db.commit()
        finally:
            await _release_evaluation_lock(db, lock_name)
    except AgentServiceError as e:
        await db.rollback()
        task.status = "failed"
        task.error_code = str(e.agent_code or "agent_error")
        task.error_message = e.message
        task.completed_at = datetime.now(timezone.utc)
        await db.flush()
        await db.commit()
    except HTTPException as e:
        await db.rollback()
        if task.status == "processing":
            task.status = "failed"
            task.error_code = "lock_timeout"
            task.error_message = "服务繁忙，请稍后重试"
            task.completed_at = datetime.now(timezone.utc)
            await db.flush()
            await db.commit()
        raise e
    except Exception as e:
        await db.rollback()
        logger.error(
            "Evaluation refresh: unexpected error user_id=%s course_id=%s type=%s message=%s",
            current_user.id, course_id, type(e).__name__, str(e),
        )
        task.status = "failed"
        task.error_code = "internal_error"
        task.error_message = str(e)[:500]
        task.completed_at = datetime.now(timezone.utc)
        await db.flush()
        await db.commit()

    return JSONResponse(
        status_code=202,
        content={"code": 202, "message": "accepted", "data": {"task_id": task.id}},
    )
