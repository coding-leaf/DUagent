import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.db.session import async_session_factory
from app.models.course import CourseEnrollment
from app.models.catalog import CourseCatalog, CourseOffering
from app.models.others import AsyncTask, LearningPath, Resource
from app.models.quiz import QuizQuestion
from app.models.user import User
from app.services.agent_client import AgentServiceError, agent_client
from app.services.course_knowledge_graphs import get_active_knowledge_graph
from app.services.resource_scope import ensure_course_resource_access, resolve_course_resource_scope, resource_scope_clause
from app.schemas.ai_features import RefreshRequest
from app.services.knowledge_progress import build_node_progress_rows
from app.services.learning_path_service import (
    apply_progress_to_nodes,
    assemble_learning_path_payload,
    build_current_position_from_nodes,
    synthesize_kg_fallback_path,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/learning-path", tags=["learning-path"])


async def _acquire_learning_path_lock(db: AsyncSession, user_id: str, course_id: str) -> str:
    """Acquire a MySQL named lock for serializing learning-path writes."""
    lock_name = f"learningpath_{user_id}_{course_id}"
    if db.bind.dialect.name == "sqlite":
        return lock_name
    lock_result = await db.execute(text("SELECT GET_LOCK(:name, 5)"), {"name": lock_name})
    if not lock_result.scalar():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": 50300, "message": "服务繁忙，请稍后重试", "data": None},
        )
    return lock_name


async def _release_learning_path_lock(db: AsyncSession, lock_name: str) -> None:
    """Release a previously acquired MySQL named lock for learning-path writes."""
    if db.bind.dialect.name == "sqlite":
        return
    await db.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": lock_name})


