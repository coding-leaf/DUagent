from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.others import Evaluation
from app.services import evaluation_service
from app.services.evaluation_service import EvaluationService


def test_evaluation_model_persists_structured_insight():
    assert "insight" in Evaluation.__table__.c


def test_facts_version_is_stable_for_equivalent_payloads():
    build_version = getattr(evaluation_service, "_build_facts_version", None)
    assert callable(build_version), "evaluation payload needs a stable facts version"

    first = {
        "user_id": "student-1",
        "course_id": "course-1",
        "quiz_results": [{"knowledge_point": "指针", "score": 75.0}],
    }
    second = {
        "quiz_results": [{"score": 75.0, "knowledge_point": "指针"}],
        "course_id": "course-1",
        "user_id": "student-1",
    }

    assert build_version(first) == build_version(second)
    assert build_version(first).startswith("sha256:")


@pytest.mark.asyncio
@patch("app.services.evaluation_service.build_node_progress_rows", new_callable=AsyncMock)
async def test_get_evaluation_returns_persisted_insight(mock_progress):
    mock_progress.return_value = []
    db = AsyncMock()
    result = MagicMock()
    result.scalars().first.return_value = SimpleNamespace(
        course_id="course-1",
        progress_table=None,
        mastery_table=None,
        resource_usage_table=None,
        summary_text="summary",
        insight={"facts_version": "facts-v7", "weak_points": []},
        generated_at=None,
    )
    db.execute.return_value = result

    response = await EvaluationService(db).get_evaluation("student-1", "course-1")

    assert response["insight"] == {
        "facts_version": "facts-v7",
        "weak_points": [],
    }
