from app.api.v1.profile import _normalize_dialogue_profile


def test_resource_preference_text_does_not_become_learning_goal():
    extracted = {
        "learning_goal": "我喜欢视频",
        "learning_preferences": ["视频", "图解"],
    }

    normalized = _normalize_dialogue_profile(extracted)

    assert normalized["learning_goal"] is None
    assert normalized["preferred_resources"] == ["video_animation", "chart_logic"]


def test_learning_goal_is_limited_to_three_enums():
    assert _normalize_dialogue_profile({"learning_goal": "准备期末考试"})["learning_goal"] == "exam_sprint"
    assert _normalize_dialogue_profile({"learning_goal": "课后作业巩固"})["learning_goal"] == "daily_homework"
    assert _normalize_dialogue_profile({"learning_goal": "兴趣拓展"})["learning_goal"] == "casual"


def test_non_enum_learning_goal_is_dropped():
    normalized = _normalize_dialogue_profile({"learning_goal": "两周内补齐指针"})

    assert normalized["learning_goal"] is None
