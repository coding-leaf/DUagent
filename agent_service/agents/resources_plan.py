"""ResourcePlan and ResourceTaskSpec dataclasses for the multi-agent resources workflow.

Phase 0: type definitions and rule-based planner.
Phase 1: generate_plan_with_llm() — LLM Planner with None-on-failure.
"""

import json
import re
from dataclasses import dataclass

from agent_service.core.ai import ChatMessage
from agent_service.core.logging import get_logger
from agent_service.prompts.resources_plan import (
    build_planner_system_prompt,
    build_planner_user_message,
)
from agent_service.schemas.resources import ResourceGenerateRequest

# v1 resource types — kept local to avoid a reverse dependency on
# agents/resources.py, which will later import resources_workflow →
# resources_plan (Phase 5).
_V1_RESOURCE_TYPES = {"document", "mindmap", "reading", "code"}
_DEFAULT_RESOURCE_TYPES = ["document", "mindmap", "reading", "code"]


def _normalize_resource_types(request: ResourceGenerateRequest) -> list[str]:
    """Resolve v1 resource scope — mirrors agents.resources.normalize_resource_types
    but lives here to keep the dependency direction one-way."""
    if not request.resource_types:
        return _DEFAULT_RESOURCE_TYPES.copy()
    # Keep only known v1 types; silently drop video and any unknowns
    return [rt for rt in request.resource_types if rt in _V1_RESOURCE_TYPES]


@dataclass
class ResourceTaskSpec:
    """Planner output for a single resource type — describes generation strategy.

    Does NOT contain the final resource content; ResourceAgent produces that.
    """

    resource_type: str  # "document" | "mindmap" | "reading" | "code"
    focus_points: list[str]  # 1-3 key knowledge points from course context
    suggested_structure: str  # short text hint for the Agent
    output_format_hint: str  # format hint for the Agent


@dataclass
class ResourcePlan:
    """LLM Planner output — a plan describing how to generate each resource type."""

    overview: str  # 1-2 sentence teaching-intent summary
    tasks: list[ResourceTaskSpec]
    knowledge_summary: str  # key knowledge extracted from RAG context by Planner


# ── Rule-based planner (no LLM) ───────────────────────────────────────────────

_DEFAULT_SPECS: dict[str, ResourceTaskSpec] = {
    "document": ResourceTaskSpec(
        resource_type="document",
        focus_points=[],  # filled per-request
        suggested_structure="概念定义 → 关键公式/定理 → 典型例题 → 注意事项",
        output_format_hint="markdown 格式的长文讲解",
    ),
    "mindmap": ResourceTaskSpec(
        resource_type="mindmap",
        focus_points=[],
        suggested_structure="核心主题 → 一级分支（概念、性质、应用、例题）→ 二级展开",
        output_format_hint="Mermaid mindmap 语法",
    ),
    "reading": ResourceTaskSpec(
        resource_type="reading",
        focus_points=[],
        suggested_structure="背景知识 → 核心延伸概念 → 实际应用 → 思考题",
        output_format_hint="markdown 格式的拓展阅读",
    ),
    "code": ResourceTaskSpec(
        resource_type="code",
        focus_points=[],
        suggested_structure="问题描述 → 算法思路 → 完整代码 → 复杂度分析 → 运行示例",
        output_format_hint="带注释的 C 语言代码，markdown 代码块包裹",
    ),
}


