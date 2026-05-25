"""ReActAgent tutoring 编排胶水层，负责将 request + retrieval_context 转换为 ReActAgent 输入并解析输出。"""

from agent_service.agents.tutoring import parse_tutoring_model_response, TutoringModelResponse
from agent_service.agents.tutoring_react import TutorReActAgent
from agent_service.core.ai import ChatProvider
from agent_service.core.logging import get_logger
from agent_service.memory.tutoring_retrieval import TutoringRetrievalContext
from agent_service.schemas.tutoring import TutoringChatRequest

logger = get_logger(__name__)


async def generate_tutoring_react_response(
    request: TutoringChatRequest,
    retrieval_context: TutoringRetrievalContext,
    chat_provider: ChatProvider,
) -> TutoringModelResponse | None:
    """用 ReActAgent 生成辅导回答，输入请求、检索上下文和 chat provider，输出模型响应或 None（降级）。"""
    if not (hasattr(chat_provider, "model") and hasattr(chat_provider, "formatter")):
        return None
    try:
        user_message = _build_react_user_message(request, retrieval_context)
        agent = TutorReActAgent(
            chat_model=chat_provider.model,
            formatter=chat_provider.formatter,
        )
        model_output = await agent.generate(user_message)
        if model_output is None:
            return None
        return parse_tutoring_model_response(model_output)
    except Exception:
        logger.warning("ReActAgent tutoring failed, degrading to chat JSON path", exc_info=True)
        return None


def _build_react_user_message(
    request: TutoringChatRequest,
    retrieval_context: TutoringRetrievalContext,
) -> str:
    profile = request.user_profile
    context_lines = [
        f"用户ID：{request.user_id}",
        f"课程ID：{request.course_id or '全局'}",
        f"引导粒度：{profile.guidance_level}",
        f"薄弱点：{', '.join(profile.knowledge_weak) or '无'}",
        f"已掌握：{', '.join(profile.knowledge_mastered) or '无'}",
        f"会话摘要：{request.conversation_summary or '无'}",
        f"长期记忆：{_join_items(retrieval_context.user_memory_facts)}",
        f"课程知识：{_join_items(retrieval_context.course_knowledge_chunks)}",
    ]
    parts = ["\n".join(context_lines)]
    for msg in request.recent_messages:
        parts.append(f"[{msg.role}] {msg.content}")
    parts.append(f"当前问题：{request.message}")
    return "\n\n".join(parts)


def _join_items(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "无"
