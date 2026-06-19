"""Focused MySQL tests for the student report query."""

import asyncio
import os
import uuid
from datetime import datetime

import pytest

database_url = os.environ.get("TEST_DATABASE_URL")
if not database_url or not database_url.startswith("mysql+aiomysql://"):
    raise RuntimeError("TEST_DATABASE_URL must point to an isolated MySQL database")
os.environ["DATABASE_URL"] = database_url

from app.db.session import async_session_factory, engine, init_db
from app.models.course import Course
from app.models.others import Evaluation, LearningPath, UserProfile
from app.models.quiz import QuizAnswer, QuizQuestion, QuizSession
from app.models.user import User


async def _init_schema() -> None:
    await init_db()
    await engine.dispose()


asyncio.run(_init_schema())

from app.services.student_report_query import StudentReportQuery, _overall_score


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


async def _course_and_student(db) -> tuple[Course, User]:
    teacher = User(
        username=_uid("teacher"),
        email=f"{_uid('teacher')}@test.local",
        password_hash="test",
        role="teacher",
        real_name="teacher name",
    )
    student = User(
        username=_uid("student"),
        email=f"{_uid('student')}@test.local",
        password_hash="test",
        role="student",
        real_name="report student",
        student_id=_uid("sid"),
    )
    db.add_all([teacher, student])
    await db.flush()
    course = Course(
        name="Student Report Query Test",
        course_code=_uid("course"),
        teacher_id=teacher.id,
    )
    db.add(course)
    await db.flush()
    return course, student


@pytest.mark.parametrize(
    ("table", "expected"),
    [
        ({"rows": [{"average_score": 80}, {"average_score": "60"}]}, 70.0),
        ({"rows": [{"average_score": True}, {"average_score": 101}]}, None),
        ({"rows": [{"average_score": "nan"}, {"average_score": "inf"}]}, None),
        ({"rows": []}, None),
        (None, None),
    ],
)
def test_overall_score_uses_only_finite_scores_in_range(table, expected):
    assert _overall_score(table) == expected


@pytest.mark.asyncio(loop_scope="module")
async def test_execute_uses_latest_records_and_real_quiz_evidence():
    async with async_session_factory() as db:
        course, student = await _course_and_student(db)
        old_time = datetime(2026, 1, 1, 8, 0, 0)
        new_time = datetime(2026, 1, 2, 8, 0, 0)
        session = QuizSession(
            user_id=student.id,
            course_id=course.id,
            chapter="chapter 1",
            score=50,
            correct_count=1,
            total_count=2,
            time_spent=60,
        )
        db.add_all(
            [
                Evaluation(user_id=student.id, course_id=course.id, mastery_table={"rows": [{"average_score": 10}]}, summary_text="old", generated_at=old_time),
                Evaluation(user_id=student.id, course_id=course.id, mastery_table={"rows": [{"average_score": 70}, {"average_score": "80"}]}, summary_text="new", generated_at=new_time),
                UserProfile(user_id=student.id, course_id=course.id, knowledge_coordinates=[{"status": "weak"}], generated_at=old_time),
                UserProfile(user_id=student.id, course_id=course.id, modal_preference={"text": 80, "code": 60}, knowledge_coordinates=[{"status": "mastered"}, {"status": "weak"}, {"status": "learning"}], generated_at=new_time),
                LearningPath(user_id=student.id, course_id=course.id, current_node_name="old", nodes=[{"status": "completed"}], generated_at=old_time),
                LearningPath(user_id=student.id, course_id=course.id, current_node_name="new", nodes=[{"status": "completed"}, {"status": "pending"}], generated_at=new_time),
                session,
            ]
        )
        await db.flush()
        correct_question = QuizQuestion(course_id=course.id, chapter="chapter 1", knowledge_point="trees", type="single_choice", content="correct?", options=["A", "B"], correct_answer="A")
        wrong_question = QuizQuestion(course_id=course.id, chapter="chapter 1", knowledge_point="trees", type="single_choice", content="wrong?", options=["A", "B"], correct_answer="A")
        db.add_all([correct_question, wrong_question])
        await db.flush()
        db.add_all(
            [
                QuizAnswer(quiz_id=session.id, question_id=correct_question.id, user_answer="A", is_correct=True, correct_answer="A"),
                QuizAnswer(quiz_id=session.id, question_id=wrong_question.id, user_answer="B", is_correct=False, correct_answer="A"),
            ]
        )
        await db.commit()

        data = await StudentReportQuery(db).execute(course.id, student)

        assert data["evaluation_summary"] == {"overall_score": 75.0, "generated_at": new_time.isoformat(), "summary_text": "new"}
        assert data["profile_summary"]["knowledge_mastered"] == 1
        assert data["profile_summary"]["knowledge_weak"] == 1
        assert data["profile_summary"]["modal_preference"] == ["text", "code"]
        assert data["path_progress"] == {"current_node": "new", "completed_nodes": 1, "total_nodes": 2}
        assert data["quiz_stats"] == {"total_attempts": 1, "avg_score": 50.0, "avg_time_spent": 60, "mastery_breakdown": [{"knowledge_point": "trees", "accuracy": 50.0}]}
        assert data["weak_points"] == [{"knowledge_point": "trees", "error_count": 1, "total_attempts": 2, "error_rate": 0.5}]
        assert [item["quiz_id"] for item in data["recent_activity"]] == [session.id]


@pytest.mark.asyncio(loop_scope="module")
async def test_execute_returns_empty_sections_without_evidence():
    async with async_session_factory() as db:
        course, student = await _course_and_student(db)
        await db.commit()

        data = await StudentReportQuery(db).execute(course.id, student)

        assert data["evaluation_summary"] is None
        assert data["profile_summary"] is None
        assert data["path_progress"] is None
        assert data["quiz_stats"] is None
        assert data["weak_points"] == []
        assert data["recent_activity"] == []
