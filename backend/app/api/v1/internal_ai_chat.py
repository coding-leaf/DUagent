from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings
from app.schemas.internal_ai_chat import LearningProgressRequest, RecentAnswersRequest
from app.services.ai_chat_learning_context import (
    build_learning_progress_overview,
    query_recent_answers,
)

router = APIRouter(prefix="/internal/ai-chat", tags=["internal-ai-chat"])


def verify_internal_agent_token(
    x_internal_agent_token: str | None = Header(default=None, alias="X-Internal-Agent-Token"),
) -> None:
    expected = settings.INTERNAL_AGENT_TOKEN
    if not expected or x_internal_agent_token != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": 40300, "message": "internal agent token invalid", "data": None},
        )


@router.post("/learning-progress")
async def read_learning_progress(
    req: LearningProgressRequest,
    _auth: None = Depends(verify_internal_agent_token),
    db: AsyncSession = Depends(get_db),
):
    data = await build_learning_progress_overview(
        db,
        user_id=req.user_id,
        course_id=req.course_id,
        limit_nodes=req.limit_nodes,
    )
    return {"code": 200, "message": "success", "data": data}


@router.post("/recent-answers")
async def read_recent_answers(
    req: RecentAnswersRequest,
    _auth: None = Depends(verify_internal_agent_token),
    db: AsyncSession = Depends(get_db),
):
    data = await query_recent_answers(
        db,
        user_id=req.user_id,
        course_id=req.course_id,
        node_id=req.node_id,
        knowledge_point=req.knowledge_point,
        limit=req.limit,
        only_wrong=req.only_wrong,
    )
    return {"code": 200, "message": "success", "data": data}
