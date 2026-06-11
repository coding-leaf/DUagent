import os
import sys

import pytest
import pytest_asyncio

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:////tmp/course_catalog_knowledge_repair.db",
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.base import Base
from app.db.session import async_session_factory, engine
from app.models.catalog import CourseCatalog, CourseCatalogMaterial
from app.services.course_catalog_knowledge_repair import (
    CatalogKnowledgeRepairProbe,
    recheck_catalog_knowledge_status,
    repair_catalog_knowledge_status,
)


@pytest_asyncio.fixture(autouse=True)
async def _reset_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


async def _seed_catalog(
    *,
    catalog_id: str = "catalog-repair",
    status: str = "ready",
    knowledge_status: str = "dirty",
    catalog_chunk_count: int = 5,
    material_statuses: list[str] | None = None,
    material_chunk_counts: list[int] | None = None,
) -> str:
    statuses = material_statuses or ["ingested"]
    chunks = material_chunk_counts or [catalog_chunk_count]
    async with async_session_factory() as db:
        db.add(
            CourseCatalog(
                id=catalog_id,
                title="Repair Catalog",
                status=status,
                knowledge_status=knowledge_status,
                material_count=len(statuses),
                chunk_count=catalog_chunk_count,
                last_error="stale dirty",
            )
        )
        for index, material_status in enumerate(statuses):
            db.add(
                CourseCatalogMaterial(
                    id=f"material-repair-{index}",
                    catalog_id=catalog_id,
                    filename=f"lesson-{index}.md",
                    source_type="file",
                    storage_uri=f"course_catalogs/{catalog_id}/material-{index}/lesson.md",
                    status=material_status,
                    chunk_count=chunks[index],
                )
            )
        await db.commit()
    return catalog_id


async def _get_catalog(catalog_id: str) -> CourseCatalog:
    async with async_session_factory() as db:
        catalog = await db.get(CourseCatalog, catalog_id)
        assert catalog is not None
        return catalog


class StaticProbe:
    def __init__(self, value: bool):
        self.value = value
        self.catalog_ids: list[str] = []

    async def __call__(self, catalog_id: str) -> CatalogKnowledgeRepairProbe:
        self.catalog_ids.append(catalog_id)
        return CatalogKnowledgeRepairProbe(ok=self.value, chunk_count=3 if self.value else 0)


@pytest.mark.asyncio
async def test_recheck_reports_repairable_when_dirty_catalog_has_ingested_chunks_and_qdrant_chunks():
    catalog_id = await _seed_catalog(catalog_chunk_count=5, material_chunk_counts=[5])
    probe = StaticProbe(True)

    async with async_session_factory() as db:
        result = await recheck_catalog_knowledge_status(db, catalog_id, qdrant_probe=probe)

    assert result.repairable is True
    assert result.current_knowledge_status == "dirty"
    assert result.target_knowledge_status == "ready"
    assert result.material_count == 1
    assert result.ingested_material_count == 1
    assert result.material_chunk_count == 5
    assert result.qdrant_chunk_count == 3
    assert result.reasons == []
    assert probe.catalog_ids == [catalog_id]


@pytest.mark.asyncio
async def test_repair_marks_dirty_catalog_ready_without_reingesting_when_recheck_passes():
    catalog_id = await _seed_catalog(catalog_chunk_count=5, material_chunk_counts=[5])

    async with async_session_factory() as db:
        result = await repair_catalog_knowledge_status(
            db,
            catalog_id,
            qdrant_probe=StaticProbe(True),
            apply=True,
        )

    assert result.repaired is True
    catalog = await _get_catalog(catalog_id)
    assert catalog.knowledge_status == "ready"
    assert catalog.chunk_count == 5
    assert catalog.last_error is None


@pytest.mark.asyncio
async def test_repair_does_not_change_catalog_when_material_is_not_ingested():
    catalog_id = await _seed_catalog(
        catalog_chunk_count=5,
        material_statuses=["ingested", "uploaded"],
        material_chunk_counts=[5, 0],
    )

    async with async_session_factory() as db:
        result = await repair_catalog_knowledge_status(
            db,
            catalog_id,
            qdrant_probe=StaticProbe(True),
            apply=True,
        )

    assert result.repaired is False
    assert "non_ingested_materials" in result.recheck.reasons
    catalog = await _get_catalog(catalog_id)
    assert catalog.knowledge_status == "dirty"
    assert catalog.last_error == "stale dirty"


@pytest.mark.asyncio
async def test_repair_does_not_change_catalog_when_qdrant_has_no_catalog_chunks():
    catalog_id = await _seed_catalog(catalog_chunk_count=5, material_chunk_counts=[5])

    async with async_session_factory() as db:
        result = await repair_catalog_knowledge_status(
            db,
            catalog_id,
            qdrant_probe=StaticProbe(False),
            apply=True,
        )

    assert result.repaired is False
    assert "qdrant_chunks_missing" in result.recheck.reasons
    catalog = await _get_catalog(catalog_id)
    assert catalog.knowledge_status == "dirty"
