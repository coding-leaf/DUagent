from typing import Literal

from pydantic import BaseModel, Field


class CodeProblemTestInput(BaseModel):
    stdin: str = Field(max_length=10000)
    is_public: bool


class CodeProblemDraft(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    statement: str = Field(min_length=1, max_length=10000)
    language: Literal["c", "cpp", "python"]
    starter_code: str = Field(max_length=20000)
    reference_solution: str = Field(min_length=1, max_length=30000)
    test_inputs: list[CodeProblemTestInput] = Field(min_length=2, max_length=8)
