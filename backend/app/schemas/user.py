from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CourseItem(BaseModel):
    course_id: str
    course_name: str
    course_code: str


class UserInfo(BaseModel):
    id: str
    username: str
    email: str
    real_name: str = ""
    student_id: str = ""
    role: str
    major: str = ""
    grade: str = ""
    guidance_level: str = "L2"
    courses: list[CourseItem] = []
    created_at: str = ""


class UpdateUserRequest(BaseModel):
    real_name: Optional[str] = None
    student_id: Optional[str] = None
    major: Optional[str] = None
    grade: Optional[str] = None
    guidance_level: Optional[str] = None
