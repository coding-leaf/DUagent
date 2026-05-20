from typing import Optional

from pydantic import BaseModel


class EvaluationRefreshRequest(BaseModel):
    course_id: str


class ProfileInitializeRequest(BaseModel):
    course_id: str


class ProfileRefreshRequest(BaseModel):
    course_id: str


class LearningPathRefreshRequest(BaseModel):
    course_id: str
