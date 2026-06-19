import sys
from app.models import others as _others
sys.modules['app.models.profile'] = _others

from app.models.user import User
from app.models.course import Course, CourseEnrollment
from app.services.profile_dialogue_service import _normalize_fields, _merge_profile
from app.models.profile import UserProfile

def test_resource_preference_text_does_not_become_learning_goal():
    extracted = {
        "learning_goal": "我喜欢视频",
        "learning_preferences": ["视频", "图解"],
    }
    normalized = _normalize_fields(extracted)
    assert normalized["learning_goal"] is None
    assert normalized["preferred_resources"] == ["video_animation", "chart_logic"]

def test_learning_goal_is_limited_to_three_enums():
    assert _normalize_fields({"learning_goal": "准备期末考试"})["learning_goal"] == "exam_sprint"
    assert _normalize_fields({"learning_goal": "课后作业巩固"})["learning_goal"] == "daily_homework"
    assert _normalize_fields({"learning_goal": "兴趣拓展"})["learning_goal"] == "casual"

def test_non_enum_learning_goal_is_dropped():
    normalized = _normalize_fields({"learning_goal": "两周内补齐指针"})
    assert normalized["learning_goal"] is None

def test_merge_profile_blindspots_and_modal_threshold():
    pf = UserProfile(
        user_id="u1",
        course_id="c1",
        cognitive_blindspots=[{"name": "指针基础", "source": "test", "updated_at": "2026-06-19T00:00:00"}],
        modal_preference={"video_animation": 40, "chart_logic": 80}
    )
    normalized = {
        "learning_goal": "casual",
        "weak_points": ["指针基础", "链表遍历"],
        "preferred_resources": ["video_animation"],
        "guidance_level": "L3"
    }
    
    result = _merge_profile(pf, normalized)
    
    # Verify Blindspots deduplication & exact match
    assert len(pf.cognitive_blindspots) == 2
    assert pf.cognitive_blindspots[0]["name"] == "指针基础"
    assert pf.cognitive_blindspots[1]["name"] == "链表遍历"
    
    # Verify Modal Preference threshold max(curr, 70)
    assert pf.modal_preference["video_animation"] == 70
    assert pf.modal_preference["chart_logic"] == 80
    assert pf.guidance_level_current == "L3"


import pytest
from unittest.mock import AsyncMock, patch
from contextlib import asynccontextmanager

@pytest.mark.asyncio
@patch("app.services.profile_dialogue_service.profile_lock")
async def test_update_from_dialogue_service(mock_lock):
    # Setup mock lock context manager
    @asynccontextmanager
    async def fake_lock(*args, **kwargs):
        yield "mocked_lock"
    mock_lock.side_effect = fake_lock

    # Setup database session mock
    db_session = AsyncMock()

    from app.services.profile_dialogue_service import ProfileDialogueService
    service = ProfileDialogueService(db_session)

    # Mock get_or_create_profile to return a UserProfile
    pf = UserProfile(
        user_id="u1",
        course_id="c1",
        cognitive_blindspots=[],
        modal_preference={"video_animation": 50}
    )
    
    # Mock ProfileService.get_or_create_profile
    service.profile_service.get_or_create_profile = AsyncMock(return_value=pf)

    extracted_data = {
        "learning_goal": "准备期末考试",
        "weak_points": ["C语言指针"],
        "preferred_resources": ["video_animation"],
        "guidance_level": "L3"
    }

    res_pf = await service.update_from_dialogue("u1", "c1", extracted_data)

    # Verify return profile and mutations
    assert res_pf == pf
    assert res_pf.guidance_level_current == "L3"
    assert res_pf.drive_intent["learning_goal"] == "exam_sprint"
    assert len(res_pf.cognitive_blindspots) == 1
    assert res_pf.cognitive_blindspots[0]["name"] == "C语言指针"
    assert res_pf.modal_preference["video_animation"] == 70
    
    # Assert DB flush was called
    assert db_session.flush.call_count >= 2


