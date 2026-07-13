import logging
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models.catalog import CourseCatalog, CourseCatalogMaterial
from app.models.others import AsyncTask
from app.services.agent_client import AgentClient, AgentServiceError

logger = logging.getLogger(__name__)
ingestion_agent_client = AgentClient(timeout=300.0)


def is_initial_ingestion(catalog: CourseCatalog) -> bool:
    return catalog.status != "ready"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def first_error(errors: list[str]) -> str:
    return (errors[0] if errors else "资料入库失败")[:500]


class CatalogIngestionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def start_catalog_ingestion(self, catalog_id: str, user_id: str) -> AsyncTask:
        result = await self.db.execute(
            select(CourseCatalog)
            .where(
                CourseCatalog.id == catalog_id,
                CourseCatalog.is_deleted == False,
            )
            .with_for_update()
        )
        catalog = result.scalar_one_or_none()
        if catalog is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": 40400, "message": "课程资源库不存在", "data": None},
            )
        if catalog.status == "ingesting" or catalog.knowledge_status == "ingesting":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": 40911, "message": "课程资源库正在入库中", "data": None},
            )

        result = await self.db.execute(
            select(CourseCatalogMaterial).where(
                CourseCatalogMaterial.catalog_id == catalog.id,
                CourseCatalogMaterial.is_deleted == False,
                CourseCatalogMaterial.status.in_(["uploaded", "failed"]),
            )
        )
        materials = result.scalars().all()
        if not materials:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": 40912, "message": "没有待入库资料", "data": None},
            )

        initial = is_initial_ingestion(catalog)
        catalog.status = "ingesting" if initial else "ready"
        catalog.knowledge_status = "ingesting"
        catalog.last_error = None

        for material in materials:
            material.status = "ingesting"
            material.last_error = None

        task = AsyncTask(
            task_type="course_catalog_ingestion",
            status="processing",
            progress=10,
            user_id=user_id,
            result={
                "catalog_id": catalog.id,
                "material_ids": [material.id for material in materials],
                "storage_uris": [material.storage_uri for material in materials],
                "initial": initial,
            },
        )
        self.db.add(task)
        await self.db.flush()
        await self.db.refresh(task)
        catalog.last_ingestion_task_id = task.id
        catalog.last_ingestion_status = "processing"
        await self.db.commit()
        return task


