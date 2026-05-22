from fastapi import APIRouter, status

from agent_service.agents.resources import accept_resource_generation
from agent_service.schemas.resources import ResourceGenerateAcceptedResponse, ResourceGenerateRequest


router = APIRouter(prefix="/resources")


@router.post(
    "/generate",
    response_model=ResourceGenerateAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Resources"],
    summary="生成资源库",
)
async def generate_resources(request: ResourceGenerateRequest) -> ResourceGenerateAcceptedResponse:
    # 设计规范关联：api 层只做 FastAPI 路由、统一响应包装和异步协议适配；
    # 资源生成的规则版承接逻辑放在 agents.resources，后续可替换为真实 worker/webhook 编排。
    task_response = accept_resource_generation(request)
    return ResourceGenerateAcceptedResponse(
        code=202,
        message="accepted",
        data=task_response,
    )
