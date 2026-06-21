import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


@patch("app.api.v1.evaluation.EvaluationService")
def test_get_evaluation_route(mock_service_cls):
    mock_service = AsyncMock()
    mock_service.get_evaluation.return_value = {
        "course_id": "c456",
        "progress_table": {"columns": [], "rows": []},
        "mastery_table": {"columns": [], "rows": []},
        "resource_usage_table": {"columns": [], "rows": []},
        "node_progress": [],
        "summary_text": "Good progress",
        "generated_at": "2026-06-20T20:00:00Z"
    }
    mock_service_cls.return_value = mock_service

    from app.api.deps import get_current_user
    app.dependency_overrides[get_current_user] = lambda: AsyncMock(id="u123", role="student")
    try:
        response = client.get("/api/v1/evaluation?course_id=c456")
        assert response.status_code == 200
        assert response.json()["code"] == 200
        assert response.json()["data"]["course_id"] == "c456"
        assert response.json()["data"]["summary_text"] == "Good progress"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@patch("app.api.v1.evaluation.EvaluationService")
def test_refresh_evaluation_route(mock_service_cls):
    mock_service = AsyncMock()
    mock_service.refresh_evaluation.return_value = {"task_id": "t123"}
    mock_service_cls.return_value = mock_service

    from app.api.deps import get_current_user
    app.dependency_overrides[get_current_user] = lambda: AsyncMock(id="u123", role="student")
    try:
        response = client.post(
            "/api/v1/evaluation/refresh",
            json={"course_id": "c456"}
        )
        assert response.status_code == 202
        assert response.json()["code"] == 202
        assert response.json()["data"]["task_id"] == "t123"
    finally:
        app.dependency_overrides.pop(get_current_user, None)

