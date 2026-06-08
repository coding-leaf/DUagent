import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_role
from app.core.config import settings
from app.db.session import async_session_factory
from app.models.catalog import CourseCatalog, CourseCatalogMaterial
from app.models.others import AsyncTask
from app.models.user import User
from app.schemas.catalog import CourseCatalogCreateRequest, CourseCatalogMaterialCreateRequest
from app.services.agent_client import AgentClient, AgentServiceError

router = APIRouter(prefix="/api/v1", tags=["course-catalogs"])
logger = logging.getLogger(__name__)
ingestion_agent_client = AgentClient(timeout=300.0)

SUPPORTED_MATERIAL_SUFFIXES = {".txt", ".md", ".pdf"}
UPLOAD_CHUNK_SIZE = 1024 * 1024


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
            if task is not None:
                task_context = task.result or {}
                catalog_id = task_context.get("catalog_id")
                material_ids = task_context.get("material_ids") or []
                initial = bool(task_context.get("initial"))
                message = str(exc)[:500]

                catalog = None
                if catalog_id:
                    catalog_result = await db.execute(
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
                    material_result = await db.execute(
                        select(CourseCatalogMaterial).where(
                            CourseCatalogMaterial.id.in_(material_ids),
                            CourseCatalogMaterial.is_deleted == False,
                        )
                    )
                    for material in material_result.scalars().all():
                        material.status = "failed"
                        material.last_error = message

                task.status = "failed"
                task.progress = 100
                task.error_code = "unexpected_error"
                task.error_message = message
                task.completed_at = _now_utc()
                task.result = {**task_context, "unexpected_error": message}
                await db.commit()


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


@router.post("/admin/course-catalogs/{catalog_id}/ingestions", status_code=202)
async def admin_start_catalog_ingestion(
    catalog_id: str,
    background_tasks: BackgroundTasks,
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
    update_result = await db.execute(
        update(CourseCatalog)
        .where(
            CourseCatalog.id == catalog.id,
            CourseCatalog.is_deleted == False,
            CourseCatalog.status != "ingesting",
            CourseCatalog.knowledge_status != "ingesting",
        )
        .values(
            status="ingesting" if initial else "ready",
            knowledge_status="ingesting",
            last_error=None,
        )
    )
    if update_result.rowcount == 0:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": 40911, "message": "课程资源库正在入库中", "data": None},
        )

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
