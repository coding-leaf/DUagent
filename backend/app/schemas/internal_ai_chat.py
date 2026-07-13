from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.code_problem import CodeProblemDraft


class LearningProgressRequest(BaseModel):
    user_id: str
    course_id: str
    limit_nodes: int = Field(default=50, ge=1, le=100)


class RecentAnswersRequest(BaseModel):
    user_id: str
    course_id: str
    scope: Literal["course", "node", "knowledge_point"]
    node_id: str | None = None
    knowledge_point: str | None = None
    limit: int = Field(default=10, ge=1, le=10)
    only_wrong: bool = True

    @model_validator(mode="after")
    def validate_scope_fields(self):
        if self.scope == "course" and (self.node_id or self.knowledge_point):
            raise ValueError("course scope cannot include node_id or knowledge_point")
        if self.scope == "node" and (not self.node_id or self.knowledge_point):
            raise ValueError("node scope requires only node_id")
        if self.scope == "knowledge_point" and (not self.knowledge_point or self.node_id):
            raise ValueError("knowledge_point scope requires only knowledge_point")
        return self


class LearnerProfileReadRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=32)
    course_id: str = Field(min_length=1, max_length=32)


class DialogueProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(min_length=1, max_length=32)
    course_id: str = Field(min_length=1, max_length=32)
    conversation_id: str = Field(min_length=1, max_length=32)
    run_id: str = Field(min_length=1, max_length=80)
    learning_goal: str | None = Field(default=None, min_length=1, max_length=500)
    resource_preferences: list[
        Literal["text_reading", "chart_logic", "code_practice", "practice_reinforcement"]
    ] | None = Field(default=None, min_length=1, max_length=4)
    guidance_level: Literal["L1", "L2", "L3"] | None = None
    custom_instruction: str | None = Field(default=None, min_length=1, max_length=1000)
    learning_habits: dict[str, str] | None = None

    @model_validator(mode="after")
    def validate_stable_facts(self):
        facts = (
            self.learning_goal,
            self.resource_preferences,
            self.guidance_level,
            self.custom_instruction,
            self.learning_habits,
        )
        if not any(value is not None for value in facts):
            raise ValueError("at least one stable profile fact is required")
        if self.resource_preferences and len(set(self.resource_preferences)) != len(
            self.resource_preferences
        ):
            raise ValueError("resource preferences must be unique")
        if self.learning_habits is not None:
            if not self.learning_habits or len(self.learning_habits) > 10:
                raise ValueError("learning habits must contain 1 to 10 entries")
            if any(
                not key.strip()
                or len(key) > 50
                or not value.strip()
                or len(value) > 200
                for key, value in self.learning_habits.items()
            ):
                raise ValueError("learning habit keys or values are invalid")
        return self


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


class PersonalChoiceQuizDraft(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    chapter: str = Field(max_length=100)
    knowledge_point: str = Field(max_length=100)
    questions: list[ChoiceQuestionDraft] = Field(min_length=1, max_length=8)


class PersonalPracticePrepareRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=32)
    course_id: str = Field(min_length=1, max_length=32)
    conversation_id: str = Field(min_length=1, max_length=32)
    run_id: str = Field(min_length=1, max_length=80)
    practice_type: Literal["choice_quiz", "code_problem"]
    choice_quiz: PersonalChoiceQuizDraft | None = None
    code_problem: CodeProblemDraft | None = None

    @model_validator(mode="after")
    def validate_practice_draft(self):
        if self.practice_type == "choice_quiz" and (
            self.choice_quiz is None or self.code_problem is not None
        ):
            raise ValueError("choice_quiz requires only choice_quiz draft")
        if self.practice_type == "code_problem" and (
            self.code_problem is None or self.choice_quiz is not None
        ):
            raise ValueError("code_problem requires only code_problem draft")
        return self


class PersonalPracticeDeliveryRequest(BaseModel):
    generation_id: str = Field(min_length=1, max_length=32)
    user_id: str = Field(min_length=1, max_length=32)
    course_id: str = Field(min_length=1, max_length=32)
