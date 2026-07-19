from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.learning_path_service import (
    LearningPathService,
)
from app.services.node_resource_service import NodeResourceService

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


@router.get("/nodes/{node_id}/resources")
async def get_node_resources(
    node_id: str,
    course_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await NodeResourceService(db).get_node_resources(current_user, course_id, node_id)
    return {
        "code": 200,
        "message": "success",
        "data": data,
    }
