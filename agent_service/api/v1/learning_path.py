from fastapi import APIRouter

from agent_service.agents.learning_path import generate_learning_path_data
from agent_service.schemas.learning_path import (
    LearningPathGenerateRequest,
    LearningPathGenerateResponse,
)


router = APIRouter(prefix="/learning-path")


@router.post("/generate", response_model=LearningPathGenerateResponse, tags=["LearningPath"], summary="生成学习路径")
async def generate_learning_path(request: LearningPathGenerateRequest) -> LearningPathGenerateResponse:
    return LearningPathGenerateResponse(code=200, message="success", data=generate_learning_path_data(request))
