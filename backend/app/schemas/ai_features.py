from typing import Optional

from pydantic import BaseModel


class ProfileInitializeRequest(BaseModel):
    course_id: str
    answers: dict = {}


class ProfileQuestionnaire(BaseModel):
    guidance_level: Optional[str] = None
    modal_preference: Optional[list[str]] = None
    learning_goal: Optional[str] = None


class RefreshRequest(BaseModel):
    course_id: str

