import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.catalog import CourseCatalog, CourseCatalogMaterial
from app.schemas.catalog import CourseCatalogMaterialCreateRequest

SUPPORTED_MATERIAL_SUFFIXES = {".txt", ".md", ".pdf"}
UPLOAD_CHUNK_SIZE = 1024 * 1024


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

    async def save_uploaded_material(
        self,
        catalog: CourseCatalog,
        file: UploadFile,
    ) -> CourseCatalogMaterial:
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
                    status=next_status,
                    knowledge_status=next_knowledge_status,
                    last_error=None,
                )
            )
            if update_result.rowcount == 0:
                remove_material_dir(target_path)
                await self.db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"code": 40911, "message": "课程资源库正在入库中", "data": None},
                )

            self.db.add(material)
            await self.db.flush()
            await self.db.refresh(material)
            await self.db.commit()
        except HTTPException:
            raise
        except Exception:
            remove_material_dir(target_path)
            await self.db.rollback()
            raise

        return material

    async def get_material_counts(self, catalog_id: str) -> dict[str, int]:
        pending_count = (
            await self.db.execute(
                select(func.count())
                .select_from(CourseCatalogMaterial)
                .where(
                    CourseCatalogMaterial.catalog_id == catalog_id,
                    CourseCatalogMaterial.is_deleted == False,
                    CourseCatalogMaterial.status == "uploaded",
                )
            )
        ).scalar() or 0
        failed_count = (
            await self.db.execute(
                select(func.count())
                .select_from(CourseCatalogMaterial)
                .where(
                    CourseCatalogMaterial.catalog_id == catalog_id,
                    CourseCatalogMaterial.is_deleted == False,
                    CourseCatalogMaterial.status == "failed",
                )
            )
        ).scalar() or 0
        return {
            "pending_material_count": pending_count,
            "failed_material_count": failed_count,
        }

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
        await self.db.commit()
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
