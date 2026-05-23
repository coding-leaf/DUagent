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


def generate_tutoring_events(
    request: TutoringChatRequest,
    retrieval_context: TutoringRetrievalContext | None = None,
) -> list[ChunkEvent | KnowledgePointsEvent | SuggestionEvent | DoneEvent]:
    """生成规则版智能辅导 SSE 事件，输入对话请求，输出结构化事件序列。"""
    context = retrieval_context or build_tutoring_retrieval_context(request)
    knowledge_points = _build_knowledge_points(request, context)
    suggested_exercises = _build_suggested_exercises(knowledge_points)
    focus_text = "、".join(item.name for item in knowledge_points) or "当前问题"

    chunk = ChunkEvent(content=_build_chunk_content(request, focus_text, context))
    knowledge_event = KnowledgePointsEvent(knowledge_points=knowledge_points)
    suggestion_event = SuggestionEvent(
        suggestion=f"建议先围绕{focus_text}复习核心概念，再完成一组相似练习。",
        suggested_exercises=suggested_exercises,
    )
    done_event = DoneEvent(
        message_id=_build_message_id(request),
        knowledge_points_used=knowledge_points,
        suggested_exercises=suggested_exercises,
    )
    return [chunk, knowledge_event, suggestion_event, done_event]


def _build_knowledge_points(request: TutoringChatRequest, context: TutoringRetrievalContext) -> list[KnowledgePoint]:
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
    "generate_tutoring_events",
    "TutoringChatRequest",
    "TutoringUserProfile",
    "UserProfile",
]
