import os
import sys
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch
from urllib.parse import urlparse

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
if not TEST_DATABASE_URL.startswith("mysql+"):
    pytest.skip("requires TEST_DATABASE_URL=mysql+...", allow_module_level=True)

parsed_test_url = urlparse(TEST_DATABASE_URL)
test_database_name = parsed_test_url.path.strip("/")
if test_database_name == "duagent":
    pytest.skip("refusing to use the real duagent database", allow_module_level=True)
if not (
    any(marker in test_database_name.lower() for marker in ("test", "pytest"))
    or test_database_name.startswith("admin_catalog_kg_generation")
):
    pytest.skip(
        "refusing to use a database not marked as test/pytest/admin_catalog_kg_generation",
        allow_module_level=True,
    )

os.environ["DATABASE_URL"] = TEST_DATABASE_URL

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.base import Base
from app.db.session import async_session_factory, engine
from app.main import app
from app.models.catalog import CourseCatalog, CourseOffering
from app.models.course import Course
from app.models.others import AsyncTask, CourseKnowledgeGraph
from app.models.user import User
from app.services.kg_generation import (
    KGGenerationInputError,
    generate_knowledge_graph_version,
    load_grounding_matches,
    load_kg_json_file,
    validate_kg_json_payload,
)


@pytest_asyncio.fixture(autouse=True)
async def _dispose_db_engine_after_test():
    yield
    await engine.dispose()


async def _reset_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def _seed_catalog_and_course(
    catalog_id: str = "catalog-kg-gen",
    course_id: str = "course-kg-gen",
    *,
    status: str = "draft",
    knowledge_status: str = "draft",
    chunk_count: int = 0,
) -> tuple[str, str]:
    async with async_session_factory() as db:
        db.add(
            User(
                id="teacher-kg-gen",
                email="teacher@example.com",
                username="teacher",
                password_hash="x",
                role="teacher",
            )
        )
        db.add(
            CourseCatalog(
                id=catalog_id,
                title="KG Catalog",
                status=status,
                knowledge_status=knowledge_status,
                chunk_count=chunk_count,
            )
        )
        db.add(
            Course(
                id=course_id,
                name="KG Course",
                course_code="KG001",
                teacher_id="teacher-kg-gen",
            )
        )
        db.add(
            CourseOffering(
                id=course_id,
                name="KG Course",
                catalog_id=catalog_id,
                teacher_id="teacher-kg-gen",
                class_code="KG001",
            )
        )
        await db.commit()
    return catalog_id, course_id


def _auth_headers(user_id: str, role: str) -> dict:
    from app.core.security import create_token

    token = create_token(user_id, role)
    return {"Authorization": f"Bearer {token}"}


async def _seed_user(user_id: str, role: str) -> None:
    async with async_session_factory() as db:
        db.add(
            User(
                id=user_id,
                email=f"{user_id}@example.com",
                username=user_id,
                password_hash="x",
                role=role,
            )
        )
        await db.commit()


async def _wait_for_task_completion(task_id: str, timeout: float = 1.5) -> AsyncTask:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        async with async_session_factory() as db:
            task = await db.get(AsyncTask, task_id)
            if task is not None and task.status in {"completed", "failed"}:
                return task
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError(f"task {task_id} did not complete in time")
        await asyncio.sleep(0.05)


def test_validate_kg_json_payload_rejects_missing_node_name():
    with pytest.raises(KGGenerationInputError) as exc:
        validate_kg_json_payload(
            {
                "nodes": [{"id": "pointer", "chapter": "第 6 章"}],
                "edges": [],
            }
        )
    assert "No valid nodes" in str(exc.value)


def test_validate_kg_json_payload_removes_dangling_edges():
    nodes, edges = validate_kg_json_payload(
        {
            "nodes": [{"id": "pointer", "name": "指针", "chapter": "第 6 章"}],
            "edges": [{"from": "missing", "to": "pointer"}],
        }
    )
    assert nodes == [{"id": "pointer", "name": "指针", "chapter": "第 6 章"}]
    assert edges == []


def test_load_kg_json_file_wraps_malformed_json(tmp_path):
    kg_file = tmp_path / "kg.json"
    kg_file.write_text("{bad json", encoding="utf-8")

    with pytest.raises(KGGenerationInputError) as exc:
        load_kg_json_file(kg_file)

    assert "Invalid KG JSON file" in str(exc.value)


def test_load_grounding_matches_wraps_malformed_json(tmp_path):
    grounding_file = tmp_path / "grounding.json"
    grounding_file.write_text("{bad json", encoding="utf-8")

    with pytest.raises(KGGenerationInputError) as exc:
        load_grounding_matches(grounding_file)

    assert "Invalid grounding JSON file" in str(exc.value)


