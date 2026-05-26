from typing import Optional

from pydantic import BaseModel


class CourseCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None


class CourseJoinRequest(BaseModel):
    course_code: str
