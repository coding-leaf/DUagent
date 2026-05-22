from fastapi import APIRouter

from agent_service.agents.profile import generate_profile_data
from agent_service.schemas.profile import ProfileData, ProfileGenerateRequest, ProfileGenerateResponse


router = APIRouter(prefix="/profile")


@router.post("/generate", response_model=ProfileGenerateResponse, tags=["Profile"], summary="生成/刷新用户画像")
async def generate_profile(request: ProfileGenerateRequest) -> ProfileGenerateResponse:
    return ProfileGenerateResponse(
        code=200,
        message="success",
        data=generate_profile_data(request),
    )
