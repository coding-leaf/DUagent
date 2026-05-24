import json
import re
from dataclasses import dataclass, field

from agent_service.memory.tutoring_retrieval import TutoringRetrievalContext, build_tutoring_retrieval_context
from agent_service.schemas.tutoring import (
    ChunkEvent,
    DiagramEvent,
    DoneEvent,
    KnowledgePoint,
    KnowledgePointsEvent,
    RecentMessage,
    SuggestedExercise,
    SuggestionEvent,
    TutoringChatRequest,
    TutoringUserProfile,
)

UserProfile = TutoringUserProfile
ChatRequest = TutoringChatRequest
_AGENT_RESULT_PATTERN = re.compile(r"<agent_result>(.*?)</agent_result>", re.DOTALL)


@dataclass(frozen=True)
class TutoringModelResponse:
    model_text: str | None = None
    knowledge_point_names: list[str] = field(default_factory=list)
    suggestion_text: str | None = None


@dataclass(frozen=True)
class TutoringGenerationResult:
    chunk_text: str
    knowledge_points: list[KnowledgePoint]
    suggestion_text: str
    suggested_exercises: list[SuggestedExercise]
    used_rule_fallback: bool


def generate_tutoring_events(
    request: TutoringChatRequest,
    retrieval_context: TutoringRetrievalContext | None = None,
    model_text: str | None = None,
    knowledge_point_names: list[str] | None = None,
    suggestion_text: str | None = None,
) -> list[ChunkEvent | KnowledgePointsEvent | SuggestionEvent | DoneEvent]:
    """生成规则版智能辅导 SSE 事件，输入对话请求，输出结构化事件序列。"""
    result = build_tutoring_generation_result(
        request,
        retrieval_context=retrieval_context,
        model_response=TutoringModelResponse(
            model_text=model_text,
            knowledge_point_names=knowledge_point_names or [],
            suggestion_text=suggestion_text,
        ),
    )
    chunk = ChunkEvent(content=result.chunk_text)
    knowledge_event = KnowledgePointsEvent(knowledge_points=result.knowledge_points)
    suggestion_event = SuggestionEvent(
        suggestion=result.suggestion_text,
        suggested_exercises=result.suggested_exercises,
    )
    done_event = DoneEvent(
        message_id=_build_message_id(request),
        knowledge_points_used=result.knowledge_points,
        suggested_exercises=result.suggested_exercises,
    )
    return [chunk, knowledge_event, suggestion_event, done_event]


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
    )


def parse_tutoring_model_response(model_output: str) -> TutoringModelResponse:
    if not model_output:
        return TutoringModelResponse()

    match = _AGENT_RESULT_PATTERN.search(model_output)
    if match is None:
        return TutoringModelResponse(model_text=model_output.strip() or None)

    cleaned_text = _AGENT_RESULT_PATTERN.sub("", model_output).strip() or None
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return TutoringModelResponse(model_text=cleaned_text)

    knowledge_point_names = payload.get("knowledge_points")
    suggestion_text = payload.get("suggestion")
    parsed_names = (
        [item.strip() for item in knowledge_point_names if isinstance(item, str) and item.strip()][:3]
        if isinstance(knowledge_point_names, list)
        else []
    )
    parsed_suggestion = suggestion_text.strip() if isinstance(suggestion_text, str) and suggestion_text.strip() else None
    return TutoringModelResponse(
        model_text=cleaned_text,
        knowledge_point_names=parsed_names,
        suggestion_text=parsed_suggestion,
    )


def _build_knowledge_points(
    request: TutoringChatRequest,
    context: TutoringRetrievalContext,
    knowledge_point_names: list[str] | None = None,
) -> list[KnowledgePoint]:
    if knowledge_point_names:
        return [
            KnowledgePoint(
                name=name,
                chapter=request.course_id if request.scope == "course" else None,
            )
            for name in knowledge_point_names[:3]
            if name
        ]
    if context.knowledge_points:
        return context.knowledge_points
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


def _build_message_id(request: TutoringChatRequest) -> str:
    conversation_part = request.conversation_id or "new"
    return f"msg_{request.user_id}_{conversation_part}"

__all__ = [
    "ChatRequest",
    "ChunkEvent",
    "DiagramEvent",
    "DoneEvent",
    "KnowledgePoint",
    "KnowledgePointsEvent",
    "RecentMessage",
    "SuggestedExercise",
    "SuggestionEvent",
    "TutoringRetrievalContext",
    "TutoringModelResponse",
    "TutoringGenerationResult",
    "build_tutoring_generation_result",
    "generate_tutoring_events",
    "parse_tutoring_model_response",
    "TutoringChatRequest",
    "TutoringUserProfile",
    "UserProfile",
]
