import os
import sys
from urllib.parse import urlparse

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
if not TEST_DATABASE_URL.startswith("mysql+"):
    pytest.skip("requires TEST_DATABASE_URL=mysql+...", allow_module_level=True)

parsed_test_url = urlparse(TEST_DATABASE_URL)
test_database_name = parsed_test_url.path.strip("/")
if test_database_name == "duagent":
    pytest.skip("refusing to use the real duagent database", allow_module_level=True)
if not (
    any(marker in test_database_name.lower() for marker in ("test", "pytest"))
    or test_database_name.startswith("courses_async")
):
    pytest.skip(
        "refusing to use a database not marked as test/pytest/courses_async",
        allow_module_level=True,
    )

os.environ["DATABASE_URL"] = TEST_DATABASE_URL

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.base import Base
from app.db.session import async_session_factory, engine
from app.main import app
from app.models.course import Course, CourseEnrollment
from app.models.user import User


@pytest_asyncio.fixture(autouse=True)
async def _dispose_db_engine_after_test():
    yield
    await engine.dispose()


async def _reset_db():
    async with engine.begin() as conn:
        await conn.exec_driver_sql("SET FOREIGN_KEY_CHECKS=0")
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        await conn.exec_driver_sql("SET FOREIGN_KEY_CHECKS=1")


def _auth_headers(user_id: str, role: str) -> dict:
    from app.core.security import create_token

    token = create_token(user_id, role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_hidden_kg_host_course_stays_out_of_teacher_and_student_course_flows():
    await _reset_db()

    async with async_session_factory() as db:
        db.add_all(
            [
                User(
                    id="admin-host",
                    email="admin-host@example.com",
                    username="admin-host",
                    password_hash="x",
                    role="admin",
                ),
                User(
                    id="teacher-host",
                    email="teacher-host@example.com",
                    username="teacher-host",
                    password_hash="x",
                    role="teacher",
                ),
                User(
                    id="student-host",
                    email="student-host@example.com",
                    username="student-host",
                    password_hash="x",
                    role="student",
                ),
            ]
        )
        db.add_all(
            [
                Course(
                    id="host-hidden-course",
                    name="[KG HOST] Hidden Catalog",
                    description="System host course for catalog hidden-catalog knowledge graphs",
                    course_code="KGHHIDE1",
                    teacher_id="admin-host",
                ),
                Course(
                    id="real-course-visible",
                    name="Visible Course",
                    description="real class",
                    course_code="VISIBLE1",
                    teacher_id="teacher-host",
                ),
            ]
        )
        db.add_all(
            [
                CourseEnrollment(student_id="student-host", course_id="host-hidden-course"),
                CourseEnrollment(student_id="student-host", course_id="real-course-visible"),
            ]
        )
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        teacher_courses = await client.get(
            "/api/v1/courses",
            headers=_auth_headers("teacher-host", "teacher"),
        )
        assert teacher_courses.status_code == 200, teacher_courses.text
        teacher_ids = [item["id"] for item in teacher_courses.json()["data"]["courses"]]
        assert "real-course-visible" in teacher_ids
        assert "host-hidden-course" not in teacher_ids

        student_courses = await client.get(
            "/api/v1/courses",
            headers=_auth_headers("student-host", "student"),
        )
        assert student_courses.status_code == 200, student_courses.text
        student_ids = [item["id"] for item in student_courses.json()["data"]["courses"]]
        assert "real-course-visible" in student_ids
        assert "host-hidden-course" not in student_ids

        join_hidden = await client.post(
            "/api/v1/courses/join",
            headers=_auth_headers("student-host", "student"),
            json={"course_code": "KGHHIDE1"},
        )
        assert join_hidden.status_code == 404, join_hidden.text
        assert join_hidden.json()["detail"]["message"] == "课程码不存在"

    async with async_session_factory() as db:
        enrollments = (
            await db.execute(
                select(CourseEnrollment).where(
                    CourseEnrollment.student_id == "student-host",
                    CourseEnrollment.course_id == "host-hidden-course",
                    CourseEnrollment.is_deleted == False,
                )
            )
        ).scalars().all()
    assert len(enrollments) == 1