@router.get("")
async def get_learning_path(
    course_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 1. 实时进度字典（node_id → {assessment_state, mastery_score}）
    progress_rows = await build_node_progress_rows(current_user.id, course_id, db)
    progress_by_id: dict[str, dict] = {
        row["node_id"]: row for row in progress_rows
    }

    # 2. 查最新快照
    result = await db.execute(
        select(LearningPath)
        .where(
            LearningPath.user_id == current_user.id,
            LearningPath.course_id == course_id,
            LearningPath.is_deleted == False,
        )
        .order_by(LearningPath.generated_at.desc())
    )
    lp = result.scalars().first()

    if lp is not None:
        # Merge 模式：用实时状态覆盖快照节点的 status/mastery，其余字段保留
        merged_nodes = apply_progress_to_nodes(lp.nodes or [], progress_by_id)
        # merged_nodes 为空时快照中的 current_node_id 可能指向不存在节点，返回 None
        if merged_nodes and lp.current_node_id:
            current_position = {"node_id": lp.current_node_id, "node_name": lp.current_node_name}
        else:
            current_position = None
        return {
            "code": 200,
            "message": "success",
            "data": {
                "course_id": lp.course_id,
                "nodes": merged_nodes,
                "edges": lp.edges or [],
                "current_position": current_position,
                "source": "realtime_merged",
                "generated_at": lp.generated_at.isoformat() if lp.generated_at else None,
            },
        }

    # 3. 无快照，尝试 KG 构建模式
    fallback = await synthesize_kg_fallback_path(db, course_id)
    if fallback is not None:
        kg_nodes = apply_progress_to_nodes(fallback["nodes"], progress_by_id)
        current_position = build_current_position_from_nodes(kg_nodes)
        # 显式组装字段，避免 **fallback unpack 导致 current_position 被隐式覆盖
        return {
            "code": 200,
            "message": "success",
            "data": {
                "course_id": fallback["course_id"],
                "nodes": kg_nodes,
                "edges": fallback.get("edges") or [],
                "current_position": current_position,
                "source": "kg_realtime",
                "generated_at": fallback.get("generated_at"),
            },
        }

    # 4. 均无数据
    return {
        "code": 200,
        "message": "success",
        "data": {
            "course_id": course_id,
            "nodes": [],
            "edges": [],
            "current_position": None,
            "source": "kg_fallback",
            "generated_at": None,
        },
    }


async def _run_learning_path_refresh_background(
    task_id: str,
    user_id: str,
    course_id: str,
    payload: dict,
) -> None:
    """后台异步执行 Agent /learning-path/generate 并写入 LearningPath。

    设计约束：
    - 只接收原始标量 + 预组装 payload，不接收请求级 ORM 实例或 db session。
    - 内部自行创建独立 DB session，Agent 调用、锁、写库、task 更新全部在后台完成。
    - 失败时记录结构化日志 + 落 task failed，不抛异常。
    """
    async with async_session_factory() as db:
        try:
            data = await agent_client.post_json("/agent/v1/learning-path/generate", payload)

            lock_name = f"learningpath_{user_id}_{course_id}"
            if db.bind.dialect.name == "sqlite":
                locked = 1
            else:
                lock_result = await db.execute(text("SELECT GET_LOCK(:name, 5)"), {"name": lock_name})
                locked = lock_result.scalar()
            if not locked:
                raise RuntimeError(f"GET_LOCK timeout: {lock_name}")

            try:
                now = datetime.now(timezone.utc)
                old_result = await db.execute(
                    select(LearningPath).where(
                        LearningPath.user_id == user_id,
                        LearningPath.course_id == course_id,
                        LearningPath.is_deleted == False,
                    )
                )
                for old in old_result.scalars().all():
                    old.is_deleted = True

                cp = data.get("current_position") or {}
                lp = LearningPath(
                    user_id=user_id,
                    course_id=course_id,
                    nodes=data.get("nodes", []),
                    edges=data.get("edges", []),
                    current_node_id=cp.get("node_id", ""),
                    current_node_name=cp.get("node_name", ""),
                    generated_at=now,
                )
                db.add(lp)

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
                    "Learning path refresh background: completed task_id=%s user_id=%s course_id=%s",
                    task_id, user_id, course_id,
                )
            finally:
                try:
                    if db.bind.dialect.name != "sqlite":
                        await db.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": lock_name})
                except Exception:
                    logger.warning(
                        "Learning path refresh background: RELEASE_LOCK failed lock_name=%s",
                        lock_name,
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
                "Learning path refresh background: AgentServiceError task_id=%s user_id=%s "
                "course_id=%s status=%s agent_code=%s message=%s",
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
                "Learning path refresh background: unexpected error task_id=%s user_id=%s "
                "course_id=%s type=%s message=%s",
                task_id, user_id, course_id, type(e).__name__, error_msg,
            )


