import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.db.session import async_session_factory
from app.models.catalog import CourseCatalog, CourseOffering
from app.models.course import CourseEnrollment
from app.models.others import AsyncTask, CourseKnowledgeGraph, Evaluation, LearningActivity, Resource, UserProfile
from app.models.quiz import QuizAnswer, QuizQuestion, QuizSession
from app.models.user import User
from app.services.agent_client import AgentServiceError, agent_client
from app.services.course_knowledge_graphs import get_active_knowledge_graph
from app.services.resource_scope import resolve_course_resource_scope, resource_scope_clause
from app.schemas.ai_features import RefreshRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/evaluation", tags=["evaluation"])

_empty_table = {"columns": [], "rows": []}

from app.services.knowledge_progress import build_node_progress_rows


def _looks_like_node_progress(rows: object) -> bool:
    return (
        isinstance(rows, list)
        and bool(rows)
        and all(isinstance(row, dict) and row.get("node_id") and row.get("node_name") for row in rows)
    )


async def _acquire_evaluation_lock(db: AsyncSession, user_id: str, course_id: str) -> str:
    """Acquire a MySQL named lock for serializing evaluation writes."""
    lock_name = f"evaluation_{user_id}_{course_id}"
    if db.bind.dialect.name == "sqlite":
        return lock_name
    lock_result = await db.execute(text("SELECT GET_LOCK(:name, 5)"), {"name": lock_name})
    if not lock_result.scalar():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": 50300, "message": "服务繁忙，请稍后重试", "data": None},
        )
    return lock_name


async def _release_evaluation_lock(db: AsyncSession, lock_name: str) -> None:
    """Release a previously acquired MySQL named lock for evaluation writes."""
    if db.bind.dialect.name == "sqlite":
        return
    await db.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": lock_name})


async def _get_processing_refresh_task(
    db: AsyncSession,
    task_type: str,
    user_id: str,
    course_id: str,
) -> AsyncTask | None:
    result = await db.execute(
        select(AsyncTask)
        .where(
            AsyncTask.task_type == task_type,
            AsyncTask.user_id == user_id,
            AsyncTask.course_id == course_id,
            AsyncTask.status == "processing",
            AsyncTask.is_deleted == False,
        )
        .order_by(AsyncTask.create_time.desc(), AsyncTask.id.desc())
    )
    return result.scalars().first()


@router.get("")
async def get_evaluation(
    course_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    node_progress = await build_node_progress_rows(current_user.id, course_id, db)
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
                "node_progress": node_progress,
                "summary_text": "",
                "generated_at": None,
            },
        }

    progress_table = ev.progress_table or _empty_table
    stored_node_progress = progress_table.get("rows") if isinstance(progress_table, dict) else None
    return {
        "code": 200,
        "message": "success",
        "data": {
            "course_id": ev.course_id,
            "progress_table": progress_table,
            "mastery_table": ev.mastery_table or _empty_table,
            "resource_usage_table": ev.resource_usage_table or _empty_table,
            "node_progress": node_progress,
            "summary_text": ev.summary_text or "",
            "generated_at": ev.generated_at.isoformat() if ev.generated_at else None,
        },
    }


