from agent_service.agents.evaluation import generate_evaluation_data
from agent_service.schemas.evaluation import (
    ChapterProgressItem,
    EvaluationGenerateRequest,
    LearningProgress,
    QuizResultItem,
    ResourceUsage,
)


def test_generate_evaluation_data_builds_progress_table() -> None:
    result = generate_evaluation_data(_build_request())

    assert result.progress_table is not None
    assert [column.key for column in result.progress_table.columns] == [
        "chapter",
        "completion_rate",
        "time_spent",
    ]
    assert result.progress_table.rows == [
        {"chapter": "函数", "completion_rate": 80.0, "time_spent": 120},
        {"chapter": "导数", "completion_rate": 40.0, "time_spent": 60},
    ]


def test_generate_evaluation_data_builds_mastery_table_from_quizzes() -> None:
    result = generate_evaluation_data(_build_request())

    assert result.mastery_table is not None
    assert [column.key for column in result.mastery_table.columns] == [
        "chapter",
        "average_score",
        "quiz_count",
        "mastery_level",
    ]
    assert result.mastery_table.rows == [
        {"chapter": "函数", "average_score": 90.0, "quiz_count": 1, "mastery_level": "strong"},
        {"chapter": "导数", "average_score": 55.0, "quiz_count": 1, "mastery_level": "weak"},
    ]


def test_generate_evaluation_data_builds_resource_usage_table() -> None:
    result = generate_evaluation_data(_build_request())

    assert result.resource_usage_table is not None
    assert [column.key for column in result.resource_usage_table.columns] == [
        "resource_type",
        "count",
    ]
    assert result.resource_usage_table.rows == [
        {"resource_type": "document", "count": 3},
        {"resource_type": "video", "count": 1},
    ]


def test_generate_evaluation_data_builds_summary_text() -> None:
    result = generate_evaluation_data(_build_request())

    assert result.summary_text == "已学习 2 个章节，平均完成率 60.0%，平均练习正确率 72.5%。薄弱章节：导数。"


def _build_request() -> EvaluationGenerateRequest:
    return EvaluationGenerateRequest(
        user_id="user-1",
        course_id="course-1",
        learning_progress=LearningProgress(
            chapter_progress=[
                ChapterProgressItem(chapter="函数", completion_rate=80, time_spent=120),
                ChapterProgressItem(chapter="导数", completion_rate=40, time_spent=60),
            ]
        ),
        quiz_results=[
            QuizResultItem(chapter="函数", score=90, created_at="2026-05-20T10:00:00Z"),
            QuizResultItem(chapter="导数", score=55, created_at="2026-05-21T10:00:00Z"),
        ],
        resource_usage=ResourceUsage(by_type={"document": 3, "video": 1}),
    )
