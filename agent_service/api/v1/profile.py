from fastapi import APIRouter

from agent_service.agents.profile import generate_profile_data, generate_profile_with_llm
from agent_service.core.ai import get_ai_providers
from agent_service.schemas.profile import ProfileGenerateRequest, ProfileGenerateResponse


router = APIRouter(prefix="/profile")


@router.post("/generate", response_model=ProfileGenerateResponse, tags=["Profile"], summary="生成/刷新用户画像")
async def generate_profile(request: ProfileGenerateRequest) -> ProfileGenerateResponse:
    rule_result = generate_profile_data(request)
    providers = get_ai_providers()
    enriched = await generate_profile_with_llm(request, rule_result, getattr(providers, "chat", None))
    return ProfileGenerateResponse(code=200, message="success", data=enriched or rule_result)
