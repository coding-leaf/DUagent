"""Focused MySQL tests for the class insights query."""

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
from app.models.course import Course, CourseEnrollment
from app.models.others import LearningPath
from app.models.quiz import QuizAnswer, QuizQuestion, QuizSession
from app.models.user import User


async def _init_schema() -> None:
    await init_db()
    await engine.dispose()


asyncio.run(_init_schema())

from app.services.class_insights_query import ClassInsightsQuery


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


async def _user(db, role: str, prefix: str) -> User:
    user = User(
        username=_uid(prefix),
        email=f"{_uid(prefix)}@test.local",
        password_hash="test",
        role=role,
        real_name=f"{prefix} name",
        student_id=_uid("sid") if role == "student" else "",
    )
    db.add(user)
    await db.flush()
    return user


async def _course(db) -> Course:
    teacher = await _user(db, "teacher", "teacher")
    course = Course(
        name="Class Insights Query Test",
        course_code=_uid("course"),
        teacher_id=teacher.id,
    )
    db.add(course)
    await db.flush()
    return course


@pytest.mark.asyncio(loop_scope="module")
async def test_execute_returns_zero_state_for_empty_class():
    async with async_session_factory() as db:
        course = await _course(db)
        await db.commit()

        data = await ClassInsightsQuery(db).execute(course.id)

        assert data == {
            "avg_quiz_score": None,
            "total_quiz_attempts": 0,
            "weak_points_top": [],
            "path_node_progress": {
                "completed": 0,
                "in_progress": 0,
                "recommended": 0,
                "pending": 0,
                "total_nodes": 0,
            },
        }


@pytest.mark.asyncio(loop_scope="module")
async def test_execute_uses_active_enrollments_and_latest_paths():
    async with async_session_factory() as db:
        course = await _course(db)
        active_student = await _user(db, "student", "active")
        removed_student = await _user(db, "student", "removed")
        old_time = datetime(2026, 2, 1, 8, 0, 0)
        new_time = datetime(2026, 2, 2, 8, 0, 0)
        active_quiz = QuizSession(
            user_id=active_student.id,
            course_id=course.id,
            score=60,
            correct_count=1,
            total_count=2,
            time_spent=30,
        )
        db.add_all(
            [
                CourseEnrollment(course_id=course.id, student_id=active_student.id),
                CourseEnrollment(course_id=course.id, student_id=removed_student.id, is_deleted=True),
                LearningPath(user_id=active_student.id, course_id=course.id, nodes=[{"status": "completed"}, {"status": "completed"}], generated_at=old_time),
                LearningPath(user_id=active_student.id, course_id=course.id, nodes=[{"status": "pending"}, {"status": "unknown"}], generated_at=new_time),
                LearningPath(user_id=removed_student.id, course_id=course.id, nodes=[{"status": "completed"}], generated_at=new_time),
                active_quiz,
                QuizSession(user_id=removed_student.id, course_id=course.id, score=100, correct_count=1, total_count=1, time_spent=10),
            ]
        )
        await db.flush()
        correct_question = QuizQuestion(course_id=course.id, chapter="chapter 1", knowledge_point="graphs", type="single_choice", content="correct?", options=["A", "B"], correct_answer="A")
        wrong_question = QuizQuestion(course_id=course.id, chapter="chapter 1", knowledge_point="graphs", type="single_choice", content="wrong?", options=["A", "B"], correct_answer="A")
        db.add_all([correct_question, wrong_question])
        await db.flush()
        db.add_all(
            [
                QuizAnswer(quiz_id=active_quiz.id, question_id=correct_question.id, user_answer="A", is_correct=True, correct_answer="A"),
                QuizAnswer(quiz_id=active_quiz.id, question_id=wrong_question.id, user_answer="B", is_correct=False, correct_answer="A"),
            ]
        )
        await db.commit()

        data = await ClassInsightsQuery(db).execute(course.id)

        assert data["avg_quiz_score"] == 60.0
        assert data["total_quiz_attempts"] == 1
        assert data["weak_points_top"] == [
            {
                "knowledge_point": "graphs",
                "error_count": 1,
                "total_attempts": 2,
                "error_rate": 0.5,
            }
        ]
        assert data["path_node_progress"] == {
            "completed": 0,
            "in_progress": 0,
            "recommended": 0,
            "pending": 1,
            "total_nodes": 1,
        }
