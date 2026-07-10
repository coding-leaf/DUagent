from collections.abc import Awaitable, Callable
from typing import Any

from app.schemas.code_problem import CodeProblemDraft


class CodeProblemValidationError(ValueError):
    pass


def normalize_code_problem_output(value: str) -> str:
    normalized_lines = value.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while normalized_lines and not normalized_lines[-1].strip():
        normalized_lines.pop()
    return "\n".join(line.rstrip() for line in normalized_lines)


def build_submission_result(
    *,
    total_cases: int,
    passed_cases: int,
    failed_case: dict[str, Any] | None,
) -> dict[str, Any]:
    if failed_case is None:
        return {
            "status": "accepted",
            "passed_cases": passed_cases,
            "total_cases": total_cases,
            "failed_case": None,
        }
    safe_case = (
        {
            "visibility": "public",
            "input": failed_case["stdin"],
            "expected_output": failed_case["expected_output"],
            "actual_output": failed_case["actual_output"],
        }
        if failed_case["is_public"]
        else {"visibility": "hidden", "message": "隐藏用例未通过"}
    )
    return {
        "status": "wrong_answer",
        "passed_cases": passed_cases,
        "total_cases": total_cases,
        "failed_case": safe_case,
    }


async def validate_code_problem_draft(
    draft: CodeProblemDraft,
    *,
    execute_case: Callable[[str, str, str], Awaitable[dict[str, Any]]] | None,
) -> None:
    seen_inputs: set[str] = set()
    public_count = 0
    hidden_count = 0
    for test_case in draft.test_inputs:
        if test_case.stdin in seen_inputs:
            raise CodeProblemValidationError("duplicate test input")
        seen_inputs.add(test_case.stdin)
        public_count += int(test_case.is_public)
        hidden_count += int(not test_case.is_public)
    if public_count == 0 or hidden_count == 0:
        raise CodeProblemValidationError("at least one public and one hidden test input are required")
    if execute_case is None:
        return
