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
    "TutoringChatRequest",
    "TutoringUserProfile",
    "UserProfile",
]
