from fastapi import APIRouter

from agent_service.agents.learning_path import (
    generate_learning_path_data,
    generate_learning_path_with_llm,
)
from agent_service.core.ai import get_ai_providers
from agent_service.schemas.learning_path import (
    LearningPathGenerateRequest,
    LearningPathGenerateResponse,
)


router = APIRouter(prefix="/learning-path")


@router.post("/generate", response_model=LearningPathGenerateResponse, tags=["LearningPath"], summary="生成学习路径")
async def generate_learning_path(request: LearningPathGenerateRequest) -> LearningPathGenerateResponse:
    providers = get_ai_providers()
    data = await generate_learning_path_with_llm(request, getattr(providers, "chat", None))
    if data is None:
        data = generate_learning_path_data(request)
    return LearningPathGenerateResponse(code=200, message="success", data=data)
