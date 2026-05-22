from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from agent_service.schemas.profile import GuidanceLevel, ModalPreference


class TutoringUserProfile(BaseModel):
    guidance_level: GuidanceLevel = Field(..., description="引导粒度：L1 / L2 / L3")
    modal_preference: ModalPreference | dict[str, Any] | None = Field(None, description="模态偏好")
    knowledge_mastered: list[str] = Field(default_factory=list, description="已掌握知识点名称列表")
    knowledge_weak: list[str] = Field(default_factory=list, description="薄弱知识点名称列表")


class RecentMessage(BaseModel):
    role: Literal["user", "assistant"] = Field(..., description="user / assistant")
    content: str = Field(..., description="消息内容")
    meta: dict[str, Any] | None = Field(None, description="Backend 保存的消息元信息")


class TutoringChatRequest(BaseModel):
    user_id: str = Field(..., description="用户 ID")
    scope: Literal["course", "global"] = Field("course", description="course / global，默认 course")
    course_id: str | None = Field(None, description="课程 ID；scope=course 时必填，scope=global 时为空")
    conversation_id: str | None = Field(None, description="对话 ID（继续已有对话时传入）")
    message: str = Field(..., description="用户当前消息")
    user_profile: TutoringUserProfile = Field(
        ...,
        description="用户画像（由 Backend 从 SQL 组装）。注意：Qdrant 检索由 Agent Service 自行完成",
    )
    conversation_summary: str | None = Field(None, description="全局对话摘要（记忆压缩后生成）")
    recent_messages: list[RecentMessage] = Field(default_factory=list, description="最近 N 轮缓冲消息")

    @model_validator(mode="after")
    def validate_scope(self) -> "TutoringChatRequest":
        if self.scope == "course" and not self.course_id:
            raise ValueError("course_id is required when scope='course'")
        if self.scope == "global":
            self.course_id = None
        return self


class ChunkEvent(BaseModel):
    type: Literal["chunk"] = "chunk"
    content: str = Field(..., description="文本片段")


class DiagramEvent(BaseModel):
    type: Literal["diagram"] = "diagram"
    data: str = Field(..., description="Mermaid 语法或图表 JSON")


class KnowledgePoint(BaseModel):
    name: str = Field(..., description="知识点名称")
    chapter: str | None = Field(None, description="所属章节")
    mastery: float | None = Field(None, ge=0, le=100, description="掌握度")


class KnowledgePointsEvent(BaseModel):
    type: Literal["knowledge_points"] = "knowledge_points"
    knowledge_points: list[KnowledgePoint] = Field(default_factory=list, description="引用的知识点")


class SuggestedExercise(BaseModel):
    title: str = Field(..., description="题目")
    chapter: str | None = Field(None, description="所属章节")


class SuggestionEvent(BaseModel):
    type: Literal["suggestion"] = "suggestion"
    suggestion: str = Field(..., description="补充学习建议")
    suggested_exercises: list[SuggestedExercise] = Field(default_factory=list, description="相似例题")


class DoneEvent(BaseModel):
    type: Literal["done"] = "done"
    message_id: str = Field(..., description="本条回复的消息 ID")
    knowledge_points_used: list[KnowledgePoint] = Field(default_factory=list, description="回答中引用的知识点")
    suggested_exercises: list[SuggestedExercise] = Field(default_factory=list, description="推送的相似例题")


TutoringSSEEvent = ChunkEvent | DiagramEvent | KnowledgePointsEvent | SuggestionEvent | DoneEvent


class SSEEventMessage(BaseModel):
    data: TutoringSSEEvent = Field(..., description="SSE 事件负载")
