from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CourseCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""


class CourseJoinRequest(BaseModel):
    course_code: str


class CourseSummary(BaseModel):
    id: str
    name: str
    description: str = ""
    course_code: str
    teacher_name: str = ""
    student_count: int = 0
    created_at: str = ""
