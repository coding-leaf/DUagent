"""ResourceAgent Protocol, ResourceResult dataclass, and skeleton fallback helpers.

Phase 0: type definitions only — no LLM calls, no AgentScope dependency.
Phase 2-3 (future): DocumentAgent, MindmapAgent, ReadingAgent, CodeAgent
                     implementations will be added here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from agent_service.core.ai import ChatMessage
from agent_service.core.logging import get_logger
from agent_service.prompts.resources_agent import (
    build_agent_system_prompt,
    build_agent_user_message,
)
from agent_service.schemas.resources import ResourceGenerateRequest

if TYPE_CHECKING:
    from agent_service.agents.resources_plan import ResourceTaskSpec

RESOURCE_TYPE_LABELS = {
    "document": "知识讲解",
    "mindmap": "知识导图",
    "reading": "拓展阅读",
    "code": "代码示例",
}


# ── ResourceAgent Protocol ────────────────────────────────────────────────────

class ResourceAgent(Protocol):
    """Protocol for all resource-type agents (Document/Mindmap/Reading/Code).

    Each agent produces a ResourceResult from a request, planner task_spec,
    RAG context, and a chat provider.
    """

    resource_type: str  # "document" | "mindmap" | "reading" | "code"

    async def generate(
        self,
        request: ResourceGenerateRequest,
        task_spec: ResourceTaskSpec,  # TYPE_CHECKING only — no runtime import
        course_knowledge_context: str,
        chat_provider,  # AgentScope ChatProvider — untyped to avoid framework coupling
    ) -> ResourceResult:
        ...


# ── ResourceResult ─────────────────────────────────────────────────────────────

@dataclass
class ResourceResult:
    """Single ResourceAgent generation result.

    Internal metadata (generated_by, fallback_reason, is_skeleton) is for
    aggregator logic and observability — it MUST NOT leak into the webhook
    payload via to_payload_dict().
    """

    title: str
    type: str  # resource_type
    description: str
    content: str  # always a string (Mermaid, markdown tree, or skeleton text)
    chapter: str  # backfilled from request by aggregator
    knowledge_point: str  # backfilled from request
    tags: list[str]

    # ── internal metadata (not exposed to webhook) ──
    generated_by: str  # "llm" | "fallback_mermaid" | "fallback"
    fallback_reason: str | None  # plan_failed / agent_failed / mermaid_invalid / ...
    is_skeleton: bool  # True = completely failed, False = usable content (incl. degraded)

    def to_payload_dict(self) -> dict:
        """Convert to the webhook payload dict.

        Deliberately excludes generated_by, fallback_reason, and is_skeleton.
        """
        return {
            "title": self.title,
            "type": self.type,
            "description": self.description,
            "content": self.content,
            "chapter": self.chapter,
            "knowledge_point": self.knowledge_point,
            "tags": self.tags,
        }


# ── Skeleton fallback ──────────────────────────────────────────────────────────

def _build_skeleton_result(
    request: ResourceGenerateRequest,
    resource_type: str,
    fallback_reason: str = "agent_failed",
) -> ResourceResult:
    """Build a skeleton ResourceResult when an Agent completely fails.

    is_skeleton=True signals to the Aggregator that this is a true failure.
    """
    chapter = request.chapter or "课程整体"
    knowledge_point = request.knowledge_point or "综合知识点"
    label = RESOURCE_TYPE_LABELS.get(resource_type, resource_type)

    return ResourceResult(
        title=f"{chapter} - {knowledge_point} - {label}",
        type=resource_type,
        description=f"面向 {knowledge_point} 的{label}。",
        content=f"规则版资源占位内容：围绕 {chapter} / {knowledge_point} 生成 {label}。",
        chapter=chapter,
        knowledge_point=knowledge_point,
        tags=[chapter, knowledge_point, resource_type],
        generated_by="fallback",
        fallback_reason=fallback_reason,
        is_skeleton=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 2: DocumentAgent + CodeAgent
# ═══════════════════════════════════════════════════════════════════════════════

logger = get_logger(__name__)


def _parse_resource_json(raw: str) -> dict:
    """Extract JSON from LLM output (markdown-fenced or bare).

    Uses line-based first+last ``` fence detection to avoid matching
    inner ``` fences that may appear inside the JSON content field
    (e.g. code blocks within a code resource).
    """
    text = raw.strip()

    # Try bare JSON first (no fence).
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    # Line-based fence detection: use the first and last ``` line as
    # the outer fence, ignoring any inner ``` inside JSON content.
    lines = text.split("\n")
    fence_indices = [
        i for i, line in enumerate(lines) if line.strip().startswith("```")
    ]
    if len(fence_indices) >= 2:
        first, last = fence_indices[0], fence_indices[-1]
        text = "\n".join(lines[first + 1:last]).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        repaired = _repair_multiline_json_string_fields(
            text, fields=("content", "description"),
        )
        data = json.loads(repaired)
    if not isinstance(data, dict):
        raise ValueError("LLM output is not a JSON object")
    return data


def _repair_multiline_json_string_fields(text: str, fields: tuple[str, ...]) -> str:
    repaired = text
    for field in fields:
        repaired = _escape_raw_newlines_inside_json_field(repaired, field)
    return repaired


def _escape_raw_newlines_inside_json_field(text: str, field: str) -> str:
    marker = f'"{field}"'
    start = text.find(marker)
    if start == -1:
        return text
    colon = text.find(":", start + len(marker))
    if colon == -1:
        return text
    first_quote = text.find('"', colon + 1)
    if first_quote == -1:
        return text

    index = first_quote + 1
    escaped = False
    while index < len(text):
        char = text[index]
        if char == "\\" and not escaped:
            escaped = True
            index += 1
            continue
        if char == '"' and not escaped:
            value = text[first_quote + 1:index]
            safe_value = (
                value
                .replace("\r\n", "\\n")
                .replace("\n", "\\n")
                .replace("\r", "\\n")
            )
            return text[:first_quote + 1] + safe_value + text[index:]
        escaped = False
        index += 1
    return text


def _str_or(value, default: str) -> str:
    return value if isinstance(value, str) and value.strip() else default


class DocumentAgent:
    """Generates a knowledge-explanation document resource."""

    resource_type = "document"

    async def generate(
        self,
        request: ResourceGenerateRequest,
        task_spec,
        course_knowledge_context: str,
        chat_provider,
    ) -> ResourceResult:
        try:
            if chat_provider is None:
                raise RuntimeError("chat_provider is None")
            raw = await chat_provider.complete([
                ChatMessage(role="system", content=build_agent_system_prompt("document")),
                ChatMessage(role="user", content=build_agent_user_message(
                    request, "document", task_spec, course_knowledge_context,
                )),
            ])
            data = _parse_resource_json(raw)
            chapter = request.chapter or "课程整体"
            knowledge_point = request.knowledge_point or "综合知识点"
            return ResourceResult(
                title=_str_or(data.get("title"), f"{chapter} - 知识讲解"),
                type="document",
                description=_str_or(data.get("description"), "知识讲解文档"),
                content=_str_or(data.get("content"), "LLM 生成内容失败。"),
                chapter=chapter,
                knowledge_point=knowledge_point,
                tags=[chapter, knowledge_point, "document"],
                generated_by="llm",
                fallback_reason=None,
                is_skeleton=False,
            )
        except Exception:
            logger.warning(
                "DocumentAgent failed: task_id=%s", request.task_id, exc_info=True,
            )
            return _build_skeleton_result(request, "document", fallback_reason="agent_failed")


class CodeAgent:
    """Generates a code-example resource."""

    resource_type = "code"

    async def generate(
        self,
        request: ResourceGenerateRequest,
        task_spec,
        course_knowledge_context: str,
        chat_provider,
    ) -> ResourceResult:
        try:
            if chat_provider is None:
                raise RuntimeError("chat_provider is None")
            raw = await chat_provider.complete([
                ChatMessage(role="system", content=build_agent_system_prompt("code")),
                ChatMessage(role="user", content=build_agent_user_message(
                    request, "code", task_spec, course_knowledge_context,
                )),
            ])
            data = _parse_resource_json(raw)
            chapter = request.chapter or "课程整体"
            knowledge_point = request.knowledge_point or "综合知识点"
            return ResourceResult(
                title=_str_or(data.get("title"), f"{chapter} - 代码示例"),
                type="code",
                description=_str_or(data.get("description"), "代码示例"),
                content=_str_or(data.get("content"), "LLM 生成内容失败。"),
                chapter=chapter,
                knowledge_point=knowledge_point,
                tags=[chapter, knowledge_point, "code"],
                generated_by="llm",
                fallback_reason=None,
                is_skeleton=False,
            )
        except Exception:
            logger.warning(
                "CodeAgent failed: task_id=%s", request.task_id, exc_info=True,
            )
            return _build_skeleton_result(request, "code", fallback_reason="agent_failed")


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 3: ReadingAgent + MindmapAgent
# ═══════════════════════════════════════════════════════════════════════════════

class ReadingAgent:
    """Generates an extended-reading resource."""

    resource_type = "reading"

    async def generate(
        self,
        request: ResourceGenerateRequest,
        task_spec,
        course_knowledge_context: str,
        chat_provider,
    ) -> ResourceResult:
        try:
            if chat_provider is None:
                raise RuntimeError("chat_provider is None")
            raw = await chat_provider.complete([
                ChatMessage(role="system", content=build_agent_system_prompt("reading")),
                ChatMessage(role="user", content=build_agent_user_message(
                    request, "reading", task_spec, course_knowledge_context,
                )),
            ])
            data = _parse_resource_json(raw)
            chapter = request.chapter or "课程整体"
            knowledge_point = request.knowledge_point or "综合知识点"
            return ResourceResult(
                title=_str_or(data.get("title"), f"{chapter} - 拓展阅读"),
                type="reading",
                description=_str_or(data.get("description"), "拓展阅读"),
                content=_str_or(data.get("content"), "LLM 生成内容失败。"),
                chapter=chapter,
                knowledge_point=knowledge_point,
                tags=[chapter, knowledge_point, "reading"],
                generated_by="llm",
                fallback_reason=None,
                is_skeleton=False,
            )
        except Exception:
            logger.warning(
                "ReadingAgent failed: task_id=%s", request.task_id, exc_info=True,
            )
            return _build_skeleton_result(request, "reading", fallback_reason="agent_failed")


class MindmapAgent:
    """Generates a mindmap resource with Mermaid-specific fallback."""

    resource_type = "mindmap"

    async def generate(
        self,
        request: ResourceGenerateRequest,
        task_spec,
        course_knowledge_context: str,
        chat_provider,
    ) -> ResourceResult:
        from agent_service.agents.resources_mermaid import (
            generate_mindmap_with_mermaid_fallback,
        )

        return await generate_mindmap_with_mermaid_fallback(
            request,
            task_spec,
            course_knowledge_context,
            chat_provider,
        )
