from typing import Literal, Optional

from pydantic import BaseModel, Field


class PersonalizedResourceGenerateRequest(BaseModel):
    course_id: str
    generate_type: Literal["quiz", "resource"] = "resource"
    source_type: Literal["quiz_wrong_answer", "manual", "ai_chat", "learning_effects"] = "manual"
    goal: Optional[str] = Field(default=None, min_length=1, max_length=2000)
    resource_preferences: Optional[list[str]] = None

    chapter: Optional[str] = None
    knowledge_point: Optional[str] = None

    # quiz 专用
    wrong_question_ids: Optional[list[str]] = None
    question_types: Optional[list[Literal["single_choice", "multi_choice"]]] = None
    count: int = Field(default=5, ge=1, le=20)
    difficulty: Optional[Literal["easy", "medium", "hard"]] = None

    # resource 专用
    resource_types: Optional[list[str]] = None
