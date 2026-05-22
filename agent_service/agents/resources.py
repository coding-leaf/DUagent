import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any
from urllib import request as urllib_request

from agent_service.schemas.common import ResourceTaskResponse
from agent_service.schemas.resources import ResourceGenerateRequest


DEFAULT_RESOURCE_TYPES = ["document", "mindmap", "reading", "code"]
SECONDS_PER_RESOURCE_TYPE = 30
MIN_ESTIMATED_DURATION_SECONDS = 60
RESOURCE_TYPE_LABELS = {
    "document": "知识讲解",
    "mindmap": "知识导图",
    "reading": "拓展阅读",
    "code": "代码示例",
    "video": "视频资源",
}
TASK_TYPE = "resource_generation"

WebhookPayload = dict[str, Any]
WebhookSender = Callable[[str, WebhookPayload], Awaitable[None]]
ResultBuilder = Callable[[ResourceGenerateRequest], WebhookPayload]


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


def build_resource_generation_result(request: ResourceGenerateRequest) -> WebhookPayload:
    """Build the completed webhook payload for the resource-generation task.

    输入：Backend 传入的 ResourceGenerateRequest。
    输出：符合《API_Agent内部接口规范》6.1 Webhook 回调约定的 dict payload。
    """
    # 设计规范关联：Agent Service 只返回结构化资源结果，Backend 才负责按 task_id 校验并写 SQL。
    # 当前规则版仅产出课程级资料骨架；content 后续可由 AgentScope/RAG/LLM 生成后替换。
    resources = [_build_resource_payload(request, resource_type) for resource_type in normalize_resource_types(request)]
    return {
        "task_id": request.task_id,
        "task_type": TASK_TYPE,
        "status": "completed",
        "result": {"resources": resources},
    }


async def run_resource_generation_task(
    request: ResourceGenerateRequest,
    send_webhook: WebhookSender | None = None,
    result_builder: ResultBuilder = build_resource_generation_result,
) -> None:
    """Run the async resource workflow and notify Backend through webhook_url.

    输入：资源生成请求、可注入的 webhook 发送函数、可注入的结果构造器。
    输出：无直接返回值；按规范 POST completed/failed payload 到 webhook_url。
    """
    # 设计规范关联：resources/generate 是 202 + webhook 异步模式。
    # api 层只注册后台任务；这里作为 agents 层承接点，后续替换为真实多智能体并行生成。
    sender = send_webhook or post_webhook_payload
    try:
        payload = result_builder(request)
    except Exception as exc:
        payload = build_resource_generation_failed_payload(request, str(exc))
    await sender(request.webhook_url, payload)


def build_resource_generation_failed_payload(request: ResourceGenerateRequest, error_message: str) -> WebhookPayload:
    """Build a failed webhook payload using the documented task status fields."""
    return {
        "task_id": request.task_id,
        "task_type": TASK_TYPE,
        "status": "failed",
        "error_message": error_message,
    }


async def post_webhook_payload(webhook_url: str, payload: WebhookPayload) -> None:
    """Post webhook payload without adding a third-party HTTP dependency."""
    # 设计规范关联：Agent 只回调 Backend 的 webhook_url，不直接接触 Backend SQL。
    # 该函数是可替换的基础设施边界；测试通过注入 fake sender 避免真实网络调用。
    await asyncio.to_thread(_post_json_payload, webhook_url, payload)


def _build_resource_payload(request: ResourceGenerateRequest, resource_type: str) -> dict[str, Any]:
    chapter = request.chapter or "课程整体"
    knowledge_point = request.knowledge_point or "综合知识点"
    label = RESOURCE_TYPE_LABELS.get(resource_type, resource_type)
    return {
        "title": f"{chapter} - {knowledge_point} - {label}",
        "type": resource_type,
        "description": f"面向 {knowledge_point} 的{label}。",
        "content": f"规则版资源占位内容：围绕 {chapter} / {knowledge_point} 生成 {label}。",
        "chapter": chapter,
        "knowledge_point": knowledge_point,
        "tags": [chapter, knowledge_point, resource_type],
    }


def _post_json_payload(webhook_url: str, payload: WebhookPayload) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib_request.Request(
        webhook_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib_request.urlopen(request, timeout=10) as response:
        if response.status >= 400:
            raise RuntimeError(f"webhook returned HTTP {response.status}")
