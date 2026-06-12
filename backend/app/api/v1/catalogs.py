import asyncio
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Body, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_role
from app.core.config import settings
from app.db.session import async_session_factory
from app.models.catalog import CourseCatalog, CourseCatalogMaterial, CourseOffering
from app.models.course import Course
from app.models.others import AsyncTask, Resource
from app.models.quiz import QuizQuestion
from app.models.user import User
from app.schemas.catalog import (
    CatalogKnowledgeGraphGenerationRequest,
    CourseCatalogCreateRequest,
    CourseCatalogMaterialCreateRequest,
)
from app.schemas.operations import CatalogResourceGenerateRequest
from app.services.agent_client import AgentClient, AgentServiceError, agent_client
from app.services.course_knowledge_graphs import get_active_knowledge_graph
from app.services.kg_generation import KGGenerationInputError, generate_knowledge_graph_version
from app.services.kg_resource_targets import select_core_resource_targets
from app.services.resource_scope import resource_scope_clause

router = APIRouter(prefix="/api/v1", tags=["course-catalogs"])
logger = logging.getLogger(__name__)
ingestion_agent_client = AgentClient(timeout=300.0)

SUPPORTED_MATERIAL_SUFFIXES = {".txt", ".md", ".pdf"}
UPLOAD_CHUNK_SIZE = 1024 * 1024
RESOURCE_TYPES = {"document", "mindmap", "reading", "code"}
KG_RESOURCE_TARGET_LIMIT = 10
HOST_COURSE_NAME_PREFIX = "[KG HOST] "
COURSE_NAME_MAX_LENGTH = 100


def _catalog_item(catalog: CourseCatalog) -> dict:
    return {
        "id": catalog.id,
        "title": catalog.title,
        "description": catalog.description or "",
        "status": catalog.status,
        "knowledge_status": catalog.knowledge_status,
        "material_count": catalog.material_count,
        "last_ingestion_task_id": catalog.last_ingestion_task_id,
        "last_ingestion_status": catalog.last_ingestion_status,
        "chunk_count": catalog.chunk_count or 0,
        "last_error": catalog.last_error,
        "created_at": catalog.create_time.isoformat() if catalog.create_time else "",
    }


def _safe_filename(filename: str) -> str:
    raw_name = (filename or "").strip()
    name = Path(raw_name).name.strip()
    if (
        not raw_name
        or not name
        or name in {".", ".."}
        or raw_name != name
        or "/" in raw_name
        or "\\" in raw_name
        or ".." in Path(raw_name).parts
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 40020, "message": "文件名不合法", "data": None},
        )
    return name


def _material_item(material: CourseCatalogMaterial, include_storage_uri: bool = False) -> dict:
    item = {
        "id": material.id,
        "catalog_id": material.catalog_id,
        "filename": material.filename,
        "source_type": material.source_type,
        "file_size": material.file_size or 0,
        "status": material.status,
        "chunk_count": material.chunk_count or 0,
        "last_error": material.last_error,
        "ingested_at": material.ingested_at.isoformat() if material.ingested_at else None,
        "created_at": material.create_time.isoformat() if material.create_time else "",
    }
    if include_storage_uri:
        item["storage_uri"] = material.storage_uri
    return item


def _state_after_material_added(catalog: CourseCatalog) -> tuple[str, str]:
    if catalog.status == "ready":
        return "ready", "dirty"
    return "draft", "draft"


def _is_initial_ingestion(catalog: CourseCatalog) -> bool:
    return catalog.status != "ready"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _first_error(errors: list[str]) -> str:
    return (errors[0] if errors else "资料入库失败")[:500]


def _remove_material_dir(target_path: Path) -> None:
    shutil.rmtree(target_path.parent, ignore_errors=True)


def _webhook_url(request: Request) -> str:
    base = str(request.base_url).rstrip("/")
    return f"{base}/api/v1/webhooks/agent"


def _async_task_catalog_id_expr():
    return func.json_unquote(func.json_extract(AsyncTask.result, "$.catalog_id"))


def _is_explicit_resource_target(req: CatalogResourceGenerateRequest) -> bool:
    return bool((req.chapter or "").strip() or (req.knowledge_point or "").strip())



def _course_material_missing() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": 40913, "message": "课程资料尚未完成入库", "data": None},
    )


def _knowledge_base_empty() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": 40914, "message": "课程知识库为空", "data": None},
    )


def _course_offering_missing() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": 40915, "message": "课程资源库尚未绑定教学班", "data": None},
    )


def _kg_knowledge_base_not_ready() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": 40917,
            "message": "课程资料尚未完成入库",
            "data": {"error_code": "knowledge_base_not_ready"},
        },
    )


def _kg_knowledge_base_empty() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": 40918,
            "message": "课程知识库为空",
            "data": {"error_code": "knowledge_base_empty"},
        },
    )


