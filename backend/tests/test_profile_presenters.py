import pytest
from datetime import datetime
from app.models.user import User
from app.models.course import Course, CourseEnrollment
from app.models.others import UserProfile
from app.services.profile_presenters import profile_data, DEFAULT_PROFILE

def test_profile_presenters_data_default():
    formatted = profile_data(None, "course456", None)
    assert formatted["guidance_level"] == {"current": "L2", "updated_at": ""}
    assert formatted["modal_preference"] == DEFAULT_PROFILE["modal_preference"]
    assert formatted["discipline_badge"] == DEFAULT_PROFILE["discipline_badge"]
    assert len(formatted["profile_dimensions"]) == 6
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
            "learning_habits": {},
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
    # user.guidance_level takes precedence over pf.guidance_level_current
    assert formatted["guidance_level"]["current"] == "L3"
    assert formatted["role"] == "teacher"
    assert formatted["generated_at"] == "2026-06-19T12:00:00"
    assert formatted["knowledge_coordinates"] == [{"x": 1, "y": 2}]
    assert formatted["cognitive_blindspots"] == ["blindspot1"]

    # video_animation (75) and text_analysis (80) are >= 70
    assert formatted["resource_preference_summary"] == "AI 交互、文本阅读"

    # profile_dimensions has the correct structure
    dims = {d["key"]: d for d in formatted["profile_dimensions"]}
    assert "learning_goal" in dims
    assert "resource_preference" in dims
    assert dims["resource_preference"]["value"] == "AI 交互、文本阅读"

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

def test_profile_presenters_deepcopy_safety():
    formatted1 = profile_data(None, "course456", None)
    formatted1["modal_preference"]["video_animation"] = 999
    formatted1["drive_intent"]["learning_habits"]["autonomy_score"] = 999

    formatted2 = profile_data(None, "course456", None)
    assert formatted2["modal_preference"]["video_animation"] == 50
    assert formatted2["drive_intent"]["learning_habits"] == {}
    assert DEFAULT_PROFILE["modal_preference"]["video_animation"] == 50

def test_profile_dimensions_structure():
    pf = UserProfile(
        id="profile123",
        user_id="user123",
        course_id="course456",
        cognitive_blindspots=[{"name": "指针", "source": "profile_dialogue", "updated_at": "2026-06-19T00:00:00"}],
        drive_intent={"type": "exam_sprint", "source": "profile_dialogue", "learning_habits": {}, "knowledge_progress_summary": {}}
    )
    formatted = profile_data(pf, "course456", None)
    dims = {d["key"]: d for d in formatted["profile_dimensions"]}

    assert dims["learning_goal"]["value"] == "exam_sprint"
    assert dims["learning_goal"]["source"] == "profile_dialogue"
    assert dims["weak_points"]["source"] == "profile_dialogue"
    assert "指针" in dims["weak_points"]["value"]
    assert dims["guidance_level"]["value"] == "L2"
