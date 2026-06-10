import importlib
import os
import sys
import types
import uuid
from urllib.parse import urlparse

import pytest
import pytest_asyncio
from sqlalchemy import select

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
MYSQL_AVAILABLE = TEST_DATABASE_URL.startswith("mysql+")
if MYSQL_AVAILABLE:
    parsed_test_url = urlparse(TEST_DATABASE_URL)
    test_database_name = parsed_test_url.path.strip("/")
    if test_database_name == "duagent":
        MYSQL_AVAILABLE = False
    if not any(marker in test_database_name.lower() for marker in ("test", "pytest")):
        MYSQL_AVAILABLE = False

if MYSQL_AVAILABLE:
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if MYSQL_AVAILABLE:
    from app.db.base import Base
    from app.db.session import async_session_factory, engine
    from app.models.course import Course
    from app.models.others import CourseKnowledgeGraph
    from app.models.user import User
    from app.services.course_knowledge_graphs import get_active_knowledge_graph
    from tools.generate_knowledge_graph import save_knowledge_graph_version
    from tools.import_knowledge_graph import (
        activate_existing_version,
        import_knowledge_graph_version,
    )


def test_import_cli_missing_source_does_not_import_app_settings(monkeypatch, capsys):
    class AppModule(types.ModuleType):
        def __getattr__(self, name):
            raise AssertionError("CLI parse validation imported app settings")

    monkeypatch.delitem(sys.modules, "tools.import_knowledge_graph", raising=False)
    monkeypatch.setitem(sys.modules, "app", AppModule("app"))
    monkeypatch.setattr(sys, "argv", ["import_knowledge_graph.py", "--course-id", "c1"])

    import_cli = importlib.import_module("tools.import_knowledge_graph")

    with pytest.raises(SystemExit) as exc_info:
        import_cli.main()

    captured = capsys.readouterr()
    assert exc_info.value.code == 2
    assert "one of --file, --stdin, --activate-version, or --activate-id is required" in captured.err


async def _ensure_schema() -> None:
    if not MYSQL_AVAILABLE:
        pytest.skip("requires TEST_DATABASE_URL=mysql+...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _course_id(label: str) -> str:
    return f"kgcli-{label[:3]}-{uuid.uuid4().hex[:8]}"


async def _seed_course(course_id: str) -> str:
    if not MYSQL_AVAILABLE:
        pytest.skip("requires TEST_DATABASE_URL=mysql+...")
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
            course_code=f"KGC{course_id[-8:]}",
            teacher_id=teacher.id,
        )
        db.add_all([teacher, course])
        await db.commit()
    return course_id


@pytest_asyncio.fixture(scope="module", autouse=True)
async def ensure_schema_once():
    if not MYSQL_AVAILABLE:
        yield
        return
    await _ensure_schema()
    yield
    await engine.dispose()


async def _graphs_for_course(course_id: str) -> list:
    if not MYSQL_AVAILABLE:
        pytest.skip("requires TEST_DATABASE_URL=mysql+...")
    async with async_session_factory() as db:
        result = await db.execute(
            select(CourseKnowledgeGraph)
            .where(CourseKnowledgeGraph.course_id == course_id)
            .order_by(CourseKnowledgeGraph.version)
        )
        return list(result.scalars().all())


@pytest.mark.asyncio(loop_scope="module")
async def test_generate_save_creates_new_active_version_without_overwriting_old_active():
    if not MYSQL_AVAILABLE:
        pytest.skip("requires TEST_DATABASE_URL=mysql+...")
    course_id = await _seed_course(_course_id("generate"))

    first = await save_knowledge_graph_version(
        course_id,
        [{"id": "v1"}],
        [],
        metrics={"run": 1},
    )
    second = await save_knowledge_graph_version(
        course_id,
        [{"id": "v2"}],
        [],
        metrics={"run": 2},
    )

    graphs = await _graphs_for_course(course_id)

    assert [graph.version for graph in graphs] == [1, 2]
    assert graphs[0].id == first["graph_id"]
    assert graphs[0].nodes == [{"id": "v1"}]
    assert graphs[0].is_active is False
    assert second["version"] == 2
    assert second["source_type"] == "outline_llm"
    assert second["generation_strategy"] == "legacy_outline"
    assert second["activated"] is True
    assert graphs[1].parent_graph_id == graphs[0].id
    assert [graph.id for graph in graphs if graph.is_active] == [graphs[1].id]


@pytest.mark.asyncio(loop_scope="module")
async def test_import_no_activate_keeps_existing_active_version():
    if not MYSQL_AVAILABLE:
        pytest.skip("requires TEST_DATABASE_URL=mysql+...")
    course_id = await _seed_course(_course_id("inactive"))

    active_result = await import_knowledge_graph_version(
        course_id,
        [{"id": "active"}],
        [],
    )
    inactive_result = await import_knowledge_graph_version(
        course_id,
        [{"id": "history"}],
        [],
        activate=False,
    )

    async with async_session_factory() as db:
        active = await get_active_knowledge_graph(db, course_id)

    graphs = await _graphs_for_course(course_id)

    assert active.id == active_result["graph_id"]
    assert inactive_result["version"] == 2
    assert inactive_result["source_type"] == "manual_import"
    assert inactive_result["generation_strategy"] == "legacy_outline"
    assert inactive_result["activated"] is False
    assert [graph.id for graph in graphs if graph.is_active] == [active_result["graph_id"]]


@pytest.mark.asyncio(loop_scope="module")
async def test_import_activate_rollback_switches_active_only():
    if not MYSQL_AVAILABLE:
        pytest.skip("requires TEST_DATABASE_URL=mysql+...")
    course_id = await _seed_course(_course_id("rollback"))

    first = await import_knowledge_graph_version(course_id, [{"id": "v1"}], [])
    second = await import_knowledge_graph_version(course_id, [{"id": "v2"}], [])

    by_version = await activate_existing_version(course_id, version=1)
    by_id = await activate_existing_version(course_id, graph_id=second["graph_id"])

    graphs = await _graphs_for_course(course_id)

    assert by_version["graph_id"] == first["graph_id"]
    assert by_version["activated"] is True
    assert by_id["graph_id"] == second["graph_id"]
    assert by_id["version"] == 2
    assert len(graphs) == 2
    assert [graph.id for graph in graphs if graph.is_active] == [second["graph_id"]]