async def _first_catalog_offering(db: AsyncSession, catalog_id: str) -> CourseOffering | None:
    result = await db.execute(
        select(CourseOffering)
        .where(
            CourseOffering.catalog_id == catalog_id,
            CourseOffering.is_deleted == False,
        )
        .order_by(CourseOffering.create_time.asc(), CourseOffering.id.asc())
    )
    return result.scalars().first()


async def _get_or_create_catalog_kg_host_course(
    db: AsyncSession,
    catalog: CourseCatalog,
    *,
    actor_user_id: str,
) -> Course:
    catalog_id = catalog.id
    locked_catalog = (
        await db.execute(
            select(CourseCatalog)
            .where(
                CourseCatalog.id == catalog_id,
                CourseCatalog.is_deleted == False,
            )
            .with_for_update()
        )
    ).scalar_one()

    if locked_catalog.kg_host_course_id:
        existing = await db.get(Course, locked_catalog.kg_host_course_id)
        if existing is not None and not existing.is_deleted:
            catalog.kg_host_course_id = existing.id
            return existing

    host_course = Course(
        name=_catalog_kg_host_course_name(locked_catalog.title),
        description=f"System host course for catalog {locked_catalog.id} knowledge graphs",
        course_code=f"KGH{uuid4().hex[:8].upper()}",
        teacher_id=actor_user_id,
    )
    try:
        db.add(host_course)
        await db.flush()
        locked_catalog.kg_host_course_id = host_course.id
        catalog.kg_host_course_id = host_course.id
        await db.flush()
        return host_course
    except IntegrityError:
        await db.rollback()
        reloaded_catalog = await db.get(CourseCatalog, catalog_id)
        if reloaded_catalog is not None and reloaded_catalog.kg_host_course_id:
            existing = await db.get(Course, reloaded_catalog.kg_host_course_id)
            if existing is not None and not existing.is_deleted:
                return existing
        raise


def _catalog_kg_host_course_name(title: str) -> str:
    max_title_length = max(COURSE_NAME_MAX_LENGTH - len(HOST_COURSE_NAME_PREFIX), 0)
    return f"{HOST_COURSE_NAME_PREFIX}{(title or '')[:max_title_length]}"


def _knowledge_graph_summary(graph) -> dict:
    return {
        "graph_id": graph.id,
        "course_id": graph.course_id,
        "version": graph.version,
        "source_type": graph.source_type,
        "generation_strategy": graph.generation_strategy,
        "node_count": len(graph.nodes or []),
        "edge_count": len(graph.edges or []),
        "is_active": graph.is_active,
        "created_at": graph.create_time.isoformat() if graph.create_time else "",
    }


def _knowledge_graph_task_summary(task: AsyncTask) -> dict:
    return {
        "task_id": task.id,
        "status": task.status,
        "progress": task.progress,
        "error_code": task.error_code,
        "error_message": task.error_message,
        "created_at": task.create_time.isoformat() if task.create_time else "",
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


async def _run_catalog_kg_generation_background(task_id: str) -> None:
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
            task.completed_at = _now_utc()
            task.result = {**task_context, **service_result}
            await db.commit()
        except KGGenerationInputError as exc:
            task.status = "failed"
            task.progress = 100
            task.error_code = getattr(exc, "error_code", "kg_invalid_input")
            task.error_message = str(exc)[:500]
            task.completed_at = _now_utc()
            task.result = task_context
            await db.commit()
        except Exception as exc:
            logger.exception("Catalog KG generation task failed unexpectedly: %s", task_id)
            task.status = "failed"
            task.progress = 100
            task.error_code = "llm_kg_generation_failed"
            task.error_message = str(exc)[:500]
            task.completed_at = _now_utc()
            task.result = task_context
            await db.commit()


async def _run_catalog_ingestion_background(task_id: str) -> None:
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
                task.completed_at = _now_utc()
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
                    "/agent/v1/knowledge/ingestions",
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
                task.completed_at = _now_utc()
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
            completed_at = _now_utc()

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
                error_message = _first_error(failed_errors)
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
                recovery_task.completed_at = _now_utc()
                recovery_task.result = {**task_context, "unexpected_error": message}
                await recovery_db.commit()


async def _get_admin_catalog_or_404(db: AsyncSession, catalog_id: str) -> CourseCatalog:
    result = await db.execute(
        select(CourseCatalog).where(
            CourseCatalog.id == catalog_id,
            CourseCatalog.is_deleted == False,
        )
    )
    catalog = result.scalar_one_or_none()
    if catalog is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40400, "message": "课程资源库不存在", "data": None},
        )
    return catalog


