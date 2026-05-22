from agent_service.schemas.common import ResourceTaskResponse
from agent_service.schemas.resources import ResourceGenerateRequest


DEFAULT_RESOURCE_TYPES = ["document", "mindmap", "reading", "code"]
SECONDS_PER_RESOURCE_TYPE = 30
MIN_ESTIMATED_DURATION_SECONDS = 60


def normalize_resource_types(request: ResourceGenerateRequest) -> list[str]:
    """Resolve v1 resource scope from the OpenAPI request contract."""
    # 设计规范关联：OpenAPI 将 video 标为预留类型，v1 默认只生成四类课程级资料；
    # 这里放在 agents 层，避免 api 层承担资源生成业务规则。
    if not request.resource_types:
        return DEFAULT_RESOURCE_TYPES.copy()
    return request.resource_types


def accept_resource_generation(request: ResourceGenerateRequest) -> ResourceTaskResponse:
    """Build the immediate 202 task response for the async resource workflow."""
    # 设计规范关联：resources/generate 是 202 + webhook 的异步协议。
    # 当前阶段只做 Agent 承接层和耗时估算，不直接写 SQL、不调用 LLM/Qdrant、不发 webhook。
    # 后续后台 worker 可从这里接入 AgentScope/RAG，并继续原样回传 Backend 提供的 task_id。
    resource_count = len(normalize_resource_types(request))
    estimated_duration = max(
        MIN_ESTIMATED_DURATION_SECONDS,
        resource_count * SECONDS_PER_RESOURCE_TYPE,
    )
    return ResourceTaskResponse(
        task_id=request.task_id,
        estimated_duration=estimated_duration,
    )
