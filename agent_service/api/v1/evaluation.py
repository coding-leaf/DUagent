from fastapi import APIRouter

from agent_service.agents.evaluation import generate_evaluation_data
from agent_service.schemas.evaluation import EvaluationData, EvaluationGenerateRequest, EvaluationGenerateResponse


router = APIRouter(prefix="/evaluation")


@router.post("/generate", response_model=EvaluationGenerateResponse, tags=["Evaluation"], summary="生成学习效果评估")
async def generate_evaluation(request: EvaluationGenerateRequest) -> EvaluationGenerateResponse:
    return EvaluationGenerateResponse(
        code=200,
        message="success",
        data=generate_evaluation_data(request),
    )
