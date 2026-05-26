"""memory/compress 接口的 LLM prompt 模板。"""

from agent_service.schemas.memory import MemoryCompressRequest


def build_memory_compress_system_prompt() -> str:
    return (
        "你是 EDUagent 的记忆压缩助手。根据给定的对话消息、旧摘要和已存在的事实，"
        "提取语义事实并生成融合摘要。\n\n"
        "输出必须是一个 JSON 对象，包含以下字段：\n"
        "- new_summary: 字符串，融合旧摘要和新消息后的全局摘要。如果旧摘要为空则生成新摘要，"
        "如果消息无有效信息可返回旧摘要原样。\n"
        "- extracted_facts: 数组，每个元素为 {content, fact_type, knowledge_point, confidence}\n"
        "  - content: 事实文本，如\"用户在递归概念上反复卡住\"（必填）\n"
        "  - fact_type: blind_spot（薄弱点/反复错误）、mastered_point（已掌握）、"
        "cognitive_preference（学习偏好/风格）之一（必填）\n"
        "  - knowledge_point: 关联的知识点名称，无则填 null\n"
        "  - confidence: 0-1 的置信度。强证据（多次出现/明确表述）用 0.9+，"
        "中等证据用 0.7-0.9，弱证据用 0.5-0.7\n\n"
        "规则：\n"
        "- 不要提取与 existing_facts 内容重复的事实\n"
        "- 不要编造对话中未出现的事实\n"
        "- extracted_facts 可以为空数组，但不能省略\n"
        "- 只输出 JSON 对象，不要加 markdown 代码块标记，不要加任何其他文字"
    )


def build_memory_compress_user_message(request: MemoryCompressRequest) -> str:
    parts: list[str] = []
    parts.append(f"旧摘要：{request.old_summary or '无'}")
    parts.append("待压缩消息：")
    for i, msg in enumerate(request.messages_to_compress, 1):
        role_label = "用户" if msg.role == "user" else "助手"
        ts = msg.timestamp.isoformat() if msg.timestamp else "未知时间"
        parts.append(f"  [{i}] [{role_label}] {ts}: {msg.content}")
    existing = "\n".join(f"- {f}" for f in request.existing_facts) if request.existing_facts else "无"
    parts.append(f"已存在的事实（不要重复提取）：\n{existing}")
    return "\n".join(parts)
