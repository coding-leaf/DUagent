"""ReActAgent 工具集，提供课程知识检索工具供 tutoring ReAct 编排使用。"""

from agentscope.tool import Toolkit, ToolResponse
from agent_service.core.logging import get_logger

logger = get_logger(__name__)


def build_tutoring_toolkit(
    course_id: str | None,
    embedding_provider,
    vector_store,
    user_id: str | None = None,
    limit: int = 3,
) -> Toolkit:
    """构建 tutoring toolkit，闭包捕获 course_id / user_id / embedding_provider / vector_store / limit。

    模型只看到 retrieve_course_knowledge(query: str) 和 retrieve_user_memory(query: str) 接口。
    vector_store 由调用方注入，避免在模块内创建 Qdrant 客户端（会触发文件锁）。
    """

    async def retrieve_course_knowledge(query: str) -> ToolResponse:
        """检索课程知识库中与查询相关的内容。"""
        if not course_id:
            return _text_response("当前对话无指定课程知识库。")
        try:
            vectors = await embedding_provider.embed_texts([query])
            results = await vector_store.search_course_knowledge(
                course_id, vectors[0], limit=limit
            )
            logger.info("RAG retrieved %d chunks for course_id=%s", len(results) if results else 0, course_id)
            if not results:
                return _text_response("未找到相关课程知识。")
            text = "\n---\n".join(r.text for r in results if r.text)
            return _text_response(text)
        except Exception:
            return _text_response("课程知识检索暂时不可用。")

    async def retrieve_user_memory(query: str) -> ToolResponse:
        """检索用户长期记忆中与查询相关的事实。"""
        if not user_id:
            return _text_response("当前对话无用户记忆数据。")
        try:
            vectors = await embedding_provider.embed_texts([query])
            results = await vector_store.search_user_memory(
                user_id, vectors[0], limit=limit
            )
            if not results:
                return _text_response("未找到相关用户记忆。")
            text = "\n---\n".join(_truncate_chunk(r.text, 500) for r in results if r.text)
            return _text_response(text)
        except Exception:
            return _text_response("用户记忆检索暂时不可用。")

    toolkit = Toolkit()
    toolkit.register_tool_function(
        retrieve_course_knowledge,
        func_name="retrieve_course_knowledge",
        func_description="检索课程知识库中与查询相关的课程内容。输入自然语言查询关键词，返回匹配的知识片段。",
    )
    toolkit.register_tool_function(
        retrieve_user_memory,
        func_name="retrieve_user_memory",
        func_description="检索用户长期记忆中与查询相关的事实和知识点。输入自然语言查询关键词，返回匹配的用户记忆片段。",
    )
    return toolkit


def _truncate_chunk(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."


def _text_response(text: str) -> ToolResponse:
    return ToolResponse(content=[{"type": "text", "text": text}])