@pytest.mark.asyncio
async def test_generate_kg_json_creates_active_version_without_chunk_ready_gate():
    await _reset_db()
    _, course_id = await _seed_catalog_and_course()

    result = await generate_knowledge_graph_version(
        course_id=course_id,
        source_type="kg_json",
        kg_json={
            "nodes": [{"id": "pointer", "name": "指针", "chapter": "第 6 章"}],
            "edges": [],
        },
        activate=True,
    )

    assert result["course_id"] == course_id
    assert result["version"] == 1
    assert result["node_count"] == 1
    assert result["edge_count"] == 0
    assert result["source_type"] == "manual_import"
    assert result["generation_strategy"] == "manual_kg_json"
    assert result["activated"] is True

    async with async_session_factory() as db:
        graph = (await db.execute(select(CourseKnowledgeGraph))).scalar_one()
        assert graph.course_id == course_id
        assert graph.is_active is True


@pytest.mark.asyncio
async def test_generate_kg_json_links_second_active_version_to_parent_graph():
    await _reset_db()
    _, course_id = await _seed_catalog_and_course()

    await generate_knowledge_graph_version(
        course_id=course_id,
        source_type="kg_json",
        kg_json={
            "nodes": [{"id": "pointer", "name": "指针", "chapter": "第 6 章"}],
            "edges": [],
        },
        activate=True,
    )

    async with async_session_factory() as db:
        first_graph = (await db.execute(select(CourseKnowledgeGraph))).scalar_one()
        first_graph_id = first_graph.id
        first_graph_version = first_graph.version
        first_graph_is_active = first_graph.is_active

    result = await generate_knowledge_graph_version(
        course_id=course_id,
        source_type="kg_json",
        kg_json={
            "nodes": [{"id": "array", "name": "数组", "chapter": "第 5 章"}],
            "edges": [],
        },
        activate=True,
    )

    assert first_graph_version == 1
    assert first_graph_is_active is True
    assert result["version"] == 2

    async with async_session_factory() as db:
        graphs = (
            await db.execute(
                select(CourseKnowledgeGraph)
                .where(CourseKnowledgeGraph.course_id == course_id)
                .order_by(CourseKnowledgeGraph.version.asc())
            )
        ).scalars().all()

    first_graph, second_graph = graphs
    assert first_graph.id == first_graph_id
    assert first_graph.is_active is False
    assert second_graph.id == result["graph_id"]
    assert second_graph.is_active is True
    assert second_graph.parent_graph_id == first_graph_id


def test_catalog_kg_host_course_migration_declares_column_index_and_fk():
    migration = Path(__file__).resolve().parent.parent / "migrations" / "2026-06-12-add-catalog-kg-host-course-id.sql"
    sql = migration.read_text(encoding="utf-8")

    assert "ADD COLUMN kg_host_course_id VARCHAR(32) NULL" in sql
    assert "ADD INDEX idx_course_catalog_kg_host_course_id (kg_host_course_id)" in sql
    assert "ADD CONSTRAINT fk_course_catalog_kg_host_course" in sql


@pytest.mark.asyncio
async def test_seed_ready_catalog_can_store_kg_host_course_id():
    await _reset_db()
    catalog_id, _ = await _seed_catalog_and_course(
        catalog_id="catalog-kg-host-course",
        course_id="host-course-1",
        status="ready",
        knowledge_status="ready",
        chunk_count=1,
    )

    async with async_session_factory() as db:
        catalog = await db.get(CourseCatalog, catalog_id)
        catalog.kg_host_course_id = "host-course-1"
        await db.commit()
        await db.refresh(catalog)

    assert catalog.kg_host_course_id == "host-course-1"


@pytest.mark.asyncio
async def test_generate_outline_text_uses_llm_and_creates_version():
    await _reset_db()
    _, course_id = await _seed_catalog_and_course()

    with patch(
        "app.services.kg_generation.generate_kg_from_llm",
        new_callable=AsyncMock,
    ) as mock_llm:
        mock_llm.return_value = {
            "nodes": [{"id": "array", "name": "数组", "chapter": "第 5 章"}],
            "edges": [],
        }
        result = await generate_knowledge_graph_version(
            course_id=course_id,
            source_type="outline_text",
            outline_text="第 5 章 数组",
            activate=True,
        )

    mock_llm.assert_awaited_once_with("第 5 章 数组")
    assert result["source_type"] == "outline_llm"
    assert result["generation_strategy"] == "legacy_outline"
    assert result["node_count"] == 1


@pytest.mark.asyncio
async def test_admin_get_catalog_kg_status_returns_empty_summary_with_course_id():
    await _reset_db()
    catalog_id, course_id = await _seed_catalog_and_course()
    await _seed_user("admin-kg-gen", "admin")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            f"/api/v1/admin/course-catalogs/{catalog_id}/knowledge-graphs",
            headers=_auth_headers("admin-kg-gen", "admin"),
        )

    assert response.status_code == 200, response.text
    assert response.json()["data"] == {
        "catalog_id": catalog_id,
        "course_id": course_id,
        "active_graph": None,
        "last_generation_task": None,
    }


