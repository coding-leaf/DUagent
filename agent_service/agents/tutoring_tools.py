"""ReActAgent 工具集，提供课程知识检索工具供 tutoring ReAct 编排使用。"""

from agentscope.tool import Toolkit, ToolResponse


def build_tutoring_toolkit(
    course_id: str | None,
    embedding_provider,
    vector_store,
    limit: int = 3,
) -> Toolkit:
    """构建 tutoring toolkit，闭包捕获 course_id / embedding_provider / vector_store / limit。

    模型只看到 retrieve_course_knowledge(query: str) 接口。
    vector_store 由调用方注入，避免在模块内创建 Qdrant 客户端（会触发文件锁）。
    """

    async def retrieve_course_knowledge(query: str) -> ToolResponse:
        """检索课程知识库中与查询相关的内容。"""
        if not course_id:
            return ToolResponse(content=[{"text": "当前对话无指定课程知识库。"}])
        try:
            vectors = await embedding_provider.embed_texts([query])
            results = await vector_store.search_course_knowledge(
                course_id, vectors[0], limit=limit
            )
            if not results:
                return ToolResponse(content=[{"text": "未找到相关课程知识。"}])
            text = "\n---\n".join(r.text for r in results if r.text)
            return ToolResponse(content=[{"text": text}])
        except Exception:
            return ToolResponse(content=[{"text": "课程知识检索暂时不可用。"}])

    toolkit = Toolkit()
    toolkit.register_tool_function(
        retrieve_course_knowledge,
        func_name="retrieve_course_knowledge",
        func_description="检索课程知识库中与查询相关的课程内容。输入自然语言查询关键词，返回匹配的知识片段。",
    )
    return toolkit