@router.get("/admin/course-catalogs")
async def admin_list_course_catalogs(
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    query = select(CourseCatalog).where(CourseCatalog.is_deleted == False)
    if status_filter:
        query = query.where(CourseCatalog.status == status_filter)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
    result = await db.execute(
        query.order_by(CourseCatalog.create_time.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    catalogs = result.scalars().all()
    return {
        "code": 200,
        "message": "success",
        "data": {
            "catalogs": [_catalog_item(c) for c in catalogs],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }


@router.post("/admin/course-catalogs", status_code=201)
async def admin_create_course_catalog(
    req: CourseCatalogCreateRequest,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    catalog = CourseCatalog(
        title=req.title.strip(),
        description=(req.description or "").strip(),
        status="draft",
        knowledge_status="draft",
        material_count=0,
    )
    db.add(catalog)
    await db.flush()
    await db.refresh(catalog)
    return {"code": 201, "message": "created", "data": _catalog_item(catalog)}


@router.get("/admin/course-catalogs/{catalog_id}")
async def admin_get_course_catalog(
    catalog_id: str,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    catalog = await _get_admin_catalog_or_404(db, catalog_id)
    return {"code": 200, "message": "success", "data": _catalog_item(catalog)}


@router.post("/admin/course-catalogs/{catalog_id}/materials/upload", status_code=201)
async def admin_upload_catalog_material(
    catalog_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    catalog = await _get_admin_catalog_or_404(db, catalog_id)
    if catalog.status == "ingesting" or catalog.knowledge_status == "ingesting":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": 40911, "message": "课程资源库正在入库中", "data": None},
        )

    filename = _safe_filename(file.filename or "")
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_MATERIAL_SUFFIXES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 40021, "message": "不支持的资料类型", "data": None},
        )

    material_id = uuid4().hex[:16]
    root = Path(settings.COURSE_CATALOG_STORAGE_ROOT)
    relative_path = Path(root.name) / catalog.id / material_id / filename
    target_path = root / catalog.id / material_id / filename
    target_path.parent.mkdir(parents=True, exist_ok=True)

    file_size = 0
    try:
        with target_path.open("wb") as f:
            while chunk := await file.read(UPLOAD_CHUNK_SIZE):
                file_size += len(chunk)
                if file_size > settings.COURSE_CATALOG_MAX_UPLOAD_BYTES:
                    _remove_material_dir(target_path)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail={"code": 41320, "message": "资料文件过大", "data": None},
                    )
                f.write(chunk)
    except HTTPException:
        raise
    except Exception:
        _remove_material_dir(target_path)
        raise

    if file_size == 0:
        _remove_material_dir(target_path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 40022, "message": "资料文件不能为空", "data": None},
        )

    next_status, next_knowledge_status = _state_after_material_added(catalog)
    material = CourseCatalogMaterial(
        id=material_id,
        catalog_id=catalog.id,
        filename=filename,
        source_type="file",
        storage_uri=relative_path.as_posix(),
        file_size=file_size,
        status="uploaded",
    )

    try:
        update_result = await db.execute(
            update(CourseCatalog)
            .where(
                CourseCatalog.id == catalog.id,
                CourseCatalog.is_deleted == False,
                CourseCatalog.status != "ingesting",
                CourseCatalog.knowledge_status != "ingesting",
            )
            .values(
                material_count=CourseCatalog.material_count + 1,
                status=next_status,
                knowledge_status=next_knowledge_status,
                last_error=None,
            )
        )
        if update_result.rowcount == 0:
            _remove_material_dir(target_path)
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": 40911, "message": "课程资源库正在入库中", "data": None},
            )

        db.add(material)
        await db.flush()
        await db.refresh(material)
        await db.commit()
    except HTTPException:
        raise
    except Exception:
        _remove_material_dir(target_path)
        await db.rollback()
        raise

    return {"code": 201, "message": "created", "data": _material_item(material)}


@router.post("/admin/course-catalogs/{catalog_id}/materials", status_code=201)
async def admin_create_catalog_material(
    catalog_id: str,
    req: CourseCatalogMaterialCreateRequest,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    catalog = await _get_admin_catalog_or_404(db, catalog_id)
    update_result = await db.execute(
        update(CourseCatalog)
        .where(
            CourseCatalog.id == catalog.id,
            CourseCatalog.is_deleted == False,
            CourseCatalog.status != "ingesting",
            CourseCatalog.knowledge_status != "ingesting",
        )
        .values(
            material_count=CourseCatalog.material_count + 1,
            status="ready" if catalog.status == "ready" else "draft",
            knowledge_status="dirty" if catalog.status == "ready" else "draft",
            last_error=None,
        )
    )
    if update_result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": 40911, "message": "课程资源库正在入库中", "data": None},
        )
    material = CourseCatalogMaterial(
        catalog_id=catalog.id,
        filename=req.filename.strip(),
        source_type=req.source_type.strip(),
        storage_uri=req.storage_uri,
        file_size=0,
        status="uploaded",
    )
    db.add(material)
    await db.flush()
    await db.refresh(material)
    return {"code": 201, "message": "created", "data": _material_item(material)}


@router.get("/admin/course-catalogs/{catalog_id}/materials")
async def admin_list_catalog_materials(
    catalog_id: str,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    await _get_admin_catalog_or_404(db, catalog_id)
    result = await db.execute(
        select(CourseCatalogMaterial)
        .where(
            CourseCatalogMaterial.catalog_id == catalog_id,
            CourseCatalogMaterial.is_deleted == False,
        )
        .order_by(CourseCatalogMaterial.create_time.desc())
    )
    materials = result.scalars().all()
    return {
        "code": 200,
        "message": "success",
        "data": {
            "materials": [_material_item(m) for m in materials]
        },
    }


@router.delete("/admin/course-catalogs/{catalog_id}/materials/{material_id}")
async def admin_delete_catalog_material(
    catalog_id: str,
    material_id: str,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    catalog = await _get_admin_catalog_or_404(db, catalog_id)
    if catalog.status == "ingesting" or catalog.knowledge_status == "ingesting":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": 40911, "message": "课程资源库正在入库中", "data": None},
        )

    result = await db.execute(
        select(CourseCatalogMaterial).where(
            CourseCatalogMaterial.id == material_id,
            CourseCatalogMaterial.catalog_id == catalog.id,
            CourseCatalogMaterial.is_deleted == False,
        )
    )
    material = result.scalar_one_or_none()
    if material is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40411, "message": "课程资源库资料不存在", "data": None},
        )

    material.is_deleted = True
    remaining_result = await db.execute(
        select(
            func.count(CourseCatalogMaterial.id),
            func.coalesce(func.sum(CourseCatalogMaterial.chunk_count), 0),
        ).where(
            CourseCatalogMaterial.catalog_id == catalog.id,
            CourseCatalogMaterial.is_deleted == False,
            CourseCatalogMaterial.id != material.id,
        )
    )
    remaining_count, remaining_chunks = remaining_result.one()
    catalog.material_count = int(remaining_count or 0)
    catalog.chunk_count = int(remaining_chunks or 0)
    if catalog.knowledge_status in {"ready", "partial"}:
        catalog.knowledge_status = "dirty"
    catalog.last_error = None
    await db.commit()

    return {
        "code": 200,
        "message": "deleted",
        "data": {
            "id": material.id,
            "catalog_id": catalog.id,
            "deleted": True,
            "knowledge_status": catalog.knowledge_status,
        },
    }


