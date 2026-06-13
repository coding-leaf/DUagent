from agent_service.core.ai import ChatMessage
from agent_service.memory.tutoring_retrieval import TutoringRetrievalContext
from agent_service.schemas.tutoring import TutoringChatRequest

TUTOR_REACT_SYSTEM_PROMPT = (
    "你是 EDUagent 的智能辅导 Agent，基于 ReActAgent 推理循环。"
    "回答必须贴合用户画像、课程范围和检索上下文，优先引导理解。"
    "请以 JSON 格式输出回复，JSON object 包含三个字段："
    "model_text（面向学生的自然语言讲解）、"
    "knowledge_points（1到3个字符串数组，本轮涉及的知识点）、"
    "suggestion（字符串，下一步学习建议）、"
    "diagram（可选字符串，涉及数据结构操作流程或复杂逻辑流程时，只提供 Mermaid 语法代码）。"
    "只输出 JSON，不要加 markdown 代码块或其他说明文字。"
)


def build_tutoring_messages(
    request: TutoringChatRequest,
    retrieval_context: TutoringRetrievalContext,
    strategy=None,
) -> list[ChatMessage]:
    """构建智能辅导模型消息，输入请求和检索上下文，输出 provider-neutral ChatMessage 列表。"""
    system_content = (
        "你是 EDUagent 的智能辅导 Agent。"
        "回答必须贴合用户画像、课程范围和检索上下文，优先引导理解，不直接替 Backend 写库。"
        "请以 JSON 格式输出回复，JSON object 包含三个字段："
        "model_text（面向学生的自然语言讲解）、"
        "knowledge_points（1到3个字符串数组，本轮涉及的知识点）、"
        "suggestion（字符串，下一步学习建议）、"
        "diagram（可选字符串，涉及数据结构操作流程或复杂逻辑流程时，只提供 Mermaid 语法代码）。"
        "只输出 JSON，不要加 markdown 代码块或其他说明文字。"
    )
    context_content = "\n".join(
        [
            f"用户ID：{request.user_id}",
            f"课程ID：{request.course_id or '全局'}",
            f"引导粒度：{request.user_profile.guidance_level}",
            f"薄弱点：{', '.join(request.user_profile.knowledge_weak) or '无'}",
            f"已掌握：{', '.join(request.user_profile.knowledge_mastered) or '无'}",
            f"会话摘要：{request.conversation_summary or '无'}",
            f"命中知识点：{_join_kg_nodes(retrieval_context.matched_kg_nodes)}",
            f"长期记忆：{_join_or_none(retrieval_context.user_memory_facts)}",
            f"课程知识：{_join_or_none(retrieval_context.course_knowledge_chunks)}",
            build_strategy_context_text(strategy) if strategy is not None else "",
        ]
    )
    messages = [
        ChatMessage(role="system", content=system_content),
        *[ChatMessage(role=item.role, content=item.content) for item in request.recent_messages],
        ChatMessage(role="user", content=f"{context_content}\n\n当前问题：{request.message}"),
    ]
    return messages


def build_strategy_selection_messages(
    request: TutoringChatRequest,
    retrieval_context: TutoringRetrievalContext,
) -> list[ChatMessage]:
    """构建策略选择模型消息，输入请求和检索上下文，输出只允许 JSON object 的 ChatMessage 列表。"""
    system_content = (
        "你是 EDUagent 的 tutoring StrategyAgent，只负责选择本轮辅导策略。"
        "可选 strategy 只有 guided_hint、direct_explanation、clarifying_question、worked_example。"
        "只输出 JSON object，不要输出 markdown 或额外说明。"
        '格式必须是 {"strategy": "...", "focus_points": ["..."], "reason": "..."}。'
    )
    user_content = "\n".join(
        [
            f"引导粒度：{request.user_profile.guidance_level}",
            f"当前问题：{request.message}",
            f"薄弱点：{', '.join(request.user_profile.knowledge_weak) or '无'}",
            f"已掌握：{', '.join(request.user_profile.knowledge_mastered) or '无'}",
            f"会话摘要：{request.conversation_summary or '无'}",
            f"命中知识点：{_join_kg_nodes(retrieval_context.matched_kg_nodes)}",
            f"长期记忆：{_join_or_none(retrieval_context.user_memory_facts)}",
            f"课程知识：{_join_or_none(retrieval_context.course_knowledge_chunks)}",
            "策略含义：guided_hint=分步骤提示；direct_explanation=直接解释概念；"
            "clarifying_question=只问一个澄清问题；worked_example=用相似例题或过程讲解。",
        ]
    )
    return [
        ChatMessage(role="system", content=system_content),
        ChatMessage(role="user", content=user_content),
    ]


def build_response_critic_messages(
    request: TutoringChatRequest,
    retrieval_context: TutoringRetrievalContext,
    model_response,
    strategy,
) -> list[ChatMessage]:
    """构建回复质量门禁消息，输入请求/上下文/候选回复/策略，输出只允许 JSON object 的 ChatMessage 列表。"""
    system_content = (
        "你是 EDUagent 的 tutoring ResponseCriticAgent，只负责判断候选回答是否可采纳。"
        "判断标准：回答不能为空，必须回应当前问题，必须贴合辅导策略和检索上下文。"
        "只输出 JSON object，不要输出 markdown 或额外说明。"
        '格式必须是 {"accepted": true, "reason": "..."}。'
    )
    user_content = "\n".join(
        [
            f"当前问题：{request.message}",
            f"引导粒度：{request.user_profile.guidance_level}",
            build_strategy_context_text(strategy),
            f"命中知识点：{_join_kg_nodes(retrieval_context.matched_kg_nodes)}",
            f"长期记忆：{_join_or_none(retrieval_context.user_memory_facts)}",
            f"课程知识：{_join_or_none(retrieval_context.course_knowledge_chunks)}",
            f"候选回答：{getattr(model_response, 'model_text', None) or '无'}",
            "候选知识点：" + (", ".join(getattr(model_response, "knowledge_point_names", []) or []) or "无"),
            f"候选建议：{getattr(model_response, 'suggestion_text', None) or '无'}",
        ]
    )
    return [
        ChatMessage(role="system", content=system_content),
        ChatMessage(role="user", content=user_content),
    ]


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

def _join_kg_nodes(nodes: list[dict]) -> str:
    return "、".join(str(n.get("name", "")) for n in nodes) if nodes else "无"
