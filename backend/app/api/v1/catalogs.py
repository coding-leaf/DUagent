import asyncio
import logging
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
from app.services.catalog_presenters import (
    catalog_item,
    knowledge_graph_summary,
    knowledge_graph_task_summary,
    material_item,
)
from app.services.catalog_material_service import (
    CatalogMaterialService,
    remove_material_dir,
    safe_filename,
    state_after_material_added,
)
from app.services.catalog_ingestion_service import (
    CatalogIngestionService,
    run_catalog_ingestion_background,
)
from app.services.catalog_service import CatalogService
from app.services.course_knowledge_graphs import get_active_knowledge_graph
from app.services.kg_generation import KGGenerationInputError, generate_knowledge_graph_version
from app.services.kg_resource_targets import select_core_resource_targets
from app.services.resource_scope import resource_scope_clause

router = APIRouter(prefix="/api/v1", tags=["course-catalogs"])
logger = logging.getLogger(__name__)
quiz_agent_client = AgentClient(timeout=300.0)

SUPPORTED_MATERIAL_SUFFIXES = {".txt", ".md", ".pdf"}
UPLOAD_CHUNK_SIZE = 1024 * 1024
RESOURCE_TYPES = {"document", "mindmap", "reading", "code"}
KG_RESOURCE_TARGET_LIMIT = 10
QUIZ_GENERATION_CONCURRENCY = 2
QUIZ_BASELINE_SINGLE_COUNT = 3
QUIZ_BASELINE_MULTI_COUNT = 4
HOST_COURSE_NAME_PREFIX = "[KG HOST] "
COURSE_NAME_MAX_LENGTH = 100


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


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


