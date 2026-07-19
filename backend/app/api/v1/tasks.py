from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.others import AsyncTask
from app.models.user import User

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


@router.get("/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AsyncTask).where(
            AsyncTask.id == task_id,
            AsyncTask.is_deleted == False,
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40400, "message": "任务不存在", "data": None},
        )

    # Permission: user owns the task, or role-specific shared task type is allowed.
    if task.user_id and task.user_id != current_user.id:
        allowed_admin_task = current_user.role == "admin" and task.task_type in {
            "course_catalog_ingestion",
            "kg_generation",
            "resource_generation",
        }
        if not allowed_admin_task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": 40400, "message": "任务不存在", "data": None},
            )

    return {
        "code": 200,
        "message": "success",
        "data": {
            "task_id": task.id,
            "task_type": task.task_type,
            "status": task.status,
            "progress": task.progress,
            "result": task.result,
            "error_code": task.error_code,
            "error_message": task.error_message,
            "created_at": task.create_time.isoformat() if task.create_time else "",
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        },
    }
