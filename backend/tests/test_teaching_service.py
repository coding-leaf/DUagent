"""Focused MySQL tests for the teaching authorization facade."""

import asyncio
import os
import uuid
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import event

database_url = os.environ.get("TEST_DATABASE_URL")
if not database_url or not database_url.startswith("mysql+aiomysql://"):
    raise RuntimeError("TEST_DATABASE_URL must point to an isolated MySQL database")
os.environ["DATABASE_URL"] = database_url

from app.db.session import async_session_factory, engine, init_db
from app.models.course import Course, CourseEnrollment
from app.models.user import User


async def _init_schema() -> None:
    await init_db()
    await engine.dispose()


asyncio.run(_init_schema())

from app.services.class_insights_query import ClassInsightsQuery
from app.services.student_report_query import StudentReportQuery
from app.services.teaching_service import TeachingService


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


async def _course(db) -> tuple[User, Course]:
    teacher = await _user(db, "teacher", "teacher")
    course = Course(
        name="Teaching Test",
        course_code=_uid("course"),
        teacher_id=teacher.id,
    )
    db.add(course)
    await db.flush()
    return teacher, course


@pytest.mark.asyncio(loop_scope="module")
async def test_get_student_info_hides_non_enrolled_user():
    async with async_session_factory() as db:
        teacher, course = await _course(db)
        outsider = await _user(db, "student", "outsider")
        await db.commit()

        with pytest.raises(HTTPException) as exc:
            await TeachingService(db).get_student_info(course.id, outsider.id, teacher)

        assert exc.value.status_code == 404
        assert exc.value.detail == {
            "code": 40400,
            "message": "学生未入班",
            "data": None,
        }


@pytest.mark.asyncio(loop_scope="module")
async def test_verify_teacher_preserves_owner_and_error_contracts():
    async with async_session_factory() as db:
        teacher, course = await _course(db)
        other_teacher = await _user(db, "teacher", "other_teacher")
        await db.commit()

        service = TeachingService(db)
        assert (await service.verify_teacher(course.id, teacher)).id == course.id

        with pytest.raises(HTTPException) as forbidden:
            await service.verify_teacher(course.id, other_teacher)
        assert forbidden.value.status_code == 403
        assert forbidden.value.detail == {
            "code": 40300,
            "message": "无权访问此班级",
            "data": None,
        }

        with pytest.raises(HTTPException) as missing:
            await service.verify_teacher("missing-course", teacher)
        assert missing.value.status_code == 404
        assert missing.value.detail == {
            "code": 40400,
            "message": "课程不存在",
            "data": None,
        }


@pytest.mark.asyncio(loop_scope="module")
async def test_list_students_is_stable_and_filters_soft_deleted_rows():
    async with async_session_factory() as db:
        teacher, course = await _course(db)
        first = await _user(db, "student", "first")
        second = await _user(db, "student", "second")
        removed_enrollment_user = await _user(db, "student", "removed_enrollment")
        removed_user = await _user(db, "student", "removed_user")
        removed_user.is_deleted = True
        joined_at = datetime(2026, 1, 1, 8, 0, 0)
        enrollment_prefix = uuid.uuid4().hex[:10]
        db.add_all(
            [
                CourseEnrollment(id=f"{enrollment_prefix}-b", course_id=course.id, student_id=second.id, create_time=joined_at),
                CourseEnrollment(id=f"{enrollment_prefix}-a", course_id=course.id, student_id=first.id, create_time=joined_at),
                CourseEnrollment(course_id=course.id, student_id=removed_enrollment_user.id, create_time=joined_at + timedelta(minutes=1), is_deleted=True),
                CourseEnrollment(course_id=course.id, student_id=removed_user.id, create_time=joined_at + timedelta(minutes=2)),
            ]
        )
        await db.commit()

        data = await TeachingService(db).list_students(course.id, teacher, page=1, page_size=20)

        assert data["total"] == 2
        assert [item["id"] for item in data["students"]] == [first.id, second.id]
        assert data["page"] == 1
        assert data["page_size"] == 20


@pytest.mark.asyncio(loop_scope="module")
async def test_list_students_query_count_does_not_grow_with_page_size():
    async with async_session_factory() as db:
        teacher, course = await _course(db)
        students = [await _user(db, "student", f"student-{i}") for i in range(20)]
        db.add_all(CourseEnrollment(course_id=course.id, student_id=student.id) for student in students)
        await db.commit()
        statements: list[str] = []

        def count_statement(_conn, _cursor, statement, _parameters, _context, _executemany):
            statements.append(statement)

        event.listen(engine.sync_engine, "before_cursor_execute", count_statement)
        try:
            statements.clear()
            await TeachingService(db).list_students(course.id, teacher, page=1, page_size=1)
            one_student_count = len(statements)
            statements.clear()
            await TeachingService(db).list_students(course.id, teacher, page=1, page_size=20)
            twenty_student_count = len(statements)
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", count_statement)

        assert one_student_count > 0
        assert twenty_student_count == one_student_count


@pytest.mark.asyncio(loop_scope="module")
async def test_student_learning_validates_enrollment_before_delegating(monkeypatch):
    async with async_session_factory() as db:
        teacher, course = await _course(db)
        student = await _user(db, "student", "delegate-student")
        db.add(CourseEnrollment(course_id=course.id, student_id=student.id))
        await db.commit()

        async def fake_execute(query, class_id, enrolled_student):
            assert query.db is db
            assert class_id == course.id
            assert enrolled_student.id == student.id
            return {"sentinel": "student-report"}

        monkeypatch.setattr(StudentReportQuery, "execute", fake_execute)
        data = await TeachingService(db).get_student_learning(course.id, student.id, teacher)

        assert data == {"sentinel": "student-report"}


@pytest.mark.asyncio(loop_scope="module")
async def test_class_insights_validates_teacher_before_delegating(monkeypatch):
    async with async_session_factory() as db:
        teacher, course = await _course(db)
        await db.commit()

        async def fake_execute(query, class_id):
            assert query.db is db
            assert class_id == course.id
            return {"sentinel": "class-insights"}

        monkeypatch.setattr(ClassInsightsQuery, "execute", fake_execute)
        data = await TeachingService(db).get_class_insights(course.id, teacher)

        assert data == {"sentinel": "class-insights"}
