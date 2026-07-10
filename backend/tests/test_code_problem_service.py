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

    with pytest.raises(CodeProblemValidationError, match="duplicate"):
        await validate_code_problem_draft(draft, execute_case=None)
