import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager
from app.models.user import User
from app.models.course import Course, CourseEnrollment
from app.models.others import UserProfile
from app.services.profile_service import ProfileService

@asynccontextmanager
async def mock_profile_lock(db, user_id, course_id):
    yield "mock_lock"

@pytest.mark.asyncio
async def test_get_or_create_profile_existing():
    db = AsyncMock()
    mock_pf = UserProfile(user_id="user1", course_id="course1", is_deleted=False)
    mock_res = MagicMock()
    mock_res.scalars().first.return_value = mock_pf
    db.execute.return_value = mock_res
    
    service = ProfileService(db)
    pf = await service.get_or_create_profile("user1", "course1")
    assert pf == mock_pf

@pytest.mark.asyncio
async def test_get_or_create_profile_new():
    db = AsyncMock()
    db.add = MagicMock()
    mock_res = MagicMock()
    mock_res.scalars().first.return_value = None
    db.execute.return_value = mock_res
    
    service = ProfileService(db)
    pf = await service.get_or_create_profile("user1", "course1")
    
    assert pf.user_id == "user1"
    assert pf.course_id == "course1"
    db.add.assert_called_once_with(pf)

@pytest.mark.asyncio
async def test_get_or_create_profile_deleted():
    db = AsyncMock()
    mock_pf = UserProfile(user_id="user1", course_id="course1", is_deleted=True)
    mock_res = MagicMock()
    mock_res.scalars().first.return_value = mock_pf
    db.execute.return_value = mock_res
    
    service = ProfileService(db)
    pf = await service.get_or_create_profile("user1", "course1")
    
    assert pf == mock_pf
    assert pf.is_deleted is False

@pytest.mark.asyncio
@patch("app.services.profile_service.profile_lock", mock_profile_lock)
async def test_initialize_profile():
    db = AsyncMock()
    mock_pf = UserProfile(user_id="user1", course_id="course1", is_deleted=False)
    mock_res = MagicMock()
    mock_res.scalars().first.return_value = mock_pf
    db.execute.return_value = mock_res
    
    service = ProfileService(db)
    answers = {
        "guidance_level": "L3",
        "modal_preference": ["text_analysis", "video_animation"],
        "learning_goal": "exam_sprint"
    }
    pf = await service.initialize_profile("user1", "course1", answers)
    
    assert pf.guidance_level_current == "L3"
    assert pf.modal_preference == {"text_analysis": 60, "video_animation": 60}
    assert pf.drive_intent["type"] == "exam_sprint"
    assert pf.drive_intent["intensity"] == 50
    db.flush.assert_awaited_once()
    db.refresh.assert_awaited_once_with(mock_pf)

@pytest.mark.asyncio
@patch("app.services.profile_service.profile_lock", mock_profile_lock)
async def test_update_learning_goal():
    db = AsyncMock()
    mock_pf = UserProfile(user_id="user1", course_id="course1", is_deleted=False)
    mock_pf.drive_intent = {"type": "casual", "intensity": 50}
    mock_res = MagicMock()
    mock_res.scalars().first.return_value = mock_pf
    db.execute.return_value = mock_res
    
    service = ProfileService(db)
    pf = await service.update_learning_goal("user1", "course1", "exam_sprint")
    
    assert pf.drive_intent["learning_goal"] == "exam_sprint"
    db.flush.assert_awaited_once()

@pytest.mark.asyncio
@patch("app.services.profile_service.profile_lock", mock_profile_lock)
async def test_update_custom_instruction():
    db = AsyncMock()
    mock_pf = UserProfile(user_id="user1", course_id="course1", is_deleted=False)
    mock_pf.drive_intent = {"type": "casual", "intensity": 50}
    mock_res = MagicMock()
    mock_res.scalars().first.return_value = mock_pf
    db.execute.return_value = mock_res
    
    service = ProfileService(db)
    pf = await service.update_custom_instruction("user1", "course1", "please use more charts")
    
    assert pf.drive_intent["custom_instruction"] == "please use more charts"
    db.flush.assert_awaited_once()
