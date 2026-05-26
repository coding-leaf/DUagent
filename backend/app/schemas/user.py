from typing import Optional

from pydantic import BaseModel


class UpdateUserRequest(BaseModel):
    real_name: Optional[str] = None
    student_id: Optional[str] = None
    major: Optional[str] = None
    grade: Optional[str] = None
    guidance_level: Optional[str] = None
