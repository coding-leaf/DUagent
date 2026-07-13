from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.code_problem import CodeProblem, CodeProblemTestCase
from app.models.conversation import Conversation
from app.models.course import CourseEnrollment
from app.models.personalized_resource_generation import PersonalizedResourceGeneration
from app.services.personalized_resource_generation_service import link_published_generation
from app.schemas.code_problem import CodeProblemDraft
from app.services.content_safety import ensure_student_visible_content_safe


class CodeProblemValidationError(ValueError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class CreatedCodeProblem:
    problem: CodeProblem
    generation: PersonalizedResourceGeneration
    public_case_count: int
    hidden_case_count: int


async def validate_personal_problem_draft(
    db: AsyncSession,
    *,
    owner_user_id: str,
    course_id: str,
    conversation_id: str,
    run_id: str,
    draft: CodeProblemDraft,
    execute_case: Callable[[str, str, str], Awaitable[dict[str, Any]]],
) -> PersonalizedResourceGeneration:
    outputs = await validate_code_problem_draft(draft, execute_case=execute_case)
    public_case_count = sum(case.is_public for case in draft.test_inputs)
    generation = PersonalizedResourceGeneration(
        user_id=owner_user_id,
        course_id=course_id,
        conversation_id=conversation_id,
        run_id=run_id,
        source_type="ai_chat",
        goal=draft.statement,
        resource_type="validated_code_problem",
        status="validated",
        draft={
            **draft.model_dump(),
            "expected_outputs": outputs,
        },
        validation_report={
            "status": "passed",
            "validator": "oj_fixed_cases",
            "public_case_count": public_case_count,
            "hidden_case_count": len(draft.test_inputs) - public_case_count,
        },
    )
    db.add(generation)
    await db.flush()
    return generation


async def create_validated_personal_problem_from_ai_chat(
    db: AsyncSession,
    *,
    owner_user_id: str,
    course_id: str,
    conversation_id: str,
    run_id: str,
    draft: CodeProblemDraft,
    execute_case: Callable[[str, str, str], Awaitable[dict[str, Any]]],
) -> CreatedCodeProblem:
    await _verify_ai_chat_problem_scope(
        db,
        owner_user_id=owner_user_id,
        course_id=course_id,
        conversation_id=conversation_id,
    )
    generation = await validate_personal_problem_draft(
        db,
        owner_user_id=owner_user_id,
        course_id=course_id,
        conversation_id=conversation_id,
        run_id=run_id,
        draft=draft,
        execute_case=execute_case,
    )
    return await _create_problem_from_generation(db, generation)


async def _verify_ai_chat_problem_scope(
    db: AsyncSession,
    *,
    owner_user_id: str,
    course_id: str,
    conversation_id: str,
) -> None:
    conversation_result = await db.execute(
        select(Conversation.id).where(
            Conversation.id == conversation_id,
            Conversation.user_id == owner_user_id,
            Conversation.course_id == course_id,
            Conversation.is_deleted.is_(False),
        )
    )
    if conversation_result.scalar_one_or_none() is None:
        raise CodeProblemValidationError("conversation_ownership_check_failed")
    enrollment_result = await db.execute(
        select(CourseEnrollment.id).where(
            CourseEnrollment.student_id == owner_user_id,
            CourseEnrollment.course_id == course_id,
            CourseEnrollment.is_deleted.is_(False),
        )
    )
    if enrollment_result.scalar_one_or_none() is None:
        raise CodeProblemValidationError("course_enrollment_check_failed")


async def publish_reviewed_personal_problem(
    db: AsyncSession,
    *,
    generation_id: str,
    user_id: str | None = None,
    course_id: str | None = None,
) -> CreatedCodeProblem:
    query = select(PersonalizedResourceGeneration).where(
        PersonalizedResourceGeneration.id == generation_id,
        PersonalizedResourceGeneration.is_deleted.is_(False),
    )
    if user_id is not None:
        query = query.where(PersonalizedResourceGeneration.user_id == user_id)
    if course_id is not None:
        query = query.where(PersonalizedResourceGeneration.course_id == course_id)
    result = await db.execute(query.with_for_update())
    generation = result.scalar_one_or_none()
    if generation is None:
        raise CodeProblemValidationError("generation_not_found")
    if generation.resource_type != "validated_code_problem":
        raise CodeProblemValidationError("resource_type_mismatch")
    if generation.validation_report.get("status") != "passed":
        raise CodeProblemValidationError("validation_required")
    if generation.review_decision not in {"approved", "approved_with_advice"}:
        raise CodeProblemValidationError("review_approval_required")
    if generation.status not in {"approved", "approved_with_advice"}:
        raise CodeProblemValidationError("invalid_generation_status")

    return await _create_problem_from_generation(db, generation)


async def _create_problem_from_generation(
    db: AsyncSession,
    generation: PersonalizedResourceGeneration,
) -> CreatedCodeProblem:
    draft = generation.draft
    ensure_student_visible_content_safe({
        key: draft.get(key) for key in ("title", "statement", "starter_code")
    })
    test_inputs = draft["test_inputs"]
    outputs = draft["expected_outputs"]
    problem = CodeProblem(
        course_id=generation.course_id,
        owner_user_id=generation.user_id,
        origin="ai_chat",
        conversation_id=generation.conversation_id,
        run_id=generation.run_id,
        title=draft["title"],
        statement=draft["statement"],
        language=draft["language"],
        starter_code=draft["starter_code"],
        reference_solution=draft["reference_solution"],
        validation_report=generation.validation_report,
        create_by=generation.user_id,
    )
    db.add(problem)
    await db.flush()
    for ordinal, (test_case, output) in enumerate(zip(test_inputs, outputs), start=1):
        db.add(
            CodeProblemTestCase(
                problem_id=problem.id,
                ordinal=ordinal,
                stdin=test_case["stdin"],
                expected_output=output,
                is_public=test_case["is_public"],
            )
        )
    await link_published_generation(
        db,
        generation=generation,
        code_problem_id=problem.id,
    )
    generation.published_code_problem_id = problem.id
    generation.status = "published"
    await db.flush()
    return CreatedCodeProblem(
        problem=problem,
        generation=generation,
        public_case_count=generation.validation_report["public_case_count"],
        hidden_case_count=generation.validation_report["hidden_case_count"],
    )


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


def build_code_problem_submission_result(
    *,
    test_cases: list[dict[str, Any]],
    execution_results: list[dict[str, Any]],
) -> dict[str, Any]:
    if len(test_cases) != len(execution_results):
        raise ValueError("test case and execution result counts must match")

    passed_cases = 0
    for test_case, execution_result in zip(test_cases, execution_results):
        execution = execution_result.get("execution") or {}
        actual_output = normalize_code_problem_output(str(execution.get("stdout") or ""))
        is_accepted = (
            execution_result.get("status") == "success"
            and execution_result.get("compile_status") == "OK"
            and actual_output == normalize_code_problem_output(test_case["expected_output"])
        )
        if is_accepted:
            passed_cases += 1
            continue

        result = build_submission_result(
            total_cases=len(test_cases),
            passed_cases=passed_cases,
            failed_case={
                "is_public": test_case["is_public"],
                "stdin": test_case["stdin"],
                "expected_output": test_case["expected_output"],
                "actual_output": actual_output,
            },
        )
        execution_status = execution_result.get("status")
        if execution_status and execution_status != "success":
            result["status"] = execution_status
            if execution_status == "compilation_error":
                result["compile_output"] = execution_result.get("compile_output") or ""
        return result

    return build_submission_result(
        total_cases=len(test_cases),
        passed_cases=passed_cases,
        failed_case=None,
    )


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
            raise CodeProblemValidationError("duplicate_test_input")
        seen_inputs.add(test_case.stdin)
        public_count += int(test_case.is_public)
        hidden_count += int(not test_case.is_public)
    if public_count == 0 or hidden_count == 0:
        raise CodeProblemValidationError("public_and_hidden_test_inputs_required")
    if execute_case is None:
        return []
    outputs: list[str] = []
    for test_case in draft.test_inputs:
        result = await execute_case(draft.reference_solution, draft.language, test_case.stdin)
        execution = result.get("execution") or {}
        if result.get("status") != "success" or result.get("compile_status") != "OK":
            raise CodeProblemValidationError("reference_solution_execution_failed")
        outputs.append(normalize_code_problem_output(str(execution.get("stdout") or "")))
    return outputs
