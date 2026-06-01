import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.others import AsyncTask, Resource
from app.schemas.webhook import AgentWebhookRequest

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


@router.post("/agent")
async def agent_webhook(
    req: AgentWebhookRequest,
    db: AsyncSession = Depends(get_db),
):
    """Agent 异步任务回调入口。v1 无额外鉴权，部署时通过内网限制访问。

    处理规则：
    - 校验 task_id 存在且 task_type 一致。
    - resource_generation 完成时校验 result.resources 并写入 resources 表。
    - 幂等：已完成任务再次收到 completed 直接返回 success，不重复插入业务数据。
    """
    result = await db.execute(
        select(AsyncTask).where(
            AsyncTask.id == req.task_id,
            AsyncTask.is_deleted == False,
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40400, "message": "任务不存在", "data": None},
        )

    # Validate task_type consistency
    if req.task_type and task.task_type and req.task_type != task.task_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 40001, "message": "task_type 与本地任务类型不一致", "data": None},
        )

    # Idempotency: skip if already completed
    if task.status == "completed":
        return {"code": 200, "message": "success", "data": {}}

    if req.status == "completed":
        # --- resource_generation: write result.resources to SQL ---
        if task.task_type == "resource_generation" and req.result:
            resources_data = req.result.get("resources", [])
            for r in resources_data:
                resource = Resource(
                    id=uuid.uuid4().hex[:16],
                    course_id=task.course_id or "",
                    title=r.get("title", ""),
                    type=r.get("type", "document"),
                    description=r.get("description", ""),
                    tags=r.get("tags", []),
                    chapter=r.get("chapter", ""),
                    knowledge_point=r.get("knowledge_point", ""),
                    content=r.get("content", ""),
                    url="",
                )
                db.add(resource)

        task.result = req.result
        task.progress = 100
        task.completed_at = datetime.now(timezone.utc)
    elif req.status == "failed":
        task.error_message = req.error_message or ""
        task.completed_at = datetime.now(timezone.utc)
    await db.flush()

    return {"code": 200, "message": "success", "data": {}}
