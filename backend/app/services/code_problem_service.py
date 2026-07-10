from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.code_problem import CodeProblem, CodeProblemTestCase
from app.models.others import UserPersonalizedResource
from app.schemas.code_problem import CodeProblemDraft


class CodeProblemValidationError(ValueError):
    pass


@dataclass(frozen=True)
class CreatedCodeProblem:
    problem: CodeProblem
    public_case_count: int
    hidden_case_count: int


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
) -> list[str]:
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
        return []
    outputs: list[str] = []
    for test_case in draft.test_inputs:
        result = await execute_case(draft.reference_solution, draft.language, test_case.stdin)
        execution = result.get("execution") or {}
        if result.get("status") != "success" or result.get("compile_status") != "OK":
            raise CodeProblemValidationError("reference solution execution failed")
        outputs.append(normalize_code_problem_output(str(execution.get("stdout") or "")))
    return outputs


async def create_validated_personal_problem(
    db: AsyncSession,
    *,
    owner_user_id: str,
    course_id: str,
    conversation_id: str,
    run_id: str,
    draft: CodeProblemDraft,
    execute_case: Callable[[str, str, str], Awaitable[dict[str, Any]]],
) -> CreatedCodeProblem:
    outputs = await validate_code_problem_draft(draft, execute_case=execute_case)
    public_case_count = sum(case.is_public for case in draft.test_inputs)
    hidden_case_count = len(draft.test_inputs) - public_case_count
    problem = CodeProblem(
        course_id=course_id,
        owner_user_id=owner_user_id,
        origin="ai_chat",
        conversation_id=conversation_id,
        run_id=run_id,
        title=draft.title,
        statement=draft.statement,
        language=draft.language,
        starter_code=draft.starter_code,
        reference_solution=draft.reference_solution,
        validation_report={
            "status": "validated",
            "public_case_count": public_case_count,
            "hidden_case_count": hidden_case_count,
        },
        create_by=owner_user_id,
    )
    db.add(problem)
    await db.flush()
    for ordinal, (test_case, output) in enumerate(zip(draft.test_inputs, outputs), start=1):
        db.add(
            CodeProblemTestCase(
                problem_id=problem.id,
                ordinal=ordinal,
                stdin=test_case.stdin,
                expected_output=output,
                is_public=test_case.is_public,
            )
        )
    db.add(
        UserPersonalizedResource(
            user_id=owner_user_id,
            course_id=course_id,
            code_problem_id=problem.id,
            source_type="ai_chat",
        )
    )
    return CreatedCodeProblem(
        problem=problem,
        public_case_count=public_case_count,
        hidden_case_count=hidden_case_count,
    )
