from typing import Optional

from pydantic import BaseModel


class QuizSubmitRequest(BaseModel):
    quiz_id: str
    answers: list[dict]
    time_spent: int


class TutoringChatRequest(BaseModel):
    message: str
    course_id: Optional[str] = None
    conversation_id: Optional[str] = None


class ResourceGenerateRequest(BaseModel):
    course_id: str
