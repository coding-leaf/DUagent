import shutil
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import CourseCatalog, CourseCatalogMaterial
from app.schemas.catalog import CourseCatalogMaterialCreateRequest


class CatalogMaterialService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_materials(self, catalog_id: str) -> list[CourseCatalogMaterial]:
        result = await self.db.execute(
            select(CourseCatalogMaterial)
            .where(
                CourseCatalogMaterial.catalog_id == catalog_id,
                CourseCatalogMaterial.is_deleted == False,
            )
            .order_by(CourseCatalogMaterial.create_time.desc())
        )
        return list(result.scalars().all())

    async def create_external_material(
        self,
        catalog: CourseCatalog,
        req: CourseCatalogMaterialCreateRequest,
    ) -> CourseCatalogMaterial:
        update_result = await self.db.execute(
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
        self.db.add(material)
        await self.db.flush()
        await self.db.refresh(material)
        return material

    async def delete_material(self, catalog: CourseCatalog, material_id: str) -> dict:
        if catalog.status == "ingesting" or catalog.knowledge_status == "ingesting":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": 40911, "message": "课程资源库正在入库中", "data": None},
            )

        result = await self.db.execute(
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
        remaining_result = await self.db.execute(
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
        return {
            "id": material.id,
            "catalog_id": catalog.id,
            "deleted": True,
            "knowledge_status": catalog.knowledge_status,
        }


def safe_filename(filename: str) -> str:
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


def state_after_material_added(catalog: CourseCatalog) -> tuple[str, str]:
    if catalog.status == "ready":
        return "ready", "dirty"
    return "draft", "draft"


def remove_material_dir(target_path: Path) -> None:
    shutil.rmtree(target_path.parent, ignore_errors=True)
