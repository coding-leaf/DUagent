# Backend Catalogs Route Refactor Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract low-risk presenter and catalog/material service logic from `backend/app/api/v1/catalogs.py` without changing API behavior.

**Architecture:** Keep `catalogs.py` as the route entrypoint for now. Request-lifecycle services use the existing class style (`CatalogService(db)`, `CatalogMaterialService(db)`) so they match current `CatalogService`; pure formatting helpers live in `catalog_presenters.py`. Background task functions are not part of Phase 1; when later migrated they must remain module-level functions in their service file, because they create their own session outside the request lifecycle.

**Tech Stack:** FastAPI, SQLAlchemy AsyncSession, pytest/pytest-asyncio, unittest.mock/pytest monkeypatch, existing `{code, message, data}` response envelope.

---

## Scope Decisions

- New request-scoped service files use class style:
  - `CatalogService(db)`
  - `CatalogMaterialService(db)`
- Pure DTO helpers use module-level functions in `backend/app/services/catalog_presenters.py`.
- No new Repository layer in Phase 1.
- No route split in Phase 1; `backend/app/api/v1/catalogs.py` remains the only router file.
- File-system cleanup tests patch `app.services.catalog_material_service.shutil.rmtree`; tests must not delete real catalog storage directories.
- Phase 1 success gate:
  - `catalogs.py` drops below 1600 lines.
  - `test_catalog_service.py`, new presenter/material service tests, `test_course_catalogs.py`, and `test_course_catalog_ingestion.py` pass in the configured test DB.
  - Client API and Agent API contract drift: no.

## File Structure

- Create `backend/app/services/catalog_presenters.py`
  - Responsibility: convert ORM/task/graph objects into existing response dictionaries.
- Modify `backend/app/services/catalog_service.py`
  - Responsibility: catalog lookup/list/create and ready public list.
- Create `backend/app/services/catalog_material_service.py`
  - Responsibility: material filename validation, material create/list/delete, upload persistence helper, file cleanup wrapper.
- Create `backend/tests/test_catalog_presenters.py`
  - Responsibility: pure presenter tests without DB.
- Create `backend/tests/test_catalog_material_service.py`
  - Responsibility: service/helper tests including file cleanup mock.
- Modify `backend/tests/test_catalog_service.py`
  - Responsibility: extend service tests for ready catalog listing.
- Modify `backend/app/api/v1/catalogs.py`
  - Responsibility: route delegates to services/presenters while preserving response shape.
- Modify `WORKFLOW.md`
  - Responsibility: record Phase 1 completion and test results after implementation.

---

### Task 1: Extract Catalog Presenters

**Files:**
- Create: `backend/app/services/catalog_presenters.py`
- Create: `backend/tests/test_catalog_presenters.py`
- Modify: `backend/app/api/v1/catalogs.py`

- [ ] **Step 1: Write failing presenter tests**

Create `backend/tests/test_catalog_presenters.py`:

