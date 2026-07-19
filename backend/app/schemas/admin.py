from typing import Literal, Optional

from pydantic import BaseModel


class AdminUpdateUserRequest(BaseModel):
    username: Optional[str] = None
    real_name: Optional[str] = None
    student_id: Optional[str] = None
    role: Optional[str] = None
    major: Optional[str] = None
    grade: Optional[str] = None
    new_password: Optional[str] = None


class CreateRegistrationCodeRequest(BaseModel):
    role: Literal["student", "teacher"]
