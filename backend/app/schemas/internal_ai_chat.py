from pydantic import BaseModel, Field, field_validator


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
