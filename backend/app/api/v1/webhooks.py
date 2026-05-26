from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.others import AsyncTask
from app.schemas.webhook import AgentWebhookRequest

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


@router.post("/agent")
async def agent_webhook(
    req: AgentWebhookRequest,
    db: AsyncSession = Depends(get_db),
):
    """v1: No extra auth — deploy on internal network only."""
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

    # Idempotency: skip if already completed
    if task.status == "completed":
        return {"code": 200, "message": "success", "data": {}}

    task.status = req.status
    if req.status == "completed":
        task.result = req.result
        task.progress = 100
        task.completed_at = datetime.now(timezone.utc)
    elif req.status == "failed":
        task.error_message = req.error_message or ""
        task.completed_at = datetime.now(timezone.utc)
    await db.flush()

    return {"code": 200, "message": "success", "data": {}}
