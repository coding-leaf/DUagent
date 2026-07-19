from pydantic import BaseModel, Field, field_validator

from app.services.code_language import normalize_code_language


class CodeProblemTestInput(BaseModel):
    stdin: str = Field(max_length=10000)
    is_public: bool


class CodeProblemDraft(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    statement: str = Field(min_length=1, max_length=10000)
    language: str
    starter_code: str = Field(max_length=20000)
    reference_solution: str = Field(min_length=1, max_length=30000)
    test_inputs: list[CodeProblemTestInput] = Field(min_length=2, max_length=8)

    @field_validator("language", mode="before")
    @classmethod
    def normalize_language(cls, value: str) -> str:
        return normalize_code_language(value)


class CodeProblemSubmissionRequest(BaseModel):
    code: str = Field(min_length=1, max_length=20000)