```python
from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.catalog_presenters import (
    catalog_item,
    knowledge_graph_summary,
    knowledge_graph_task_summary,
    material_item,
)


def test_catalog_item_preserves_existing_response_shape():
    created_at = datetime(2026, 6, 18, 8, 0, tzinfo=timezone.utc)
    catalog = SimpleNamespace(
        id="cat1",
        title="数据结构",
        description=None,
        status="ready",
        knowledge_status="partial",
        material_count=2,
        last_ingestion_task_id="task1",
        last_ingestion_status="completed",
        chunk_count=None,
        last_error=None,
        create_time=created_at,
    )

    assert catalog_item(catalog) == {
        "id": "cat1",
        "title": "数据结构",
        "description": "",
        "status": "ready",
        "knowledge_status": "partial",
        "material_count": 2,
        "last_ingestion_task_id": "task1",
        "last_ingestion_status": "completed",
        "chunk_count": 0,
        "last_error": None,
        "created_at": created_at.isoformat(),
    }


def test_material_item_optionally_includes_storage_uri():
    created_at = datetime(2026, 6, 18, 8, 1, tzinfo=timezone.utc)
    ingested_at = datetime(2026, 6, 18, 8, 2, tzinfo=timezone.utc)
    material = SimpleNamespace(
        id="mat1",
        catalog_id="cat1",
        filename="intro.pdf",
        source_type="file",
        file_size=None,
        status="ingested",
        chunk_count=None,
        last_error=None,
        ingested_at=ingested_at,
        create_time=created_at,
        storage_uri="course_catalogs/cat1/mat1/intro.pdf",
    )

    assert material_item(material) == {
        "id": "mat1",
        "catalog_id": "cat1",
        "filename": "intro.pdf",
        "source_type": "file",
        "file_size": 0,
        "status": "ingested",
        "chunk_count": 0,
        "last_error": None,
        "ingested_at": ingested_at.isoformat(),
        "created_at": created_at.isoformat(),
    }
    assert material_item(material, include_storage_uri=True)["storage_uri"] == "course_catalogs/cat1/mat1/intro.pdf"


def test_knowledge_graph_presenters_preserve_existing_keys():
    created_at = datetime(2026, 6, 18, 8, 3, tzinfo=timezone.utc)
    completed_at = datetime(2026, 6, 18, 8, 4, tzinfo=timezone.utc)
    graph = SimpleNamespace(
        id="graph1",
        course_id="course1",
        version=3,
        source_type="route_a",
        generation_strategy="route_a_prune",
        nodes=[{"id": "n1"}],
        edges=[{"source": "n1", "target": "n2"}],
        is_active=True,
        create_time=created_at,
    )
    task = SimpleNamespace(
        id="task1",
        status="completed",
        progress=100,
        error_code=None,
        error_message="",
        create_time=created_at,
        completed_at=completed_at,
    )

    assert knowledge_graph_summary(graph)["node_count"] == 1
    assert knowledge_graph_summary(graph)["edge_count"] == 1
    assert knowledge_graph_task_summary(task) == {
        "task_id": "task1",
        "status": "completed",
        "progress": 100,
        "error_code": None,
        "error_message": "",
        "created_at": created_at.isoformat(),
        "completed_at": completed_at.isoformat(),
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
../.venv/bin/python -m pytest tests/test_catalog_presenters.py -q -p no:cacheprovider
```

Expected: fail with `ModuleNotFoundError: No module named 'app.services.catalog_presenters'`.

- [ ] **Step 3: Implement presenter module**

Create `backend/app/services/catalog_presenters.py`:

```python
from app.models.catalog import CourseCatalog, CourseCatalogMaterial
from app.models.others import AsyncTask


def catalog_item(catalog: CourseCatalog) -> dict:
    return {
        "id": catalog.id,
        "title": catalog.title,
        "description": catalog.description or "",
        "status": catalog.status,
        "knowledge_status": catalog.knowledge_status,
        "material_count": catalog.material_count,
        "last_ingestion_task_id": catalog.last_ingestion_task_id,
        "last_ingestion_status": catalog.last_ingestion_status,
        "chunk_count": catalog.chunk_count or 0,
        "last_error": catalog.last_error,
        "created_at": catalog.create_time.isoformat() if catalog.create_time else "",
    }


def material_item(material: CourseCatalogMaterial, include_storage_uri: bool = False) -> dict:
    item = {
        "id": material.id,
        "catalog_id": material.catalog_id,
        "filename": material.filename,
        "source_type": material.source_type,
        "file_size": material.file_size or 0,
        "status": material.status,
        "chunk_count": material.chunk_count or 0,
        "last_error": material.last_error,
        "ingested_at": material.ingested_at.isoformat() if material.ingested_at else None,
        "created_at": material.create_time.isoformat() if material.create_time else "",
    }
    if include_storage_uri:
        item["storage_uri"] = material.storage_uri
    return item


def knowledge_graph_summary(graph) -> dict:
    return {
        "graph_id": graph.id,
        "course_id": graph.course_id,
        "version": graph.version,
        "source_type": graph.source_type,
        "generation_strategy": graph.generation_strategy,
        "node_count": len(graph.nodes or []),
        "edge_count": len(graph.edges or []),
        "is_active": graph.is_active,
        "created_at": graph.create_time.isoformat() if graph.create_time else "",
    }


def knowledge_graph_task_summary(task: AsyncTask) -> dict:
    return {
        "task_id": task.id,
        "status": task.status,
        "progress": task.progress,
        "error_code": task.error_code,
        "error_message": task.error_message,
        "created_at": task.create_time.isoformat() if task.create_time else "",
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }
```

