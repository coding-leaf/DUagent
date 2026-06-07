from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_role
from app.models.catalog import CourseCatalog, CourseCatalogMaterial
from app.models.user import User
from app.schemas.catalog import CourseCatalogCreateRequest, CourseCatalogMaterialCreateRequest

router = APIRouter(prefix="/api/v1", tags=["course-catalogs"])


def _catalog_item(catalog: CourseCatalog) -> dict:
    return {
        "id": catalog.id,
        "title": catalog.title,
        "description": catalog.description or "",
        "status": catalog.status,
        "knowledge_status": catalog.knowledge_status,
        "material_count": catalog.material_count,
        "created_at": catalog.create_time.isoformat() if catalog.create_time else "",
    }


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
            CourseCatalog.status != "ingesting",
        )
        .values(
            material_count=CourseCatalog.material_count + 1,
            status="draft",
            knowledge_status="draft",
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
        status="uploaded",
    )
    db.add(material)
    await db.flush()
    await db.refresh(material)
    return {
        "code": 201,
        "message": "created",
        "data": {
            "id": material.id,
            "catalog_id": material.catalog_id,
            "filename": material.filename,
            "source_type": material.source_type,
            "status": material.status,
            "created_at": material.create_time.isoformat() if material.create_time else "",
        },
    }


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
            "materials": [
                {
                    "id": m.id,
                    "catalog_id": m.catalog_id,
                    "filename": m.filename,
                    "source_type": m.source_type,
                    "status": m.status,
                    "created_at": m.create_time.isoformat() if m.create_time else "",
                }
                for m in materials
            ]
        },
    }


@router.get("/admin/course-catalogs/{catalog_id}/knowledge-status")
async def admin_get_catalog_knowledge_status(
    catalog_id: str,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    catalog = await _get_admin_catalog_or_404(db, catalog_id)
    return {
        "code": 200,
        "message": "success",
        "data": {
            "catalog_id": catalog.id,
            "status": catalog.status,
            "knowledge_status": catalog.knowledge_status,
            "material_count": catalog.material_count or 0,
        },
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
