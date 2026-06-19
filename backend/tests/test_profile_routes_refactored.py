import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@patch("app.api.v1.profile.ProfileService")
@patch("app.api.v1.profile._verify_course_enrollment")
def test_get_profile_route(mock_verify, mock_service_cls):
    mock_service = AsyncMock()
    mock_service.get_or_create_profile.return_value = AsyncMock()
    mock_service_cls.return_value = mock_service
    
    with patch("app.api.v1.profile.get_current_user") as mock_user:
        mock_user.return_value = AsyncMock(id="u123", role="student")
        response = client.get("/api/v1/profile?course_id=c456")
        assert response.status_code == 200

@patch("app.api.v1.profile.ProfileService")
@patch("app.api.v1.profile._verify_course_enrollment")
def test_initialize_profile_route(mock_verify, mock_service_cls):
    mock_service = AsyncMock()
    mock_service.initialize_profile.return_value = AsyncMock()
    mock_service_cls.return_value = mock_service
    
    with patch("app.api.v1.profile.get_current_user") as mock_user:
        mock_user.return_value = AsyncMock(id="u123", role="student")
        response = client.post(
            "/api/v1/profile/initialize",
            json={"course_id": "c456", "answers": {"learning_goal": "casual"}}
        )
        assert response.status_code == 200

@patch("app.api.v1.profile.ProfileDialogueService")
@patch("app.api.v1.profile.agent_client")
@patch("app.api.v1.profile._verify_course_enrollment")
def test_dialogue_update_profile_route(mock_verify, mock_agent_client, mock_dialogue_service_cls):
    mock_dialogue_service = AsyncMock()
    mock_dialogue_service.update_from_dialogue.return_value = AsyncMock()
    mock_dialogue_service_cls.return_value = mock_dialogue_service
    
    mock_agent_client.post_json = AsyncMock(return_value={"profile": {"learning_goal": "exam_sprint"}})
    
    with patch("app.api.v1.profile.get_current_user") as mock_user:
        mock_user.return_value = AsyncMock(id="u123", role="student")
        response = client.post(
            "/api/v1/profile/dialogue-update",
            json={"course_id": "c456", "message": "I need to prepare for my exam."}
        )
        assert response.status_code == 200

@patch("app.api.v1.profile.ProfileService")
@patch("app.api.v1.profile._verify_course_enrollment")
def test_update_learning_goal_route(mock_verify, mock_service_cls):
    mock_service = AsyncMock()
    mock_service.update_learning_goal.return_value = AsyncMock()
    mock_service_cls.return_value = mock_service
    
    with patch("app.api.v1.profile.get_current_user") as mock_user:
        mock_user.return_value = AsyncMock(id="u123", role="student")
        response = client.post(
            "/api/v1/profile/update-goal",
            json={"course_id": "c456", "learning_goal": "exam_sprint"}
        )
        assert response.status_code == 200

@patch("app.api.v1.profile.ProfileService")
@patch("app.api.v1.profile._verify_course_enrollment")
def test_update_custom_instruction_route(mock_verify, mock_service_cls):
    mock_service = AsyncMock()
    mock_service.update_custom_instruction.return_value = AsyncMock()
    mock_service_cls.return_value = mock_service
    
    with patch("app.api.v1.profile.get_current_user") as mock_user:
        mock_user.return_value = AsyncMock(id="u123", role="student")
        response = client.post(
            "/api/v1/profile/update-instruction",
            json={"course_id": "c456", "custom_instruction": "use diagrams"}
        )
        assert response.status_code == 200

@patch("app.api.v1.profile.ProfileRefreshService")
@patch("app.api.v1.profile._verify_course_enrollment")
@patch("app.api.v1.profile.run_profile_refresh_background")
def test_refresh_profile_route(mock_run_bg, mock_verify, mock_refresh_service_cls):
    mock_refresh_service = AsyncMock()
    
    # Test case 1: Active task exists
    mock_active_task = MagicMock()
    mock_active_task.id = "t123"
    mock_active_task.status = "processing"
    mock_active_task.create_time = datetime.now(timezone.utc)
    mock_refresh_service.get_processing_refresh_task.return_value = mock_active_task
    
    # Test case 2: No active task, creates a new one
    mock_new_task = MagicMock()
    mock_new_task.id = "t456"
    mock_new_task.status = "processing"
    mock_new_task.create_time = datetime.now(timezone.utc)
    mock_refresh_service.create_refresh_task.return_value = mock_new_task
    
    mock_refresh_service_cls.return_value = mock_refresh_service
    
    with patch("app.api.v1.profile.get_current_user") as mock_user:
        mock_user.return_value = AsyncMock(id="u123", role="student")
        
        # 1. When task exists
        response = client.post("/api/v1/profile/refresh?course_id=c456")
        assert response.status_code == 200
        assert response.json()["data"]["task_id"] == "t123"
        
        # 2. When no task exists
        mock_refresh_service.get_processing_refresh_task.return_value = None
        response = client.post("/api/v1/profile/refresh?course_id=c456")
        assert response.status_code == 202
        assert response.json()["data"]["task_id"] == "t456"