- [ ] **Step 4: Switch route imports to presenter functions**

Modify `backend/app/api/v1/catalogs.py`:

```python
from app.services.catalog_presenters import (
    catalog_item,
    knowledge_graph_summary,
    knowledge_graph_task_summary,
    material_item,
)
```

Then replace usages:

```python
_catalog_item(...) -> catalog_item(...)
_material_item(...) -> material_item(...)
_knowledge_graph_summary(...) -> knowledge_graph_summary(...)
_knowledge_graph_task_summary(...) -> knowledge_graph_task_summary(...)
```

Delete the old local functions from `catalogs.py`.

- [ ] **Step 5: Run presenter and catalog route regression tests**

Run:

```bash
cd backend
../.venv/bin/python -m pytest tests/test_catalog_presenters.py tests/test_course_catalogs.py -q -p no:cacheprovider
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/catalog_presenters.py backend/app/api/v1/catalogs.py backend/tests/test_catalog_presenters.py
git commit -m "refactor: 提取课程资源库响应格式化"
```

---

### Task 2: Extend CatalogService for Ready Catalog Listing

**Files:**
- Modify: `backend/app/services/catalog_service.py`
- Modify: `backend/app/api/v1/catalogs.py`
- Modify: `backend/tests/test_catalog_service.py`

- [ ] **Step 1: Write failing service test**

Append to `backend/tests/test_catalog_service.py`:

```python
from app.models.catalog import CourseCatalog


@pytest.mark.asyncio
async def test_list_ready_catalogs_filters_deleted_and_orders_by_title():
    async with async_session_factory() as db:
        db.add_all([
            CourseCatalog(id="ready-b", title="B Catalog", status="ready", knowledge_status="ready"),
            CourseCatalog(id="draft-a", title="A Draft", status="draft", knowledge_status="draft"),
            CourseCatalog(id="ready-a", title="A Catalog", status="ready", knowledge_status="ready"),
            CourseCatalog(id="deleted", title="Deleted Catalog", status="ready", knowledge_status="ready", is_deleted=True),
        ])
        await db.commit()

        service = CatalogService(db)
        catalogs = await service.list_ready_catalogs("ready")

    assert [catalog.id for catalog in catalogs] == ["ready-a", "ready-b"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend
../.venv/bin/python -m pytest tests/test_catalog_service.py::test_list_ready_catalogs_filters_deleted_and_orders_by_title -q -p no:cacheprovider
```

Expected: fail with `AttributeError: 'CatalogService' object has no attribute 'list_ready_catalogs'`.

- [ ] **Step 3: Implement service method**

Modify `backend/app/services/catalog_service.py`:

```python
    async def list_ready_catalogs(self, status_filter: str | None = "ready") -> list[CourseCatalog]:
        query = select(CourseCatalog).where(CourseCatalog.is_deleted == False)
        if status_filter:
            query = query.where(CourseCatalog.status == status_filter)
        result = await self.db.execute(query.order_by(CourseCatalog.title.asc()))
        return list(result.scalars().all())
```

