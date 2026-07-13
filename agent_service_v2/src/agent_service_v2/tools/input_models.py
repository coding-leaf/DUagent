from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ToolInputModel(BaseModel):
    @classmethod
    def tool_schema(cls) -> dict[str, Any]:
        schema = cls.model_json_schema()
        schema.pop("title", None)
        return schema


class ChoiceOptionInput(BaseModel):
    key: str = Field(min_length=1, max_length=8, description="Stable option key.")
    text: str = Field(min_length=1, max_length=1000, description="Option text.")


class ChoiceQuestionInput(BaseModel):
    type: Literal["single_choice", "multi_choice"] = Field(description="Choice question type.")
    content: str = Field(min_length=1, max_length=5000, description="Question stem.")
    options: list[ChoiceOptionInput] = Field(min_length=2, max_length=6, description="Answer options.")
    answer: str | list[str] = Field(description="One key for single choice; key list for multiple choice.")
    explanation: str = Field(default="", max_length=5000, description="Answer explanation.")
    difficulty: Literal["easy", "medium", "hard"] = Field(default="medium", description="Difficulty.")

    @model_validator(mode="after")
    def validate_answers(self):
        keys = [option.key for option in self.options]
        if len(keys) != len(set(keys)):
            raise ValueError("choice option keys must be unique")
        answers = [self.answer] if isinstance(self.answer, str) else self.answer
        if not answers or any(answer not in keys for answer in answers):
            raise ValueError("choice answers must reference existing option keys")
        if self.type == "single_choice" and len(answers) != 1:
            raise ValueError("single choice must have exactly one answer")
        if self.type == "multi_choice" and not isinstance(self.answer, list):
            raise ValueError("multi choice answer must be a list")
        return self


class PersonalChoiceQuizInput(ToolInputModel):
    title: str = Field(min_length=1, max_length=200, description="Practice card title.")
    chapter: str = Field(max_length=100, description="Shared course chapter.")
    knowledge_point: str = Field(max_length=100, description="Shared knowledge point.")
    questions: list[ChoiceQuestionInput] = Field(min_length=1, max_length=8, description="Complete questions.")


class PersonalCodeProblemInput(ToolInputModel):
    title: str = Field(min_length=1, max_length=200, description="Problem title.")
    statement: str = Field(min_length=1, max_length=20000, description="Markdown problem statement.")
    language: Literal["c", "cpp", "python", "java", "go", "javascript"] = Field(description="Runtime language.")
    starter_code: str = Field(default="", max_length=50000, description="Student starter code.")
    reference_solution: str = Field(min_length=1, max_length=50000, description="Private reference solution.")
    public_inputs: list[str] = Field(min_length=1, max_length=10, description="Visible stdin cases.")
    hidden_inputs: list[str] = Field(min_length=1, max_length=20, description="Private stdin cases.")


class LearningProgressInput(ToolInputModel):
    limit_nodes: int = Field(default=50, ge=1, le=100, description="Maximum progress nodes.")


class RecentAnswersInput(ToolInputModel):
    scope: Literal["course", "node", "knowledge_point"] = Field(description="Evidence scope.")
    node_id: str | None = Field(default=None, min_length=1, max_length=64, description="Required for node scope.")
    knowledge_point: str | None = Field(default=None, min_length=1, max_length=100, description="Required for knowledge-point scope.")
    limit: int = Field(default=10, ge=1, le=10, description="Maximum answer records.")
    only_wrong: bool = Field(default=True, description="Return only incorrect answers.")

    @model_validator(mode="after")
    def validate_scope_fields(self):
        if self.scope == "course" and (self.node_id or self.knowledge_point):
            raise ValueError("course scope cannot include node_id or knowledge_point")
        if self.scope == "node" and (not self.node_id or self.knowledge_point):
            raise ValueError("node scope requires only node_id")
        if self.scope == "knowledge_point" and (not self.knowledge_point or self.node_id):
            raise ValueError("knowledge_point scope requires only knowledge_point")
        return self


class OJExecutionInput(ToolInputModel):
    code: str = Field(min_length=1, max_length=100000, description="Complete source code.")
    language: Literal["c", "cpp", "python", "java", "go", "javascript"] = Field(description="Runtime language.")
    stdin: str = Field(default="", max_length=50000, description="Complete standard input.")


class ArtifactFileInput(ToolInputModel):
    filename: str = Field(min_length=1, max_length=200, description="Workspace artifact basename.")
    content: str = Field(min_length=1, max_length=200000, description="Complete artifact content.")
    artifact_type: Literal["Markdown", "Mermaid"] = Field(description="Artifact type matching the extension.")
    title: str = Field(default="", max_length=200, description="Student-facing title.")
