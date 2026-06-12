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
from app.models.others import AsyncTask, Evaluation, LearningPath, Resource, UserProfile
from app.models.quiz import QuizQuestion
from app.models.user import User
from app.services.agent_client import AgentServiceError, agent_client
from app.services.course_knowledge_graphs import get_active_knowledge_graph
from app.services.resource_scope import ensure_course_resource_access, resolve_course_resource_scope, resource_scope_clause
from app.schemas.ai_features import RefreshRequest

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


def _topo_sort_kg_nodes(
    nodes: list[dict],
    edges: list[dict],
) -> list[dict]:
    """Kahn topological sort of KG nodes based on edges.

    Returns nodes ordered so that prerequisites come before dependents.
    Falls back to original array order if edges is empty.
    """
    if not nodes:
        return []
    if not edges:
        return list(nodes)

    node_ids = {n["id"] for n in nodes}
    in_degree: dict[str, int] = {n["id"]: 0 for n in nodes}
    adj: dict[str, list[str]] = {n["id"]: [] for n in nodes}

    for edge in edges:
        from_id = edge.get("from", "")
        to_id = edge.get("to", "")
        if from_id in node_ids and to_id in node_ids:
            adj[from_id].append(to_id)
            in_degree[to_id] = in_degree.get(to_id, 0) + 1

    # Start with nodes that have zero in-degree, in original array order
    queue = [n["id"] for n in nodes if in_degree.get(n["id"], 0) == 0]
    sorted_ids: list[str] = []
    while queue:
        node_id = queue.pop(0)
        sorted_ids.append(node_id)
        for neighbor in adj.get(node_id, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # Append any remaining nodes not reached (cycles or missing edge refs)
    sorted_set = set(sorted_ids)
    for n in nodes:
        if n["id"] not in sorted_set:
            sorted_ids.append(n["id"])

    # Map back to node dicts preserving all fields
    node_map = {n["id"]: dict(n) for n in nodes}
    return [node_map[nid] for nid in sorted_ids if nid in node_map]


async def _synthesize_kg_fallback_path(
    db: AsyncSession,
    course_id: str,
) -> dict | None:
    """从 active KG 合成学习路径骨架。

    查找链: CourseOffering(id=course_id) → catalog_id →
            CourseCatalog → kg_host_course_id → active KG.
    返回 KG 节点（拓扑排序）+ 边，全部 status="recommended"。
    如果任一环节查不到，返回 None。
    """
    # 1. CourseOffering → catalog_id
    offering_result = await db.execute(
        select(CourseOffering).where(
            CourseOffering.id == course_id,
            CourseOffering.is_deleted == False,
        )
    )
    offering = offering_result.scalar_one_or_none()
    if offering is None:
        return None

    # 2. CourseCatalog → kg_host_course_id
    catalog_result = await db.execute(
        select(CourseCatalog).where(
            CourseCatalog.id == offering.catalog_id,
            CourseCatalog.is_deleted == False,
        )
    )
    catalog = catalog_result.scalar_one_or_none()
    if catalog is None or not catalog.kg_host_course_id:
        return None

    # 3. Active KG
    kg = await get_active_knowledge_graph(db, catalog.kg_host_course_id)
    if kg is None:
        return None

    kg_nodes = kg.nodes if isinstance(kg.nodes, list) else []
    if not kg_nodes:
        return None

    kg_edges = kg.edges if isinstance(kg.edges, list) else []

    # 4. Topo sort
    sorted_nodes = _topo_sort_kg_nodes(kg_nodes, kg_edges)

    # 5. Assemble nodes with status/mastery/order
    assembled_nodes = []
    for idx, node in enumerate(sorted_nodes):
        assembled_nodes.append({
            "id": node.get("id", ""),
            "name": node.get("name", ""),
            "chapter": node.get("chapter", ""),
            "order": idx + 1,
            "status": "recommended",
            "mastery": 0,
        })

    first_node = assembled_nodes[0]

    return {
        "course_id": course_id,
        "nodes": assembled_nodes,
        "edges": kg_edges,
        "current_position": {
            "node_id": first_node["id"],
            "node_name": first_node["name"],
        },
        "source": "kg_fallback",
        "generated_at": kg.create_time.isoformat() if kg.create_time else None,
    }


@router.get("")
async def get_learning_path(
    course_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 永远读最新一条（幂等写入可能遗留多行在软删窗口期）
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

    if lp is None:
        fallback = await _synthesize_kg_fallback_path(db, course_id)
        if fallback is not None:
            return {"code": 200, "message": "success", "data": fallback}
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

    return {
        "code": 200,
        "message": "success",
        "data": {
            "course_id": lp.course_id,
            "nodes": lp.nodes or [],
            "edges": lp.edges or [],
            "current_position": {
                "node_id": lp.current_node_id,
                "node_name": lp.current_node_name,
            } if lp.current_node_id else None,
            "source": "learning_path",
            "generated_at": lp.generated_at.isoformat() if lp.generated_at else None,
        },
    }


async def _assemble_learning_path_payload(
    user_id: str, course_id: str, db: AsyncSession,
) -> dict:
    """组装调用 Agent /learning-path/generate 所需的 payload。"""
    payload: dict = {"user_id": user_id, "course_id": course_id}

    # evaluation: 最近一次评估
    ev_r = await db.execute(
        select(Evaluation)
        .where(Evaluation.user_id == user_id, Evaluation.course_id == course_id, Evaluation.is_deleted == False)
        .order_by(Evaluation.generated_at.desc())
    )
    ev = ev_r.scalars().first()
    payload["evaluation"] = {
        "progress_table": ev.progress_table,
        "mastery_table": ev.mastery_table,
        "summary_text": ev.summary_text,
    } if ev else {}

    # profile: 最近画像
    pf_r = await db.execute(
        select(UserProfile)
        .where(UserProfile.user_id == user_id, UserProfile.course_id == course_id, UserProfile.is_deleted == False)
        .order_by(UserProfile.generated_at.desc())
    )
    pf = pf_r.scalars().first()
    payload["profile"] = {
        "modal_preference": pf.modal_preference,
        "guidance_level": pf.guidance_level_current,
        "knowledge_coordinates": pf.knowledge_coordinates,
    } if pf else {}

    # knowledge_graph: 课程静态知识图谱
    kg = await get_active_knowledge_graph(db, course_id)
    if kg:
        payload["knowledge_graph"] = {"nodes": kg.nodes or [], "edges": kg.edges or []}
    else:
        payload["knowledge_graph"] = {"nodes": [], "edges": []}

    return payload


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
    payload = await _assemble_learning_path_payload(current_user.id, course_id, db)

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

    # 1. 查找用户在该课程的最新学习路径
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
                node_name = node.get("name", node_id)
                break

    # 2. 从知识图谱获取 chapter（schema 约定 [{id, name, chapter}]）
    kg = await get_active_knowledge_graph(db, course_id)
    if kg and kg.nodes:
        kg_nodes = kg.nodes if isinstance(kg.nodes, list) else []
        for kg_node in kg_nodes:
            if isinstance(kg_node, dict) and kg_node.get("id") == node_id:
                chapter = kg_node.get("chapter", "")
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
