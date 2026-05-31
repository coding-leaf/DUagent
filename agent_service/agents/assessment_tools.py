"""ReActAgent 工具集，提供辅助工具供出题 ReAct 编排使用。"""

import json
from agentscope.tool import Toolkit, ToolResponse
from agent_service.core.logging import get_logger

logger = get_logger(__name__)
_SUPPORTED_QUESTION_TYPES = {"single_choice", "multi_choice", "code", "short_answer"}


def build_assessment_toolkit(
    course_id: str | None,
    embedding_provider,
    vector_store,
    limit: int = 5,
) -> Toolkit:
    """构建 assessment toolkit，闭包捕获 course_id / embedding_provider / vector_store。"""

    async def retrieve_course_knowledge(query: str) -> ToolResponse:
        """检索课程知识库中与查询相关的内容。"""
        if not course_id:
            return ToolResponse(content=[{"text": "当前无指定课程知识库。"}])
        if embedding_provider is None or vector_store is None:
            return ToolResponse(content=[{"text": "知识检索暂时不可用。"}])
        try:
            vectors = await embedding_provider.embed_texts([query])
            results = await vector_store.search_course_knowledge(
                course_id, vectors[0], limit=limit
            )
            logger.info("RAG retrieved %d chunks for course_id=%s (assessment tools)", len(results) if results else 0, course_id)
            if not results:
                return ToolResponse(content=[{"text": "未找到相关课程知识。"}])
            text = "\n---\n".join(_truncate_chunk(r.text, 1000) for r in results if r.text)
            return ToolResponse(content=[{"text": text}])
        except Exception as e:
            logger.warning("课程知识检索失败 (assessment tools)", exc_info=True)
            return ToolResponse(content=[{"text": f"检索出错: {e}"}])

    def validate_question_format(questions_json_str: str) -> ToolResponse:
        """校验生成的题目 JSON 数组格式是否正确。"""
        return ToolResponse(content=[{"text": _validate_question_format_content(questions_json_str)}])

    toolkit = Toolkit()
    toolkit.register_tool_function(
        retrieve_course_knowledge,
        func_name="retrieve_course_knowledge",
        func_description="检索课程知识库中与查询相关的课程内容。在出题前，必须先调用此工具获取相关知识点的内容。",
    )
    toolkit.register_tool_function(
        validate_question_format,
        func_name="validate_question_format",
        func_description="校验生成的题目数据格式。输入为 JSON 字符串形式的题目数组。在最终输出题目之前，建议调用此工具确保格式正确。",
    )
    return toolkit


def _truncate_chunk(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."


def _validate_question_format_content(questions_json_str: str) -> str:
    try:
        data = json.loads(questions_json_str)
    except Exception as e:
        return f"JSON 解析失败: {e}"
    if not isinstance(data, list):
        return "错误：根节点必须是 JSON 数组。"

    errors = []
    for index, question in enumerate(data):
        number = index + 1
        if not isinstance(question, dict):
            errors.append(f"第 {number} 题必须是 JSON 对象。")
            continue
        qtype = question.get("type")
        if qtype not in _SUPPORTED_QUESTION_TYPES:
            errors.append(f"第 {number} 题 type 错误，不支持 '{qtype}'。")
            continue
        options = question.get("options", [])
        if qtype in {"single_choice", "multi_choice"}:
            if not isinstance(options, list) or len(options) == 0:
                errors.append(f"第 {number} 题必须包含选项 options 数组。")
        elif options not in ([], None):
            errors.append(f"第 {number} 题非选择题 options 必须为空数组。")

    if errors:
        return "校验失败:\n" + "\n".join(errors)
    return "校验通过，格式合法。"
