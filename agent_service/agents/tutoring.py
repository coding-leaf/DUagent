import json
import re
from dataclasses import dataclass, field

from agent_service.core.logging import get_logger
from agent_service.memory.tutoring_retrieval import TutoringRetrievalContext, build_tutoring_retrieval_context
from agent_service.schemas.tutoring import (
    KnowledgePoint,
    SuggestedExercise,
    TutoringChatRequest,
    TutoringUserProfile,
)

_AGENT_RESULT_PATTERN = re.compile(r"<agent_result>(.*?)</agent_result>", re.DOTALL)
logger = get_logger(__name__)


@dataclass(frozen=True)
class TutoringModelResponse:
    model_text: str | None = None
    knowledge_point_names: list[str] = field(default_factory=list)
    suggestion_text: str | None = None
    diagram: str | None = None


@dataclass(frozen=True)
class TutoringGenerationResult:
    chunk_text: str
    knowledge_points: list[KnowledgePoint]
    suggestion_text: str
    suggested_exercises: list[SuggestedExercise]
    used_rule_fallback: bool
    diagram: str | None = None


def build_tutoring_generation_result(
    request: TutoringChatRequest,
    retrieval_context: TutoringRetrievalContext | None = None,
    model_response: TutoringModelResponse | None = None,
) -> TutoringGenerationResult:
    """整合 tutoring 运行态结果，输入请求、检索上下文和可选模型结果，输出统一内部结果对象。"""
    context = retrieval_context or build_tutoring_retrieval_context(request)
    response = model_response or TutoringModelResponse()
    knowledge_points = _build_knowledge_points(
        request,
        context,
        knowledge_point_names=response.knowledge_point_names,
    )
    suggested_exercises = _build_suggested_exercises(knowledge_points)
    focus_text = "、".join(item.name for item in knowledge_points) or "当前问题"
    chunk_text = response.model_text or _build_chunk_content(request, focus_text, context)
    suggestion = response.suggestion_text or f"建议先围绕{focus_text}复习核心概念，再完成一组相似练习。"
    return TutoringGenerationResult(
        chunk_text=chunk_text,
        knowledge_points=knowledge_points,
        suggestion_text=suggestion,
        suggested_exercises=suggested_exercises,
        used_rule_fallback=response.model_text is None,
        diagram=response.diagram,
    )


def parse_tutoring_model_response(model_output: str) -> TutoringModelResponse:
    """解析模型输出为 TutoringModelResponse，输入模型原始文本，输出结构化结果。

    解析链：json.loads 整段 JSON → <agent_result> 正则提取 → 原始文本作为 model_text。
    """
    if not model_output:
        return TutoringModelResponse()

    json_result = _try_parse_json_mode_output(model_output)
    if json_result is not None:
        return json_result

    fenced_json_result = _try_parse_markdown_json_output(model_output)
    if fenced_json_result is not None:
        return fenced_json_result

    match = _AGENT_RESULT_PATTERN.search(model_output)
    if match is None:
        return TutoringModelResponse(model_text=model_output.strip() or None)

    cleaned_text = _AGENT_RESULT_PATTERN.sub("", model_output).strip() or None
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return TutoringModelResponse(model_text=cleaned_text)

    return _build_response_from_payload(cleaned_text, payload)


def _try_parse_markdown_json_output(model_output: str) -> TutoringModelResponse | None:
    """从含 Markdown 围栏/散文的输出里提取结构化 JSON，避免泄露到前端正文。

    用括号配平定位首个"携带 model_text 且能解析"的 JSON object（即泄露到正文的完整
    结构化信封）；扫描时跳过字符串字面量内的括号与转义，因此 model_text 内嵌的
    ```c 代码块或花括号不会截断解析。仅作为 model_text 的信封时才接管，
    不抢占 <agent_result> 旁挂元数据（无 model_text）那条解析路径。
    """
    for payload in _iter_json_objects(model_output):
        if "model_text" not in payload:
            continue
        model_text = payload.get("model_text")
        clean_text = (
            model_text.strip()
            if isinstance(model_text, str) and model_text.strip()
            else None
        )
        return _build_response_from_payload(clean_text, payload)
    return None


def _iter_json_objects(text: str):
    """惰性产出文本中按括号配平、且能 json.loads 成功的 JSON object（dict）。"""
    i = 0
    n = len(text)
    while i < n:
        start = text.find("{", i)
        if start == -1:
            return
        end = _scan_balanced_object_end(text, start)
        if end is None:
            i = start + 1
            continue
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            yield parsed
        i = end + 1


def _scan_balanced_object_end(text: str, start: int) -> int | None:
    """从 start 处 '{' 起做括号配平，返回匹配 '}' 的索引；跳过字符串内括号与转义；未配平返回 None。"""
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
    return None


