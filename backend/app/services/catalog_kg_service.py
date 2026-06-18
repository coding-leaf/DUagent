import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models.catalog import CourseCatalog, CourseOffering
from app.models.course import Course
from app.models.others import AsyncTask
from app.schemas.catalog import CatalogKnowledgeGraphGenerationRequest
from app.services.course_knowledge_graphs import get_active_knowledge_graph
from app.services.kg_generation import KGGenerationInputError, generate_knowledge_graph_version

logger = logging.getLogger(__name__)
HOST_COURSE_NAME_PREFIX = "[KG HOST] "
COURSE_NAME_MAX_LENGTH = 100


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def async_task_catalog_id_expr():
    return func.json_unquote(func.json_extract(AsyncTask.result, "$.catalog_id"))


def catalog_kg_host_course_name(title: str) -> str:
    max_title_length = max(COURSE_NAME_MAX_LENGTH - len(HOST_COURSE_NAME_PREFIX), 0)
    return f"{HOST_COURSE_NAME_PREFIX}{(title or '')[:max_title_length]}"


def kg_knowledge_base_not_ready() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": 40917,
            "message": "课程资料尚未完成入库",
            "data": {"error_code": "knowledge_base_not_ready"},
        },
    )


def kg_knowledge_base_empty() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": 40918,
            "message": "课程知识库为空",
            "data": {"error_code": "knowledge_base_empty"},
        },
    )


class CatalogKGService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_catalog_kg_host_course(
        self,
        catalog: CourseCatalog,
        *,
        actor_user_id: str,
    ) -> Course:
        catalog_id = catalog.id
        locked_catalog = (
            await self.db.execute(
                select(CourseCatalog)
                .where(
                    CourseCatalog.id == catalog_id,
                    CourseCatalog.is_deleted == False,
                )
                .with_for_update()
            )
        ).scalar_one()

        if locked_catalog.kg_host_course_id:
            existing = await self.db.get(Course, locked_catalog.kg_host_course_id)
            if existing is not None and not existing.is_deleted:
                catalog.kg_host_course_id = existing.id
                return existing

        offering_result = await self.db.execute(
            select(CourseOffering)
            .where(
                CourseOffering.catalog_id == catalog_id,
                CourseOffering.is_deleted == False,
            )
            .order_by(CourseOffering.create_time.asc(), CourseOffering.id.asc())
            .limit(1)
        )
        offering = offering_result.scalars().first()
        if offering is not None:
            existing = await self.db.get(Course, offering.id)
            if existing is not None and not existing.is_deleted:
                locked_catalog.kg_host_course_id = existing.id
                catalog.kg_host_course_id = existing.id
                await self.db.flush()
                return existing

        host_course = Course(
            name=catalog_kg_host_course_name(locked_catalog.title),
            description=f"System host course for catalog {locked_catalog.id} knowledge graphs",
            course_code=f"KGH{uuid4().hex[:8].upper()}",
            teacher_id=actor_user_id,
        )
        try:
            self.db.add(host_course)
            await self.db.flush()
            locked_catalog.kg_host_course_id = host_course.id
            catalog.kg_host_course_id = host_course.id
            await self.db.flush()
            return host_course
        except IntegrityError:
            await self.db.rollback()
            reloaded_catalog = await self.db.get(CourseCatalog, catalog_id)
            if reloaded_catalog is not None and reloaded_catalog.kg_host_course_id:
                existing = await self.db.get(Course, reloaded_catalog.kg_host_course_id)
                if existing is not None and not existing.is_deleted:
                    return existing
            raise

    async def get_knowledge_graph_status(
        self,
        catalog: CourseCatalog,
        *,
        actor_user_id: str,
    ) -> dict:
        host_course = await self.get_or_create_catalog_kg_host_course(
            catalog,
            actor_user_id=actor_user_id,
        )
        graph = await get_active_knowledge_graph(self.db, host_course.id)

        task_result = await self.db.execute(
            select(AsyncTask)
            .where(
                AsyncTask.task_type == "kg_generation",
                AsyncTask.is_deleted == False,
                async_task_catalog_id_expr() == catalog.id,
            )
            .order_by(AsyncTask.create_time.desc(), AsyncTask.id.desc())
            .limit(1)
        )
        return {
            "host_course": host_course,
            "graph": graph,
            "last_generation_task": task_result.scalar_one_or_none(),
        }

    async def start_kg_generation(
        self,
        catalog: CourseCatalog,
        req: CatalogKnowledgeGraphGenerationRequest,
        *,
        actor_user_id: str,
    ) -> AsyncTask:
        if req.source_type == "catalog_chunks":
            if catalog.knowledge_status not in {"ready", "partial"}:
                raise kg_knowledge_base_not_ready()
            if (catalog.chunk_count or 0) <= 0:
                raise kg_knowledge_base_empty()

        duplicate_result = await self.db.execute(
            select(AsyncTask)
            .where(
                AsyncTask.task_type == "kg_generation",
                AsyncTask.status == "processing",
                AsyncTask.is_deleted == False,
                async_task_catalog_id_expr() == catalog.id,
            )
            .order_by(AsyncTask.create_time.desc(), AsyncTask.id.desc())
            .limit(1)
        )
        if duplicate_result.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": 40916,
                    "message": "课程知识图谱正在生成中",
                    "data": {"error_code": "kg_task_running"},
                },
            )

        host_course = await self.get_or_create_catalog_kg_host_course(
            catalog,
            actor_user_id=actor_user_id,
        )

        task_result = {
            "catalog_id": catalog.id,
            "course_id": host_course.id,
            "source_type": req.source_type,
            "activate": req.activate,
        }
        if req.outline_text is not None:
            task_result["outline_text"] = req.outline_text
        if req.kg_json is not None:
            task_result["kg_json"] = req.kg_json

        task = AsyncTask(
            task_type="kg_generation",
            status="processing",
            progress=10,
            user_id=actor_user_id,
            course_id=host_course.id,
            result=task_result,
        )
        self.db.add(task)
        await self.db.flush()
        await self.db.refresh(task)
        await self.db.commit()
        return task


