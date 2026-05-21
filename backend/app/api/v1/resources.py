from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_role
from app.models.others import AsyncTask, Resource
from app.models.user import User
from app.schemas.operations import ResourceGenerateRequest

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
    query = select(Resource).where(Resource.course_id == course_id)
    if type:
        query = query.where(Resource.type == type)
    if keyword:
        query = query.where(Resource.title.contains(keyword))

    count_r = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_r.scalar() or 0

    offset = (page - 1) * page_size
    result = await db.execute(query.order_by(Resource.created_at.desc()).offset(offset).limit(page_size))
    resources = result.scalars().all()

    return {
        "code": 200,
        "message": "success",
        "data": [
            {
                "id": r.id,
                "title": r.title,
                "type": r.type,
                "description": r.description,
                "tags": r.tags,
                "chapter": r.chapter,
                "view_count": r.view_count,
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in resources
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/generate")
async def generate_resources(
    req: ResourceGenerateRequest,
    current_user: User = Depends(require_role("teacher")),
    db: AsyncSession = Depends(get_db),
):
    task = AsyncTask(
        task_type="resource",
        status="processing",
        user_id=current_user.id,
        course_id=req.course_id,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)

    # Simulate resource generation
    new_resources = [
        Resource(
            course_id=req.course_id,
            title="自动生成的课程讲义",
            type="document",
            description="AI 根据课程大纲生成的讲义文档",
            tags=["AI生成", "讲义"],
            chapter="综合",
            url=f"/files/resources/{req.course_id}/lecture_notes.pdf",
        ),
        Resource(
            course_id=req.course_id,
            title="知识思维导图",
            type="mindmap",
            description="课程知识体系思维导图",
            tags=["AI生成", "思维导图"],
            chapter="综合",
            url=f"/files/resources/{req.course_id}/mindmap.png",
        ),
    ]
    for r in new_resources:
        db.add(r)

    task.status = "completed"
    task.result = {"resources_generated": len(new_resources)}
    task.completed_at = datetime.now(timezone.utc)
    await db.flush()

    return JSONResponse(
        status_code=202,
        content={"code": 200, "message": "success", "data": {"task_id": task.id}},
    )
