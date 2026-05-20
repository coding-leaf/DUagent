from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class StudentSummary(BaseModel):
    id: str
    username: str
    real_name: str = ""
    student_id: str = ""
    major: str = ""
    grade: str = ""
    joined_at: str = ""


class LearningOverview(BaseModel):
    evaluation_summary: Optional[dict] = None
    profile_summary: Optional[dict] = None
    path_progress: Optional[dict] = None
    quiz_stats: Optional[dict] = None
