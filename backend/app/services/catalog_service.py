from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.catalog import CourseCatalog
from app.exceptions.catalog_exceptions import CatalogNotFoundError

class CatalogService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_catalog(self, catalog_id: str) -> CourseCatalog:
        result = await self.db.execute(
            select(CourseCatalog).where(
                CourseCatalog.id == catalog_id,
                CourseCatalog.is_deleted == False,
            )
        )
        catalog = result.scalar_one_or_none()
        if not catalog:
            raise CatalogNotFoundError()
        return catalog

    async def list_catalogs(self, status_filter: str | None, page: int, page_size: int) -> tuple[list[CourseCatalog], int]:
        query = select(CourseCatalog).where(CourseCatalog.is_deleted == False)
        if status_filter:
            query = query.where(CourseCatalog.status == status_filter)

        total = (await self.db.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
        result = await self.db.execute(
            query.order_by(CourseCatalog.create_time.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def list_ready_catalogs(self, status_filter: str | None = "ready") -> list[CourseCatalog]:
        query = select(CourseCatalog).where(CourseCatalog.is_deleted == False)
        if status_filter:
            query = query.where(CourseCatalog.status == status_filter)
        result = await self.db.execute(query.order_by(CourseCatalog.title.asc()))
        return list(result.scalars().all())

    async def create_catalog(self, title: str, description: str) -> CourseCatalog:
        catalog = CourseCatalog(
            title=title.strip(),
            description=(description or "").strip(),
            status="draft",
            knowledge_status="draft",
            material_count=0,
        )
        self.db.add(catalog)
        await self.db.flush()
        await self.db.refresh(catalog)
        return catalog
