import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models.code_problem import CodeProblem, CodeProblemTestCase
from app.models.others import AsyncTask
from app.services.code_problem_service import (
    CodeProblemValidationError,
    build_code_problem_submission_result,
)
from app.services.oj_execution_service import (
    OJExecutionError,
    execute_code_batch_in_oj,
    poll_code_batch_results_in_oj,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PreparedCodeProblemSubmission:
    task_id: str
    code: str
    language: str
    test_cases: list[dict[str, Any]]


async def prepare_code_problem_submission(
    db: AsyncSession,
    *,
    problem_id: str,
    owner_user_id: str,
    code: str,
) -> PreparedCodeProblemSubmission | None:
    if not code.strip():
        raise CodeProblemValidationError("submission code cannot be blank")
    problem_result = await db.execute(
        select(CodeProblem).where(
            CodeProblem.id == problem_id,
            CodeProblem.owner_user_id == owner_user_id,
            CodeProblem.status == "validated",
            CodeProblem.is_deleted == False,
        )
    )
    problem = problem_result.scalar_one_or_none()
    if problem is None:
        return None

    cases_result = await db.execute(
        select(CodeProblemTestCase)
        .where(CodeProblemTestCase.problem_id == problem.id)
        .order_by(CodeProblemTestCase.ordinal)
    )
    test_cases = [
        {
            "stdin": case.stdin,
            "expected_output": case.expected_output,
            "is_public": case.is_public,
        }
        for case in cases_result.scalars().all()
    ]
    if not test_cases:
        raise CodeProblemValidationError("validated problem has no test cases")

    task = AsyncTask(
        task_type="code_problem_judging",
        status="processing",
        progress=0,
        user_id=owner_user_id,
        course_id=problem.course_id,
    )
    db.add(task)
    await db.flush()
    return PreparedCodeProblemSubmission(
        task_id=task.id,
        code=code,
        language=problem.language,
        test_cases=test_cases,
    )


async def start_code_problem_submission(
    db: AsyncSession,
    *,
    problem_id: str,
    owner_user_id: str,
    code: str,
) -> str | None:
    submission = await prepare_code_problem_submission(
        db,
        problem_id=problem_id,
        owner_user_id=owner_user_id,
        code=code,
    )
    if submission is None:
        return None
    await db.commit()
    asyncio.create_task(run_code_problem_submission_background(submission))
    return submission.task_id


async def get_personal_code_problem_detail(
    db: AsyncSession,
    *,
    problem_id: str,
    owner_user_id: str,
) -> dict[str, Any] | None:
    problem_result = await db.execute(
        select(CodeProblem).where(
            CodeProblem.id == problem_id,
            CodeProblem.owner_user_id == owner_user_id,
            CodeProblem.status == "validated",
            CodeProblem.is_deleted == False,
        )
    )
    problem = problem_result.scalar_one_or_none()
    if problem is None:
        return None
    cases_result = await db.execute(
        select(CodeProblemTestCase)
        .where(
            CodeProblemTestCase.problem_id == problem.id,
            CodeProblemTestCase.is_public == True,
        )
        .order_by(CodeProblemTestCase.ordinal)
    )
    return {
        "id": problem.id,
        "course_id": problem.course_id,
        "title": problem.title,
        "statement": problem.statement,
        "language": problem.language,
        "starter_code": problem.starter_code,
        "public_cases": [
            {"stdin": case.stdin, "expected_output": case.expected_output}
            for case in cases_result.scalars().all()
        ],
    }


async def run_code_problem_submission_background(
    submission: PreparedCodeProblemSubmission,
) -> None:
    try:
        tokens = await execute_code_batch_in_oj(
            code=submission.code,
            language=submission.language,
            stdins=[case["stdin"] for case in submission.test_cases],
        )
        execution_results = await poll_code_batch_results_in_oj(tokens=tokens)
        result = build_code_problem_submission_result(
            test_cases=submission.test_cases,
            execution_results=execution_results,
        )
        await _complete_code_problem_submission_task(submission.task_id, result)
    except OJExecutionError as exc:
        await _fail_code_problem_submission_task(
            submission.task_id,
            error_code=exc.reason,
            error_message="判题服务暂时不可用，请稍后重新提交",
        )
    except Exception:
        logger.exception("Code problem judging failed task_id=%s", submission.task_id)
        await _fail_code_problem_submission_task(
            submission.task_id,
            error_code="internal_error",
            error_message="判题任务执行失败，请稍后重新提交",
        )


async def _complete_code_problem_submission_task(task_id: str, result: dict[str, Any]) -> None:
    async with async_session_factory() as db:
        await db.execute(
            update(AsyncTask)
            .where(AsyncTask.id == task_id)
            .values(
                status="completed",
                progress=100,
                result=result,
                completed_at=datetime.now(timezone.utc),
            )
        )
        await db.commit()


async def _fail_code_problem_submission_task(
    task_id: str,
    *,
    error_code: str,
    error_message: str,
) -> None:
    async with async_session_factory() as db:
        await db.execute(
            update(AsyncTask)
            .where(AsyncTask.id == task_id)
            .values(
                status="failed",
                error_code=error_code,
                error_message=error_message,
                completed_at=datetime.now(timezone.utc),
            )
        )
        await db.commit()
