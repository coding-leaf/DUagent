"""Planner prompt templates for the multi-agent resources workflow.

Phase 1: LLM Planner prompts — instruct the model to output a structured
ResourcePlan JSON from course metadata and RAG context.
"""

from agent_service.schemas.resources import ResourceGenerateRequest


def build_planner_system_prompt() -> str:
    """Return the Planner system prompt — describes the role and JSON output schema."""
    return (
        "你是 EDUagent 的教学资源规划师。根据课程信息和知识点，制定资源生成计划。"
        "输出必须是一个 JSON 对象，用 ```json ... ``` 代码块包裹，"
        "不要加任何其他解释文字。"
        "\n\n"
        "JSON schema:\n"
        '  "overview": 1-2 句话描述整体教学意图\n'
        '  "knowledge_summary": 从课程参考资料中提取的关键知识点摘要\n'
        '  "tasks": [\n'
        '    {\n'
        '      "resource_type": "document|mindmap|reading|code",\n'
        '      "focus_points": ["知识点1", "知识点2"],\n'
        '      "suggested_structure": "建议结构说明",\n'
        '      "output_format_hint": "输出格式提示"\n'
        '    }\n'
        '  ]\n'
        "\n"
        "要求：\n"
        "- tasks 数组必须为每个请求的 resource_type 生成一个 task。\n"
        "- focus_points 从课程参考资料中提炼 1-3 个具体知识点，不要泛化。\n"
        "- suggested_structure 用中文描述推荐的章节/段落结构。\n"
        "- output_format_hint 指明期望的输出格式（如 markdown/Mermaid 等）。\n"
        "- 如果没有课程参考资料，基于课程的基础概念生成计划。"
    )


def build_planner_user_message(
    request: ResourceGenerateRequest,
    resource_types: list[str],
    course_knowledge_context: str = "",
) -> str:
    """Build the Planner user message from request metadata and RAG context.

    Input:
      request — ResourceGenerateRequest (course_id, chapter, knowledge_point)
      resource_types — normalized v1 type list (excludes video)
      course_knowledge_context — RAG-retrieved chunks or empty string

    Output: single string to use as the user message in the LLM call.
    """
    parts = [
        f"课程ID：{request.course_id}",
        f"章节：{request.chapter or '课程整体'}",
        f"知识点：{request.knowledge_point or '综合'}",
        f"需要生成的资源类型：{', '.join(resource_types)}",
    ]
    if course_knowledge_context:
        parts.append(
            f"\n课程参考资料（以下内容来自课程知识库，请基于这些内容规划资源生成）：\n"
            f"{course_knowledge_context}"
        )
    else:
        parts.append("\n无课程参考资料，请基于课程的基础概念规划资源生成。")
    return "\n".join(parts)
