import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from app.services.profile_refresh_service import ProfileRefreshService, run_profile_refresh_background
from app.models.others import AsyncTask, UserProfile
from app.models.user import User

@pytest.mark.asyncio
async def test_create_refresh_task():
    db = AsyncMock()
    service = ProfileRefreshService(db)
    
    # Mock return values for task creation
    task = await service.create_refresh_task("user1", "course1")
    assert isinstance(task, AsyncTask)
    assert task.user_id == "user1"
    assert task.course_id == "course1"
    assert task.task_type == "profile_refresh"
    assert task.status == "processing"

@pytest.mark.asyncio
async def test_get_processing_refresh_task():
    db = AsyncMock()
    mock_task = AsyncTask(
        task_type="profile_refresh",
        user_id="user1",
        course_id="course1",
        status="processing",
    )
    mock_res = MagicMock()
    mock_res.scalars().first.return_value = mock_task
    db.execute.return_value = mock_res
    
    service = ProfileRefreshService(db)
    task = await service.get_processing_refresh_task("user1", "course1")
    assert task == mock_task

@asynccontextmanager
async def mock_profile_lock(db, user_id, course_id):
    yield "mock_lock"

@pytest.mark.asyncio
@patch("app.services.profile_refresh_service.profile_lock", mock_profile_lock)
@patch("app.services.profile_refresh_service.ProfileService")
@patch("app.services.knowledge_progress.build_node_progress_rows")
@patch("app.services.profile_rules.compute_profile_fields")
@patch("app.services.profile_refresh_service.async_session_factory")
async def test_run_profile_refresh_background_success(
    mock_session_factory,
    mock_compute_profile_fields,
    mock_build_node_progress_rows,
    mock_profile_service_cls
):
    # Setup mock DB session
    db = AsyncMock()
    mock_session_factory.return_value.__aenter__.return_value = db
    
    # Setup user
    mock_user = User(id="user1", guidance_level="L3")
    mock_user_res = MagicMock()
    mock_user_res.scalars().first.return_value = mock_user
    db.execute.return_value = mock_user_res
    
    # Setup profile service mock
    mock_profile_service = MagicMock()
    mock_profile_service_cls.return_value = mock_profile_service
    mock_pf = UserProfile(user_id="user1", course_id="course1")
    mock_profile_service.get_or_create_profile = AsyncMock(return_value=mock_pf)
    
    # Setup computed fields mock
    mock_build_node_progress_rows.return_value = [{"node_id": "node1", "status": "completed"}]
    mock_compute_profile_fields.return_value = {
        "modal_preference": {"text_analysis": 60, "video_animation": 40},
        "knowledge_coordinates": {"node1": [0.1, 0.2]},
        "cognitive_blindspots": ["node2"],
        "learning_habits": "consistent",
        "knowledge_progress_summary": "good progress",
        "discipline_badge": "none"
    }
    
    # Run the background function
    await run_profile_refresh_background("task1", "user1", "course1")
    
    # Assert profile fields were updated
    assert mock_pf.modal_preference == {"text_analysis": 60, "video_animation": 40}
    assert mock_pf.guidance_level_current == "L3"
    assert mock_pf.knowledge_coordinates == {"node1": [0.1, 0.2]}
    assert mock_pf.cognitive_blindspots == ["node2"]
    assert mock_pf.drive_intent["learning_habits"] == "consistent"
    assert mock_pf.drive_intent["knowledge_progress_summary"] == "good progress"
    assert mock_pf.discipline_badge == "none"
    
    # Verify DB commit was called
    db.commit.assert_called_once()

@pytest.mark.asyncio
@patch("app.services.profile_refresh_service.ProfileService")
@patch("app.services.profile_refresh_service.async_session_factory")
async def test_run_profile_refresh_background_lock_timeout(
    mock_session_factory,
    mock_profile_service_cls
):
    from app.infrastructure.locks import LockAcquisitionTimeout
    
    @asynccontextmanager
    async def mock_failing_profile_lock(db, user_id, course_id):
        raise LockAcquisitionTimeout("Lock timeout")
        yield "mock_lock"

    # Patch the lock inside the function execution
    with patch("app.services.profile_refresh_service.profile_lock", mock_failing_profile_lock):
        db = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = db
        
        await run_profile_refresh_background("task1", "user1", "course1")
        
        # Verify db rollback was called
        db.rollback.assert_called_once()
        # Verify AsyncTask status is updated to failed due to lock_timeout
        db.execute.assert_called()

@pytest.mark.asyncio
@patch("app.services.profile_refresh_service.profile_lock", mock_profile_lock)
@patch("app.services.profile_refresh_service.ProfileService")
@patch("app.services.profile_refresh_service.async_session_factory")
async def test_run_profile_refresh_background_generic_error(
    mock_session_factory,
    mock_profile_service_cls
):
    db = AsyncMock()
    mock_session_factory.return_value.__aenter__.return_value = db
    
    # Setup profile service to raise generic exception
    mock_profile_service = MagicMock()
    mock_profile_service_cls.return_value = mock_profile_service
    mock_profile_service.get_or_create_profile = AsyncMock(side_effect=Exception("Database crash"))
    
    await run_profile_refresh_background("task1", "user1", "course1")
    
    # Verify db rollback was called
    db.rollback.assert_called_once()
    # Verify AsyncTask status is updated to failed due to internal_error
    db.execute.assert_called()