@pytest.mark.asyncio
async def test_non_admin_cannot_start_catalog_kg_generation():
    await _reset_db()
    catalog_id, _ = await _seed_catalog_and_course()
    await _seed_user("teacher-kg-api", "teacher")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/admin/course-catalogs/{catalog_id}/knowledge-graphs/generations",
            headers=_auth_headers("teacher-kg-api", "teacher"),
            json={"source_type": "outline_text", "outline_text": "第 1 章 绪论"},
        )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_catalog_kg_generation_reuses_existing_hidden_host_course_when_no_offering():
    await _reset_db()
    await _seed_user("admin-kg-gen", "admin")
    async with async_session_factory() as db:
        host_course = Course(
            id="host-course-existing",
            name="[KG HOST] Existing Catalog",
            course_code="KGHNOOFF1",
            teacher_id="admin-kg-gen",
        )
        db.add(host_course)
        await db.flush()
        db.add(
            CourseCatalog(
                id="catalog-no-offering",
                title="No Offering Catalog",
                status="ready",
                knowledge_status="ready",
                chunk_count=3,
                kg_host_course_id=host_course.id,
            )
        )
        await db.commit()

    with patch("app.api.v1.catalogs.generate_knowledge_graph_version", new_callable=AsyncMock) as mock_generate:
        mock_generate.return_value = {
            "course_id": "host-course-existing",
            "graph_id": "graph-reuse",
            "version": 1,
            "node_count": 1,
            "edge_count": 0,
            "source_type": "catalog_chunks",
            "generation_strategy": "catalog_chunks_llm",
            "metrics": {},
            "activated": True,
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/admin/course-catalogs/catalog-no-offering/knowledge-graphs/generations",
                headers=_auth_headers("admin-kg-gen", "admin"),
                json={},
            )

    assert response.status_code == 202, response.text

    async with async_session_factory() as db:
        catalog = await db.get(CourseCatalog, "catalog-no-offering")
        host_course = await db.get(Course, "host-course-existing")
        task = (
            await db.execute(
                select(AsyncTask)
                .where(AsyncTask.task_type == "kg_generation")
                .order_by(AsyncTask.create_time.desc(), AsyncTask.id.desc())
                .limit(1)
            )
        ).scalar_one()

    assert catalog.kg_host_course_id == "host-course-existing"
    assert host_course is not None
    assert task.course_id == "host-course-existing"
    assert task.result["course_id"] == "host-course-existing"


@pytest.mark.asyncio
async def test_catalog_kg_generation_creates_hidden_host_course_when_no_offering():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    async with async_session_factory() as db:
        db.add(
            CourseCatalog(
                id="catalog-host-course",
                title="Host Course Catalog",
                status="ready",
                knowledge_status="ready",
                chunk_count=5,
            )
        )
        await db.commit()
    catalog_id = "catalog-host-course"

    with patch("app.api.v1.catalogs.generate_knowledge_graph_version", new_callable=AsyncMock) as mock_generate:
        mock_generate.return_value = {
            "course_id": "host-course-generated",
            "graph_id": "graph-1",
            "version": 1,
            "node_count": 1,
            "edge_count": 0,
            "source_type": "catalog_chunks",
            "generation_strategy": "catalog_chunks_llm",
            "metrics": {},
            "activated": True,
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/course-catalogs/{catalog_id}/knowledge-graphs/generations",
                headers=_auth_headers("admin-admin-gen", "admin"),
                json={},
            )

    assert response.status_code == 202, response.text

    async with async_session_factory() as db:
        catalog = await db.get(CourseCatalog, catalog_id)
        host_course = await db.get(Course, catalog.kg_host_course_id)
        task = (
            await db.execute(
                select(AsyncTask)
                .where(AsyncTask.task_type == "kg_generation")
                .order_by(AsyncTask.create_time.desc(), AsyncTask.id.desc())
                .limit(1)
            )
        ).scalar_one()

    assert catalog.kg_host_course_id is not None
    assert host_course is not None
    assert host_course.teacher_id == "admin-admin-gen"
    assert host_course.name.startswith("[KG HOST]")
    assert task.course_id == host_course.id
    assert task.result["course_id"] == host_course.id


