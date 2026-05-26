import asyncio
import json
import re
from collections.abc import Awaitable, Callable
from typing import Any
from urllib import request as urllib_request

from agent_service.core.ai import ChatMessage, get_ai_providers
from agent_service.core.logging import get_logger
from agent_service.prompts.resources import (
    build_resource_system_prompt,
    build_resource_user_message,
)
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
logger = get_logger(__name__)

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
    max_webhook_attempts: int = 3,
    webhook_base_delay_seconds: float = 1.0,
) -> None:
    """Run the async resource workflow and notify Backend through webhook_url.

    输入：资源生成请求、可注入的 webhook 发送函数、可注入的结果构造器。
    输出：无直接返回值；按规范 POST completed/failed payload 到 webhook_url。

    优先尝试 LLM 生成（附 RAG 课程知识上下文），失败时降级到 result_builder。
    result_builder 抛异常时仍按现有逻辑发 failed webhook payload。
    """
    try:
        providers = get_ai_providers()
        course_knowledge_context = await _build_course_knowledge_context(
            request,
            getattr(providers, "embedding", None),
        )
        llm_resources = await generate_resources_with_llm(
            request,
            getattr(providers, "chat", None),
            course_knowledge_context=course_knowledge_context,
        )
        if llm_resources is not None:
            payload = {
                "task_id": request.task_id,
                "task_type": TASK_TYPE,
                "status": "completed",
                "result": {"resources": llm_resources},
            }
        else:
            payload = result_builder(request)
    except Exception as exc:
        logger.warning(
            "Resource generation failed before webhook: task_id=%s error=%s",
            request.task_id,
            exc,
        )
        payload = build_resource_generation_failed_payload(request, str(exc))
    try:
        await send_webhook_with_retry(
            request.webhook_url,
            payload,
            sender=send_webhook,
            max_attempts=max_webhook_attempts,
            base_delay_seconds=webhook_base_delay_seconds,
        )
    except Exception as exc:
        logger.warning(
            "Resource generation webhook failed: task_id=%s error=%s",
            request.task_id,
            exc,
        )
        return


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


async def send_webhook_with_retry(
    webhook_url: str,
    payload: WebhookPayload,
    sender: WebhookSender | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    max_attempts: int = 3,
    base_delay_seconds: float = 1.0,
) -> None:
    """发送 webhook 并按指数退避重试，输入回调地址和 payload，失败时最终抛出最后异常。"""
    webhook_sender = sender or post_webhook_payload
    attempts = max(1, max_attempts)
    for attempt in range(attempts):
        try:
            await webhook_sender(webhook_url, payload)
            return
        except Exception:
            if attempt == attempts - 1:
                raise
            await sleep(base_delay_seconds * (2**attempt))


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


_V1_RESOURCE_TYPES = {"document", "mindmap", "reading", "code"}
_MARKDOWN_FENCE_PATTERN = re.compile(r"```(?:json)?\s*\n?(.*?)```", re.DOTALL)


async def _build_course_knowledge_context(
    request: ResourceGenerateRequest,
    embedding_provider,
    limit: int = 5,
) -> str:
    """检索课程知识库中与请求相关的片段，输入请求和 embedding provider，输出拼接后的上下文字符串。

    无 embedding provider 或检索失败时返回空字符串，不抛异常。
    """
    if embedding_provider is None:
        return ""
    try:
        from agent_service.memory.vector_store import QdrantVectorStore

        query_text = " ".join(
            part for part in [request.chapter, request.knowledge_point]
            if part
        ) or request.course_id
        vectors = await embedding_provider.embed_texts([query_text])
        store = QdrantVectorStore()
        results = await store.search_course_knowledge(
            request.course_id, vectors[0], limit=limit
        )
        if not results:
            return ""
        chunks = [r.text for r in results if r.text]
        if not chunks:
            return ""
        return "\n---\n".join(chunks)
    except Exception:
        logger.warning(
            "Course knowledge retrieval failed: course_id=%s",
            request.course_id,
            exc_info=True,
        )
        return ""


async def generate_resources_with_llm(
    request: ResourceGenerateRequest,
    chat_provider,
    course_knowledge_context: str | None = None,
) -> list[dict] | None:
    """尝试用 LLM 生成课程资源，输入请求、chat provider 和可选的 RAG 上下文，输出资源 payload 列表或 None（降级）。

    任一资源类型生成失败，整体返回 None。非 v1 四类（含 video）整体返回 None。
    """
    if chat_provider is None:
        return None
    resource_types = normalize_resource_types(request)
    if not set(resource_types).issubset(_V1_RESOURCE_TYPES):
        return None
    try:
        tasks = [
            _generate_single_resource(request, rt, chat_provider, course_knowledge_context)
            for rt in resource_types
        ]
        results = await asyncio.gather(*tasks)
        return list(results)
    except Exception:
        logger.warning(
            "LLM resource generation failed, falling back to skeleton",
            exc_info=True,
        )
        return None


async def _generate_single_resource(
    request: ResourceGenerateRequest,
    resource_type: str,
    chat_provider,
    course_knowledge_context: str | None = None,
) -> dict:
    messages = [
        ChatMessage(
            role="system", content=build_resource_system_prompt(resource_type)
        ),
        ChatMessage(
            role="user",
            content=build_resource_user_message(
                request, resource_type, course_knowledge_context=course_knowledge_context
            ),
        ),
    ]
    raw = await chat_provider.complete(messages)
    data = _parse_resource_json(raw)
    return _coerce_resource_item(data, request, resource_type)


def _parse_resource_json(raw: str) -> dict:
    text = raw.strip()
    match = _MARKDOWN_FENCE_PATTERN.search(text)
    if match:
        text = match.group(1).strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("LLM output is not a JSON object")
    return data


def _coerce_resource_item(
    data: dict,
    request: ResourceGenerateRequest,
    resource_type: str,
) -> dict[str, Any]:
    chapter = request.chapter or "课程整体"
    knowledge_point = request.knowledge_point or "综合知识点"
    label = RESOURCE_TYPE_LABELS.get(resource_type, resource_type)
    return {
        "title": _str_or(data.get("title"), f"{chapter} - {knowledge_point} - {label}"),
        "type": resource_type,
        "description": _str_or(data.get("description"), f"面向 {knowledge_point} 的{label}。"),
        "content": _str_or(data.get("content"), f"LLM 生成内容：围绕 {chapter} / {knowledge_point} 生成 {label}。"),
        "chapter": chapter,
        "knowledge_point": knowledge_point,
        "tags": [chapter, knowledge_point, resource_type],
    }


def _str_or(value, default: str) -> str:
    return value if isinstance(value, str) and value.strip() else default


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
