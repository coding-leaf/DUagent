from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


PublicResourceType = Literal["lesson", "diagram", "example"]
ResourceFormat = Literal["markdown", "mermaid"]


class PublicResourceDraft(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    description: str = Field("", max_length=1000)
    tags: list[str] = Field(default_factory=list)
    diagram_kind: str | None = None


class PublicResourceAsset(BaseModel):
    title: str
    type: PublicResourceType
    format: ResourceFormat
    content: str
    description: str
    chapter: str
    knowledge_point: str
    tags: list[str]
    sources: list[dict[str, Any]]
    diagram_kind: str | None = None

    @model_validator(mode="after")
    def validate_diagram_shape(self):
        if self.type == "diagram" and not self.diagram_kind:
            raise ValueError("diagram_kind_required")
        if self.type != "diagram" and self.diagram_kind:
            raise ValueError("diagram_kind_only_for_diagram")
        return self
