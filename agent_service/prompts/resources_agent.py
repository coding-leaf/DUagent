"""ResourceAgent prompt templates for the multi-agent resources workflow.

Phase 2: document and code agent prompts.
Phase 3: reading and mindmap prompts.
"""

from agent_service.schemas.resources import ResourceGenerateRequest


def build_agent_system_prompt(resource_type: str) -> str:
    """Build the system prompt for a ResourceAgent, specialised by type.

    All agents share the same base instruction: output a JSON object with
    title/description/content. The specifics block varies per type.
    """
    base = (
        "你是 EDUagent 的资源生成助手。根据课程信息和教学计划生成结构化教学资源。"
        "输出必须是一个 JSON 对象，包含 title/description/content 三个字段，"
        "用 ```json ... ``` 代码块包裹，不要加任何其他文字。"
    )
    specifics = {
        "document": (
            "生成一份知识讲解文档。title 是文档标题，description 是简短摘要，"
            "content 是 markdown 格式的完整讲解内容，"
            "包含概念定义、关键公式、典型例题和注意事项。"
        ),
        "code": (
            "生成一个代码示例。title 是示例名称，description 是代码说明，"
            "content 是 markdown 格式，包含问题描述、算法思路、"
            "带注释的 C 语言代码（用 markdown 代码块包裹）、复杂度分析和运行示例。"
        ),
        "reading": (
            "生成一份拓展阅读材料。title 是阅读标题，description 是简短摘要，"
            "content 是 markdown 格式，包含背景知识、核心延伸概念、实际应用和思考题。"
        ),
        "mindmap": (
            "生成一份 Mermaid mindmap 知识导图。title 是导图标题，description 是简短摘要，"
            "content 必须只包含 Mermaid mindmap 语法文本，以 mindmap 开头，"
            "包含 root 节点和至少一个分支，不要在 content 内包裹 markdown 代码块。"
        ),
    }
    return f"{base}\n{specifics.get(resource_type, base)}"


def build_agent_user_message(
    request: ResourceGenerateRequest,
    resource_type: str,
    task_spec,  # ResourceTaskSpec
    course_knowledge_context: str = "",
) -> str:
    """Build the user message for a ResourceAgent call."""
    parts = [
        f"课程ID：{request.course_id}",
        f"章节：{request.chapter or '课程整体'}",
        f"知识点：{request.knowledge_point or '综合'}",
        f"资源类型：{resource_type}",
        f"重点知识：{'、'.join(task_spec.focus_points) if task_spec.focus_points else '综合'}",
        f"建议结构：{task_spec.suggested_structure}",
        f"输出格式：{task_spec.output_format_hint}",
    ]
    if course_knowledge_context:
        parts.append(
            f"\n课程参考资料（请基于以下内容生成资源）：\n{course_knowledge_context}"
        )
    return "\n".join(parts)


def build_mindmap_markdown_tree_system_prompt() -> str:
    """Build the fallback prompt for a markdown nested-list mindmap."""
    return (
        "你是 EDUagent 的知识导图降级生成助手。Mermaid 导图生成失败时，"
        "你需要生成 markdown 嵌套列表树。输出必须是一个 JSON 对象，"
        "包含 title/description/content 三个字段，用 ```json ... ``` 代码块包裹，"
        "不要加任何其他文字。content 必须以 '- ' 开头，并使用缩进表达层级。"
    )


def build_mindmap_markdown_tree_user_message(
    request: ResourceGenerateRequest,
    task_spec,  # ResourceTaskSpec
    course_knowledge_context: str = "",
) -> str:
    """Build the user message for the mindmap markdown-tree fallback."""
    parts = [
        f"课程ID：{request.course_id}",
        f"章节：{request.chapter or '课程整体'}",
        f"知识点：{request.knowledge_point or '综合'}",
        f"重点知识：{'、'.join(task_spec.focus_points) if task_spec.focus_points else '综合'}",
        f"建议结构：{task_spec.suggested_structure}",
        "输出格式：markdown 嵌套列表树，例如 '- 主题\\n  - 分支\\n    - 细节'",
    ]
    if course_knowledge_context:
        parts.append(
            f"\n课程参考资料（请基于以下内容生成 markdown 树）：\n{course_knowledge_context}"
        )
    return "\n".join(parts)


def build_resource_critic_prompt(
    request: ResourceGenerateRequest,
    resource_json: str,
    course_knowledge_context: str | None = None,
) -> str:
    """构建资源质量审查提示词，输入请求和单个资源 JSON，输出是否接受的 JSON 判定。"""
    context = course_knowledge_context or "无"
    return (
        "你是 EDUagent 的资源质量审查员。请只判断资源是否可用于回调，不要改写资源。\n\n"
        "审查标准：\n"
        "- 资源必须贴合请求的章节和知识点\n"
        "- title、description、content 必须非空且互相一致\n"
        "- document/reading/code 应是可读的 markdown 教学内容\n"
        "- mindmap 应是 Mermaid mindmap，或可用的 markdown 嵌套列表树\n"
        "- skeleton 占位内容、明显跑题内容、格式完全错误的内容应拒绝\n\n"
        "请求：\n"
        f"课程ID：{request.course_id}\n"
        f"章节：{request.chapter or '课程整体'}\n"
        f"知识点：{request.knowledge_point or '综合'}\n"
        f"资源类型：{', '.join(request.resource_types) if request.resource_types else 'document, mindmap, reading, code'}\n\n"
        "课程参考资料：\n"
        f"{context}\n\n"
        "待审查资源 JSON：\n"
        f"{resource_json}\n\n"
        "只输出 JSON 对象：{\"accepted\": true|false, \"reasons\": [\"...\"]}。"
    )
