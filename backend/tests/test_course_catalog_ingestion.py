import os
import sys

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "mysql+aiomysql://root:123456@127.0.0.1:3306/duagent_test?charset=utf8mb4",
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.models.catalog import CourseCatalog, CourseCatalogMaterial
from app.schemas.catalog import CourseCatalogMaterialItem


def test_course_catalog_model_has_ingestion_fields():
    columns = CourseCatalog.__table__.columns

    assert "last_ingestion_task_id" in columns
    assert "last_ingestion_status" in columns
    assert "chunk_count" in columns
    assert "last_error" in columns


def test_course_catalog_material_model_has_ingestion_fields():
    columns = CourseCatalogMaterial.__table__.columns

    assert "file_size" in columns
    assert "last_error" in columns
    assert "ingested_at" in columns
    assert "chunk_count" in columns


def test_course_catalog_storage_settings_exist():
    assert hasattr(settings, "COURSE_CATALOG_STORAGE_ROOT")
    assert hasattr(settings, "COURSE_CATALOG_MAX_UPLOAD_BYTES")
    assert settings.COURSE_CATALOG_STORAGE_ROOT
    assert settings.COURSE_CATALOG_MAX_UPLOAD_BYTES > 0


def test_course_catalog_material_schema_has_ingestion_fields():
    material = CourseCatalogMaterialItem(
        id="mat1",
        catalog_id="cat1",
        filename="intro.md",
        source_type="file",
        file_size=12,
        status="uploaded",
        chunk_count=0,
        last_error=None,
        ingested_at=None,
        created_at="2026-06-08T00:00:00",
    )

    assert material.file_size == 12
    assert material.chunk_count == 0
    assert material.last_error is None


def test_course_catalog_ingestion_upgrade_migration_is_idempotent():
    migration_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "migrations",
        "2026-06-08-extend-course-catalog-ingestion.sql",
    )
    with open(migration_path, encoding="utf-8") as f:
        migration_sql = f.read()

    assert "information_schema.columns" in migration_sql
    for column_name in (
        "last_ingestion_task_id",
        "last_ingestion_status",
        "chunk_count",
        "last_error",
        "file_size",
        "ingested_at",
    ):
        assert f"column_name = '{column_name}'" in migration_sql
