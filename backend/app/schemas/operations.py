from typing import Literal, Optional

from pydantic import BaseModel, Field


class QuizSubmitRequest(BaseModel):
    quiz_id: str
    answers: list[dict]
    time_spent: int


class QuizGenerateRequest(BaseModel):
    course_id: str
    chapter: Optional[str] = None
    knowledge_point: Optional[str] = None
    question_types: list[Literal["single_choice", "multi_choice"]] = Field(
        default_factory=lambda: ["single_choice", "multi_choice"]
    )
    count: int = Field(default=5, ge=1, le=20)
    difficulty: Optional[Literal["easy", "medium", "hard"]] = None
    personalized: bool = True


class TutoringChatRequest(BaseModel):
    message: str
    action: str = "chat"  # "chat" | "edit" | "regenerate"
    scope: str = "course"
    course_id: Optional[str] = None
    conversation_id: Optional[str] = None
    active_kg_nodes: list[dict] = Field(default_factory=list, description="当前课程绑定资源库的 Active KG 节点精简列表")


class ResourceGenerateRequest(BaseModel):
    course_id: str
    chapter: Optional[str] = None
    knowledge_point: Optional[str] = None
    resource_types: Optional[list[str]] = None


class CatalogResourceGenerateRequest(BaseModel):
    chapter: Optional[str] = None
    knowledge_point: Optional[str] = None
    resource_types: Optional[list[str]] = None