def _try_parse_json_mode_output(model_output: str) -> TutoringModelResponse | None:
    """尝试将整个输出解析为 JSON object，成功则提取字段，失败返回 None。"""
    stripped = model_output.strip()
    if not stripped.startswith("{"):
        return None
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    # 不校验 JSON schema：prompt 约定字段后，仅提取已知 key，未知 key 静默忽略
    model_text = payload.get("model_text")
    return _build_response_from_payload(
        model_text.strip() if isinstance(model_text, str) and model_text.strip() else None,
        payload,
    )


def _build_response_from_payload(model_text: str | None, payload: dict) -> TutoringModelResponse:
    """从已解析的 payload dict 提取 knowledge_points 和 suggestion。"""
    knowledge_point_names = payload.get("knowledge_points")
    suggestion_text = payload.get("suggestion")
    parsed_names = (
        [item.strip() for item in knowledge_point_names if isinstance(item, str) and item.strip()][:3]
        if isinstance(knowledge_point_names, list)
        else []
    )
    parsed_suggestion = suggestion_text.strip() if isinstance(suggestion_text, str) and suggestion_text.strip() else None
    diagram_text = payload.get("diagram")
    parsed_diagram = diagram_text.strip() if isinstance(diagram_text, str) and diagram_text.strip() else None
    return TutoringModelResponse(
        model_text=model_text,
        knowledge_point_names=parsed_names,
        suggestion_text=parsed_suggestion,
        diagram=parsed_diagram,
    )


def build_tutoring_response_from_metadata(metadata: dict) -> TutoringModelResponse:
    """把 ReActAgent structured_model 的 metadata dict 映射为 TutoringModelResponse。

    复用 _build_response_from_payload，因此 knowledge_points 截断到 3 个、字段做 strip。
    """
    model_text = metadata.get("model_text")
    clean_text = (
        model_text.strip()
        if isinstance(model_text, str) and model_text.strip()
        else None
    )
    return _build_response_from_payload(clean_text, metadata)


def _build_knowledge_points(
    request: TutoringChatRequest,
    context: TutoringRetrievalContext,
    knowledge_point_names: list[str] | None = None,
) -> list[KnowledgePoint]:
    # 1. 优先使用模型生成的 names
    if knowledge_point_names:
        return [
            KnowledgePoint(
                name=name,
                chapter=request.course_id if request.scope == "course" else None,
            )
            for name in knowledge_point_names[:3]
            if name
        ]
        
    # 2. 兜底 1: 真实图谱命中节点
    if context.matched_kg_nodes:
        return [
            KnowledgePoint(
                name=node.get("name", "未知节点"),
                chapter=node.get("chapter") or request.course_id if request.scope == "course" else None,
            )
            for node in context.matched_kg_nodes[:3]
        ]
        
    # 3. 兜底 2: Context 里自带的 Knowledge Points (旧逻辑兼容)
    if context.knowledge_points:
        return context.knowledge_points
        
    # 4. 兜底 3: Profile 薄弱/掌握项，或字面截断
    weak_points = request.user_profile.knowledge_weak
    mastered_points = request.user_profile.knowledge_mastered
    names = weak_points or mastered_points or [request.message[:20] or "当前问题"]
    mastery = 40.0 if weak_points else 70.0 if mastered_points else None
    return [
        KnowledgePoint(
            name=name,
            chapter=request.course_id if request.scope == "course" else None,
            mastery=mastery,
        )
        for name in names[:3]
        if name
    ]


def _build_suggested_exercises(knowledge_points: list[KnowledgePoint]) -> list[SuggestedExercise]:
    return [
        SuggestedExercise(title=f"{item.name} 巩固练习", chapter=item.chapter)
        for item in knowledge_points[:2]
    ]


def _build_chunk_content(request: TutoringChatRequest, focus_text: str, context: TutoringRetrievalContext) -> str:
    guidance_text = {
        "L1": "我会先拆成更小的步骤来讲。",
        "L2": "我会用关键步骤帮你串起来。",
        "L3": "我会直接给出核心思路和检查点。",
    }[request.user_profile.guidance_level]
    retrieval_text = ""
    if context.user_memory_facts or context.course_knowledge_chunks:
        retrieval_text = "结合长期记忆和课程知识，"
    summary_text = f"结合已有摘要：{request.conversation_summary}" if request.conversation_summary else "先基于你当前的问题分析。"
    return f"{retrieval_text}{guidance_text}{summary_text}这次重点看{focus_text}。"


def _build_retry_request(request: TutoringChatRequest, strategy) -> TutoringChatRequest:
    """构建重试请求：收紧 ReAct 输入，使回答围绕当前 focus_points。"""
    focus = "、".join(strategy.focus_points) if strategy and strategy.focus_points else "当前问题"
    tightened = f"{request.message}\n\n[请直接针对「{focus}」给出可用的辅导回答，不要偏题。]"
    return request.model_copy(update={"message": tightened})