@router.post("/refresh")
async def refresh_learning_path(
    req: RefreshRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """请求刷新学习路径（真异步）。

    请求内：权限校验 → payload 组装 → 创建 AsyncTask → commit → 返回 202。
    后台 _run_learning_path_refresh_background：Agent 调用 → 锁 → 写库 → task 完成/失败。
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
    payload = await assemble_learning_path_payload(current_user.id, course_id, db)

    # 创建任务并立即提交
    task = AsyncTask(
        task_type="learning_path_refresh",
        status="processing",
        user_id=current_user.id,
        course_id=course_id,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)
    await db.commit()

    # 后台异步执行 Agent 调用 + 写库
    asyncio.create_task(_run_learning_path_refresh_background(
        task_id=task.id,
        user_id=current_user.id,
        course_id=course_id,
        payload=payload,
    ))

    return JSONResponse(
        status_code=202,
        content={"code": 202, "message": "accepted", "data": {"task_id": task.id}},
    )


@router.get("/nodes/{node_id}/resources")
async def get_node_resources(
    node_id: str,
    course_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取指定学习路径节点的关联资源。

    从 LearningPath.nodes 中查找节点名称，从 Resource/QuizQuestion 表中
    按 knowledge_point 和 chapter 匹配资源并分组返回。
    """
    await ensure_course_resource_access(db, current_user, course_id)
    resource_scope = await resolve_course_resource_scope(db, course_id)

    node_name = node_id
    chapter = ""

    # 1. 查 KG（通过 CourseOffering → Catalog → kg_host_course_id）
    kg = None
    offering_result = await db.execute(
        select(CourseOffering).where(
            CourseOffering.id == course_id,
            CourseOffering.is_deleted == False,
        )
    )
    offering = offering_result.scalar_one_or_none()
    if offering is not None:
        catalog_result = await db.execute(
            select(CourseCatalog).where(
                CourseCatalog.id == offering.catalog_id,
                CourseCatalog.is_deleted == False,
            )
        )
        catalog = catalog_result.scalar_one_or_none()
        if catalog is not None and catalog.kg_host_course_id:
            kg = await get_active_knowledge_graph(db, catalog.kg_host_course_id)
    if kg is None:
        kg = await get_active_knowledge_graph(db, course_id)

    # 2. 从 KG 获取 node_name 和 chapter
    if kg and kg.nodes:
        kg_nodes = kg.nodes if isinstance(kg.nodes, list) else []
        for kg_node in kg_nodes:
            if isinstance(kg_node, dict) and kg_node.get("id") == node_id:
                node_name = kg_node.get("name", node_id)
                chapter = kg_node.get("chapter", "")
                break

    # 3. 查找用户在该课程的最新 LearningPath（LP 中的 node_name 优先于 KG）
    lp_result = await db.execute(
        select(LearningPath)
        .where(
            LearningPath.user_id == current_user.id,
            LearningPath.course_id == course_id,
            LearningPath.is_deleted == False,
        )
        .order_by(LearningPath.generated_at.desc())
    )
    lp = lp_result.scalars().first()
    if lp and lp.nodes:
        nodes = lp.nodes if isinstance(lp.nodes, list) else []
        for node in nodes:
            if isinstance(node, dict) and node.get("id") == node_id:
                node_name = node.get("name", node_name)
                break

    # 3. weak_point_tutorials: Resource 按 knowledge_point 匹配
    weak_point_tutorials = []
    res_result = await db.execute(
        select(Resource)
        .where(
            resource_scope_clause(course_id, resource_scope.catalog_id),
            Resource.knowledge_point == node_name,
            Resource.is_deleted == False,
        )
    )
    for r in res_result.scalars().all():
        weak_point_tutorials.append({
            "id": r.id,
            "title": r.title,
            "content": (r.content or "")[:160],
        })

    # 4. exercises: QuizQuestion 按 knowledge_point 匹配
    exercises = []
    qq_result = await db.execute(
        select(QuizQuestion)
        .where(
            QuizQuestion.course_id == course_id,
            QuizQuestion.knowledge_point == node_name,
            QuizQuestion.is_deleted == False,
        )
    )
    for q in qq_result.scalars().all():
        exercises.append({
            "id": q.id,
            "type": q.type,
            "content": q.content,
        })

    # 5. chapter_materials: Resource 按 chapter 匹配（依赖 KG 预置数据）
    chapter_materials = []
    if chapter:
        ch_result = await db.execute(
            select(Resource)
            .where(
                resource_scope_clause(course_id, resource_scope.catalog_id),
                Resource.chapter == chapter,
                Resource.is_deleted == False,
            )
        )
        for r in ch_result.scalars().all():
            chapter_materials.append({
                "id": r.id,
                "title": r.title,
                "type": r.type,
                "url": r.url or "",
            })

    # 6. full_exercise_set: 课程全部 QuizQuestion（限 50 条）
    full_exercise_set = []
    all_qq_result = await db.execute(
        select(QuizQuestion)
        .where(
            QuizQuestion.course_id == course_id,
            QuizQuestion.is_deleted == False,
        )
        .limit(50)
    )
    for q in all_qq_result.scalars().all():
        full_exercise_set.append({
            "id": q.id,
            "type": q.type,
            "content": q.content,
        })

    return {
        "code": 200,
        "message": "success",
        "data": {
            "node_id": node_id,
            "node_name": node_name,
            "weak_point_tutorials": weak_point_tutorials,
            "exercises": exercises,
            "chapter_materials": chapter_materials,
            "full_exercise_set": full_exercise_set,
        },
    }
