import asyncio
import os
import sys
import uuid

import pytest
import pytest_asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///./test_node_resource_service.db",
)

from app.db.session import async_session_factory, engine, init_db  # noqa: E402

asyncio.run(init_db())
asyncio.run(engine.dispose())

from app.models.catalog import CourseCatalog, CourseOffering  # noqa: E402
from app.models.course import Course, CourseEnrollment  # noqa: E402
from app.models.others import CourseKnowledgeGraph, LearningPath, Resource  # noqa: E402
from app.models.quiz import QuizQuestion  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.node_resource_service import NodeResourceService  # noqa: E402


@pytest_asyncio.fixture(scope="module", autouse=True)
async def _dispose_engine_for_module_loop():
    await engine.dispose()
    yield
    await engine.dispose()


@pytest.mark.asyncio(loop_scope="module")
async def test_node_resource_service_prefers_learning_path_node_name():
    suffix = uuid.uuid4().hex[:8]
    teacher_id = f"teacher_{suffix}"
    student_id = f"student_{suffix}"
    course_id = f"course_{suffix}"
    node_id = "node_1"

    async with async_session_factory() as db:
        teacher = User(
            id=teacher_id,
            username=f"teacher_{suffix}",
            email=f"teacher_{suffix}@test.com",
            password_hash="hash",
            role="teacher",
        )
        student = User(
            id=student_id,
            username=f"student_{suffix}",
            email=f"student_{suffix}@test.com",
            password_hash="hash",
            role="student",
        )
        db.add_all([teacher, student])
        db.add(Course(
            id=course_id,
            name="Node Service Course",
            course_code=f"NS{suffix[:8]}",
            teacher_id=teacher_id,
        ))
        await db.flush()
        db.add(CourseEnrollment(student_id=student_id, course_id=course_id))
        db.add(CourseKnowledgeGraph(
            course_id=course_id,
            version=1,
            is_active=True,
            nodes=[{"id": node_id, "name": "KG Name", "chapter": "chapter_1"}],
            edges=[],
        ))
        db.add(LearningPath(
            user_id=student_id,
            course_id=course_id,
            nodes=[{"id": node_id, "name": "LP Name", "status": "in_progress", "mastery": 50}],
            edges=[],
            current_node_id=node_id,
            current_node_name="LP Name",
        ))
        db.add(Resource(
            id=f"res_{suffix}",
            course_id=course_id,
            title="LP Resource",
            type="document",
            knowledge_point="LP Name",
            chapter="chapter_1",
            content="content",
        ))
        db.add(QuizQuestion(
            course_id=course_id,
            chapter="chapter_1",
            knowledge_point="LP Name",
            type="single_choice",
            content="Question",
            options=["A", "B"],
            correct_answer="A",
        ))
        await db.commit()

        data = await NodeResourceService(db).get_node_resources(student, course_id, node_id)

    assert data["node_id"] == node_id
    assert data["node_name"] == "LP Name"
    assert data["weak_point_tutorials"][0]["title"] == "LP Resource"
    assert data["exercises"][0]["content"] == "Question"


@pytest.mark.asyncio(loop_scope="module")
async def test_node_resource_service_resolves_catalog_quizzes():
    suffix = uuid.uuid4().hex[:8]
    teacher_id = f"teacher_{suffix}"
    student_id = f"student_{suffix}"
    catalog_id = f"catalog_{suffix}"
    host_course_id = f"host_{suffix}"
    offering_course_id = f"offering_{suffix}"
    node_id = "node_2"

    async with async_session_factory() as db:
        teacher = User(
            id=teacher_id,
            username=f"teacher_{suffix}",
            email=f"teacher_{suffix}@test.com",
            password_hash="hash",
            role="teacher",
        )
        student = User(
            id=student_id,
            username=f"student_{suffix}",
            email=f"student_{suffix}@test.com",
            password_hash="hash",
            role="student",
        )
        db.add_all([teacher, student])
        
        # Add host course & offering course
        db.add(Course(
            id=host_course_id,
            name="Host Course",
            course_code=f"HC{suffix[:8]}",
            teacher_id=teacher_id,
        ))
        db.add(Course(
            id=offering_course_id,
            name="Offering Course",
            course_code=f"OC{suffix[:8]}",
            teacher_id=teacher_id,
        ))
        await db.flush()

        # Add CourseCatalog
        db.add(CourseCatalog(
            id=catalog_id,
            title="Test Catalog",
            kg_host_course_id=host_course_id,
            status="ready",
        ))
        await db.flush()

        # Add CourseOffering
        db.add(CourseOffering(
            id=offering_course_id,
            name="Offering Course Class",
            catalog_id=catalog_id,
            teacher_id=teacher_id,
            class_code=f"OC{suffix[:8]}",
        ))
        db.add(CourseEnrollment(student_id=student_id, course_id=offering_course_id))

        # Add CourseKnowledgeGraph
        db.add(CourseKnowledgeGraph(
            course_id=host_course_id,
            version=1,
            is_active=True,
            nodes=[{"id": node_id, "name": "Catalog Node", "chapter": "chapter_2"}],
            edges=[],
        ))

        # Add QuizQuestion at the catalog / host_course level
        db.add(QuizQuestion(
            course_id=host_course_id,
            catalog_id=catalog_id,
            chapter="chapter_2",
            knowledge_point="Catalog Node",
            type="single_choice",
            content="Catalog Level Question",
            options=["A", "B"],
            correct_answer="A",
            source="baseline",
            personalized=False,
        ))
        await db.commit()

        # Query NodeResourceService using offering_course_id
        data = await NodeResourceService(db).get_node_resources(student, offering_course_id, node_id)

    assert data["node_id"] == node_id
    assert data["node_name"] == "Catalog Node"
    assert len(data["exercises"]) == 1
    assert data["exercises"][0]["content"] == "Catalog Level Question"
    assert data["full_exercise_count"] == 1
    assert data["full_exercise_set"][0]["content"] == "Catalog Level Question"
