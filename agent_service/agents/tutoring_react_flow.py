"""ReActAgent tutoring 编排胶水层，负责将 request + retrieval_context 转换为 ReActAgent 输入并解析输出。"""

from agent_service.agents.tutoring import (
    build_tutoring_response_from_metadata,
    parse_tutoring_model_response,
    TutoringModelResponse,
)
from agent_service.agents.tutoring_react import TutorReActAgent
from agent_service.agents.tutoring_tools import build_tutoring_toolkit
from agent_service.core.ai import ChatProvider, EmbeddingProvider
from agent_service.core.logging import get_logger
from agent_service.memory.tutoring_retrieval import TutoringRetrievalContext
from agent_service.prompts.tutoring import build_strategy_context_text, _join_or_none
from agent_service.schemas.tutoring import TutoringChatRequest

logger = get_logger(__name__)


async def generate_tutoring_react_response(
    request: TutoringChatRequest,
    retrieval_context: TutoringRetrievalContext,
    chat_provider: ChatProvider,
    embedding_provider: EmbeddingProvider | None = None,
    vector_store=None,
    strategy=None,
) -> TutoringModelResponse | None:
    """用 ReActAgent 生成辅导回答，输入请求、检索上下文、chat/embedding provider、vector store，输出模型响应或 None（降级）。

    embedding_provider 和 vector_store 均非 None 时挂载 retrieve_course_knowledge toolkit。
    vector_store 由调用方注入，避免模块内重复创建 Qdrant 客户端导致文件锁冲突。
    """
    if not (hasattr(chat_provider, "model") and hasattr(chat_provider, "formatter")):
        return None
    try:
        user_message = _build_react_user_message(request, retrieval_context, strategy=strategy)
        toolkit = None
        if embedding_provider is not None and vector_store is not None:
            # 课程知识按 catalog_id 入库；缺省回落 course_id 兼容旧路径。
            knowledge_course_id = getattr(request, "catalog_id", None) or request.course_id
            toolkit = build_tutoring_toolkit(
                course_id=knowledge_course_id,
                embedding_provider=embedding_provider,
                vector_store=vector_store,
                user_id=request.user_id,
            )
        agent = TutorReActAgent(
            chat_model=chat_provider.model,
            formatter=chat_provider.formatter,
            toolkit=toolkit,
            custom_instruction=request.user_profile.custom_instruction,
        )
        model_output = await agent.generate(user_message)
        if model_output is None:
            logger.info("Tutoring ReAct degraded: no model output, falling back")
            return None
        logger.info("Tutoring ReAct succeeded")
        if isinstance(model_output, dict):
            return build_tutoring_response_from_metadata(model_output)
        return parse_tutoring_model_response(model_output)
    except Exception:
        logger.warning("ReActAgent tutoring failed, degrading to chat JSON path", exc_info=True)
        return None


def _build_react_user_message(
    request: TutoringChatRequest,
    retrieval_context: TutoringRetrievalContext,
    strategy=None,
) -> str:
    profile = request.user_profile
    # weak chunk 上浮：含 knowledge_weak 词条的 chunk 优先排前（稳定排序，不丢弃任何 chunk）
    weak_terms = {w.strip() for w in (profile.knowledge_weak or []) if w.strip()}
    chunks = list(retrieval_context.course_knowledge_chunks)
    if weak_terms:
        chunks.sort(key=lambda c: 0 if any(t in c for t in weak_terms) else 1)
    retrieval_context = retrieval_context.model_copy(update={"course_knowledge_chunks": chunks})

    context_lines = [
        f"用户ID：{request.user_id}",
        f"课程ID：{request.course_id or '全局'}",
        f"引导粒度：{profile.guidance_level}",
        f"薄弱点：{', '.join(profile.knowledge_weak) or '无'}",
        f"已掌握：{', '.join(profile.knowledge_mastered) or '无'}",
        f"会话摘要：{request.conversation_summary or '无'}",
        f"长期记忆：{_join_items(retrieval_context.user_memory_facts)}",
        f"课程知识：{_join_items(retrieval_context.course_knowledge_chunks)}",
        f"图谱节点：{_join_or_none([str(n.get('chapter', '')) + ' - ' + str(n.get('name', '')) for n in retrieval_context.matched_kg_nodes])}",
    ]
    if strategy is not None:
        context_lines.append(build_strategy_context_text(strategy))
    parts = ["\n".join(context_lines)]
    if request.recent_messages:
        recent_lines = [
            "最近对话（短期上下文）：",
            "当前问题提到刚才、上文或之前时，优先依据最近对话回答；课程知识只作为补充。",
        ]
        for msg in request.recent_messages:
            recent_lines.append(f"[{msg.role}] {msg.content}")
        parts.append("\n".join(recent_lines))
    parts.append(f"当前问题：{request.message}")
    return "\n\n".join(parts)


def _join_items(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "无"
