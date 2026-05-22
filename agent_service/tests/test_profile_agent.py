from agent_service.agents.profile import generate_profile_data
from agent_service.schemas.profile import (
    DriveIntentData,
    ProfileGenerateRequest,
    QuizHistoryItem,
    ResourceUsageStats,
)


def test_generate_profile_data_builds_modal_preference_from_resource_usage() -> None:
    result = generate_profile_data(_build_request())

    assert result.modal_preference is not None
    assert result.modal_preference.video_animation == 50.0
    assert result.modal_preference.text_analysis == 100.0
    assert result.modal_preference.code_practice == 25.0
    assert result.modal_preference.chart_logic == 0.0
    assert result.modal_preference.formula_derivation == 0.0


def test_generate_profile_data_recommends_guidance_level_from_average_score() -> None:
    result = generate_profile_data(_build_request())

    assert result.guidance_level_suggestion is not None
    assert result.guidance_level_suggestion.recommended == "L2"
    assert result.guidance_level_suggestion.reason == "最近练习平均正确率 75.0%，建议保持适中引导。"


def test_generate_profile_data_builds_knowledge_coordinates_and_blindspots() -> None:
    result = generate_profile_data(_build_request())

    assert [(item.name, item.status) for item in result.knowledge_coordinates] == [
        ("函数", "mastered"),
        ("导数", "learning"),
    ]
    assert [(item.name, item.error_count, item.severity) for item in result.cognitive_blindspots] == [
        ("导数", 1, "medium"),
    ]


def test_generate_profile_data_builds_drive_intent_and_badge() -> None:
    result = generate_profile_data(_build_request())

    assert result.drive_intent is not None
    assert result.drive_intent.type == "daily_homework"
    assert result.drive_intent.intensity == 58.0
    assert result.discipline_badge is not None
    assert result.discipline_badge.subject == "course-1"
    assert result.discipline_badge.level == "steady"
    assert result.discipline_badge.streak_days == 4


def _build_request() -> ProfileGenerateRequest:
    return ProfileGenerateRequest(
        user_id="user-1",
        course_id="course-1",
        quiz_history=[
            QuizHistoryItem(score=90, chapter="函数", created_at="2026-05-20T10:00:00Z"),
            QuizHistoryItem(score=60, chapter="导数", created_at="2026-05-21T10:00:00Z"),
        ],
        resource_usage_stats=ResourceUsageStats(
            video_count=2,
            document_count=4,
            code_count=1,
            quiz_count=3,
        ),
        drive_intent_data=DriveIntentData(recent_7d_sessions=4, recent_7d_duration=180),
    )
