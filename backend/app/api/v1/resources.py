from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_role
from app.models.user import User
from app.schemas.operations import ResourceGenerateRequest
from app.services.resource_service import ResourceService

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
    service = ResourceService(db)
    resources, total = await service.list_resources(
        course_id=course_id,
        current_user=current_user,
        type=type,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )

    return {
        "code": 200,
        "message": "success",
        "data": {
            "resources": [
                {
                    "id": r.id,
                    "title": r.title,
                    "type": r.type,
                    "description": r.description or "",
                    "tags": r.tags or [],
                    "chapter": r.chapter,
                    "knowledge_point": r.knowledge_point,
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
    service = ResourceService(db)
    resource, preview = await service.get_resource_detail(id, current_user)

    return {
        "code": 200,
        "message": "success",
        "data": {
            "id": resource.id,
            "course_id": resource.course_id,
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
    service = ResourceService(db)
    task = await service.generate_resources(
        req=req,
        current_user=current_user,
        webhook_url=_webhook_url(request),
    )

    return JSONResponse(
        status_code=202,
        content={"code": 202, "message": "accepted", "data": {"task_id": task.id}},
    )
