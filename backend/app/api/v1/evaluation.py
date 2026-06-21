import logging
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.ai_features import RefreshRequest
from app.services.evaluation_service import EvaluationService

# Keep legacy mock target valid
from app.services.agent_client import agent_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/evaluation", tags=["evaluation"])


@router.get("")
async def get_evaluation(
    course_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = EvaluationService(db)
    data = await service.get_evaluation(current_user.id, course_id)
    return {
        "code": 200,
        "message": "success",
        "data": data,
    }


@router.post("/refresh")
async def refresh_evaluation(
    req: RefreshRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = EvaluationService(db)
    data = await service.refresh_evaluation(current_user, req.course_id)
    return JSONResponse(
        status_code=202,
        content={"code": 202, "message": "accepted", "data": data},
    )
