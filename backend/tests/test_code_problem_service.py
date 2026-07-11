import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_normalize_code_problem_output_ignores_line_endings_and_trailing_whitespace():
    from app.services.code_problem_service import normalize_code_problem_output

    assert normalize_code_problem_output("first  \r\nsecond\n\n") == "first\nsecond"


def test_build_submission_result_hides_hidden_case_values():
    from app.services.code_problem_service import build_submission_result

    result = build_submission_result(
        total_cases=2,
        passed_cases=1,
        failed_case={
            "is_public": False,
            "stdin": "123 456\n",
            "expected_output": "579\n",
            "actual_output": "0\n",
        },
    )

    assert result["status"] == "wrong_answer"
    assert result["failed_case"] == {"visibility": "hidden", "message": "隐藏用例未通过"}
    assert "123" not in str(result)


def test_build_code_problem_submission_result_accepts_all_fixed_cases():
    from app.services.code_problem_service import build_code_problem_submission_result

    result = build_code_problem_submission_result(
        test_cases=[
            {"stdin": "1\n", "expected_output": "1", "is_public": True},
            {"stdin": "2\n", "expected_output": "2", "is_public": False},
        ],
        execution_results=[
            {"status": "success", "compile_status": "OK", "execution": {"stdout": "1\n"}},
            {"status": "success", "compile_status": "OK", "execution": {"stdout": "2\n"}},
        ],
    )

    assert result == {
        "status": "accepted",
        "passed_cases": 2,
        "total_cases": 2,
        "failed_case": None,
    }


def test_build_code_problem_submission_result_never_exposes_hidden_case_data():
    from app.services.code_problem_service import build_code_problem_submission_result

    result = build_code_problem_submission_result(
        test_cases=[
            {"stdin": "1\n", "expected_output": "1", "is_public": True},
            {"stdin": "987 654\n", "expected_output": "secret-value", "is_public": False},
        ],
        execution_results=[
            {"status": "success", "compile_status": "OK", "execution": {"stdout": "1\n"}},
            {"status": "success", "compile_status": "OK", "execution": {"stdout": "wrong\n"}},
        ],
    )

    assert result["status"] == "wrong_answer"
    assert result["passed_cases"] == 1
    assert result["failed_case"] == {"visibility": "hidden", "message": "隐藏用例未通过"}
    assert "987" not in str(result)
    assert "secret-value" not in str(result)


@pytest.mark.asyncio
async def test_create_validated_problem_rejects_duplicate_test_inputs_before_persisting():
    from app.schemas.code_problem import CodeProblemDraft, CodeProblemTestInput
    from app.services.code_problem_service import CodeProblemValidationError, validate_code_problem_draft

    draft = CodeProblemDraft(
        title="重复输入",
        statement="读取一个整数并输出它。",
        language="python",
        starter_code="print(input())\n",
        reference_solution="print(input())\n",
        test_inputs=[
            CodeProblemTestInput(stdin="1\n", is_public=True),
            CodeProblemTestInput(stdin="1\n", is_public=False),
        ],
    )

    with pytest.raises(CodeProblemValidationError, match="duplicate") as exc:
        await validate_code_problem_draft(draft, execute_case=None)

    assert exc.value.reason == "duplicate_test_input"


@pytest.mark.asyncio
async def test_validate_code_problem_runs_reference_solution_for_every_fixed_input():
    from app.schemas.code_problem import CodeProblemDraft, CodeProblemTestInput
    from app.services.code_problem_service import validate_code_problem_draft

    calls = []

    async def execute_case(code, language, stdin):
        calls.append((code, language, stdin))
        return {"status": "success", "compile_status": "OK", "execution": {"stdout": stdin}}

    draft = CodeProblemDraft(
        title="回显",
        statement="读取并输出输入。",
        language="python",
        starter_code="print(input())\n",
        reference_solution="print(input())\n",
        test_inputs=[
            CodeProblemTestInput(stdin="first\n", is_public=True),
            CodeProblemTestInput(stdin="second\n", is_public=False),
        ],
    )

    outputs = await validate_code_problem_draft(draft, execute_case=execute_case)

    assert calls == [(draft.reference_solution, "python", "first\n"), (draft.reference_solution, "python", "second\n")]
    assert outputs == ["first", "second"]


@pytest.mark.asyncio
async def test_validation_draft_does_not_publish_problem_or_personal_resource():
    from app.schemas.code_problem import CodeProblemDraft, CodeProblemTestInput
    from app.services.code_problem_service import validate_personal_problem_draft

    class FakeSession:
        def __init__(self):
            self.added = []

        def add(self, item):
            self.added.append(item)

        async def flush(self):
            return None

    async def execute_case(_code, _language, stdin):
        return {"status": "success", "compile_status": "OK", "execution": {"stdout": stdin}}

    draft = CodeProblemDraft(
        title="回显",
        statement="读取并输出输入。",
        language="python",
        starter_code="print(input())\n",
        reference_solution="print(input())\n",
        test_inputs=[
            CodeProblemTestInput(stdin="first\n", is_public=True),
            CodeProblemTestInput(stdin="second\n", is_public=False),
        ],
    )

    session = FakeSession()
    generation = await validate_personal_problem_draft(
        session,
        owner_user_id="student-1",
        course_id="course-1",
        conversation_id="conversation-1",
        run_id="run-1",
        draft=draft,
        execute_case=execute_case,
    )

    assert generation.status == "validated"
    assert generation.validation_report["status"] == "passed"
    assert generation.validation_report["public_case_count"] == 1
    assert generation.validation_report["hidden_case_count"] == 1
    assert len(session.added) == 1


@pytest.mark.asyncio
async def test_publish_code_problem_requires_independent_review_approval():
    from unittest.mock import AsyncMock, MagicMock

    from app.services.code_problem_service import (
        CodeProblemValidationError,
        publish_reviewed_personal_problem,
    )

    db = MagicMock()
    db.execute = AsyncMock()
    generation = MagicMock(
        status="validated",
        review_decision=None,
        validation_report={"status": "passed"},
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = generation
    db.execute.return_value = result

    with pytest.raises(CodeProblemValidationError, match="review_approval_required"):
        await publish_reviewed_personal_problem(db, generation_id="generation-1")
