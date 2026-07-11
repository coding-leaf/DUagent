from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class WorkbenchChatRequest(BaseModel):
    user_id: str
    conversation_id: str | None = None
    message: str
    scope: str = "course"
    course_id: str | None = None
    catalog_id: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
