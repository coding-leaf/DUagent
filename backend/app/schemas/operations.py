from typing import Optional

from pydantic import BaseModel


class QuizSubmitRequest(BaseModel):
    quiz_id: str
    answers: list[dict]
    time_spent: int


class QuizGenerateRequest(BaseModel):
    course_id: str
    chapter: Optional[str] = None
    knowledge_point: Optional[str] = None
    question_types: Optional[list[str]] = None
    count: int = 5
    difficulty: Optional[str] = None
    personalized: bool = True


class TutoringChatRequest(BaseModel):
    message: str
    scope: str = "course"
    course_id: Optional[str] = None
    conversation_id: Optional[str] = None


class ResourceGenerateRequest(BaseModel):
    course_id: str
    chapter: Optional[str] = None
    knowledge_point: Optional[str] = None
    resource_types: Optional[list[str]] = None


class CatalogResourceGenerateRequest(BaseModel):
    chapter: Optional[str] = None
    knowledge_point: Optional[str] = None
    resource_types: Optional[list[str]] = None
