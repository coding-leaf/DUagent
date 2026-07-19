import os
import sys
import uuid
from urllib.parse import urlparse

import pytest
import pytest_asyncio
from sqlalchemy import select, update

# This MySQL integration module ensures schema once and relies on unique test IDs;
# it is not intended for xdist runs against a shared database.
pytestmark = pytest.mark.asyncio(loop_scope="module")

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
if not TEST_DATABASE_URL.startswith("mysql+"):
    pytest.skip("requires TEST_DATABASE_URL=mysql+...", allow_module_level=True)

parsed_test_url = urlparse(TEST_DATABASE_URL)
test_database_name = parsed_test_url.path.strip("/")
if test_database_name == "duagent":
    pytest.skip("refusing to use the real duagent database", allow_module_level=True)
if not any(marker in test_database_name.lower() for marker in ("test", "pytest")):
    pytest.skip("refusing to use a database not marked as test/pytest", allow_module_level=True)

os.environ["DATABASE_URL"] = TEST_DATABASE_URL

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.base import Base
from app.db.session import async_session_factory, engine
from app.models.course import Course
from app.models.others import CourseKnowledgeGraph
from app.models.user import User
from app.services.course_knowledge_graphs import (
    activate_knowledge_graph_version,
    create_knowledge_graph_version,
    get_active_knowledge_graph,
)


async def _ensure_schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _seed_course(course_id: str) -> str:
    async with async_session_factory() as db:
        teacher = User(
            id=f"teacher-{course_id}",
            email=f"teacher-{course_id}@example.com",
            username=f"teacher_{course_id}",
            password_hash="x",
            role="teacher",
        )
        course = Course(
            id=course_id,
            name=f"Course {course_id}",
            course_code=f"KG{course_id[-8:]}",
            teacher_id=teacher.id,
        )
        db.add_all([teacher, course])
        await db.commit()
    return course_id


def _course_id(label: str) -> str:
    return f"ckg-{label[:3]}-{uuid.uuid4().hex[:8]}"


@pytest_asyncio.fixture(scope="module", autouse=True)
async def ensure_schema_once():
    await _ensure_schema()
    yield
    await engine.dispose()


async def test_create_two_versions_makes_only_second_active():
    course_id = await _seed_course(_course_id("two-versions"))

    async with async_session_factory() as db:
        first = await create_knowledge_graph_version(
            db,
            course_id=course_id,
            nodes=[{"id": "n1"}],
            edges=[],
            source_type="manual_import",
            generation_strategy="outline_v1",
        )
        second = await create_knowledge_graph_version(
            db,
            course_id=course_id,
            nodes=[{"id": "n2"}],
            edges=[],
            source_type="agent_generated",
            generation_strategy="outline_v2",
            metrics={"node_count": 1},
            parent_graph_id=first.id,
        )
        await db.commit()

        active = await get_active_knowledge_graph(db, course_id)
        graphs = (
            await db.execute(
                select(CourseKnowledgeGraph).where(CourseKnowledgeGraph.course_id == course_id)
            )
        ).scalars().all()

    assert first.version == 1
    assert second.version == 2
    assert active.id == second.id
    assert active.is_active is True
    assert [graph.id for graph in graphs if graph.is_active] == [second.id]
    assert second.parent_graph_id == first.id
    assert second.metrics == {"node_count": 1}


async def test_activate_can_roll_back_to_first_version():
    course_id = await _seed_course(_course_id("rollback"))

    async with async_session_factory() as db:
        first = await create_knowledge_graph_version(
            db,
            course_id=course_id,
            nodes=[{"id": "v1"}],
            edges=[],
            source_type="manual_import",
            generation_strategy="outline_v1",
        )
        await create_knowledge_graph_version(
            db,
            course_id=course_id,
            nodes=[{"id": "v2"}],
            edges=[],
            source_type="agent_generated",
            generation_strategy="outline_v2",
        )

        target = await activate_knowledge_graph_version(db, course_id, version=1)
        await db.commit()

        active = await get_active_knowledge_graph(db, course_id)

    assert target.id == first.id
    assert active.id == first.id
    assert active.version == 1


async def test_create_inactive_version_keeps_existing_active():
    course_id = await _seed_course(_course_id("inactive"))

    async with async_session_factory() as db:
        first = await create_knowledge_graph_version(
            db,
            course_id=course_id,
            nodes=[{"id": "active"}],
            edges=[],
            source_type="manual_import",
            generation_strategy="outline_v1",
        )
        inactive = await create_knowledge_graph_version(
            db,
            course_id=course_id,
            nodes=[{"id": "inactive"}],
            edges=[],
            source_type="agent_generated",
            generation_strategy="outline_v2",
            activate=False,
        )
        await db.commit()

        active = await get_active_knowledge_graph(db, course_id)

    assert inactive.version == 2
    assert inactive.is_active is False
    assert active.id == first.id


async def test_get_active_returns_highest_version_when_dirty_multiple_active():
    course_id = await _seed_course(_course_id("dirty-active"))

    async with async_session_factory() as db:
        first = await create_knowledge_graph_version(
            db,
            course_id=course_id,
            nodes=[{"id": "v1"}],
            edges=[],
            source_type="manual_import",
            generation_strategy="outline_v1",
        )
        second = await create_knowledge_graph_version(
            db,
            course_id=course_id,
            nodes=[{"id": "v2"}],
            edges=[],
            source_type="agent_generated",
            generation_strategy="outline_v2",
        )
        await db.execute(
            update(CourseKnowledgeGraph)
            .where(CourseKnowledgeGraph.id.in_([first.id, second.id]))
            .values(is_active=True)
        )
        await db.commit()

        active = await get_active_knowledge_graph(db, course_id)

    assert active.id == second.id
    assert active.version == 2
