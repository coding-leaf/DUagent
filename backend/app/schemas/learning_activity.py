from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


LearningActivityType = Literal[
    "resource_view",
    "resource_study",
    "node_view",
    "node_practice_start",
    "node_practice_submit",
]


class LearningActivityCreate(BaseModel):
    course_id: str
    activity_type: LearningActivityType
    node_id: str | None = None
    node_name: str | None = None
    resource_id: str | None = None
    quiz_id: str | None = None
    duration_seconds: int | None = Field(default=None, ge=0, le=14400)
    occurred_at: datetime | None = None
    metadata: dict[str, Any] | None = None

    @field_validator("metadata")
    @classmethod
    def metadata_must_be_object(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is None:
            return value
        return {str(key): item for key, item in value.items()}


class LearningActivityCreated(BaseModel):
    id: str
