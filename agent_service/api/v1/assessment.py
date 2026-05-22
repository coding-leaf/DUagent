from fastapi import APIRouter

from agent_service.agents.assessment import evaluate_assessment_data, generate_questions_data
from agent_service.schemas.assessment import (
    AssessmentEvaluateRequest,
    AssessmentEvaluateResponse,
    QuestionGenerateRequest,
    QuestionGenerateResponse,
)


router = APIRouter(prefix="/assessment")


@router.post("/evaluate", response_model=AssessmentEvaluateResponse, tags=["Assessment"], summary="测验评估")
async def evaluate_assessment(request: AssessmentEvaluateRequest) -> AssessmentEvaluateResponse:
    return AssessmentEvaluateResponse(code=200, message="success", data=evaluate_assessment_data(request))


@router.post(
    "/generate-questions",
    response_model=QuestionGenerateResponse,
    tags=["Assessment"],
    summary="生成题目",
)
async def generate_questions(request: QuestionGenerateRequest) -> QuestionGenerateResponse:
    return QuestionGenerateResponse(code=200, message="success", data=generate_questions_data(request))
