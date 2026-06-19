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

