from agent_service.core.ai import ChatMessage
from agent_service.memory.tutoring_retrieval import TutoringRetrievalContext
from agent_service.schemas.tutoring import TutoringChatRequest


def build_tutoring_messages(
    request: TutoringChatRequest,
    retrieval_context: TutoringRetrievalContext,
) -> list[ChatMessage]:
    """构建智能辅导模型消息，输入请求和检索上下文，输出 provider-neutral ChatMessage 列表。"""
    system_content = (
        "你是 EDUagent 的智能辅导 Agent。"
        "回答必须贴合用户画像、课程范围和检索上下文，优先引导理解，不直接替 Backend 写库。"
    )
    context_content = "\n".join(
        [
            f"用户ID：{request.user_id}",
            f"课程ID：{request.course_id or '全局'}",
            f"引导粒度：{request.user_profile.guidance_level}",
            f"薄弱点：{', '.join(request.user_profile.knowledge_weak) or '无'}",
            f"已掌握：{', '.join(request.user_profile.knowledge_mastered) or '无'}",
            f"会话摘要：{request.conversation_summary or '无'}",
            f"长期记忆：{_join_or_none(retrieval_context.user_memory_facts)}",
            f"课程知识：{_join_or_none(retrieval_context.course_knowledge_chunks)}",
        ]
    )
    messages = [
        ChatMessage(role="system", content=system_content),
        *[ChatMessage(role=item.role, content=item.content) for item in request.recent_messages],
        ChatMessage(role="user", content=f"{context_content}\n\n当前问题：{request.message}"),
    ]
    return messages


def _join_or_none(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "无"
