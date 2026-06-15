from typing import Literal, Optional

from pydantic import BaseModel


class PersonalizedResourceGenerateRequest(BaseModel):
    course_id: str
    generate_type: Literal["quiz", "resource"]
    source_type: Literal["quiz_wrong_answer", "manual"]

    chapter: Optional[str] = None
    knowledge_point: Optional[str] = None

    # quiz 专用
    wrong_question_ids: Optional[list[str]] = None
    question_types: Optional[list[str]] = None
    count: int = 5
    difficulty: Optional[str] = None

    # resource 专用
    resource_types: Optional[list[str]] = None
