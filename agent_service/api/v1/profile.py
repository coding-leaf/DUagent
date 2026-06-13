from fastapi import APIRouter

from agent_service.agents.profile import generate_profile_data, generate_profile_with_llm
from agent_service.core.ai import get_ai_providers
from agent_service.schemas.profile import (
    ProfileDialogueUpdateData,
    ProfileDialogueUpdateRequest,
    ProfileDialogueUpdateResponse,
    ProfileGenerateRequest,
    ProfileGenerateResponse,
)


router = APIRouter(prefix="/profile")


@router.post("/generate", response_model=ProfileGenerateResponse, tags=["Profile"], summary="生成/刷新用户画像")
async def generate_profile(request: ProfileGenerateRequest) -> ProfileGenerateResponse:
    rule_result = generate_profile_data(request)
    providers = get_ai_providers()
    enriched = await generate_profile_with_llm(request, rule_result, getattr(providers, "chat", None))
    return ProfileGenerateResponse(code=200, message="success", data=enriched or rule_result)


def _extract_dialogue_profile(message: str) -> ProfileDialogueUpdateData:
    text = message.strip()
    weak_points: list[str] = []
    preferred_resources: list[str] = []

    weak_keywords = ["动态内存分配", "指针", "数组", "字符串", "输入输出", "函数", "递归", "结构体"]
    for keyword in weak_keywords:
        if keyword in text:
            weak_points.append(keyword)

    if any(keyword in text for keyword in ["代码", "编程", "实操", "练习"]):
        preferred_resources.append("code_practice")
    if any(keyword in text for keyword in ["图解", "图示", "流程图", "示意图"]):
        preferred_resources.append("chart_logic")
    if any(keyword in text for keyword in ["阅读", "文本", "讲义", "材料"]):
        preferred_resources.append("text_analysis")

    guidance_level = None
    if "少提示" in text or "自己思考" in text:
        guidance_level = "L1"
    elif "分步骤" in text or "逐步" in text:
        guidance_level = "L2"
    elif "直接给答案" in text or "保姆" in text:
        guidance_level = "L3"

    return ProfileDialogueUpdateData(
        learning_goal=text,
        weak_points=list(dict.fromkeys(weak_points)),
        preferred_resources=list(dict.fromkeys(preferred_resources)),
        guidance_level=guidance_level,
    )


@router.post(
    "/dialogue-update",
    response_model=ProfileDialogueUpdateResponse,
    tags=["Profile"],
    summary="对话补充用户画像",
)
async def update_profile_by_dialogue(request: ProfileDialogueUpdateRequest) -> ProfileDialogueUpdateResponse:
    data = _extract_dialogue_profile(request.message)
    return ProfileDialogueUpdateResponse(code=200, message="success", data=data)
