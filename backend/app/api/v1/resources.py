from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_role
from app.core.config import settings
from app.models.others import AsyncTask, Resource
from app.models.course import Course, CourseEnrollment
from app.models.user import User
from app.schemas.operations import ResourceGenerateRequest
from app.services.agent_client import AgentServiceError, agent_client
from app.services.course_catalog_gate import resolve_generation_catalog

router = APIRouter(prefix="/api/v1/resources", tags=["resources"])


@router.get("")
async def list_resources(
    course_id: str = Query(...),
    type: str = Query(None),
    keyword: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Resource).where(Resource.course_id == course_id, Resource.is_deleted == False)
    if type:
        query = query.where(Resource.type == type)
    if keyword:
        query = query.where(Resource.title.contains(keyword))

    count_r = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_r.scalar() or 0

    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(Resource.create_time.desc()).offset(offset).limit(page_size)
    )
    resources = result.scalars().all()

    return {
        "code": 200,
        "message": "success",
        "data": {
            "resources": [
                {
                    "id": r.id, "title": r.title, "type": r.type,
                    "description": r.description or "", "tags": r.tags or [],
                    "chapter": r.chapter, "knowledge_point": r.knowledge_point,
                    "view_count": r.view_count,
                    "created_at": r.create_time.isoformat() if r.create_time else "",
                }
                for r in resources
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }


@router.get("/{id}")
async def get_resource_detail(
    id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Resource).where(Resource.id == id, Resource.is_deleted == False)
    )
    resource = result.scalar_one_or_none()
    if resource is None:
        raise HTTPException(status_code=404, detail="Resource not found")

    # 校验当前用户是否有该资源所属课程的访问权限
    course_r = await db.execute(
        select(Course).where(Course.id == resource.course_id, Course.is_deleted == False)
    )
    course = course_r.scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=404, detail="Resource not found")

    if course.teacher_id != current_user.id:
        enrollment_r = await db.execute(
            select(CourseEnrollment).where(
                CourseEnrollment.course_id == course.id,
                CourseEnrollment.student_id == current_user.id,
                CourseEnrollment.is_deleted == False,
            )
        )
        if enrollment_r.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="No access to this course")

    preview = None
    if resource.type in ("document", "reading") and resource.content:
        preview = resource.content[:500]

    return {
        "code": 200,
        "message": "success",
        "data": {
            "id": resource.id,
            "title": resource.title,
            "type": resource.type,
            "description": resource.description or "",
            "tags": resource.tags or [],
            "chapter": resource.chapter,
            "knowledge_point": resource.knowledge_point,
            "view_count": resource.view_count,
            "created_at": resource.create_time.isoformat() if resource.create_time else "",
            "content_preview": preview,
            "content": resource.content,
        },
    }


def _webhook_url(request: Request) -> str:
    """构造 Backend webhook 回调地址。"""
    base = str(request.base_url).rstrip("/")
    return f"{base}/api/v1/webhooks/agent"


@router.post("/generate")
async def generate_resources(
    req: ResourceGenerateRequest,
    request: Request,
    current_user: User = Depends(require_role("teacher")),
    db: AsyncSession = Depends(get_db),
):
    """触发资源生成。创建任务后调用 Agent /resources/generate，Agent 完成后通过 Webhook 回调落库。"""
    catalog_context = await resolve_generation_catalog(db, req.course_id)

    # 创建任务
    task = AsyncTask(
        task_type="resource_generation",
        status="processing",
        user_id=current_user.id,
        course_id=req.course_id,
        result=catalog_context.model_dump(),
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)

    # 组装 Agent payload — task_id 由 Backend 生成并原样传入
    payload: dict = {
        "task_id": task.id,
        "user_id": current_user.id,
        "course_id": catalog_context.catalog_id,
        "webhook_url": _webhook_url(request),
    }
    if req.chapter:
        payload["chapter"] = req.chapter
    if req.knowledge_point:
        payload["knowledge_point"] = req.knowledge_point
    if req.resource_types:
        payload["resource_types"] = req.resource_types

    try:
        # 调用 Agent（异步，立即返回 202）
        await agent_client.post_json("/agent/v1/resources/generate", payload)
    except AgentServiceError as e:
        task.status = "failed"
        task.error_code = str(e.agent_code or "agent_error")
        task.error_message = e.message
        task.completed_at = datetime.now(timezone.utc)
        await db.commit()
        return JSONResponse(
            status_code=202,
            content={"code": 202, "message": "accepted", "data": {"task_id": task.id}},
        )

    await db.flush()

    return JSONResponse(
        status_code=202,
        content={"code": 202, "message": "accepted", "data": {"task_id": task.id}},
    )