@router.get("/admin/course-catalogs/{catalog_id}/knowledge-status")
async def admin_get_catalog_knowledge_status(
    catalog_id: str,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    catalog = await _get_admin_catalog_or_404(db, catalog_id)
    pending_count = (
        await db.execute(
            select(func.count())
            .select_from(CourseCatalogMaterial)
            .where(
                CourseCatalogMaterial.catalog_id == catalog.id,
                CourseCatalogMaterial.is_deleted == False,
                CourseCatalogMaterial.status == "uploaded",
            )
        )
    ).scalar() or 0
    failed_count = (
        await db.execute(
            select(func.count())
            .select_from(CourseCatalogMaterial)
            .where(
                CourseCatalogMaterial.catalog_id == catalog.id,
                CourseCatalogMaterial.is_deleted == False,
                CourseCatalogMaterial.status == "failed",
            )
        )
    ).scalar() or 0
    return {
        "code": 200,
        "message": "success",
        "data": {
            "catalog_id": catalog.id,
            "status": catalog.status,
            "knowledge_status": catalog.knowledge_status,
            "material_count": catalog.material_count or 0,
            "chunk_count": catalog.chunk_count or 0,
            "pending_material_count": pending_count,
            "failed_material_count": failed_count,
            "last_ingestion_task_id": catalog.last_ingestion_task_id,
            "last_ingestion_status": catalog.last_ingestion_status,
            "last_error": catalog.last_error,
        },
    }


@router.get("/admin/course-catalogs/{catalog_id}/knowledge-graphs")
async def admin_get_catalog_knowledge_graph_status(
    catalog_id: str,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    catalog = await _get_admin_catalog_or_404(db, catalog_id)
    host_course = await _get_or_create_catalog_kg_host_course(
        db,
        catalog,
        actor_user_id=current_user.id,
    )
    graph = await get_active_knowledge_graph(db, host_course.id)

    task_result = await db.execute(
        select(AsyncTask)
        .where(
            AsyncTask.task_type == "kg_generation",
            AsyncTask.is_deleted == False,
            _async_task_catalog_id_expr() == catalog.id,
        )
        .order_by(AsyncTask.create_time.desc(), AsyncTask.id.desc())
        .limit(1)
    )
    last_generation_task = task_result.scalar_one_or_none()

    return {
        "code": 200,
        "message": "success",
        "data": {
            "catalog_id": catalog.id,
            "course_id": host_course.id,
            "active_graph": _knowledge_graph_summary(graph) if graph else None,
            "last_generation_task": (
                _knowledge_graph_task_summary(last_generation_task)
                if last_generation_task is not None
                else None
            ),
        },
    }


@router.post("/admin/course-catalogs/{catalog_id}/ingestions", status_code=202)
async def admin_start_catalog_ingestion(
    catalog_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
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

    result = await db.execute(
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

    initial = _is_initial_ingestion(catalog)
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
        user_id=current_user.id,
        result={
            "catalog_id": catalog.id,
            "material_ids": [material.id for material in materials],
            "storage_uris": [material.storage_uri for material in materials],
            "initial": initial,
        },
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)
    catalog.last_ingestion_task_id = task.id
    catalog.last_ingestion_status = "processing"
    await db.commit()

    background_tasks.add_task(_run_catalog_ingestion_background, task.id)

    return {
        "code": 202,
        "message": "accepted",
        "data": {"task_id": task.id, "catalog_id": catalog.id, "status": "processing"},
    }


@router.post("/admin/course-catalogs/{catalog_id}/knowledge-graphs/generations", status_code=202)
async def admin_generate_catalog_knowledge_graph(
    catalog_id: str,
    req: CatalogKnowledgeGraphGenerationRequest | None = Body(default=None),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    req = req or CatalogKnowledgeGraphGenerationRequest()
    catalog = await _get_admin_catalog_or_404(db, catalog_id)

    if req.source_type == "catalog_chunks":
        if catalog.knowledge_status not in {"ready", "partial"}:
            raise _kg_knowledge_base_not_ready()
        if (catalog.chunk_count or 0) <= 0:
            raise _kg_knowledge_base_empty()

    duplicate_result = await db.execute(
        select(AsyncTask)
        .where(
            AsyncTask.task_type == "kg_generation",
            AsyncTask.status == "processing",
            AsyncTask.is_deleted == False,
            _async_task_catalog_id_expr() == catalog.id,
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

    host_course = await _get_or_create_catalog_kg_host_course(
        db,
        catalog,
        actor_user_id=current_user.id,
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
        user_id=current_user.id,
        course_id=host_course.id,
        result=task_result,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)
    await db.commit()

    asyncio.create_task(_run_catalog_kg_generation_background(task.id))

    return {
        "code": 202,
        "message": "accepted",
        "data": {"task_id": task.id, "catalog_id": catalog.id, "status": "processing"},
    }


@router.get("/admin/course-catalogs/{catalog_id}/resources")
async def admin_list_catalog_resources(
    catalog_id: str,
    type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    await _get_admin_catalog_or_404(db, catalog_id)
    offering_result = await db.execute(
        select(CourseOffering.id).where(
            CourseOffering.catalog_id == catalog_id,
            CourseOffering.is_deleted == False,
        )
    )
    course_ids = list(offering_result.scalars().all())

    query = select(Resource).where(Resource.is_deleted == False)
    if course_ids:
        query = query.where(or_(*(resource_scope_clause(course_id, catalog_id) for course_id in course_ids)))
    else:
        query = query.where(Resource.catalog_id == catalog_id)
    if type:
        query = query.where(Resource.type == type)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
    result = await db.execute(
        query.order_by(Resource.create_time.desc(), Resource.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    resources = result.scalars().all()
    return {
        "code": 200,
        "message": "success",
        "data": {
            "resources": [
                {
                    "id": r.id,
                    "course_id": r.course_id,
                    "title": r.title,
                    "type": r.type,
                    "description": r.description or "",
                    "tags": r.tags or [],
                    "chapter": r.chapter,
                    "knowledge_point": r.knowledge_point,
                    "view_count": r.view_count,
                    "created_at": r.create_time.isoformat() if r.create_time else "",
                }
                for r in resources
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }


@router.delete("/admin/resources/{resource_id}")
async def admin_delete_resource(
    resource_id: str,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Resource).where(Resource.id == resource_id, Resource.is_deleted == False)
    )
    resource = result.scalar_one_or_none()
    if resource is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40412, "message": "资源不存在", "data": None},
        )

    resource.is_deleted = True
    resource.update_by = current_user.id
    await db.commit()
    return {"code": 200, "message": "deleted", "data": {"id": resource.id, "deleted": True}}


@router.post("/admin/course-catalogs/{catalog_id}/resources/generations", status_code=202)
async def admin_generate_catalog_resources(
    catalog_id: str,
    req: CatalogResourceGenerateRequest,
    request: Request,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    catalog = await _get_admin_catalog_or_404(db, catalog_id)
    if catalog.status != "ready":
        raise _course_material_missing()
    if catalog.knowledge_status not in {"ready", "partial"}:
        raise _course_material_missing()
    if (catalog.chunk_count or 0) <= 0:
        raise _knowledge_base_empty()

    if not req.resource_types:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": 42210, "message": "至少选择一种资源类型", "data": None},
        )
    invalid_types = [item for item in req.resource_types if item not in RESOURCE_TYPES]
    if invalid_types:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": 42210, "message": "资源类型不合法", "data": {"invalid_types": invalid_types}},
        )

    offerings_result = await db.execute(
        select(CourseOffering)
        .where(
            CourseOffering.catalog_id == catalog.id,
            CourseOffering.is_deleted == False,
        )
        .order_by(CourseOffering.create_time.asc(), CourseOffering.id.asc())
    )
    offerings = offerings_result.scalars().all()
    fanout_course_ids = [offering.id for offering in offerings]
    if not fanout_course_ids:
        raise _course_offering_missing()

    resource_types = req.resource_types

    if not _is_explicit_resource_target(req):
        kg = await get_active_knowledge_graph(db, catalog.kg_host_course_id or "")
        if kg is None:
            task = AsyncTask(
                task_type="resource_generation",
                status="failed",
                progress=100,
                user_id=current_user.id,
                course_id=None,
                result={
                    "catalog_id": catalog.id,
                    "catalog_title": catalog.title,
                    "fanout_course_ids": fanout_course_ids,
                    "mode": "kg_node_targets",
                    "resource_types": resource_types,
                },
                error_code="kg_not_ready",
                error_message="课程知识图谱未就绪",
                completed_at=_now_utc(),
            )
            db.add(task)
            await db.commit()
            return {
                "code": 202,
                "message": "accepted",
                "data": {"task_id": task.id, "catalog_id": catalog.id, "status": "processing"},
            }

        selection = select_core_resource_targets(
            kg.nodes if isinstance(kg.nodes, list) else [],
            max_targets=KG_RESOURCE_TARGET_LIMIT,
        )
        target_nodes = selection["targets"]
        if not target_nodes:
            task = AsyncTask(
                task_type="resource_generation",
                status="failed",
                progress=100,
                user_id=current_user.id,
                course_id=None,
                result={
                    "catalog_id": catalog.id,
                    "catalog_title": catalog.title,
                    "fanout_course_ids": fanout_course_ids,
                    "mode": "kg_node_targets",
                    "resource_types": resource_types,
                    "target_node_count": 0,
                    "total_child_count": 0,
                    "selection_degraded": selection["selection_degraded"],
                    "selection_degraded_reason": selection["degraded_reason"],
                },
                error_code="kg_target_empty",
                error_message="没有可用于资源挂载的 KG 节点",
                completed_at=_now_utc(),
            )
            db.add(task)
            await db.commit()
            return {
                "code": 202,
                "message": "accepted",
                "data": {"task_id": task.id, "catalog_id": catalog.id, "status": "processing"},
            }

        parent = AsyncTask(
            task_type="resource_generation",
            status="processing",
            progress=10,
            user_id=current_user.id,
            course_id=None,
            result={
                "catalog_id": catalog.id,
                "catalog_title": catalog.title,
                "fanout_course_ids": fanout_course_ids,
                "mode": "kg_node_targets",
                "knowledge_status": catalog.knowledge_status,
                "degraded": catalog.knowledge_status == "partial",
                "chunk_count": catalog.chunk_count or 0,
                "resource_types": resource_types,
                "target_node_count": len(target_nodes),
                "total_child_count": len(target_nodes),
                "target_nodes": target_nodes,
                "selection_degraded": selection["selection_degraded"],
                "selection_degraded_reason": selection["degraded_reason"],
                "completed_child_count": 0,
                "failed_child_count": 0,
                "successful_node_count": 0,
                "failed_node_count": 0,
            },
        )
        db.add(parent)
        await db.flush()
        await db.refresh(parent)

        children: list[AsyncTask] = []
        for target_node in target_nodes:
            child = AsyncTask(
                task_type="resource_generation",
                status="processing",
                progress=10,
                user_id=current_user.id,
                course_id=None,
                result={
                    "catalog_id": catalog.id,
                    "catalog_title": catalog.title,
                    "parent_task_id": parent.id,
                    "fanout_course_ids": fanout_course_ids,
                    "mode": "kg_node_target",
                    "target_node": target_node,
                    "resource_types": resource_types,
                },
            )
            db.add(child)
            children.append(child)
        await db.flush()

        for child in children:
            target_node = child.result["target_node"]
            payload = {
                "task_id": child.id,
                "user_id": current_user.id,
                "course_id": catalog.id,
                "chapter": target_node["chapter"],
                "knowledge_point": target_node["node_name"],
                "resource_types": resource_types,
                "webhook_url": _webhook_url(request),
            }
            try:
                await agent_client.post_json("/agent/v1/resources/generate", payload)
            except AgentServiceError as e:
                child.status = "failed"
                child.error_code = str(e.agent_code or "agent_error")
                child.error_message = e.message
                child.progress = 100
                child.completed_at = _now_utc()

        await db.commit()
        return {
            "code": 202,
            "message": "accepted",
            "data": {"task_id": parent.id, "catalog_id": catalog.id, "status": "processing"},
        }

    task_result = {
        "catalog_id": catalog.id,
        "catalog_title": catalog.title,
        "fanout_course_ids": fanout_course_ids,
        "knowledge_status": catalog.knowledge_status,
        "degraded": catalog.knowledge_status == "partial",
        "chunk_count": catalog.chunk_count or 0,
        "resource_types": resource_types,
    }
    if req.chapter:
        task_result["chapter"] = req.chapter
    if req.knowledge_point:
        task_result["knowledge_point"] = req.knowledge_point

    task = AsyncTask(
        task_type="resource_generation",
        status="processing",
        progress=10,
        user_id=current_user.id,
        course_id=None,
        result=task_result,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)

    payload = {
        "task_id": task.id,
        "user_id": current_user.id,
        "course_id": catalog.id,
        "resource_types": resource_types,
        "webhook_url": _webhook_url(request),
    }
    if req.chapter:
        payload["chapter"] = req.chapter
    if req.knowledge_point:
        payload["knowledge_point"] = req.knowledge_point

    try:
        await agent_client.post_json("/agent/v1/resources/generate", payload)
    except AgentServiceError as e:
        task.status = "failed"
        task.error_code = str(e.agent_code or "agent_error")
        task.error_message = e.message
        task.progress = 100
        task.completed_at = _now_utc()
        await db.commit()
        return {
            "code": 202,
            "message": "accepted",
            "data": {"task_id": task.id, "catalog_id": catalog.id, "status": "processing"},
        }

    await db.commit()
    return {
        "code": 202,
        "message": "accepted",
        "data": {"task_id": task.id, "catalog_id": catalog.id, "status": "processing"},
    }


async def _run_quiz_generation_background(
    parent_id: str,
    child_task_ids: list[str],
    fanout_course_ids: list[str],
) -> None:
    """后台异步：遍历子任务调 Agent 出题落库，完成后汇总父任务。"""
    async with async_session_factory() as db:
        child_futures = []
        for child_id in child_task_ids:
            child_futures.append(_generate_quiz_for_child(db, child_id, fanout_course_ids))

        # 并发执行所有子任务
        results = await asyncio.gather(*child_futures, return_exceptions=True)

        # 汇总父任务
        parent_result = await db.execute(
            select(AsyncTask).where(AsyncTask.id == parent_id, AsyncTask.is_deleted == False)
        )
        parent = parent_result.scalar_one_or_none()
        if parent is None:
            logger.error("Quiz generation parent task missing: %s", parent_id)
            return

        completed = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "completed")
        failed = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "failed")
        total_qs = sum(
            (r.get("question_count") or 0)
            for r in results if isinstance(r, dict) and r.get("status") == "completed"
        )
        parent.status = "completed" if failed == 0 else ("partial" if completed > 0 else "failed")
        parent.progress = 100
        parent.completed_at = _now_utc()
        parent.result = {
            **parent.result,
            "completed_node_count": completed,
            "failed_node_count": failed,
            "total_question_count": total_qs,
        }
        await db.commit()


async def _generate_quiz_for_child(
    db: AsyncSession,
    child_id: str,
    fanout_course_ids: list[str],
) -> dict:
    """处理单个 quiz 子任务：调 Agent 出题落库，更新子 task。"""
    child_result = await db.execute(
        select(AsyncTask).where(AsyncTask.id == child_id, AsyncTask.is_deleted == False)
    )
    child = child_result.scalar_one_or_none()
    if child is None:
        return {"status": "failed", "error": "child task not found"}

    child_data = child.result or {}
    node_name = child_data.get("node_name", "")
    chapter = child_data.get("chapter") or ""
    course_ids = child_data.get("course_ids") or fanout_course_ids

    payload = {
        "task_id": child.id,
        "user_id": child.user_id or "",
        "course_id": child.course_id or "",
        "chapter": chapter,
        "knowledge_point": node_name,
        "question_types": [
            "single_choice", "single_choice", "single_choice",
            "multi_choice", "multi_choice", "multi_choice", "multi_choice",
        ],
        "count": 7,
        "difficulty": "medium",
        "source": "baseline",
    }

    try:
        data = await agent_client.post_json(
            "/agent/v1/assessment/generate-questions",
            payload,
        )
        questions = data.get("questions") if isinstance(data, dict) else []
        new_questions: list[QuizQuestion] = []
        for cid in course_ids:
            for q in (questions if isinstance(questions, list) else []):
                new_questions.append(QuizQuestion(
                    course_id=cid,
                    chapter=chapter,
                    knowledge_point=node_name,
                    type=q.get("type", "single_choice"),
                    source="baseline",
                    personalized=False,
                    difficulty="medium",
                    content=q.get("content", ""),
                    options=q.get("options", []),
                    correct_answer=str(q.get("answer", "")),
                    explanation=q.get("explanation", ""),
                ))
        for q in new_questions:
            db.add(q)

        child.status = "completed"
        child.progress = 100
        child.completed_at = _now_utc()
        child.result = {**child_data, "question_count": len(questions) if isinstance(questions, list) else 0}
        return {"status": "completed", "question_count": len(questions) if isinstance(questions, list) else 0}
    except AgentServiceError as e:
        child.status = "failed"
        child.progress = 100
        child.error_code = str(e.agent_code or "agent_error")
        child.error_message = e.message
        child.completed_at = _now_utc()
        return {"status": "failed", "error": e.message}
    except Exception as e:
        child.status = "failed"
        child.progress = 100
        child.error_code = "unexpected_error"
        child.error_message = str(e)[:500]
        child.completed_at = _now_utc()
        return {"status": "failed", "error": str(e)[:500]}


@router.post("/admin/course-catalogs/{catalog_id}/quiz/generations", status_code=202)
async def admin_generate_catalog_quiz(
    catalog_id: str,
    request: Request,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Admin 批量生成保底题库：遍历 active KG 全部节点，异步调 Agent 出题落库。"""
    catalog = await _get_admin_catalog_or_404(db, catalog_id)
    if catalog.status != "ready":
        raise _course_material_missing()
    if catalog.knowledge_status not in {"ready", "partial"}:
        raise _course_material_missing()
    if (catalog.chunk_count or 0) <= 0:
        raise _knowledge_base_empty()

    offerings_result = await db.execute(
        select(CourseOffering)
        .where(
            CourseOffering.catalog_id == catalog.id,
            CourseOffering.is_deleted == False,
        )
        .order_by(CourseOffering.create_time.asc(), CourseOffering.id.asc())
    )
    offerings = offerings_result.scalars().all()
    if not offerings:
        raise _course_offering_missing()

    fanout_course_ids = [offering.id for offering in offerings]

    kg = await get_active_knowledge_graph(db, catalog.kg_host_course_id or "")
    if kg is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": 40917,
                "message": "课程知识图谱未就绪",
                "data": {"error_code": "kg_not_ready"},
            },
        )

    kg_nodes = kg.nodes if isinstance(kg.nodes, list) else []
    if not kg_nodes:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": 40918,
                "message": "课程知识图谱节点为空",
                "data": {"error_code": "kg_nodes_empty"},
            },
        )

    # 重复生成前软删除旧保底题
    for cid in fanout_course_ids:
        await db.execute(
            update(QuizQuestion)
            .where(
                QuizQuestion.course_id == cid,
                QuizQuestion.source == "baseline",
                QuizQuestion.is_deleted == False,
            )
            .values(is_deleted=True)
        )

    parent = AsyncTask(
        task_type="quiz_generation",
        status="processing",
        progress=10,
        user_id=current_user.id,
        course_id=None,
        result={
            "catalog_id": catalog.id,
            "catalog_title": catalog.title,
            "fanout_course_ids": fanout_course_ids,
            "total_node_count": len(kg_nodes),
            "completed_node_count": 0,
            "failed_node_count": 0,
            "total_question_count": 0,
        },
    )
    db.add(parent)
    await db.flush()
    await db.refresh(parent)

    child_task_ids: list[str] = []
    for kg_node in kg_nodes:
        node_name = kg_node.get("name", "")
        chapter = kg_node.get("chapter", "")
        child = AsyncTask(
            task_type="quiz_generation",
            status="processing",
            progress=10,
            user_id=current_user.id,
            course_id=fanout_course_ids[0],
            result={
                "catalog_id": catalog.id,
                "parent_task_id": parent.id,
                "node_name": node_name,
                "chapter": chapter,
                "course_ids": fanout_course_ids,
            },
        )
        db.add(child)
        await db.flush()
        child_task_ids.append(child.id)

    await db.commit()

    # 后台异步执行 Agent 调用 + 写库
    asyncio.create_task(_run_quiz_generation_background(
        parent_id=parent.id,
        child_task_ids=child_task_ids,
        fanout_course_ids=fanout_course_ids,
    ))

    return {
        "code": 202,
        "message": "accepted",
        "data": {"task_id": parent.id, "catalog_id": catalog.id, "status": "processing"},
    }


@router.get("/course-catalogs")
async def list_ready_course_catalogs(
    status_filter: str | None = Query("ready", alias="status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(CourseCatalog).where(CourseCatalog.is_deleted == False)
    if status_filter:
        query = query.where(CourseCatalog.status == status_filter)
    result = await db.execute(query.order_by(CourseCatalog.title.asc()))
    catalogs = result.scalars().all()
    return {
        "code": 200,
        "message": "success",
        "data": {"catalogs": [_catalog_item(c) for c in catalogs]},
    }
