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
from app.models.others import AsyncTask, CourseKnowledgeGraph, Evaluation, Resource
from app.models.quiz import QuizAnswer, QuizQuestion, QuizSession
from app.models.user import User
from app.services.agent_client import AgentServiceError, agent_client
from app.services.course_knowledge_graphs import get_active_knowledge_graph
from app.services.resource_scope import resolve_course_resource_scope, resource_scope_clause
from app.schemas.ai_features import RefreshRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/evaluation", tags=["evaluation"])

_empty_table = {"columns": [], "rows": []}


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


def _looks_like_node_progress(rows: object) -> bool:
    return (
        isinstance(rows, list)
        and bool(rows)
        and all(isinstance(row, dict) and row.get("node_id") and row.get("node_name") for row in rows)
    )


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

        if score is not None:
            assessment_state = "scored"
            status_text = "已掌握" if score >= 75 else "已练习"
            mastery_label = _mastery_label(score)
        elif question_count > 0:
            assessment_state = "pending_practice"
            status_text = "待练习"
            mastery_label = "待练习"
        else:
            assessment_state = "unassessed_default_pass"
            status_text = "未测评/默认通过"
            mastery_label = "未测评/默认通过"

        duration = int(attempt_stats["duration"]) if attempt_stats and attempt_stats["duration"] else None
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
                "resource_visit_count": None,
                "last_activity_at": None,
            }
        )
    return rows


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


@router.get("")
async def get_evaluation(
    course_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    node_progress = await _build_node_progress_rows(current_user.id, course_id, db)
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
            "node_progress": (
                stored_node_progress
                if _looks_like_node_progress(stored_node_progress)
                else node_progress
            ),
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
        try:
            data = await agent_client.post_json("/agent/v1/evaluation/generate", payload)

            lock_name = f"evaluation_{user_id}_{course_id}"
            if db.bind.dialect.name == "sqlite":
                locked = 1
            else:
                lock_result = await db.execute(text("SELECT GET_LOCK(:name, 5)"), {"name": lock_name})
                locked = lock_result.scalar()
            if not locked:
                raise RuntimeError(f"GET_LOCK timeout: {lock_name}")

            try:
                now = datetime.now(timezone.utc)
                node_progress = await _build_node_progress_rows(user_id, course_id, db)
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
                await db.commit()
                logger.info(
                    "Evaluation refresh background: completed task_id=%s user_id=%s course_id=%s",
                    task_id, user_id, course_id,
                )
            finally:
                try:
                    if db.bind.dialect.name != "sqlite":
                        await db.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": lock_name})
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