- [ ] **Step 4: Route delegates to service**

Modify `backend/app/api/v1/catalogs.py` public catalog route:

```python
@router.get("/course-catalogs")
async def list_ready_course_catalogs(
    status_filter: str | None = Query("ready", alias="status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    catalogs = await CatalogService(db).list_ready_catalogs(status_filter)
    return {
        "code": 200,
        "message": "success",
        "data": {"catalogs": [catalog_item(c) for c in catalogs]},
    }
```

- [ ] **Step 5: Run service and API regression tests**

Run:

```bash
cd backend
../.venv/bin/python -m pytest tests/test_catalog_service.py tests/test_course_catalogs.py -q -p no:cacheprovider
```

Expected: selected tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/catalog_service.py backend/app/api/v1/catalogs.py backend/tests/test_catalog_service.py
git commit -m "refactor: 收口课程资源库公开列表查询"
```

---

### Task 3: Extract CatalogMaterialService Helpers

**Files:**
- Create: `backend/app/services/catalog_material_service.py`
- Create: `backend/tests/test_catalog_material_service.py`
- Modify: `backend/app/api/v1/catalogs.py`

- [ ] **Step 1: Write failing helper tests**

Create `backend/tests/test_catalog_material_service.py`:

```python
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


@pytest.mark.parametrize(
    "raw",
    ["", ".", "..", "../evil.pdf", "nested/evil.pdf", "nested\\evil.pdf", "safe/../evil.pdf"],
)
def test_safe_filename_rejects_unsafe_values(raw):
    with pytest.raises(HTTPException) as exc_info:
        safe_filename(raw)
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == 40020


def test_safe_filename_accepts_basename():
    assert safe_filename(" intro.pdf ") == "intro.pdf"


def test_state_after_material_added_marks_ready_catalog_dirty():
    class Catalog:
        status = "ready"

    assert state_after_material_added(Catalog()) == ("ready", "dirty")


def test_state_after_material_added_keeps_non_ready_as_draft():
    class Catalog:
        status = "draft"

    assert state_after_material_added(Catalog()) == ("draft", "draft")


def test_remove_material_dir_uses_rmtree_on_parent_without_touching_real_storage():
    target = Path("/tmp/catalog/cat1/mat1/file.pdf")
    with patch("app.services.catalog_material_service.shutil.rmtree") as mock_rmtree:
        remove_material_dir(target)
    mock_rmtree.assert_called_once_with(target.parent, ignore_errors=True)


def test_catalog_material_service_uses_class_style_with_db_dependency():
    marker_db = object()
    service = CatalogMaterialService(marker_db)
    assert service.db is marker_db
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
../.venv/bin/python -m pytest tests/test_catalog_material_service.py -q -p no:cacheprovider
```

Expected: fail with `ModuleNotFoundError: No module named 'app.services.catalog_material_service'`.

- [ ] **Step 3: Implement helper module with class style**

Create `backend/app/services/catalog_material_service.py`:

```python
import shutil
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession


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


def state_after_material_added(catalog) -> tuple[str, str]:
    if catalog.status == "ready":
        return "ready", "dirty"
    return "draft", "draft"


def remove_material_dir(target_path: Path) -> None:
    shutil.rmtree(target_path.parent, ignore_errors=True)
```

- [ ] **Step 4: Route imports helper functions**

Modify `backend/app/api/v1/catalogs.py`:

```python
from app.services.catalog_material_service import (
    remove_material_dir,
    safe_filename,
    state_after_material_added,
)
```

Then replace usages:

```python
_safe_filename(...) -> safe_filename(...)
_state_after_material_added(...) -> state_after_material_added(...)
_remove_material_dir(...) -> remove_material_dir(...)
```

Delete old local helper functions from `catalogs.py`.

- [ ] **Step 5: Run helper and upload regression tests**

Run:

```bash
cd backend
../.venv/bin/python -m pytest tests/test_catalog_material_service.py tests/test_course_catalog_ingestion.py::test_admin_upload_catalog_material tests/test_course_catalog_ingestion.py::test_upload_removes_material_dir_for_empty_file -q -p no:cacheprovider
```

Expected: selected tests pass. The helper test must verify `shutil.rmtree` through mock patching; no real configured storage directory should be removed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/catalog_material_service.py backend/app/api/v1/catalogs.py backend/tests/test_catalog_material_service.py
git commit -m "refactor: 提取课程资源库资料基础服务"
```

