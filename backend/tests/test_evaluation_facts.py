from datetime import datetime, timedelta, timezone

from app.services import evaluation_service


def test_quiz_results_use_latest_ten_answers_per_knowledge_point():
    aggregate = getattr(evaluation_service, "_aggregate_quiz_results", None)
    assert callable(aggregate), "evaluation facts need a dedicated quiz aggregator"

    started_at = datetime(2026, 7, 1, tzinfo=timezone.utc)
    rows = [
        {
            "is_correct": index >= 4,
            "create_time": started_at + timedelta(minutes=index),
            "knowledge_point": "指针传参",
            "chapter": "指针",
            "personalized": index % 2 == 0,
        }
        for index in range(12)
    ]

    result = aggregate(rows)

    assert result == [
        {
            "knowledge_point": "指针传参",
            "chapter": "指针",
            "score": 66.7,
            "total_answers": 12,
            "personalized_count": 6,
            "recent_trend": 80.0,
        }
    ]


def test_resource_usage_counts_student_activity_not_catalog_inventory():
    aggregate = getattr(evaluation_service, "_aggregate_resource_usage", None)
    assert callable(aggregate), "evaluation facts need a resource-usage aggregator"

    result = aggregate(["lesson", "lesson", "diagram", None])

    assert result == {"lesson": 2, "diagram": 1}


def test_chapter_progress_uses_recorded_study_duration():
    aggregate = getattr(evaluation_service, "_aggregate_chapter_progress", None)
    assert callable(aggregate), "evaluation facts need a chapter-progress aggregator"

    result = aggregate(
        [
            {
                "chapter": "指针",
                "assessment_state": "mastered",
                "study_duration_seconds": 120,
            },
            {
                "chapter": "指针",
                "assessment_state": "learning",
                "study_duration_seconds": 90,
            },
            {
                "chapter": "函数",
                "assessment_state": "mastered",
                "study_duration_seconds": 60,
            },
            {
                "chapter": "数组",
                "assessment_state": "unstarted",
                "study_duration_seconds": None,
            },
        ]
    )

    assert result == [
        {"chapter": "指针", "completion_rate": 50.0, "time_spent": 4},
        {"chapter": "函数", "completion_rate": 100.0, "time_spent": 1},
        {"chapter": "数组", "completion_rate": 0.0, "time_spent": 0},
    ]
