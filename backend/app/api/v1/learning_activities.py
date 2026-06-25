from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.learning_activity import LearningActivityCreate
from app.services import learning_activity_service

router = APIRouter(prefix="/api/v1/learning-activities", tags=["learning-activities"])


@router.post("")
async def create_learning_activity(
    req: LearningActivityCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await learning_activity_service.check_access(db, current_user, req)
    learning_activity_service.validate_activity_fields(req)
    activity_id = await learning_activity_service.create_activity(db, current_user, req)
    return {"code": 200, "message": "success", "data": {"id": activity_id}}