def build_rule_based_plan(request: ResourceGenerateRequest) -> ResourcePlan:
    """Rule-based Planner: no LLM, builds plan from request metadata and defaults.

    Input: ResourceGenerateRequest (course_id, chapter, knowledge_point, resource_types)
    Output: ResourcePlan with one ResourceTaskSpec per v1 resource type.
            Non-v1 types (e.g. video) are silently excluded.
    """
    chapter = request.chapter or "课程整体"
    kp = request.knowledge_point or "综合知识点"
    resource_types = _normalize_resource_types(request)

    tasks: list[ResourceTaskSpec] = []
    for rt in resource_types:
        spec = _DEFAULT_SPECS.get(rt)
        if spec is None:
            continue  # excludes video and any unknown types
        # Fill per-request focus_points (immutable: create new instance)
        tasks.append(ResourceTaskSpec(
            resource_type=spec.resource_type,
            focus_points=[kp],
            suggested_structure=spec.suggested_structure,
            output_format_hint=spec.output_format_hint,
        ))

    return ResourcePlan(
        overview=f"{chapter} - {kp} 教学资源生成",
        tasks=tasks,
        knowledge_summary=f"基于章节「{chapter}」知识点「{kp}」的课程知识。",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 1: LLM Planner — generate_plan_with_llm()
# ═══════════════════════════════════════════════════════════════════════════════

logger = get_logger(__name__)

_MARKDOWN_FENCE_PATTERN = re.compile(r"```(?:json)?\s*\n?(.*?)```", re.DOTALL)


async def generate_plan_with_llm(
    request: ResourceGenerateRequest,
    chat_provider,
    course_knowledge_context: str = "",
) -> ResourcePlan | None:
    """Call the LLM to produce a ResourcePlan from course metadata and RAG context.

    Input:
      request — ResourceGenerateRequest (course_id, chapter, knowledge_point)
      chat_provider — AgentScope ChatProvider (or compatible fake for tests)
      course_knowledge_context — RAG chunks or empty string

    Output:
      ResourcePlan on success, None on any failure (bad JSON, provider None,
      LLM exception, etc.). Never raises.

    Phase 5 will wrap this with _run_planner_with_fallback() to add rule-based
    fallback on None.
    """
    if chat_provider is None:
        return None

    resource_types = _normalize_resource_types(request)
    system_prompt = build_planner_system_prompt()
    user_message = build_planner_user_message(request, resource_types, course_knowledge_context)

    try:
        raw = await chat_provider.complete([
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_message),
        ])
        data = _parse_plan_json(raw)
        plan = _coerce_plan(data, request)
        if plan is None:
            logger.warning(
                "LLM Planner returned no usable tasks: task_id=%s",
                request.task_id,
            )
        return plan
    except Exception:
        logger.warning(
            "LLM Planner failed: task_id=%s course_id=%s",
            request.task_id,
            request.course_id,
            exc_info=True,
        )
        return None


def _parse_plan_json(raw: str) -> dict:
    """Extract and parse JSON from LLM output.

    Handles markdown ```json ... ``` fences and bare JSON. Follows the same
    pattern as _parse_resource_json in agents/resources.py.
    """
    text = raw.strip()
    match = _MARKDOWN_FENCE_PATTERN.search(text)
    if match:
        text = match.group(1).strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("LLM Planner output is not a JSON object")
    return data


def _coerce_plan(data: dict, request: ResourceGenerateRequest) -> ResourcePlan:
    """Guard and backfill LLM Planner output into a ResourcePlan.

    Defensive rules:
    1. Drop tasks whose resource_type is not in the requested list (LLM
       inventing types).
    2. Backfill empty focus_points with [knowledge_point or "综合知识点"].
    3. Backfill missing requested types from _DEFAULT_SPECS so the plan
       always covers every requested type.
    """
    resource_types = _normalize_resource_types(request)
    kp = request.knowledge_point or "综合知识点"

    tasks_raw = data.get("tasks", [])
    if not isinstance(tasks_raw, list):
        tasks_raw = []

    valid_types = set(resource_types)
    seen_types: set[str] = set()
    tasks: list[ResourceTaskSpec] = []

    for item in tasks_raw:
        if not isinstance(item, dict):
            continue
        rt = item.get("resource_type", "")
        if rt not in valid_types:
            continue  # drop invented types

        focus_points = _coerce_str_list(item.get("focus_points"))
        if not focus_points:
            focus_points = [kp]  # backfill empty focus_points

        tasks.append(ResourceTaskSpec(
            resource_type=rt,
            focus_points=focus_points,
            suggested_structure=_coerce_str(
                item.get("suggested_structure"),
                _DEFAULT_SPECS.get(rt, ResourceTaskSpec(rt, [], "", "")).suggested_structure,
            ),
            output_format_hint=_coerce_str(
                item.get("output_format_hint"),
                _DEFAULT_SPECS.get(rt, ResourceTaskSpec(rt, [], "", "")).output_format_hint,
            ),
        ))
        seen_types.add(rt)

    # Backfill any requested type the LLM missed — use rule-based defaults.
    for rt in resource_types:
        if rt not in seen_types:
            spec = _DEFAULT_SPECS.get(rt)
            if spec is not None:
                tasks.append(ResourceTaskSpec(
                    resource_type=rt,
                    focus_points=[kp],
                    suggested_structure=spec.suggested_structure,
                    output_format_hint=spec.output_format_hint,
                ))

    return ResourcePlan(
        overview=_coerce_str(data.get("overview"), "课程资源生成计划"),
        tasks=tasks,
        knowledge_summary=_coerce_str(data.get("knowledge_summary"), ""),
    )


def _coerce_str(value, default: str) -> str:
    """Return value if it's a non-empty string, else default."""
    return value if isinstance(value, str) and value.strip() else default


def _coerce_str_list(value) -> list[str]:
    """Return value if it's a list of strings, else empty list."""
    if isinstance(value, list):
        return [str(v) for v in value if v]
    return []
