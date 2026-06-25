from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.others import CourseKnowledgeGraph, LearningActivity, Resource
from app.models.user import User
from app.schemas.learning_activity import LearningActivityCreate
from app.services.course_knowledge_graphs import get_active_knowledge_graph
from app.services.resource_scope import (
    ensure_course_resource_access,
    resolve_course_resource_scope,
    resource_scope_clause,
    user_can_access_catalog_resources,
)

_DURATION_REQUIRED = {"resource_study", "node_practice_submit"}
_DURATION_FORBIDDEN = {"resource_view", "node_view", "node_practice_start"}
_RESOURCE_REQUIRED = {"resource_view", "resource_study"}
_NODE_REQUIRED = {"node_view", "node_practice_start", "node_practice_submit"}


def _validation_error(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={"code": 42200, "message": message, "data": None},
    )


async def _resolve_resource_catalog_id(
    db: AsyncSession,
    resource_id: str | None,
) -> str | None:
    if not resource_id:
        return None
    result = await db.execute(
        select(Resource.catalog_id).where(
            Resource.id == resource_id,
            Resource.is_deleted == False,
        )
    )
    row = result.first()
    return row[0] if row and row[0] else None


async def _resolve_node_name(
    db: AsyncSession,
    course_id: str,
    node_id: str | None,
    fallback: str | None,
) -> str | None:
    if fallback or not node_id:
        return fallback
    kg: CourseKnowledgeGraph | None = await get_active_knowledge_graph(db, course_id)
    nodes = kg.nodes if kg and isinstance(kg.nodes, list) else []
    for node in nodes:
        if isinstance(node, dict) and str(node.get("id") or node.get("node_id") or "") == node_id:
            name = str(node.get("name") or "").strip()
            return name or fallback
    return fallback


async def _ensure_resource_in_course_scope(
    db: AsyncSession,
    course_id: str,
    resource_id: str | None,
) -> None:
    if not resource_id:
        return
    scope = await resolve_course_resource_scope(db, course_id)
    result = await db.execute(
        select(Resource.id).where(
            Resource.id == resource_id,
            resource_scope_clause(course_id, scope.catalog_id),
            Resource.is_deleted == False,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40400, "message": "资源不存在或不属于该课程", "data": None},
        )


async def check_access(
    db: AsyncSession,
    current_user: User,
    req: LearningActivityCreate,
) -> None:
    """验证用户是否有权限记录该课程的学习活动。"""
    scope = await resolve_course_resource_scope(db, req.course_id)
    if scope.catalog_id:
        if not await user_can_access_catalog_resources(db, current_user, scope.catalog_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": 40300, "message": "无权访问该课程", "data": None},
            )
    elif req.resource_id:
        catalog_id = await _resolve_resource_catalog_id(db, req.resource_id)
        if catalog_id:
            if not await user_can_access_catalog_resources(db, current_user, catalog_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"code": 40300, "message": "无权访问该课程", "data": None},
                )
        else:
            await ensure_course_resource_access(db, current_user, req.course_id)
    else:
        await ensure_course_resource_access(db, current_user, req.course_id)


def validate_activity_fields(req: LearningActivityCreate) -> None:
    """校验学习活动字段组合是否合法。"""
    if req.activity_type in _DURATION_REQUIRED and req.duration_seconds is None:
        raise _validation_error("该学习行为需要 duration_seconds")
    if req.activity_type in _DURATION_FORBIDDEN and req.duration_seconds is not None:
        raise _validation_error("该学习行为不应包含 duration_seconds")
    if req.activity_type in _RESOURCE_REQUIRED and not req.resource_id:
        raise _validation_error("该学习行为需要 resource_id")
    if req.activity_type in _NODE_REQUIRED and not req.node_id:
        raise _validation_error("该学习行为需要 node_id")
    if req.activity_type == "node_practice_submit" and not req.quiz_id:
        raise _validation_error("节点练习提交需要 quiz_id")


async def create_activity(
    db: AsyncSession,
    current_user: User,
    req: LearningActivityCreate,
) -> str:
    """创建学习活动记录，返回记录 id。"""
    await _ensure_resource_in_course_scope(db, req.course_id, req.resource_id)

    metadata = dict(req.metadata or {})
    if req.quiz_id:
        metadata["quiz_id"] = req.quiz_id

    activity = LearningActivity(
        user_id=current_user.id,
        course_id=req.course_id,
        node_id=req.node_id,
        node_name=await _resolve_node_name(db, req.course_id, req.node_id, req.node_name),
        resource_id=req.resource_id,
        activity_type=req.activity_type,
        duration_seconds=req.duration_seconds,
        occurred_at=req.occurred_at or datetime.now(timezone.utc),
        metadata_json=metadata or None,
        create_by=current_user.id,
        update_by=current_user.id,
    )
    db.add(activity)
    await db.flush()
    await db.refresh(activity)
    return activity.id