async def _assemble_evaluation_payload(
    user_id: str, course_id: str, db: AsyncSession,
) -> dict:
    """组装调用 Agent /evaluation/generate 所需的 payload。"""
    payload: dict = {"user_id": user_id, "course_id": course_id}
    resource_scope = await resolve_course_resource_scope(db, course_id)
    node_progress = await build_node_progress_rows(user_id, course_id, db)

    user_result = await db.execute(select(User).where(User.id == user_id, User.is_deleted == False))
    user = user_result.scalar_one_or_none()
    if user:
        payload["student_profile"] = {
            "major": user.major,
            "grade": user.grade,
            "guidance_level": user.guidance_level,
        }

    profile_result = await db.execute(
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

    kg = await get_active_knowledge_graph(db, course_id)
    if kg is None:
        offering_result = await db.execute(
            select(CourseOffering).where(
                CourseOffering.id == course_id,
                CourseOffering.is_deleted == False,
            )
        )
        offering = offering_result.scalar_one_or_none()
        if offering:
            catalog_result = await db.execute(
                select(CourseCatalog).where(
                    CourseCatalog.id == offering.catalog_id,
                    CourseCatalog.is_deleted == False,
                )
            )
            catalog = catalog_result.scalar_one_or_none()
            if catalog and catalog.kg_host_course_id:
                kg = await get_active_knowledge_graph(db, catalog.kg_host_course_id)
    payload["kg_context"] = {
        "nodes": kg.nodes if kg and isinstance(kg.nodes, list) else [],
        "node_progress": node_progress,
    }

    activity_result = await db.execute(
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

    # learning_progress (简化：按课程资源章节统计)
    chapters_r = await db.execute(
        select(Resource.chapter, func.count(Resource.id))
        .where(resource_scope_clause(course_id, resource_scope.catalog_id), Resource.is_deleted == False)
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
                resource_scope_clause(course_id, resource_scope.catalog_id),
                Resource.type == t,
                Resource.is_deleted == False,
            )
        )
        by_type[t] = c_r.scalar() or 0
    payload["resource_usage"] = {"by_type": by_type}

    return payload


async def _run_evaluation_refresh_background(
    task_id: str,
    user_id: str,
    course_id: str,
    payload: dict,
) -> None:
    """后台异步执行 Agent /evaluation/generate 并写入 Evaluation。

    设计约束：
    - 只接收原始标量 + 预组装 payload，不接收请求级 ORM 实例或 db session。
    - 内部自行创建独立 DB session，Agent 调用、锁、写库、task 更新全部在后台完成。
    - 失败时记录结构化日志 + 落 task failed，不抛异常。
    """
    async with async_session_factory() as db:
        lock_name = f"evaluation_{user_id}_{course_id}"
        lock_acquired = False
        try:
            data = await agent_client.post_json("/agent/v1/evaluation/generate", payload)

            if db.bind.dialect.name == "sqlite":
                locked = 1
            else:
                lock_result = await db.execute(text("SELECT GET_LOCK(:name, 5)"), {"name": lock_name})
                locked = lock_result.scalar()
            if not locked:
                raise RuntimeError(f"GET_LOCK timeout: {lock_name}")
            lock_acquired = True

            try:
                now = datetime.now(timezone.utc)
                node_progress = await build_node_progress_rows(user_id, course_id, db)
                progress_table = data.get("progress_table", _empty_table)
                if not isinstance(progress_table, dict):
                    progress_table = _empty_table
                progress_table = {
                    "columns": progress_table.get("columns") or [],
                    "rows": node_progress,
                }
                old_result = await db.execute(
                    select(Evaluation).where(
                        Evaluation.user_id == user_id,
                        Evaluation.course_id == course_id,
                        Evaluation.is_deleted == False,
                    )
                )
                for old in old_result.scalars().all():
                    old.is_deleted = True

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

                await db.execute(
                    update(AsyncTask)
                    .where(AsyncTask.id == task_id)
                    .values(
                        status="completed",
                        result={"updated_at": now.isoformat()},
                        completed_at=now,
                    )
                )
                await db.flush()
                if db.bind.dialect.name != "sqlite":
                    await db.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": lock_name})
                lock_acquired = False
                await db.commit()
                logger.info(
                    "Evaluation refresh background: completed task_id=%s user_id=%s course_id=%s",
                    task_id, user_id, course_id,
                )
            finally:
                if lock_acquired and db.bind.dialect.name != "sqlite":
                    try:
                        await db.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": lock_name})
                        lock_acquired = False
                    except Exception:
                        logger.warning(
                            "Evaluation refresh background: RELEASE_LOCK failed lock_name=%s", lock_name,
                        )
        except AgentServiceError as e:
            await db.rollback()
            await db.execute(
                update(AsyncTask)
                .where(AsyncTask.id == task_id)
                .values(
                    status="failed",
                    error_code=str(e.agent_code or "agent_error"),
                    error_message=e.message,
                    completed_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()
            logger.error(
                "Evaluation refresh background: AgentServiceError task_id=%s user_id=%s course_id=%s "
                "status=%s agent_code=%s message=%s",
                task_id, user_id, course_id, e.status_code, e.agent_code, e.message,
            )
        except Exception as e:
            await db.rollback()
            error_msg = str(e)[:500]
            is_lock_timeout = "GET_LOCK timeout" in str(e)
            await db.execute(
                update(AsyncTask)
                .where(AsyncTask.id == task_id)
                .values(
                    status="failed",
                    error_code="lock_timeout" if is_lock_timeout else "internal_error",
                    error_message=error_msg,
                    completed_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()
            logger.error(
                "Evaluation refresh background: unexpected error task_id=%s user_id=%s course_id=%s "
                "type=%s message=%s",
                task_id, user_id, course_id, type(e).__name__, error_msg,
            )


@router.post("/refresh")
async def refresh_evaluation(
    req: RefreshRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """请求刷新学习效果评估（真异步）。

    请求内：权限校验 → payload 组装 → 创建 AsyncTask → commit → 返回 202。
    后台 _run_evaluation_refresh_background：Agent 调用 → 锁 → 写库 → task 完成/失败。
    """
    course_id = req.course_id
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

    existing_task = await _get_processing_refresh_task(db, "evaluation_refresh", current_user.id, course_id)
    if existing_task:
        return JSONResponse(
            status_code=202,
            content={"code": 202, "message": "accepted", "data": {"task_id": existing_task.id}},
        )

    # 组装 payload（需要 DB，在请求内完成）
    payload = await _assemble_evaluation_payload(current_user.id, course_id, db)

    # 创建任务并立即提交
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

    # 后台异步执行 Agent 调用 + 写库
    asyncio.create_task(_run_evaluation_refresh_background(
        task_id=task.id,
        user_id=current_user.id,
        course_id=course_id,
        payload=payload,
    ))

    return JSONResponse(
        status_code=202,
        content={"code": 202, "message": "accepted", "data": {"task_id": task.id}},
    )