async def run_catalog_kg_generation_background(task_id: str) -> None:
    async with async_session_factory() as db:
        result = await db.execute(
            select(AsyncTask).where(AsyncTask.id == task_id, AsyncTask.is_deleted == False)
        )
        task = result.scalar_one_or_none()
        if task is None:
            logger.error("Catalog KG generation task missing: %s", task_id)
            return

        task_context = task.result or {}
        try:
            service_result = await generate_knowledge_graph_version(
                course_id=str(task_context.get("course_id") or task.course_id or ""),
                source_type=str(task_context.get("source_type") or ""),
                catalog_id=task_context.get("catalog_id"),
                outline_text=task_context.get("outline_text"),
                kg_json=task_context.get("kg_json"),
                activate=bool(task_context.get("activate", True)),
            )
            task.status = "completed"
            task.progress = 100
            task.error_code = None
            task.error_message = ""
            task.completed_at = now_utc()
            task.result = {**task_context, **service_result}
            await db.commit()
        except KGGenerationInputError as exc:
            task.status = "failed"
            task.progress = 100
            task.error_code = getattr(exc, "error_code", "kg_invalid_input")
            task.error_message = str(exc)[:500]
            task.completed_at = now_utc()
            task.result = task_context
            await db.commit()
        except Exception as exc:
            logger.exception("Catalog KG generation task failed unexpectedly: %s", task_id)
            task.status = "failed"
            task.progress = 100
            task.error_code = "llm_kg_generation_failed"
            task.error_message = str(exc)[:500]
            task.completed_at = now_utc()
            task.result = task_context
            await db.commit()
