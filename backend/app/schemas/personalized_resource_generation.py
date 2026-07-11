from typing import Literal

from pydantic import BaseModel, Field


class PersonalizedDraftCreateRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=32)
    course_id: str = Field(min_length=1, max_length=32)
    source_type: str = Field(min_length=1, max_length=30)
    goal: str = Field(min_length=1, max_length=2000)
    resource_type: str = Field(min_length=1, max_length=40)
    draft: dict
    conversation_id: str | None = None
    run_id: str | None = None


class PersonalizedGenerationScopeRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=32)
    course_id: str = Field(min_length=1, max_length=32)
    resource_kind: Literal["resource", "code_problem"] = "resource"


class PersonalizedValidationRequest(PersonalizedGenerationScopeRequest):
    report: dict


class PersonalizedReviewRequest(PersonalizedGenerationScopeRequest):
    decision: Literal["approved", "approved_with_advice", "rejected"]
    hard_failures: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    summary: str = ""
