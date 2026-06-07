import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.catalog import CourseCatalog, CourseCatalogMaterial, CourseOffering
from app.schemas.catalog import CourseCatalogCreateRequest, CourseOfferingCreateRequest


def test_catalog_models_and_schemas_importable():
    catalog = CourseCatalog(
        title="数据结构",
        description="共享数据结构课程资源库",
        status="draft",
    )
    material = CourseCatalogMaterial(
        catalog_id="cat001",
        filename="ds.pdf",
        source_type="pdf",
        status="uploaded",
    )
    offering = CourseOffering(
        name="2026 春 数据结构 1 班",
        catalog_id="cat001",
        teacher_id="teacher001",
        class_code="ABC12345",
    )

    req = CourseCatalogCreateRequest(title="数据结构", description="基础课程")
    class_req = CourseOfferingCreateRequest(
        name="2026 春 数据结构 1 班",
        catalog_id="cat001",
        description="教学班",
    )

    assert catalog.title == "数据结构"
    assert material.source_type == "pdf"
    assert offering.catalog_id == "cat001"
    assert req.title == "数据结构"
    assert class_req.catalog_id == "cat001"
