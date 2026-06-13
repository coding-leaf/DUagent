from agent_service.core.ai import ChatMessage
from agent_service.memory.tutoring_retrieval import TutoringRetrievalContext
from agent_service.schemas.tutoring import TutoringChatRequest

TUTOR_REACT_SYSTEM_PROMPT = (
    "你是 EDUagent 的智能辅导 Agent，基于 ReActAgent 推理循环。"
    "回答必须贴合用户画像、课程范围和检索上下文，优先引导理解。"
    "如果提供了图谱节点，knowledge_points 应优先从这些节点名称中选择；回答应围绕最相关节点展开，不要机械覆盖所有节点。\n"
    "请以 JSON 格式输出回复，JSON object 包含三个字段："
    "model_text（面向学生的自然语言讲解）、"
    "knowledge_points（1到3个字符串数组，本轮涉及的知识点）、"
    "suggestion（字符串，下一步学习建议）、"
    "diagram（可选字符串，涉及数据结构操作流程或复杂逻辑流程时，只提供 Mermaid 语法代码）。"
    "只输出 JSON，不要加 markdown 代码块或其他说明文字。"
)


def build_strategy_context_text(strategy) -> str:
    """构建下游 tutoring 生成用策略文本，输入内部策略对象，输出紧凑中文上下文。"""
    focus_points = getattr(strategy, "focus_points", None) or []
    focus_text = "、".join(focus_points) if focus_points else "当前问题"
    return "\n".join(
        [
            f"辅导策略：{strategy.strategy}",
            f"策略要求：{strategy.instruction}",
            f"策略关注点：{focus_text}",
        ]
    )


def _join_or_none(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "无"