@pytest.mark.asyncio
async def test_admin_catalog_kg_generation_rejects_catalog_chunks_when_knowledge_not_ready():
    await _reset_db()
    catalog_id, _ = await _seed_catalog_and_course(
        status="ready",
        knowledge_status="draft",
        chunk_count=3,
    )
    await _seed_user("admin-kg-gen", "admin")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/admin/course-catalogs/{catalog_id}/knowledge-graphs/generations",
            headers=_auth_headers("admin-kg-gen", "admin"),
            json={},
        )

    assert response.status_code == 409
    assert response.json()["detail"]["data"]["error_code"] == "knowledge_base_not_ready"

    async with async_session_factory() as db:
        catalog = await db.get(CourseCatalog, catalog_id)
        host_course_count = (
            await db.execute(
                select(func.count())
                .select_from(Course)
                .where(Course.name.like("[KG HOST]%"))
            )
        ).scalar_one()

    assert catalog.kg_host_course_id is None
    assert host_course_count == 0


@pytest.mark.asyncio
async def test_admin_catalog_kg_generation_rejects_catalog_chunks_when_empty():
    await _reset_db()
    catalog_id, _ = await _seed_catalog_and_course(
        status="ready",
        knowledge_status="ready",
        chunk_count=0,
    )
    await _seed_user("admin-kg-gen", "admin")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/admin/course-catalogs/{catalog_id}/knowledge-graphs/generations",
            headers=_auth_headers("admin-kg-gen", "admin"),
            json={},
        )

    assert response.status_code == 409
    assert response.json()["detail"]["data"]["error_code"] == "knowledge_base_empty"


@pytest.mark.asyncio
async def test_admin_catalog_kg_generation_rejects_duplicate_processing_task():
    await _reset_db()
    catalog_id, course_id = await _seed_catalog_and_course(
        status="ready",
        knowledge_status="ready",
        chunk_count=3,
    )
    await _seed_user("admin-kg-gen", "admin")
    async with async_session_factory() as db:
        db.add(
            AsyncTask(
                id="task-kg-running",
                task_type="kg_generation",
                status="processing",
                user_id="admin-kg-gen",
                course_id=course_id,
                result={"catalog_id": catalog_id, "course_id": course_id},
            )
        )
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/admin/course-catalogs/{catalog_id}/knowledge-graphs/generations",
            headers=_auth_headers("admin-kg-gen", "admin"),
            json={"source_type": "outline_text", "outline_text": "第 1 章 绪论"},
        )

    assert response.status_code == 409
    assert response.json()["detail"]["data"]["error_code"] == "kg_task_running"


@pytest.mark.asyncio
async def test_admin_catalog_kg_generation_creates_task_and_background_graph():
    await _reset_db()
    catalog_id, course_id = await _seed_catalog_and_course(
        status="ready",
        knowledge_status="ready",
        chunk_count=3,
    )
    await _seed_user("admin-kg-gen", "admin")

    with patch(
        "app.api.v1.catalogs.generate_knowledge_graph_version",
        new_callable=AsyncMock,
    ) as mock_generate:
        mock_generate.return_value = {
            "course_id": course_id,
            "graph_id": "graph-task-kg",
            "version": 1,
            "node_count": 1,
            "edge_count": 0,
            "source_type": "catalog_chunks",
            "generation_strategy": "catalog_chunks_llm",
            "metrics": {},
            "activated": True,
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/course-catalogs/{catalog_id}/knowledge-graphs/generations",
                headers=_auth_headers("admin-kg-gen", "admin"),
                json={},
            )

        assert response.status_code == 202, response.text
        data = response.json()["data"]
        assert data["catalog_id"] == catalog_id
        assert data["status"] == "processing"
        task_id = data["task_id"]

        task = await _wait_for_task_completion(task_id)
        assert task.task_type == "kg_generation"
        assert task.user_id == "admin-kg-gen"
        assert task.course_id == course_id
        assert task.status == "completed"
        assert task.progress == 100
        assert task.error_code is None
        assert task.result["catalog_id"] == catalog_id
        assert task.result["course_id"] == course_id
        assert task.result["source_type"] == "catalog_chunks"
        assert task.result["activate"] is True
        assert task.result["graph_id"] == "graph-task-kg"
        assert task.result["version"] == 1

    mock_generate.assert_awaited_once_with(
        course_id=course_id,
        source_type="catalog_chunks",
        catalog_id=catalog_id,
        outline_text=None,
        kg_json=None,
        activate=True,
    )


@pytest.mark.asyncio
async def test_admin_can_poll_kg_generation_task_owned_by_other_admin():
    await _reset_db()
    catalog_id, course_id = await _seed_catalog_and_course()
    await _seed_user("admin-owner", "admin")
    await _seed_user("admin-reader", "admin")
    async with async_session_factory() as db:
        db.add(
            AsyncTask(
                id="task-kg-admin",
                task_type="kg_generation",
                status="processing",
                user_id="admin-owner",
                course_id=course_id,
                result={"catalog_id": catalog_id, "course_id": course_id},
            )
        )
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/tasks/task-kg-admin",
            headers=_auth_headers("admin-reader", "admin"),
        )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["task_type"] == "kg_generation"
