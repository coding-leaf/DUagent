from agent_service.core.ai import ChatMessage
from agent_service.memory.tutoring_retrieval import TutoringRetrievalContext
from agent_service.schemas.tutoring import TutoringChatRequest

TUTOR_REACT_SYSTEM_PROMPT = (
    "你是 EDUagent 的智能辅导 Agent，基于 ReActAgent 推理循环。"
    "回答必须贴合用户画像、课程范围和检索上下文，优先引导理解。"
    "如果提供了图谱节点，knowledge_points 应优先从这些节点名称中选择；"
    "回答应围绕最相关节点展开，不要机械覆盖所有节点。"
    "需要课程知识时调用 retrieve_course_knowledge 工具检索后再作答。"
    "完成时，把面向学生的讲解放入 model_text，本轮知识点放入 knowledge_points，"
    "下一步学习建议放入 suggestion；涉及数据结构操作或复杂逻辑流程时，"
    "diagram 给出 Mermaid 语法代码，否则留空。"
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
