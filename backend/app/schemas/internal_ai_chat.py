from pydantic import BaseModel, Field, field_validator

from app.schemas.code_problem import CodeProblemDraft


class LearningProgressRequest(BaseModel):
    user_id: str
    course_id: str
    limit_nodes: int = Field(default=50, ge=1, le=100)


class RecentAnswersRequest(BaseModel):
    user_id: str
    course_id: str
    node_id: str | None = None
    knowledge_point: str | None = None
    limit: int = Field(default=10, ge=1)
    only_wrong: bool = True

    @field_validator("limit")
    @classmethod
    def cap_limit(cls, value: int) -> int:
        return min(int(value), 10)


class OJEvaluationRequest(BaseModel):
    code: str
    language: str
    stdin: str = ""


class PersonalCodeProblemCreateRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=32)
    course_id: str = Field(min_length=1, max_length=32)
    conversation_id: str = Field(min_length=1, max_length=32)
    run_id: str = Field(min_length=1, max_length=80)
    draft: CodeProblemDraft
