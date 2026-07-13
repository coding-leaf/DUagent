from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.quiz_service import _validate_submission_shape


def test_rejects_partial_submission_for_a_started_quiz():
    quiz = SimpleNamespace(total_count=2)

    with pytest.raises(HTTPException) as exc_info:
        _validate_submission_shape(
            quiz,
            [{"question_id": "q1", "answer": "A"}],
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["message"] == "请完成全部题目后再提交"
