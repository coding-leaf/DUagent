"""Resource quality critic for resources/generate workflow."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from agent_service.agents.resources_agents import ResourceResult
from agent_service.core.ai import ChatMessage
from agent_service.core.logging import get_logger
from agent_service.prompts.resources_agent import build_resource_critic_prompt
from agent_service.schemas.resources import ResourceGenerateRequest

logger = get_logger(__name__)

_SUPPORTED_TYPES = {"document", "mindmap", "reading", "code"}


@dataclass(frozen=True)
class ResourceCriticResult:
    accepted: bool
    reasons: list[str]
    source: str


class ResourceCriticAgent:
    """审查单个资源是否可用于 webhook，输入请求和资源结果，输出是否接受及原因。"""

    def __init__(self, chat_provider=None) -> None:
        self._chat_provider = chat_provider

    async def review(
        self,
        request: ResourceGenerateRequest,
        resource: ResourceResult,
        course_knowledge_context: str | None = None,
    ) -> ResourceCriticResult:
        rule_result = _review_by_rules(request, resource)
        if not rule_result.accepted:
            logger.warning("ResourceCritic rule gate rejected resource: %s", rule_result.reasons)
            return rule_result
        if self._chat_provider is None:
            return rule_result
        try:
            return await self._review_with_llm(
                request,
                resource,
                course_knowledge_context=course_knowledge_context,
                fallback=rule_result,
            )
        except Exception:
            logger.warning("ResourceCritic LLM review failed; using rule result", exc_info=True)
            return rule_result

    async def _review_with_llm(
        self,
        request: ResourceGenerateRequest,
        resource: ResourceResult,
        course_knowledge_context: str | None,
        fallback: ResourceCriticResult,
    ) -> ResourceCriticResult:
        raw = await self._chat_provider.complete([
            ChatMessage(role="system", content="你是 EDUagent 的资源质量审查员。只输出 JSON。"),
            ChatMessage(
                role="user",
                content=build_resource_critic_prompt(
                    request,
                    json.dumps(_resource_to_dict(resource), ensure_ascii=False),
                    course_knowledge_context=course_knowledge_context,
                ),
            ),
        ])
        data = _parse_critic_payload(raw)
        accepted = data.get("accepted")
        if not isinstance(accepted, bool):
            return fallback
        reasons = _coerce_reasons(data.get("reasons"))
        if not accepted:
            logger.warning("ResourceCritic LLM rejected resource: %s", reasons)
        return ResourceCriticResult(accepted=accepted, reasons=reasons, source="llm")


def _review_by_rules(
    request: ResourceGenerateRequest,
    resource: ResourceResult,
) -> ResourceCriticResult:
    reasons: list[str] = []
    if resource.is_skeleton:
        reasons.append("skeleton_result")
    if resource.type not in _SUPPORTED_TYPES:
        reasons.append("unsupported_type")
    if not _non_empty(resource.title):
        reasons.append("empty_title")
    if not _non_empty(resource.description):
        reasons.append("empty_description")
    if not _non_empty(resource.content):
        reasons.append("empty_content")

    if not reasons and resource.type == "mindmap" and not _valid_mindmap_content(resource.content):
        reasons.append("invalid_mindmap_content")
    if not reasons and resource.type in {"document", "reading", "code"} and not _valid_markdownish_content(resource.content):
        reasons.append("weak_content")
    if not reasons and not _matches_request_topic(request, resource):
        reasons.append("topic_mismatch")

    return ResourceCriticResult(not reasons, reasons, "rule")


def _non_empty(value: str) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _valid_markdownish_content(content: str) -> bool:
    text = str(content or "").strip()
    if len(_compact(text)) < 8:
        return False
    return any(marker in text for marker in ("#", "-", "```", "\n")) or len(_compact(text)) >= 20


def _valid_mindmap_content(content: str) -> bool:
    text = str(content or "").strip()
    return text.startswith("mindmap") or text.startswith("- ")


def _matches_request_topic(request: ResourceGenerateRequest, resource: ResourceResult) -> bool:
    targets = [value for value in (request.chapter, request.knowledge_point) if isinstance(value, str) and value.strip()]
    if not targets:
        return True
    haystack = _compact(" ".join([
        resource.title,
        resource.description,
        resource.content,
        " ".join(resource.tags),
    ]))
    return any(_compact(target) in haystack for target in targets)


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "")).lower()


def _parse_critic_payload(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("ResourceCritic output is not a JSON object")
    return data


def _coerce_reasons(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _resource_to_dict(resource: ResourceResult) -> dict[str, Any]:
    return {
        "title": resource.title,
        "type": resource.type,
        "description": resource.description,
        "content": resource.content,
        "chapter": resource.chapter,
        "knowledge_point": resource.knowledge_point,
        "tags": resource.tags,
        "generated_by": resource.generated_by,
        "fallback_reason": resource.fallback_reason,
        "is_skeleton": resource.is_skeleton,
    }
