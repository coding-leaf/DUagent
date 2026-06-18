import shutil
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import CourseCatalog


class CatalogMaterialService:
    def __init__(self, db: AsyncSession):
        self.db = db


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
