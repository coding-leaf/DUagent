from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.services.catalog_material_service import (
    CatalogMaterialService,
    remove_material_dir,
    safe_filename,
    state_after_material_added,
)


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
