import asyncio
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Body, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_role
from app.core.config import settings
from app.models.catalog import CourseCatalog, CourseCatalogMaterial
from app.models.others import AsyncTask
from app.models.user import User
from app.schemas.catalog import (
    CatalogKnowledgeGraphGenerationRequest,
    CourseCatalogCreateRequest,
    CourseCatalogMaterialCreateRequest,
)
from app.schemas.operations import CatalogResourceGenerateRequest
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
from app.services.catalog_kg_service import (
    CatalogKGService,
    run_catalog_kg_generation_background,
)
from app.services.catalog_resource_generation_service import CatalogResourceGenerationService
from app.services.catalog_quiz_generation_service import (
    CatalogQuizGenerationService,
    run_quiz_generation_background,
)
from app.services.catalog_service import CatalogService

router = APIRouter(prefix="/api/v1", tags=["course-catalogs"])

SUPPORTED_MATERIAL_SUFFIXES = {".txt", ".md", ".pdf"}
UPLOAD_CHUNK_SIZE = 1024 * 1024


def _webhook_url(request: Request) -> str:
    base = str(request.base_url).rstrip("/")
    return f"{base}/api/v1/webhooks/agent"


def _async_task_catalog_id_expr():
    return func.json_unquote(func.json_extract(AsyncTask.result, "$.catalog_id"))


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
    status_data = await CatalogKGService(db).get_knowledge_graph_status(
        catalog,
        actor_user_id=current_user.id,
    )
    host_course = status_data["host_course"]
    graph = status_data["graph"]
    last_generation_task = status_data["last_generation_task"]

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
    task = await CatalogKGService(db).start_kg_generation(
        catalog,
        req,
        actor_user_id=current_user.id,
    )
    asyncio.create_task(run_catalog_kg_generation_background(task.id))

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
    data = await CatalogResourceGenerationService(db).list_catalog_resources(
        catalog_id,
        resource_type=type,
        page=page,
        page_size=page_size,
    )
    return {
        "code": 200,
        "message": "success",
        "data": data,
    }


@router.delete("/admin/resources/{resource_id}")
async def admin_delete_resource(
    resource_id: str,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    resource = await CatalogResourceGenerationService(db).delete_resource(
        resource_id,
        actor_user_id=current_user.id,
    )
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
    task = await CatalogResourceGenerationService(db).start_resource_generation(
        catalog,
        req,
        actor_user_id=current_user.id,
        webhook_url=_webhook_url(request),
    )
    return {
        "code": 202,
        "message": "accepted",
        "data": {"task_id": task.id, "catalog_id": catalog.id, "status": "processing"},
    }


@router.post("/admin/course-catalogs/{catalog_id}/quiz/generations", status_code=202)
async def admin_generate_catalog_quiz(
    catalog_id: str,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Admin 批量生成保底题库：遍历 active KG 全部节点，异步调 Agent 出题落库。"""
    catalog = await CatalogService(db).get_catalog(catalog_id)
    parent, child_task_ids, fanout_course_ids = await CatalogQuizGenerationService(
        db
    ).start_quiz_generation(catalog, actor_user_id=current_user.id)

    # 后台异步执行 Agent 调用 + 写库
    asyncio.create_task(
        run_quiz_generation_background(
            parent_id=parent.id,
            child_task_ids=child_task_ids,
            fanout_course_ids=fanout_course_ids,
        )
    )

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