---

### Task 4: Move Material CRUD Methods into CatalogMaterialService

**Files:**
- Modify: `backend/app/services/catalog_material_service.py`
- Modify: `backend/app/api/v1/catalogs.py`
- Modify: `backend/tests/test_catalog_material_service.py`

- [ ] **Step 1: Write failing service tests for list and delete**

Append to `backend/tests/test_catalog_material_service.py`:

```python
import os
import sys
from urllib.parse import urlparse

import pytest_asyncio

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
if not TEST_DATABASE_URL.startswith("mysql+"):
    pytest.skip("requires TEST_DATABASE_URL=mysql+...", allow_module_level=True)

parsed_test_url = urlparse(TEST_DATABASE_URL)
if parsed_test_url.path.strip("/") == "duagent":
    pytest.skip("refusing to use real duagent database", allow_module_level=True)

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import async_session_factory
from app.models.catalog import CourseCatalog, CourseCatalogMaterial


@pytest_asyncio.fixture
async def material_db():
    async with async_session_factory() as db:
        yield db
        await db.rollback()


@pytest.mark.asyncio
async def test_list_materials_orders_by_create_time_desc(material_db):
    material_db.add(CourseCatalog(id="mat-service-cat", title="Catalog", status="draft", knowledge_status="draft"))
    material_db.add_all([
        CourseCatalogMaterial(id="mat-old", catalog_id="mat-service-cat", filename="old.pdf", source_type="file", status="uploaded"),
        CourseCatalogMaterial(id="mat-new", catalog_id="mat-service-cat", filename="new.pdf", source_type="file", status="uploaded"),
    ])
    await material_db.commit()

    service = CatalogMaterialService(material_db)
    materials = await service.list_materials("mat-service-cat")

    assert {material.id for material in materials} == {"mat-old", "mat-new"}


@pytest.mark.asyncio
async def test_delete_material_recomputes_catalog_counts_and_marks_knowledge_dirty(material_db):
    catalog = CourseCatalog(id="mat-delete-cat", title="Catalog", status="ready", knowledge_status="ready", material_count=2, chunk_count=5)
    material_db.add(catalog)
    material_db.add_all([
        CourseCatalogMaterial(id="delete-me", catalog_id=catalog.id, filename="delete.pdf", source_type="file", status="ingested", chunk_count=2),
        CourseCatalogMaterial(id="keep-me", catalog_id=catalog.id, filename="keep.pdf", source_type="file", status="ingested", chunk_count=3),
    ])
    await material_db.commit()

    service = CatalogMaterialService(material_db)
    result = await service.delete_material(catalog, "delete-me")

    assert result["deleted"] is True
    assert catalog.material_count == 1
    assert catalog.chunk_count == 3
    assert catalog.knowledge_status == "dirty"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
../.venv/bin/python -m pytest tests/test_catalog_material_service.py::test_delete_material_recomputes_catalog_counts_and_marks_knowledge_dirty -q -p no:cacheprovider
```

Expected: fail because `CatalogMaterialService.delete_material` is missing.

- [ ] **Step 3: Implement list and delete methods**

Add to `CatalogMaterialService`:

```python
from fastapi import HTTPException, status
from sqlalchemy import func, select

from app.models.catalog import CourseCatalog, CourseCatalogMaterial


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

    async def delete_material(self, catalog: CourseCatalog, material_id: str) -> dict:
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
```

