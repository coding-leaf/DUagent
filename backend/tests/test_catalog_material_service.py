from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse
import os
import uuid

import pytest
from fastapi import HTTPException

from app.models.catalog import CourseCatalog, CourseCatalogMaterial
from app.schemas.catalog import CourseCatalogMaterialCreateRequest
from app.services.catalog_material_service import (
    CatalogMaterialService,
    remove_material_dir,
    safe_filename,
    state_after_material_added,
)


def _require_mysql_test_db():
    test_database_url = os.environ.get("TEST_DATABASE_URL", "")
    if not test_database_url.startswith("mysql+"):
        pytest.skip("requires TEST_DATABASE_URL=mysql+...")
    test_database_name = urlparse(test_database_url).path.strip("/")
    if test_database_name == "duagent":
        pytest.skip("refusing to use the real duagent database")
    os.environ["DATABASE_URL"] = test_database_url

    from app.db.session import async_session_factory, engine, init_db

    return async_session_factory, engine, init_db


def test_catalog_material_service_uses_class_style_with_db_dependency():
    marker_db = object()
    service = CatalogMaterialService(marker_db)
    assert service.db is marker_db


@pytest.mark.parametrize("raw", ["", ".", "..", "../evil.pdf", "nested/evil.pdf", "nested\\evil.pdf"])
def test_safe_filename_rejects_unsafe_values(raw):
    with pytest.raises(HTTPException) as exc:
        safe_filename(raw)
    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == 40020


def test_safe_filename_accepts_basename():
    assert safe_filename(" intro.pdf ") == "intro.pdf"


def test_state_after_material_added_marks_ready_catalog_dirty():
    catalog = type("Catalog", (), {"status": "ready"})()
    assert state_after_material_added(catalog) == ("ready", "dirty")


def test_remove_material_dir_mocks_rmtree():
    target = Path("/tmp/catalog/cat1/mat1/file.pdf")
    with patch("app.services.catalog_material_service.shutil.rmtree") as mock_rmtree:
        remove_material_dir(target)
    mock_rmtree.assert_called_once_with(target.parent, ignore_errors=True)


@pytest.mark.asyncio(loop_scope="module")
async def test_list_materials_excludes_deleted_records():
    async_session_factory, engine, init_db = _require_mysql_test_db()
    try:
        await init_db()
        suffix = uuid.uuid4().hex[:8]
        catalog = CourseCatalog(
            id=f"cat-list-{suffix}",
            title=f"Catalog List {suffix}",
            status="ready",
            knowledge_status="ready",
        )
        visible = CourseCatalogMaterial(
            id=f"mat-visible-{suffix}",
            catalog_id=catalog.id,
            filename="visible.pdf",
            source_type="pdf",
            status="uploaded",
        )
        deleted = CourseCatalogMaterial(
            id=f"mat-deleted-{suffix}",
            catalog_id=catalog.id,
            filename="deleted.pdf",
            source_type="pdf",
            status="uploaded",
            is_deleted=True,
        )
        async with async_session_factory() as db:
            db.add_all([catalog, visible, deleted])
            await db.commit()

            materials = await CatalogMaterialService(db).list_materials(catalog.id)

        assert [material.id for material in materials] == [visible.id]
    finally:
        await engine.dispose()


@pytest.mark.asyncio(loop_scope="module")
async def test_delete_material_recomputes_catalog_counts_and_marks_knowledge_dirty():
    async_session_factory, engine, init_db = _require_mysql_test_db()
    try:
        await init_db()
        suffix = uuid.uuid4().hex[:8]
        catalog_id = f"cat-delete-{suffix}"
        target_id = f"mat-delete-{suffix}"
        keep_id = f"mat-keep-{suffix}"
        catalog = CourseCatalog(
            id=catalog_id,
            title=f"Catalog Delete {suffix}",
            status="ready",
            knowledge_status="partial",
            material_count=2,
            chunk_count=8,
            last_error="old error",
        )
        target = CourseCatalogMaterial(
            id=target_id,
            catalog_id=catalog_id,
            filename="target.pdf",
            source_type="pdf",
            status="ingested",
            chunk_count=3,
        )
        keep = CourseCatalogMaterial(
            id=keep_id,
            catalog_id=catalog_id,
            filename="keep.pdf",
            source_type="pdf",
            status="ingested",
            chunk_count=5,
        )
        async with async_session_factory() as db:
            db.add_all([catalog, target, keep])
            await db.commit()

            result = await CatalogMaterialService(db).delete_material(catalog, target_id)
            await db.commit()
            refreshed_catalog = await db.get(CourseCatalog, catalog_id)
            refreshed_target = await db.get(CourseCatalogMaterial, target_id)

        assert result == {
            "id": target_id,
            "catalog_id": catalog_id,
            "deleted": True,
            "knowledge_status": "dirty",
        }
        assert refreshed_target.is_deleted is True
        assert refreshed_catalog.material_count == 1
        assert refreshed_catalog.chunk_count == 5
        assert refreshed_catalog.knowledge_status == "dirty"
        assert refreshed_catalog.last_error is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio(loop_scope="module")
