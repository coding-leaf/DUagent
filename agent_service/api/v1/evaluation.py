from fastapi import APIRouter

from agent_service.agents.evaluation import generate_evaluation_data, generate_evaluation_with_llm
from agent_service.core.ai import get_ai_providers
from agent_service.schemas.evaluation import EvaluationGenerateRequest, EvaluationGenerateResponse


router = APIRouter(prefix="/evaluation")


@router.post("/generate", response_model=EvaluationGenerateResponse, tags=["Evaluation"], summary="生成学习效果评估")
async def generate_evaluation(request: EvaluationGenerateRequest) -> EvaluationGenerateResponse:
    rule_result = generate_evaluation_data(request)
    providers = get_ai_providers()
    enriched = await generate_evaluation_with_llm(request, rule_result, getattr(providers, "chat", None))
    return EvaluationGenerateResponse(code=200, message="success", data=enriched or rule_result)