async def run_catalog_ingestion_background(task_id: str) -> None:
    async with async_session_factory() as db:
        task = None
        try:
            result = await db.execute(
                select(AsyncTask).where(AsyncTask.id == task_id, AsyncTask.is_deleted == False)
            )
            task = result.scalar_one_or_none()
            if task is None:
                logger.error("CourseCatalog ingestion task missing: %s", task_id)
                return

            task_context = task.result or {}
            catalog_id = task_context.get("catalog_id")
            material_ids = task_context.get("material_ids") or []
            initial = bool(task_context.get("initial"))

            catalog_result = await db.execute(
                select(CourseCatalog).where(
                    CourseCatalog.id == catalog_id,
                    CourseCatalog.is_deleted == False,
                )
            )
            catalog = catalog_result.scalar_one_or_none()
            if catalog is None:
                task.status = "failed"
                task.progress = 100
                task.error_code = "catalog_not_found"
                task.error_message = "课程资源库不存在"
                task.completed_at = now_utc()
                await db.commit()
                return

            material_result = await db.execute(
                select(CourseCatalogMaterial).where(
                    CourseCatalogMaterial.id.in_(material_ids),
                    CourseCatalogMaterial.catalog_id == catalog.id,
                    CourseCatalogMaterial.is_deleted == False,
                )
            )
            materials = material_result.scalars().all()
            payload = {
                "catalog_id": catalog.id,
                "materials": [{"storage_uri": material.storage_uri or ""} for material in materials],
            }

            try:
                agent_data = await ingestion_agent_client.post_json(
                    "/agent/v2/knowledge/ingestions",
                    payload,
                )
            except AgentServiceError as exc:
                message = exc.message[:500]
                for material in materials:
                    material.status = "failed"
                    material.last_error = message
                catalog.status = "failed" if initial else "ready"
                catalog.knowledge_status = "failed" if initial else "partial"
                catalog.last_ingestion_status = "failed"
                catalog.last_error = message
                task.status = "failed"
                task.progress = 100
                task.error_code = "agent_failed"
                task.error_message = message
                task.completed_at = now_utc()
                task.result = {**task_context, "agent_error": message}
                await db.commit()
                return

            results_by_uri = {
                item.get("storage_uri"): item
                for item in (agent_data.get("materials") or [])
                if item.get("storage_uri")
            }
            failed_errors: list[str] = []
            total_chunks = 0
            completed_at = now_utc()

            for material in materials:
                item = results_by_uri.get(material.storage_uri or "")
                if item and item.get("status") == "ingested":
                    chunk_count_raw = item.get("chunk_count")
                    chunk_count = int(chunk_count_raw) if chunk_count_raw is not None else 0
                    material.status = "ingested"
                    material.chunk_count = chunk_count
                    material.ingested_at = completed_at
                    material.last_error = None
                    total_chunks += chunk_count
                else:
                    error = ((item or {}).get("error") or "资料入库失败")[:500]
                    material.status = "failed"
                    material.last_error = error
                    failed_errors.append(error)

            agent_chunks = agent_data.get("chunk_count")
            added_chunks = int(agent_chunks) if agent_chunks is not None else total_chunks
            if added_chunks > 0:
                catalog.chunk_count = (catalog.chunk_count or 0) + added_chunks

            if failed_errors:
                has_ingested_material = any(material.status == "ingested" for material in materials)
                if initial and not has_ingested_material:
                    catalog.status = "failed"
                    catalog.knowledge_status = "failed"
                else:
                    catalog.status = "ready"
                    catalog.knowledge_status = "partial"
                error_message = first_error(failed_errors)
                catalog.last_ingestion_status = "failed"
                catalog.last_error = error_message
                task.status = "failed"
                task.error_code = "material_failed"
                task.error_message = error_message
            else:
                catalog.status = "ready"
                catalog.knowledge_status = "ready"
                catalog.last_ingestion_status = "completed"
                catalog.last_error = None
                task.status = "completed"
                task.error_code = None
                task.error_message = ""

            task.progress = 100
            task.completed_at = completed_at
            task.result = {**task_context, **agent_data}
            await db.commit()
        except Exception as exc:
            logger.exception("CourseCatalog ingestion task failed unexpectedly: %s", task_id)
            message = str(exc)[:500]
            await db.rollback()

            async with async_session_factory() as recovery_db:
                task_result = await recovery_db.execute(
                    select(AsyncTask).where(AsyncTask.id == task_id, AsyncTask.is_deleted == False)
                )
                recovery_task = task_result.scalar_one_or_none()
                if recovery_task is None:
                    return

                task_context = recovery_task.result or {}
                catalog_id = task_context.get("catalog_id")
                material_ids = task_context.get("material_ids") or []
                initial = bool(task_context.get("initial"))

                catalog = None
                if catalog_id:
                    catalog_result = await recovery_db.execute(
                        select(CourseCatalog).where(
                            CourseCatalog.id == catalog_id,
                            CourseCatalog.is_deleted == False,
                        )
                    )
                    catalog = catalog_result.scalar_one_or_none()
                if catalog is not None:
                    catalog.status = "failed" if initial else "ready"
                    catalog.knowledge_status = "failed" if initial else "partial"
                    catalog.last_ingestion_status = "failed"
                    catalog.last_error = message
                if material_ids:
                    material_result = await recovery_db.execute(
                        select(CourseCatalogMaterial).where(
                            CourseCatalogMaterial.id.in_(material_ids),
                            CourseCatalogMaterial.catalog_id == catalog_id,
                            CourseCatalogMaterial.is_deleted == False,
                        )
                    )
                    for material in material_result.scalars().all():
                        material.status = "failed"
                        material.chunk_count = 0
                        material.ingested_at = None
                        material.last_error = message

                recovery_task.status = "failed"
                recovery_task.progress = 100
                recovery_task.error_code = "unexpected_error"
                recovery_task.error_message = message
                recovery_task.completed_at = now_utc()
                recovery_task.result = {**task_context, "unexpected_error": message}
                await recovery_db.commit()