- [ ] **Step 4: Route delegates list/delete to service**

Modify `admin_list_catalog_materials`:

```python
    await CatalogService(db).get_catalog(catalog_id)
    materials = await CatalogMaterialService(db).list_materials(catalog_id)
```

Modify `admin_delete_catalog_material` after ingestion-state guard:

```python
    data = await CatalogMaterialService(db).delete_material(catalog, material_id)
    await db.commit()
    return {"code": 200, "message": "deleted", "data": data}
```

- [ ] **Step 5: Run material service and API regression tests**

Run:

```bash
cd backend
../.venv/bin/python -m pytest tests/test_catalog_material_service.py tests/test_course_catalogs.py tests/test_course_catalog_ingestion.py -q -p no:cacheprovider
```

Expected: selected tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/catalog_material_service.py backend/app/api/v1/catalogs.py backend/tests/test_catalog_material_service.py
git commit -m "refactor: 下沉课程资源库资料查询删除逻辑"
```

---

### Task 5: Verification, Metrics, and Workflow Record

**Files:**
- Modify: `WORKFLOW.md`

- [ ] **Step 1: Run syntax checks**

Run:

```bash
cd backend
../.venv/bin/python -m py_compile app/api/v1/catalogs.py app/services/catalog_service.py app/services/catalog_material_service.py app/services/catalog_presenters.py
```

Expected: command exits 0.

- [ ] **Step 2: Run Phase 1 regression suite**

Run:

```bash
cd backend
../.venv/bin/python -m pytest tests/test_catalog_presenters.py tests/test_catalog_material_service.py tests/test_catalog_service.py tests/test_course_catalogs.py tests/test_course_catalog_ingestion.py -q -p no:cacheprovider
```

Expected: selected tests pass. If MySQL-specific tests require `TEST_DATABASE_URL`, set it explicitly to a non-production test database before running.

- [ ] **Step 3: Check `catalogs.py` line count**

Run:

```bash
cd frontend
wc -l ../backend/app/api/v1/catalogs.py
```

Expected: line count below 1600. If it is above 1600, do not force extra unrelated extraction; record the actual count and continue only if tests are green.

- [ ] **Step 4: Update `WORKFLOW.md`**

Append an entry:

```markdown
### 2026-06-18 (后端 catalogs.py 分层重构 Phase 1)
- **改了什么文件**: `backend/app/api/v1/catalogs.py`, `backend/app/services/catalog_service.py`, `backend/app/services/catalog_presenters.py`, `backend/app/services/catalog_material_service.py`, `backend/tests/test_catalog_presenters.py`, `backend/tests/test_catalog_material_service.py`, `backend/tests/test_catalog_service.py`
- **核心改动**: 将课程资源库响应 DTO、公开 catalog 列表查询、资料基础校验/删除/列表逻辑从胖路由下沉到 service/presenter 层。请求生命周期 service 统一采用 `ClassName(db)` 类风格；后台任务函数本阶段未迁移。
- **测试结果**: `<填入实际命令和结果>`
- **是否有接口漂移**: 无。Client API / Agent API 路径、字段、状态码语义未改变。
- **下一步**: 进入 Phase 2：Catalog ingestion service。
```

- [ ] **Step 5: Commit final record**

```bash
git add WORKFLOW.md
git commit -m "docs: 记录 catalogs 分层重构第一阶段"
```

---

## Later-Phase Notes

- Phase 2 background ingestion functions should be module-level functions in `catalog_ingestion_service.py`, not instance methods, because they create independent sessions through `async_session_factory()`.
- Phase 3 KG host course migration needs targeted review around `SELECT ... FOR UPDATE`, MySQL isolation behavior, and IntegrityError fallback.
- Phase 5 quiz generation migration must first add a concurrency/failure test around `asyncio.gather(..., return_exceptions=True)` so one child failure cannot break parent aggregation.
