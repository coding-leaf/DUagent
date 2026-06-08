from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import CourseCatalog, CourseOffering


class GenerationCatalogContext(BaseModel):
    class_course_id: str
    catalog_id: str
    catalog_title: str
    knowledge_status: str
    degraded: bool
    chunk_count: int


def _course_catalog_missing() -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "code": "course_catalog_missing",
            "message": "课程未绑定可用资源库",
            "data": None,
        },
    )


def _course_material_missing() -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={
            "code": "course_material_missing",
            "message": "课程资料尚未完成入库",
            "data": None,
        },
    )


def _knowledge_base_empty() -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={
            "code": "knowledge_base_empty",
            "message": "课程知识库为空",
            "data": None,
        },
    )


async def resolve_generation_catalog(db: AsyncSession, course_id: str) -> GenerationCatalogContext:
    offering_result = await db.execute(
        select(CourseOffering).where(
            CourseOffering.id == course_id,
            CourseOffering.is_deleted == False,
        )
    )
    offering = offering_result.scalar_one_or_none()
    if not offering:
        raise _course_catalog_missing()

    catalog_result = await db.execute(
        select(CourseCatalog).where(
            CourseCatalog.id == offering.catalog_id,
            CourseCatalog.is_deleted == False,
        )
    )
    catalog = catalog_result.scalar_one_or_none()
    if not catalog:
        raise _course_catalog_missing()

    if catalog.status != "ready":
        raise _course_material_missing()

    if catalog.knowledge_status not in {"ready", "partial"}:
        raise _course_material_missing()

    if catalog.chunk_count <= 0:
        raise _knowledge_base_empty()

    return GenerationCatalogContext(
        class_course_id=course_id,
        catalog_id=catalog.id,
        catalog_title=catalog.title,
        knowledge_status=catalog.knowledge_status,
        degraded=catalog.knowledge_status == "partial",
        chunk_count=catalog.chunk_count,
    )