async def test_create_external_material_preserves_ready_catalog_transition():
    async_session_factory, engine, init_db = _require_mysql_test_db()
    try:
        await init_db()
        suffix = uuid.uuid4().hex[:8]
        catalog_id = f"cat-create-{suffix}"
        catalog = CourseCatalog(
            id=catalog_id,
            title=f"Catalog Create {suffix}",
            status="ready",
            knowledge_status="ready",
            material_count=0,
            last_error="old error",
        )
        req = CourseCatalogMaterialCreateRequest(
            filename=" external.pdf ",
            source_type=" pdf ",
            storage_uri="local://external.pdf",
        )
        async with async_session_factory() as db:
            db.add(catalog)
            await db.commit()

            material = await CatalogMaterialService(db).create_external_material(catalog, req)
            await db.commit()
            refreshed_catalog = await db.get(CourseCatalog, catalog_id)

        assert material.catalog_id == catalog_id
        assert material.filename == "external.pdf"
        assert material.source_type == "pdf"
        assert material.status == "uploaded"
        assert refreshed_catalog.status == "ready"
        assert refreshed_catalog.knowledge_status == "dirty"
        assert refreshed_catalog.material_count == 1
        assert refreshed_catalog.last_error is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio(loop_scope="module")
async def test_get_material_counts_returns_uploaded_and_failed_counts():
    async_session_factory, engine, init_db = _require_mysql_test_db()
    try:
        await init_db()
        suffix = uuid.uuid4().hex[:8]
        catalog_id = f"cat-counts-{suffix}"
        catalog = CourseCatalog(
            id=catalog_id,
            title=f"Catalog Counts {suffix}",
            status="ready",
            knowledge_status="ready",
        )
        mat_uploaded = CourseCatalogMaterial(
            id=f"mat-up-{suffix}",
            catalog_id=catalog_id,
            filename="up.pdf",
            source_type="pdf",
            status="uploaded",
        )
        mat_failed = CourseCatalogMaterial(
            id=f"mat-fail-{suffix}",
            catalog_id=catalog_id,
            filename="fail.pdf",
            source_type="pdf",
            status="failed",
        )
        mat_ingested = CourseCatalogMaterial(
            id=f"mat-ing-{suffix}",
            catalog_id=catalog_id,
            filename="ing.pdf",
            source_type="pdf",
            status="ingested",
        )
        async with async_session_factory() as db:
            db.add_all([catalog, mat_uploaded, mat_failed, mat_ingested])
            await db.commit()

            counts = await CatalogMaterialService(db).get_material_counts(catalog_id)

        assert counts == {
            "pending_material_count": 1,
            "failed_material_count": 1,
        }
    finally:
        await engine.dispose()


@pytest.mark.asyncio(loop_scope="module")
async def test_save_uploaded_material_saves_file_and_updates_db():
    from fastapi import UploadFile
    from unittest.mock import MagicMock, AsyncMock
    import shutil

    async_session_factory, engine, init_db = _require_mysql_test_db()
    try:
        await init_db()
        suffix = uuid.uuid4().hex[:8]
        catalog_id = f"cat-upload-{suffix}"
        catalog = CourseCatalog(
            id=catalog_id,
            title=f"Catalog Upload {suffix}",
            status="draft",
            knowledge_status="draft",
            material_count=0,
        )
        async with async_session_factory() as db:
            db.add(catalog)
            await db.commit()

        # Mock UploadFile
        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "test_upload.pdf"
        mock_file.read = AsyncMock(side_effect=[b"hello pdf file", b""])

        async with async_session_factory() as db:
            db_catalog = await db.get(CourseCatalog, catalog_id)
            service = CatalogMaterialService(db)
            material = await service.save_uploaded_material(db_catalog, mock_file)
            await db.commit()
            
            refreshed_catalog = await db.get(CourseCatalog, catalog_id)

        assert material.filename == "test_upload.pdf"
        assert material.file_size == len("hello pdf file")
        assert material.status == "uploaded"
        assert refreshed_catalog.material_count == 1
        
        # Clean up files created in COURSE_CATALOG_STORAGE_ROOT
        from app.core.config import settings
        target_dir = Path(settings.COURSE_CATALOG_STORAGE_ROOT) / catalog_id / material.id
        if target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=True)
    finally:
        await engine.dispose()
