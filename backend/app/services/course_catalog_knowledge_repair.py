from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import CourseCatalog, CourseCatalogMaterial


QdrantProbe = Callable[[str], Awaitable["CatalogKnowledgeRepairProbe"]]


@dataclass(frozen=True)
class CatalogKnowledgeRepairProbe:
    ok: bool
    chunk_count: int = 0
    error: str | None = None


@dataclass(frozen=True)
class CatalogKnowledgeRecheckResult:
    catalog_id: str
    found: bool
    current_status: str | None = None
    current_knowledge_status: str | None = None
    target_knowledge_status: str | None = None
    repairable: bool = False
    material_count: int = 0
    ingested_material_count: int = 0
    material_chunk_count: int = 0
    catalog_chunk_count: int = 0
    qdrant_chunk_count: int = 0
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CatalogKnowledgeRepairResult:
    recheck: CatalogKnowledgeRecheckResult
    repaired: bool
    dry_run: bool


async def recheck_catalog_knowledge_status(
    db: AsyncSession,
    catalog_id: str,
    *,
    qdrant_probe: QdrantProbe | None = None,
) -> CatalogKnowledgeRecheckResult:
    catalog = await db.get(CourseCatalog, catalog_id)
    if catalog is None or catalog.is_deleted:
        return CatalogKnowledgeRecheckResult(
            catalog_id=catalog_id,
            found=False,
            reasons=["catalog_missing"],
        )

    result = await db.execute(
        select(CourseCatalogMaterial).where(
            CourseCatalogMaterial.catalog_id == catalog.id,
            CourseCatalogMaterial.is_deleted == False,
        )
    )
    materials = list(result.scalars().all())
    material_count = len(materials)
    ingested_material_count = sum(1 for item in materials if item.status == "ingested")
    material_chunk_count = sum(int(item.chunk_count or 0) for item in materials)
    catalog_chunk_count = int(catalog.chunk_count or 0)

    reasons: list[str] = []
    target_knowledge_status: str | None = None

    if catalog.status != "ready":
        reasons.append("catalog_not_ready")
    if catalog.knowledge_status != "dirty":
        reasons.append("knowledge_status_not_dirty")
    if material_count <= 0:
        reasons.append("materials_missing")
    if material_count > 0 and ingested_material_count != material_count:
        reasons.append("non_ingested_materials")
    if catalog_chunk_count <= 0:
        reasons.append("catalog_chunks_missing")
    if material_chunk_count <= 0:
        reasons.append("material_chunks_missing")

    qdrant_chunk_count = 0
    if qdrant_probe is None:
        reasons.append("qdrant_probe_missing")
    else:
        probe_result = await qdrant_probe(catalog.id)
        qdrant_chunk_count = int(probe_result.chunk_count or 0)
        if not probe_result.ok or qdrant_chunk_count <= 0:
            reasons.append("qdrant_chunks_missing")

    repairable = not reasons
    if repairable:
        target_knowledge_status = "ready"

    return CatalogKnowledgeRecheckResult(
        catalog_id=catalog.id,
        found=True,
        current_status=catalog.status,
        current_knowledge_status=catalog.knowledge_status,
        target_knowledge_status=target_knowledge_status,
        repairable=repairable,
        material_count=material_count,
        ingested_material_count=ingested_material_count,
        material_chunk_count=material_chunk_count,
        catalog_chunk_count=catalog_chunk_count,
        qdrant_chunk_count=qdrant_chunk_count,
        reasons=reasons,
    )


async def repair_catalog_knowledge_status(
    db: AsyncSession,
    catalog_id: str,
    *,
    qdrant_probe: QdrantProbe | None = None,
    apply: bool = False,
) -> CatalogKnowledgeRepairResult:
    recheck = await recheck_catalog_knowledge_status(
        db,
        catalog_id,
        qdrant_probe=qdrant_probe,
    )
    if not apply or not recheck.repairable:
        return CatalogKnowledgeRepairResult(
            recheck=recheck,
            repaired=False,
            dry_run=not apply,
        )

    catalog = await db.get(CourseCatalog, catalog_id)
    if catalog is None or catalog.is_deleted:
        return CatalogKnowledgeRepairResult(
            recheck=recheck,
            repaired=False,
            dry_run=False,
        )

    catalog.knowledge_status = "ready"
    catalog.last_error = None
    await db.commit()

    return CatalogKnowledgeRepairResult(
        recheck=recheck,
        repaired=True,
        dry_run=False,
    )
