"""ResourceAggregator — merge Plan + ResourceAgent results into webhook payload.

Phase 4: field validation, skeleton detection, payload construction.
Phase 5 (future): used by ResourceWorkflowOrchestrator.
"""

from typing import Any

from agent_service.agents.resources_plan import ResourcePlan
from agent_service.agents.resources_agents import ResourceResult
from agent_service.core.logging import get_logger
from agent_service.schemas.resources import ResourceGenerateRequest

logger = get_logger(__name__)

WebhookPayload = dict[str, Any]
TASK_TYPE = "resource_generation"


def aggregate_resource_results(
    request: ResourceGenerateRequest,
    plan: ResourcePlan,
    results: list[ResourceResult],
) -> WebhookPayload | None:
    """Merge Agent results and build a webhook payload.

    Rules:
    1. If ALL results have is_skeleton=True → return None (sentinel).
       fallback_mermaid (is_skeleton=False) counts as success, NOT failure.
    2. Validate each resource's title/description/content — backfill
       empty fields with safe defaults.
    3. Internal fields (generated_by, fallback_reason, is_skeleton) are
       excluded from the output payload.

    Returns None when the orchestrator should fall back to the next
    degradation layer (generate_resources_with_llm → skeleton).
    """
    if not results:
        return None

    all_skeleton = all(r.is_skeleton for r in results)
    if all_skeleton:
        return None

    resources_payload: list[dict] = []
    for result in results:
        resources_payload.append(_ensure_resource_completeness(result, request))

    success_count = sum(1 for r in results if not r.is_skeleton)
    fallback_count = sum(1 for r in results if r.is_skeleton)
    logger.info(
        "Aggregator merged results: task_id=%s success=%d fallback=%d total=%d",
        request.task_id, success_count, fallback_count, len(results),
    )
    return {
        "task_id": request.task_id,
        "task_type": TASK_TYPE,
        "status": "completed",
        "result": {"resources": resources_payload},
    }


def _ensure_resource_completeness(
    result: ResourceResult,
    request: ResourceGenerateRequest,
) -> dict:
    """Validate and backfill a ResourceResult into a payload-safe dict."""
    chapter = request.chapter or "课程整体"
    knowledge_point = request.knowledge_point or "综合知识点"
    label = _RESOURCE_TYPE_LABELS.get(result.type, result.type)

    title = _non_empty(result.title, f"{chapter} - {knowledge_point} - {label}")
    description = _non_empty(result.description, f"面向 {knowledge_point} 的{label}。")
    content = _non_empty(
        result.content,
        f"规则版资源占位内容：围绕 {chapter} / {knowledge_point} 生成 {label}。",
    )
    return {
        "title": title,
        "type": result.type,
        "description": description,
        "content": content,
        "chapter": chapter,
        "knowledge_point": knowledge_point,
        "tags": [chapter, knowledge_point, result.type],
    }


def _non_empty(value: str, default: str) -> str:
    return value if isinstance(value, str) and value.strip() else default


_RESOURCE_TYPE_LABELS = {
    "document": "知识讲解",
    "mindmap": "知识导图",
    "reading": "拓展阅读",
    "code": "代码示例",
}