@router.get("/admin/course-catalogs")
async def admin_list_course_catalogs(
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    service = CatalogService(db)
    catalogs, total = await service.list_catalogs(status_filter, page, page_size)
    return {
        "code": 200,
        "message": "success",
        "data": {
            "catalogs": [catalog_item(c) for c in catalogs],
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
    service = CatalogService(db)
    catalog = await service.create_catalog(req.title, req.description)
    return {"code": 201, "message": "created", "data": catalog_item(catalog)}


@router.get("/admin/course-catalogs/{catalog_id}")
async def admin_get_course_catalog(
    catalog_id: str,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    service = CatalogService(db)
    catalog = await service.get_catalog(catalog_id)
    return {"code": 200, "message": "success", "data": catalog_item(catalog)}


@router.post("/admin/course-catalogs/{catalog_id}/materials/upload", status_code=201)
async def admin_upload_catalog_material(
    catalog_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    catalog = await CatalogService(db).get_catalog(catalog_id)
    if catalog.status == "ingesting" or catalog.knowledge_status == "ingesting":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": 40911, "message": "课程资源库正在入库中", "data": None},
        )

    filename = safe_filename(file.filename or "")
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
                    remove_material_dir(target_path)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail={"code": 41320, "message": "资料文件过大", "data": None},
                    )
                f.write(chunk)
    except HTTPException:
        raise
    except Exception:
        remove_material_dir(target_path)
        raise

    if file_size == 0:
        remove_material_dir(target_path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 40022, "message": "资料文件不能为空", "data": None},
        )

    next_status, next_knowledge_status = state_after_material_added(catalog)
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
            remove_material_dir(target_path)
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
        remove_material_dir(target_path)
        await db.rollback()
        raise

    return {"code": 201, "message": "created", "data": material_item(material)}


@router.post("/admin/course-catalogs/{catalog_id}/materials", status_code=201)
async def admin_create_catalog_material(
    catalog_id: str,
    req: CourseCatalogMaterialCreateRequest,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    catalog = await CatalogService(db).get_catalog(catalog_id)
    material = await CatalogMaterialService(db).create_external_material(catalog, req)
    return {"code": 201, "message": "created", "data": material_item(material)}


@router.get("/admin/course-catalogs/{catalog_id}/materials")
async def admin_list_catalog_materials(
    catalog_id: str,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    await CatalogService(db).get_catalog(catalog_id)
    materials = await CatalogMaterialService(db).list_materials(catalog_id)
    return {
        "code": 200,
        "message": "success",
        "data": {
            "materials": [material_item(m) for m in materials]
        },
    }


@router.delete("/admin/course-catalogs/{catalog_id}/materials/{material_id}")
async def admin_delete_catalog_material(
    catalog_id: str,
    material_id: str,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    catalog = await CatalogService(db).get_catalog(catalog_id)
    delete_result = await CatalogMaterialService(db).delete_material(catalog, material_id)
    await db.commit()

    return {
        "code": 200,
        "message": "deleted",
        "data": delete_result,
    }


@router.get("/admin/course-catalogs/{catalog_id}/knowledge-status")
async def admin_get_catalog_knowledge_status(
    catalog_id: str,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    catalog = await CatalogService(db).get_catalog(catalog_id)
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
    catalog = await CatalogService(db).get_catalog(catalog_id)
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
            "active_graph": knowledge_graph_summary(graph) if graph else None,
            "last_generation_task": (
                knowledge_graph_task_summary(last_generation_task)
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
    task = await CatalogIngestionService(db).start_catalog_ingestion(
        catalog_id,
        current_user.id,
    )
    background_tasks.add_task(run_catalog_ingestion_background, task.id)

    return {
        "code": 202,
        "message": "accepted",
        "data": {"task_id": task.id, "catalog_id": catalog_id, "status": "processing"},
    }


@router.post("/admin/course-catalogs/{catalog_id}/knowledge-graphs/generations", status_code=202)
async def admin_generate_catalog_knowledge_graph(
    catalog_id: str,
    req: CatalogKnowledgeGraphGenerationRequest | None = Body(default=None),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    req = req or CatalogKnowledgeGraphGenerationRequest()
    catalog = await CatalogService(db).get_catalog(catalog_id)

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
    await CatalogService(db).get_catalog(catalog_id)
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
    catalog = await CatalogService(db).get_catalog(catalog_id)
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
    if not fanout_course_ids and catalog.kg_host_course_id:
        fanout_course_ids = [catalog.kg_host_course_id]
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
    semaphore = asyncio.Semaphore(QUIZ_GENERATION_CONCURRENCY)

    async def _run_child(child_id: str) -> dict:
        async with semaphore:
            async with async_session_factory() as child_db:
                result = await _generate_quiz_for_child(child_db, child_id, fanout_course_ids)
                await child_db.commit()
                return result

    results = await asyncio.gather(
        *[_run_child(child_id) for child_id in child_task_ids],
        return_exceptions=True,
    )

    async with async_session_factory() as db:
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
        inserted_question_ids = [
            question_id
            for r in results if isinstance(r, dict)
            for question_id in (r.get("inserted_question_ids") or [])
        ]
        if inserted_question_ids:
            fanout_catalog_id = None
            for r in results:
                if isinstance(r, dict) and r.get("fanout_catalog_id"):
                    fanout_catalog_id = r["fanout_catalog_id"]
                    break
            if fanout_catalog_id:
                await db.execute(
                    update(QuizQuestion)
                    .where(
                        QuizQuestion.catalog_id == fanout_catalog_id,
                        QuizQuestion.source == "baseline",
                        QuizQuestion.is_deleted == False,
                        ~QuizQuestion.id.in_(inserted_question_ids),
                    )
                    .values(is_deleted=True)
                )
            else:
                for cid in fanout_course_ids:
                    await db.execute(
                        update(QuizQuestion)
                        .where(
                            QuizQuestion.course_id == cid,
                            QuizQuestion.source == "baseline",
                            QuizQuestion.is_deleted == False,
                            ~QuizQuestion.id.in_(inserted_question_ids),
                        )
                        .values(is_deleted=True)
                    )
        parent.status = "completed" if failed == 0 else ("partial" if completed > 0 else "failed")
        parent.progress = 100
        parent.completed_at = _now_utc()
        parent.result = {
            **parent.result,
            "completed_node_count": completed,
            "failed_node_count": failed,
            "total_question_count": total_qs,
            "inserted_question_count": len(inserted_question_ids),
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
    fanout_catalog_id = child_data.get("fanout_catalog_id")
    agent_course_id = child_data.get("agent_course_id") or child_data.get("catalog_id") or child.course_id or ""

    try:
        questions = await _generate_baseline_quiz_questions(
            child=child,
            agent_course_id=agent_course_id,
            course_ids=course_ids,
            chapter=chapter,
            node_name=node_name,
        )
        new_questions: list[QuizQuestion] = []
        inserted_question_ids: list[str] = []
        for cid in course_ids:
            for q in (questions if isinstance(questions, list) else []):
                if _is_skeleton_quiz_question(q):
                    continue
                question_id = uuid4().hex[:16]
                inserted_question_ids.append(question_id)
                new_questions.append(QuizQuestion(
                    id=question_id,
                    course_id=cid,
                    catalog_id=fanout_catalog_id,
                    chapter=chapter,
                    knowledge_point=node_name,
                    type=q.get("type", "single_choice"),
                    source="baseline",
                    personalized=False,
                    difficulty="medium",
                    content=q.get("content", ""),
                    options=q.get("options", []),
                    correct_answer=_format_quiz_answer(q.get("answer", "")),
                    explanation=q.get("explanation", ""),
                ))
        if not new_questions:
            child.status = "failed"
            child.progress = 100
            child.error_code = "skeleton_rejected"
            child.error_message = "Agent returned only skeleton fallback questions"
            child.completed_at = _now_utc()
            child.result = {**child_data, "question_count": 0, "rejected_reason": "skeleton"}
            return {"status": "failed", "error": "skeleton_rejected"}
        for q in new_questions:
            db.add(q)

        child.status = "completed"
        child.progress = 100
        child.completed_at = _now_utc()
        child.result = {
            **child_data,
            "agent_course_id": agent_course_id,
            "question_count": len(new_questions),
            "inserted_question_ids": inserted_question_ids,
        }
        return {
            "status": "completed",
            "question_count": len(new_questions),
            "inserted_question_ids": inserted_question_ids,
            "fanout_catalog_id": fanout_catalog_id,
        }
    except AgentServiceError as e:
        child.status = "failed"
        child.progress = 100
        child.error_code = str(e.agent_code or "agent_error")
        child.error_message = e.message
        child.completed_at = _now_utc()
        return {"status": "failed", "error": e.message, "fanout_catalog_id": fanout_catalog_id}
    except Exception as e:
        child.status = "failed"
        child.progress = 100
        child.error_code = "unexpected_error"
        child.error_message = str(e)[:500]
        child.completed_at = _now_utc()
        return {"status": "failed", "error": str(e)[:500], "fanout_catalog_id": fanout_catalog_id}


def _build_baseline_quiz_payload(
    *,
    child: AsyncTask,
    agent_course_id: str,
    course_ids: list[str],
    chapter: str,
    node_name: str,
    question_types: list[str],
    count: int,
) -> dict:
    return {
        "task_id": child.id,
        "user_id": child.user_id or "",
        "course_id": agent_course_id,
        "class_course_ids": course_ids,
        "chapter": chapter,
        "knowledge_point": node_name,
        "question_types": question_types,
        "count": count,
        "difficulty": "medium",
        "source": "baseline",
    }


async def _request_baseline_quiz_questions(payload: dict) -> list[dict]:
    data = await quiz_agent_client.post_json(
        "/agent/v1/assessment/generate-questions",
        payload,
    )
    questions = data.get("questions") if isinstance(data, dict) else []
    if not isinstance(questions, list):
        return []
    return [question for question in questions if isinstance(question, dict)]


async def _generate_baseline_quiz_questions(
    *,
    child: AsyncTask,
    agent_course_id: str,
    course_ids: list[str],
    chapter: str,
    node_name: str,
) -> list[dict]:
    bulk_payload = _build_baseline_quiz_payload(
        child=child,
        agent_course_id=agent_course_id,
        course_ids=course_ids,
        chapter=chapter,
        node_name=node_name,
        question_types=(["single_choice"] * QUIZ_BASELINE_SINGLE_COUNT)
        + (["multi_choice"] * QUIZ_BASELINE_MULTI_COUNT),
        count=QUIZ_BASELINE_SINGLE_COUNT + QUIZ_BASELINE_MULTI_COUNT,
    )
    questions = await _request_baseline_quiz_questions(bulk_payload)
    if _non_skeleton_quiz_questions(questions):
        return questions

    split_questions: list[dict] = []
    for question_type, count in (
        ("single_choice", QUIZ_BASELINE_SINGLE_COUNT),
        ("multi_choice", QUIZ_BASELINE_MULTI_COUNT),
    ):
        payload = _build_baseline_quiz_payload(
            child=child,
            agent_course_id=agent_course_id,
            course_ids=course_ids,
            chapter=chapter,
            node_name=node_name,
            question_types=[question_type],
            count=count,
        )
        batch_questions = await _request_baseline_quiz_questions(payload)
        split_questions.extend(_non_skeleton_quiz_questions(batch_questions))
    return split_questions


def _non_skeleton_quiz_questions(questions: list[dict]) -> list[dict]:
    return [
        question
        for question in questions
        if isinstance(question, dict) and not _is_skeleton_quiz_question(question)
    ]


def _format_quiz_answer(answer) -> str:
    if isinstance(answer, list):
        return ",".join(str(item).strip() for item in answer if str(item).strip())
    return str(answer or "").strip()


def _quiz_option_text(option) -> str:
    if isinstance(option, dict):
        return str(option.get("text") or option.get("label") or option.get("content") or "").strip()
    return str(option or "").strip()


def _is_skeleton_quiz_question(question: dict) -> bool:
    if not isinstance(question, dict):
        return False
    content = str(question.get("content") or "")
    if "请围绕" not in content or "完成一道" not in content:
        return False
    options = question.get("options")
    if not isinstance(options, list):
        return False
    option_texts = [_quiz_option_text(option) for option in options]
    option_texts = [text for text in option_texts if text]
    return option_texts == ["正确表述", "易混淆表述", "相关补充表述", "无关表述"]


@router.post("/admin/course-catalogs/{catalog_id}/quiz/generations", status_code=202)
async def admin_generate_catalog_quiz(
    catalog_id: str,
    request: Request,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Admin 批量生成保底题库：遍历 active KG 全部节点，异步调 Agent 出题落库。"""
    catalog = await CatalogService(db).get_catalog(catalog_id)
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
    fanout_course_ids = [offering.id for offering in offerings]
    if not fanout_course_ids and catalog.kg_host_course_id:
        fanout_course_ids = [catalog.kg_host_course_id]
    if not fanout_course_ids:
        raise _course_offering_missing()

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

    parent = AsyncTask(
        task_type="quiz_generation",
        status="processing",
        progress=10,
        user_id=current_user.id,
        course_id=None,
        result={
            "catalog_id": catalog.id,
            "catalog_title": catalog.title,
            "agent_course_id": catalog.id,
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
                "agent_course_id": catalog.id,
                "node_name": node_name,
                "chapter": chapter,
                "course_ids": fanout_course_ids,
                "fanout_catalog_id": catalog.id,
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
    catalogs = await CatalogService(db).list_ready_catalogs(status_filter)
    return {
        "code": 200,
        "message": "success",
        "data": {"catalogs": [catalog_item(c) for c in catalogs]},
    }
