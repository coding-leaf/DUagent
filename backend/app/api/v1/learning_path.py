import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.course import CourseEnrollment
from app.models.catalog import CourseCatalog, CourseOffering
from app.models.others import LearningPath, Resource
from app.models.quiz import QuizQuestion
from app.models.user import User
from app.services.course_knowledge_graphs import get_active_knowledge_graph
from app.services.resource_scope import ensure_course_resource_access, resolve_course_resource_scope, resource_scope_clause
from app.schemas.ai_features import RefreshRequest
from app.services.learning_path_refresh_service import (
    LearningPathRefreshService,
    run_learning_path_refresh_background,
)
from app.services.learning_path_service import (
    LearningPathService,
)

router = APIRouter(prefix="/api/v1/learning-path", tags=["learning-path"])


@router.get("")
async def get_learning_path(
    course_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await LearningPathService(db).get_learning_path(current_user.id, course_id)
    return {
        "code": 200,
        "message": "success",
        "data": data,
    }


@router.post("/refresh")
async def refresh_learning_path(
    req: RefreshRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """请求刷新学习路径（真异步）。

    请求内：权限校验 → payload 组装 → 创建 AsyncTask → commit → 返回 202。
    后台 run_learning_path_refresh_background：Agent 调用 → 锁 → 写库 → task 完成/失败。
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

    refresh_service = LearningPathRefreshService(db)
    payload = await refresh_service.assemble_payload(current_user.id, course_id)
    task = await refresh_service.create_refresh_task(current_user.id, course_id)
    # commit point: task persisted before background dispatch
    await db.commit()

    # 后台异步执行 Agent 调用 + 写库
    asyncio.create_task(run_learning_path_refresh_background(
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
