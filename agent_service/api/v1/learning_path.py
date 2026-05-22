from fastapi import APIRouter

from agent_service.schemas.learning_path import (
    LearningPathData,
    LearningPathGenerateRequest,
    LearningPathGenerateResponse,
)


router = APIRouter(prefix="/learning-path")


@router.post("/generate", response_model=LearningPathGenerateResponse, tags=["LearningPath"], summary="生成学习路径")
async def generate_learning_path(_: LearningPathGenerateRequest) -> LearningPathGenerateResponse:
    return LearningPathGenerateResponse(code=200, message="success", data=LearningPathData())
