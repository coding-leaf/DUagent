from fastapi import APIRouter, status

from agent_service.schemas.common import ResourceTaskResponse
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
    return ResourceGenerateAcceptedResponse(
        code=202,
        message="accepted",
        data=ResourceTaskResponse(task_id=request.task_id, estimated_duration=60),
    )
