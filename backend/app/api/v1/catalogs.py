from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_role
from app.models.catalog import CourseCatalog
from app.models.user import User
from app.schemas.catalog import CourseCatalogCreateRequest

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
    return {"code": 200, "message": "success", "data": _catalog_item(catalog)}


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
