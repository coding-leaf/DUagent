"""resources/generate 接口的 LLM prompt 模板。"""

from agent_service.schemas.resources import ResourceGenerateRequest


def build_resource_system_prompt(resource_type: str) -> str:
    base = (
        "你是 EDUagent 的资源生成助手。根据课程信息生成结构化教学资源。"
        "输出必须是一个 JSON 对象，包含 title/description/content 三个字段，不要加任何其他文字。"
    )
    specifics = {
        "document": (
            "生成一份知识讲解文档。title 是文档标题，description 是简短摘要，"
            "content 是 markdown 格式的完整讲解内容，包含概念定义、关键公式、例题。"
        ),
        "mindmap": (
            "生成一个知识导图。title 是导图名称，description 是导图概述，"
            "content 是 markdown 列表格式的树形结构，每个节点一行，用缩进表示层级。"
        ),
        "reading": (
            "生成一份拓展阅读材料。title 是阅读标题，description 是阅读引导，"
            "content 是 markdown 格式的拓展阅读内容，包含背景知识和延伸思考。"
        ),
        "code": (
            "生成一个代码示例。title 是示例名称，description 是代码说明，"
            "content 是带注释的可运行代码（用 markdown 代码块包裹）。"
        ),
    }
    return f"{base}\n{specifics.get(resource_type, base)}"


def build_resource_user_message(
    request: ResourceGenerateRequest,
    resource_type: str,
    course_knowledge_context: str | None = None,
) -> str:
    parts = [
        f"课程ID：{request.course_id}",
        f"章节：{request.chapter or '课程整体'}",
        f"知识点：{request.knowledge_point or '综合'}",
        f"资源类型：{resource_type}",
    ]
    if course_knowledge_context:
        parts.append(f"\n课程参考资料（以下内容来自课程知识库，请基于这些内容生成资源）：\n{course_knowledge_context}")
    return "\n".join(parts)
