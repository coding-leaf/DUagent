import os
import sys
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:////tmp/admin_catalog_kg_generation.db",
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.base import Base
from app.db.session import async_session_factory, engine
from app.models.catalog import CourseCatalog, CourseOffering
from app.models.course import Course
from app.models.others import CourseKnowledgeGraph
from app.models.user import User
from app.services.kg_generation import (
    KGGenerationInputError,
    generate_knowledge_graph_version,
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
                status="draft",
                knowledge_status="draft",
                chunk_count=0,
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
