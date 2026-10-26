from __future__ import annotations

from pydantic import BaseModel, Field


class PersonalizedResourceGenerationRequest(BaseModel):
    """Payload Backend sends when starting one personalized-resource task.

    Extra keys (for example `webhook_url`) are ignored: publication results are
    reported through the Backend internal API instead of a webhook callback.
    """

    task_id: str
    user_id: str
    course_id: str
    catalog_id: str | None = None
    course_title: str | None = None
    goal: str = Field(min_length=1, max_length=2000)
    chapter: str | None = None
    knowledge_point: str | None = None
    resource_types: list[str] = Field(default_factory=list)
    resource_preferences: list[str] = Field(default_factory=list)
    difficulty: str | None = None
    conversation_id: str | None = None
    source_type: str = "manual"
