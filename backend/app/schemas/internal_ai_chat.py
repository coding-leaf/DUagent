from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

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


class ChoiceOptionDraft(BaseModel):
    key: str = Field(min_length=1, max_length=8)
    text: str = Field(min_length=1, max_length=1000)


class ChoiceQuestionDraft(BaseModel):
    type: Literal["single_choice", "multi_choice"]
    content: str = Field(min_length=1, max_length=5000)
    options: list[ChoiceOptionDraft] = Field(min_length=2, max_length=6)
    answer: str | list[str]
    explanation: str = Field(default="", max_length=5000)
    difficulty: Literal["easy", "medium", "hard"] = "medium"

    @model_validator(mode="after")
    def validate_answer_keys(self):
        option_keys = [option.key for option in self.options]
        if len(option_keys) != len(set(option_keys)):
            raise ValueError("choice option keys must be unique")
        answers = [self.answer] if isinstance(self.answer, str) else self.answer
        if not answers or any(answer not in option_keys for answer in answers):
            raise ValueError("choice answers must reference existing option keys")
        if self.type == "single_choice" and len(answers) != 1:
            raise ValueError("single choice must have exactly one answer")
        if self.type == "multi_choice" and not isinstance(self.answer, list):
            raise ValueError("multi choice answer must be a list")
        return self


class PersonalChoiceQuizCreateRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=32)
    course_id: str = Field(min_length=1, max_length=32)
    conversation_id: str = Field(min_length=1, max_length=32)
    run_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    chapter: str = Field(default="", max_length=100)
    knowledge_point: str = Field(default="", max_length=100)
    questions: list[ChoiceQuestionDraft] = Field(min_length=1, max_length=8)