async def generate_tutoring_sse_events(request, providers=None):
    """生成 tutoring SSE 事件流：Retrieval → ReAct → 重试一次（仅 LLM 无产出时）→ 输出。"""
    import json

    from agent_service.agents.tutoring_react_flow import generate_tutoring_react_response
    from agent_service.agents.tutoring_strategy import select_tutoring_strategy_by_rule
    from agent_service.core.ai import get_ai_providers
    from agent_service.memory.tutoring_retrieval import (
        build_tutoring_retrieval_context,
        build_tutoring_retrieval_context_with_ai,
    )
    from agent_service.memory.vector_store import QdrantVectorStore
    from agent_service.schemas.tutoring import (
        DiagramEvent,
        DoneEvent,
        KnowledgePointsEvent,
        SuggestionEvent,
    )

    if providers is None:
        providers = get_ai_providers()
    embedding = getattr(providers, "embedding", None)
    vector_store = None
    if embedding is not None:
        try:
            vector_store = QdrantVectorStore()
        except Exception:
            logger.warning("Failed to create QdrantVectorStore", exc_info=True)

    yield f"data: {json.dumps({'type': 'status', 'stage': 'retrieval', 'message': '正在检索课程知识...'}, ensure_ascii=False)}\n\n"

    reranker = getattr(providers, "reranker", None)
    try:
        if reranker is None:
            retrieval_context = await build_tutoring_retrieval_context_with_ai(
                request, embedding_provider=embedding, vector_store=vector_store
            )
        else:
            retrieval_context = await build_tutoring_retrieval_context_with_ai(
                request, embedding_provider=embedding, reranker_provider=reranker, vector_store=vector_store
            )
    except Exception:
        logger.warning("Tutoring retrieval failed, using fallback context", exc_info=True)
        retrieval_context = build_tutoring_retrieval_context(request)

    chat = getattr(providers, "chat", None)
    strategy = select_tutoring_strategy_by_rule(request, retrieval_context)
    yield f"data: {json.dumps({'type': 'status', 'stage': 'generation', 'message': '正在生成回答...'}, ensure_ascii=False)}\n\n"
    agent_path = "rule"
    output_source = "rule"
    quality_gate = "not_applicable"

    react_response = await generate_tutoring_react_response(
        request, retrieval_context, chat,
        embedding_provider=embedding,
        vector_store=vector_store,
        strategy=strategy,
    )
    if react_response is not None:
        agent_path = "react"
        output_source = "react"
        quality_gate = "accepted"

    if react_response is None and chat is not None:
        # 仅当 LLM 实际无产出（None）时重试一次，不再做相关性 Guard 拦截。
        retry_request = _build_retry_request(request, strategy)
        react_response = await generate_tutoring_react_response(
            retry_request, retrieval_context, chat,
            embedding_provider=embedding,
            vector_store=vector_store,
            strategy=strategy,
        )
        if react_response is not None:
            agent_path = "react_retry"
            output_source = "react_retry"
            quality_gate = "accepted_on_retry"

    runtime_result = build_tutoring_generation_result(
        request, retrieval_context=retrieval_context, model_response=react_response
    )
    logger.info(
        "agent_trace interface=tutoring/chat user_id=%s course_id=%s retrieval_hit_count=%d agent_path=%s quality_gate=%s output_source=%s",
        request.user_id,
        request.course_id,
        len(retrieval_context.user_memory_facts) + len(retrieval_context.course_knowledge_chunks),
        agent_path,
        quality_gate,
        output_source,
    )
    if runtime_result.chunk_text:
        yield f"data: {json.dumps({'type': 'chunk', 'content': runtime_result.chunk_text}, ensure_ascii=False)}\n\n"

    if runtime_result.diagram:
        yield f"data: {json.dumps(DiagramEvent(data=runtime_result.diagram).model_dump(), ensure_ascii=False)}\n\n"

    for event in [
        KnowledgePointsEvent(knowledge_points=runtime_result.knowledge_points),
        SuggestionEvent(suggestion=runtime_result.suggestion_text, suggested_exercises=runtime_result.suggested_exercises),
        DoneEvent(
            message_id=f"msg_{request.user_id}_{request.conversation_id or 'new'}",
            knowledge_points_used=runtime_result.knowledge_points,
            suggested_exercises=runtime_result.suggested_exercises,
        ),
    ]:
        yield f"data: {json.dumps(event.model_dump(), ensure_ascii=False)}\n\n"


__all__ = [
    "TutoringModelResponse",
    "TutoringGenerationResult",
    "build_tutoring_generation_result",
    "build_tutoring_response_from_metadata",
    "generate_tutoring_sse_events",
    "parse_tutoring_model_response",
]
