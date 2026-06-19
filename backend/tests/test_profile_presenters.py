import pytest
from datetime import datetime
from app.models.user import User
from app.models.course import Course, CourseEnrollment
from app.models.others import UserProfile
from app.services.profile_presenters import profile_data, _default_profile

def test_profile_presenters_data_default():
    formatted = profile_data(None, "course456", None)
    assert formatted["guidance_level_current"] == "L2"
    assert formatted["modal_preference"] == _default_profile["modal_preference"]
    assert formatted["discipline_badge"] == _default_profile["discipline_badge"]
    assert len(formatted["dimensions"]) == 4
    assert formatted["resource_preference_summary"] == "未设置偏好"

def test_profile_presenters_data_with_objects():
    user = User(
        id="user123",
        role="teacher",
        guidance_level="L3"
    )
    
    pf = UserProfile(
        id="profile123",
        user_id="user123",
        course_id="course456",
        guidance_level_current="L1",
        generated_at=datetime(2026, 6, 19, 12, 0, 0),
        modal_preference={
            "video_animation": 75,
            "chart_logic": 40,
            "text_analysis": 80,
            "code_practice": 30,
            "formula_derivation": 10,
        },
        knowledge_coordinates=[{"x": 1, "y": 2}],
        cognitive_blindspots=["blindspot1"],
        drive_intent={
            "learning_goal": "career",
            "learning_habits": {
                "autonomy_score": 85,
                "achievement_score": 90,
                "reflective_score": 75,
                "persistence_score": 65
            },
            "knowledge_progress_summary": {}
        },
        discipline_badge={
            "badge_id": "pro",
            "name": "学习达人",
            "description": "卓越的学习习惯",
            "level": 3
        }
    )
    
    formatted = profile_data(pf, "course456", user)
    
    assert formatted["id"] == "profile123"
    assert formatted["user_id"] == "user123"
    assert formatted["course_id"] == "course456"
    assert formatted["guidance_level_current"] == "L1"
    assert formatted["role"] == "teacher"
    assert formatted["guidance_level_base"] == "L3"
    assert formatted["generated_at"] == "2026-06-19T12:00:00"
    assert formatted["knowledge_coordinates"] == [{"x": 1, "y": 2}]
    assert formatted["cognitive_blindspots"] == ["blindspot1"]
    
    # Custom modal_preference: video_animation (75) and text_analysis (80) are >= 70
    assert formatted["resource_preference_summary"] == "视频/动画、文本阅读"
    
    # Custom learning habits scoring in dimensions
    assert formatted["dimensions"][0] == {"name": "自主学习度", "value": 85}
    assert formatted["dimensions"][1] == {"name": "成就导向度", "value": 90}
    assert formatted["dimensions"][2] == {"name": "反思性特征", "value": 75}
    assert formatted["dimensions"][3] == {"name": "持久力指数", "value": 65}

def test_resource_preference_summary_balanced():
    pf = UserProfile(
        id="profile123",
        user_id="user123",
        course_id="course456",
        modal_preference={
            "video_animation": 60,
            "chart_logic": 65,
            "text_analysis": 55,
            "code_practice": 50,
            "formula_derivation": 45,
        }
    )
    formatted = profile_data(pf, "course456", None)
    assert formatted["resource_preference_summary"] == "偏好均衡"

def test_profile_dimensions_clamping():
    pf = UserProfile(
        id="profile123",
        user_id="user123",
        course_id="course456",
        drive_intent={
            "learning_goal": "casual",
            "learning_habits": {
                "autonomy_score": 10,       # Should be max(30, 10) = 30
                "achievement_score": 150,   # Should be min(100, 150) = 100
                "reflective_score": "75",   # String conversion check
                "persistence_score": 50
            }
        }
    )
    formatted = profile_data(pf, "course456", None)
    assert formatted["dimensions"][0]["value"] == 30
    assert formatted["dimensions"][1]["value"] == 100
    assert formatted["dimensions"][2]["value"] == 75
    assert formatted["dimensions"][3]["value"] == 50

def test_profile_presenters_deepcopy_safety():
    # Make sure mutations on formatted default profiles don't pollute the global _default_profile
    formatted1 = profile_data(None, "course456", None)
    formatted1["modal_preference"]["video_animation"] = 999
    formatted1["drive_intent"]["learning_habits"]["autonomy_score"] = 999
    
    formatted2 = profile_data(None, "course456", None)
    assert formatted2["modal_preference"]["video_animation"] == 50
    assert formatted2["drive_intent"]["learning_habits"] == {}
    assert _default_profile["modal_preference"]["video_animation"] == 50

def test_profile_presenters_invalid_types():
    pf = UserProfile(
        id="profile123",
        user_id="user123",
        course_id="course456",
        modal_preference={
            "video_animation": "invalid",
            "chart_logic": None,
            "text_analysis": 80,
            "code_practice": [1, 2],
            "formula_derivation": {},
        },
        drive_intent={
            "learning_goal": "casual",
            "learning_habits": {
                "autonomy_score": "not_an_int",
                "achievement_score": None,
                "reflective_score": [100],
                "persistence_score": 85
            }
        }
    )
    
    formatted = profile_data(pf, "course456", None)
    # text_analysis is 80 (>= 70), others are invalid and fallback to 50 (< 70)
    assert formatted["resource_preference_summary"] == "文本阅读"
    
    # Check fallback values for dimensions when parsing fails
    assert formatted["dimensions"][0]["value"] == 60  # Default value fallback
    assert formatted["dimensions"][1]["value"] == 60  # Default value fallback
    assert formatted["dimensions"][2]["value"] == 60  # Default value fallback
    assert formatted["dimensions"][3]["value"] == 85  # Clean parsing
