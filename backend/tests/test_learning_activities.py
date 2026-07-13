import asyncio
import os
import sys
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///./test_learning_activities.db",
)

from app.api.deps import get_current_user
from app.services.knowledge_progress import build_node_progress_rows as _build_node_progress_rows
from app.db.session import async_session_factory, init_db

asyncio.run(init_db())

from app.main import app
from app.models.catalog import CourseCatalog, CourseOffering
from app.models.course import Course
from app.models.others import CourseKnowledgeGraph, LearningActivity, Resource
from app.models.quiz import QuizQuestion
from app.models.user import User


def test_learning_activity_model_shape():
    table = LearningActivity.__table__
    assert table.name == "learning_activities"

    for name in [
        "id",
        "user_id",
        "course_id",
        "node_id",
        "node_name",
        "resource_id",
        "activity_type",
        "duration_seconds",
        "occurred_at",
        "metadata",
        "create_time",
        "update_time",
        "is_deleted",
    ]:
        assert name in table.columns

    indexes = {index.name: tuple(column.name for column in index.columns) for index in table.indexes}
    assert indexes["idx_learning_activities_user_course_node"] == (
        "user_id",
        "course_id",
        "node_id",
        "is_deleted",
    )
    assert indexes["idx_learning_activities_type_time"] == (
        "user_id",
        "course_id",
        "activity_type",
        "occurred_at",
    )
    assert indexes["idx_learning_activities_resource"] == ("resource_id", "is_deleted")


async def _seed_course_resource():
    suffix = uuid.uuid4().hex[:8]
    teacher = User(
        id=f"u{suffix}",
        username=f"teacher_{suffix}",
        email=f"teacher_{suffix}@test.local",
        password_hash="x",
        role="teacher",
    )
    course = Course(
        id=f"c{suffix}",
        name=f"Course {suffix}",
        course_code=f"C{suffix}",
        teacher_id=teacher.id,
    )
    resource = Resource(
        id=f"r{suffix}",
        course_id=course.id,
        title="Resource",
        type="document",
        knowledge_point="指针基础",
    )
    kg = CourseKnowledgeGraph(
        id=f"kg{suffix}",
        course_id=course.id,
        version=1,
        is_active=True,
        nodes=[{"id": "node_1", "name": "指针基础"}],
        edges=[],
    )
    async with async_session_factory() as db:
        db.add(teacher)
        await db.flush()
        db.add(course)
        await db.flush()
        db.add_all([resource, kg])
        await db.commit()
    return teacher, course, resource


@pytest.mark.asyncio
async def test_create_learning_activity_and_validate_duration():
    teacher, course, resource = await _seed_course_resource()

    async def override_user():
        return teacher

    app.dependency_overrides[get_current_user] = override_user
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/learning-activities",
                json={
                    "course_id": course.id,
                    "activity_type": "resource_study",
                    "resource_id": resource.id,
                    "node_id": "node_1",
                    "duration_seconds": 42,
                    "metadata": {"source": "test"},
                },
            )
            assert response.status_code == 200, response.json()
            assert response.json()["data"]["id"]

            invalid = await client.post(
                "/api/v1/learning-activities",
                json={
                    "course_id": course.id,
                    "activity_type": "resource_study",
                    "resource_id": resource.id,
                    "duration_seconds": 14401,
                },
            )
            assert invalid.status_code == 422
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_evaluation_node_progress_uses_learning_activity_duration():
    teacher, course, resource = await _seed_course_resource()
    async with async_session_factory() as db:
        db.add(
            LearningActivity(
                user_id=teacher.id,
                course_id=course.id,
                node_id="node_1",
                node_name="指针基础",
                resource_id=resource.id,
                activity_type="resource_study",
                duration_seconds=75,
            )
        )
        await db.commit()

    async with async_session_factory() as db:
        rows = await _build_node_progress_rows(teacher.id, course.id, db)

    assert rows
    node = next(row for row in rows if row["node_id"] == "node_1")
    assert node["study_duration_seconds"] == 75
    assert node["last_activity_at"] is not None


@pytest.mark.asyncio
async def test_evaluation_node_progress_counts_shared_and_owned_questions_only():
    suffix = uuid.uuid4().hex[:8]
    teacher = User(
        id=f"ut{suffix}",
        username=f"scope_teacher_{suffix}",
        email=f"scope_teacher_{suffix}@test.local",
        password_hash="x",
        role="teacher",
    )
    host_course = Course(
        id=f"ch{suffix}",
        name="Catalog Host",
        course_code=f"H{suffix}",
        teacher_id=teacher.id,
    )
    class_course = Course(
        id=f"cc{suffix}",
        name="Class Course",
        course_code=f"C{suffix}",
        teacher_id=teacher.id,
    )
    catalog = CourseCatalog(
        id=f"cat{suffix}",
        title="Shared Catalog",
        status="ready",
        knowledge_status="ready",
        kg_host_course_id=host_course.id,
    )
    offering = CourseOffering(
        id=class_course.id,
        name=class_course.name,
        catalog_id=catalog.id,
        teacher_id=teacher.id,
        class_code=f"O{suffix}",
    )
    kg = CourseKnowledgeGraph(
        id=f"kg{suffix}",
        course_id=host_course.id,
        version=1,
        is_active=True,
        nodes=[{"id": "node_shared", "name": "变量与数据类型"}],
        edges=[],
    )

    def question(question_id, source, owner_user_id=None):
        return QuizQuestion(
            id=question_id,
            course_id=host_course.id if source != "personalized" else class_course.id,
            catalog_id=catalog.id if source != "personalized" else None,
            knowledge_point="变量与数据类型",
            type="single_choice",
            source=source,
            personalized=source == "personalized",
            owner_user_id=owner_user_id,
            content=question_id,
            options=[],
            correct_answer="A",
        )

    async with async_session_factory() as db:
        db.add(teacher)
        await db.flush()
        db.add_all([host_course, class_course])
        await db.flush()
        db.add(catalog)
        await db.flush()
        db.add_all([offering, kg])
        db.add_all([
            question(f"qb{suffix}", "baseline"),
            question(f"qc{suffix}", "common"),
            question(f"qo{suffix}", "personalized", teacher.id),
            question(f"qx{suffix}", "personalized", "another-user"),
        ])
        await db.commit()

    async with async_session_factory() as db:
        rows = await _build_node_progress_rows(teacher.id, class_course.id, db)

    assert rows[0]["question_count"] == 3
    assert rows[0]["assessment_state"] == "pending_practice"
