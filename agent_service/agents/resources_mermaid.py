"""Mermaid mindmap validation and fallback generation for resource agents."""

from __future__ import annotations

import re

from agent_service.agents.resources_agents import (
    ResourceResult,
    _build_skeleton_result,
    _parse_resource_json,
    _str_or,
)
from agent_service.core.ai import ChatMessage
from agent_service.core.logging import get_logger
from agent_service.prompts.resources_agent import (
    build_agent_system_prompt,
    build_agent_user_message,
    build_mindmap_markdown_tree_system_prompt,
    build_mindmap_markdown_tree_user_message,
)
from agent_service.schemas.resources import ResourceGenerateRequest

logger = get_logger(__name__)

_MERMAID_MINDMAP_PATTERN = re.compile(r"^\s*mindmap\s*$")


def validate_mermaid_mindmap(content: str) -> bool:
    """Return True when content looks like a usable Mermaid mindmap.

    This is intentionally a basic guard, not a full Mermaid parser.
    """
    if not isinstance(content, str) or not content.strip():
        return False

    text = _strip_mermaid_fence(content)
    non_empty = [line for line in text.strip().splitlines() if line.strip()]
    if not non_empty or not _MERMAID_MINDMAP_PATTERN.match(non_empty[0].strip()):
        return False
    if len(non_empty) < 3:
        return False

    root_index = next(
        (idx for idx, line in enumerate(non_empty) if line.strip().startswith("root")),
        None,
    )
    if root_index is None:
        return False

    return any(line.strip() and idx > root_index for idx, line in enumerate(non_empty))


async def generate_mindmap_with_mermaid_fallback(
    request: ResourceGenerateRequest,
    task_spec,
    course_knowledge_context: str,
    chat_provider,
) -> ResourceResult:
    """Generate mindmap content with Mermaid -> markdown tree -> skeleton fallback."""
    try:
        mermaid_data = await _call_llm_for_mindmap(
            request, task_spec, course_knowledge_context, chat_provider
        )
        mermaid_content = mermaid_data.get("content")
        if validate_mermaid_mindmap(mermaid_content):
            logger.info(
                "Mermaid mindmap generated and validated: task_id=%s",
                request.task_id,
            )
            return _build_result(
                request,
                mermaid_data,
                _strip_mermaid_fence(mermaid_content),
                generated_by="llm",
                fallback_reason=None,
            )
        logger.warning(
            "Mermaid mindmap validation failed: task_id=%s",
            request.task_id,
        )
    except Exception:
        logger.warning(
            "Mermaid LLM call failed: task_id=%s",
            request.task_id,
            exc_info=True,
        )

    try:
        markdown_data = await _call_llm_for_mindmap_markdown_tree(
            request, task_spec, course_knowledge_context, chat_provider
        )
        markdown_tree = markdown_data.get("content")
        if not _validate_markdown_tree(markdown_tree):
            raise ValueError("Markdown tree fallback output is invalid")
        logger.info("Markdown tree fallback for mindmap: task_id=%s", request.task_id)
        return _build_result(
            request,
            markdown_data,
            markdown_tree.strip(),
            generated_by="fallback_mermaid",
            fallback_reason="mermaid_invalid",
        )
    except Exception:
        logger.warning(
            "Markdown tree LLM call failed: task_id=%s",
            request.task_id,
            exc_info=True,
        )

    logger.warning("Mindmap skeleton fallback: task_id=%s", request.task_id)
    return _build_skeleton_result(
        request,
        "mindmap",
        fallback_reason="mermaid_and_markdown_failed",
    )


async def _call_llm_for_mindmap(
    request: ResourceGenerateRequest,
    task_spec,
    course_knowledge_context: str,
    chat_provider,
) -> dict:
    """Call the LLM for primary Mermaid mindmap output."""
    if chat_provider is None:
        raise RuntimeError("chat_provider is None")
    raw = await chat_provider.complete([
        ChatMessage(role="system", content=build_agent_system_prompt("mindmap")),
        ChatMessage(
            role="user",
            content=build_agent_user_message(
                request, "mindmap", task_spec, course_knowledge_context
            ),
        ),
    ])
    return _parse_resource_json(raw)


async def _call_llm_for_mindmap_markdown_tree(
    request: ResourceGenerateRequest,
    task_spec,
    course_knowledge_context: str,
    chat_provider,
) -> dict:
    """Call the LLM for markdown nested-list fallback output."""
    if chat_provider is None:
        raise RuntimeError("chat_provider is None")
    raw = await chat_provider.complete([
        ChatMessage(role="system", content=build_mindmap_markdown_tree_system_prompt()),
        ChatMessage(
            role="user",
            content=build_mindmap_markdown_tree_user_message(
                request, task_spec, course_knowledge_context
            ),
        ),
    ])
    return _parse_resource_json(raw)


def _build_result(
    request: ResourceGenerateRequest,
    data: dict,
    content: str,
    generated_by: str,
    fallback_reason: str | None,
) -> ResourceResult:
    chapter = request.chapter or "课程整体"
    knowledge_point = request.knowledge_point or "综合知识点"
    return ResourceResult(
        title=_str_or(data.get("title"), f"{chapter} - 知识导图"),
        type="mindmap",
        description=_str_or(data.get("description"), "知识导图"),
        content=content,
        chapter=chapter,
        knowledge_point=knowledge_point,
        tags=[chapter, knowledge_point, "mindmap"],
        generated_by=generated_by,
        fallback_reason=fallback_reason,
        is_skeleton=False,
    )


def _strip_mermaid_fence(content: str) -> str:
    text = content.strip()
    lines = text.splitlines()
    if (
        len(lines) >= 2
        and lines[0].strip().startswith("```")
        and lines[-1].strip() == "```"
    ):
        return "\n".join(lines[1:-1]).strip()
    return text


def _validate_markdown_tree(content: str) -> bool:
    if not isinstance(content, str) or not content.strip():
        return False
    return any(
        line.strip().startswith("- ") or line.strip().startswith("* ")
        for line in content.splitlines()
    )
