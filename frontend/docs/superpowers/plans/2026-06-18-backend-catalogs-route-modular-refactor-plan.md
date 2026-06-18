# Backend Catalogs Route Modular Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Modularize `backend/app/api/v1/catalogs.py` end-to-end so the route file becomes HTTP glue while catalog CRUD, material handling, ingestion, KG, resource generation, quiz generation, and response DTO logic live in focused service modules.

**Architecture:** Keep the public API surface unchanged. Use `Router -> Service -> DB/Agent/FileSystem` with class-style request-scoped services (`CatalogMaterialService(db)`, `CatalogKGService(db)`) and module-level background task functions (`run_catalog_ingestion_background(...)`) for code that owns its own `async_session_factory()` session.

**Tech Stack:** FastAPI, SQLAlchemy AsyncSession, existing `AsyncTask` table, existing `AgentClient`, pytest/pytest-asyncio, unittest.mock/pytest monkeypatch.

---

## Hard Rules

- Strict TDD for every module:
  1. Write or move the target test first.
  2. Run it and record the RED failure.
  3. Implement the smallest migration.
  4. Run the focused test and record GREEN.
  5. Run the module regression tests.
  6. Review the diff before commit.
- No code is considered complete without fresh command output.
- Do not change Client API paths, params, response fields, status code semantics, or Agent API payload semantics.
- Do not modify `.env`, secrets, uploaded files, MySQL volume data, `node_modules`, or build artifacts.
- Do not introduce Celery, Redis Queue, CQRS, new DI containers, or generic repositories in this pass.
- Do not trust route-level behavior after moving code; rerun API regression tests.
- Agent calls in tests must be mocked.
- File-system destructive operations in tests must use `tmp_path` or mock patching; never point at real configured catalog storage.

## Service Style Decisions

- Request-scoped services are classes:
  - `CatalogService(db)`
  - `CatalogMaterialService(db)`
  - `CatalogIngestionService(db)`
  - `CatalogKGService(db)`
  - `CatalogResourceGenerationService(db)`
  - `CatalogQuizGenerationService(db)`
- Pure presenter functions are module-level functions.
- Background task runners are module-level functions in the matching service file:
  - `run_catalog_ingestion_background(task_id)`
  - `run_catalog_kg_generation_background(task_id)`
  - `run_quiz_generation_background(parent_id, child_task_ids, fanout_course_ids)`
- Background task runners must create their own DB session with `async_session_factory()` and must not depend on a request-scoped service instance.

## Target File Structure

- Create `backend/app/services/catalog_presenters.py`
- Modify `backend/app/services/catalog_service.py`
- Create `backend/app/services/catalog_material_service.py`
- Create `backend/app/services/catalog_ingestion_service.py`
- Create `backend/app/services/catalog_kg_service.py`
- Create `backend/app/services/catalog_resource_generation_service.py`
- Create `backend/app/services/catalog_quiz_generation_service.py`
- Modify `backend/app/api/v1/catalogs.py`
- Create or extend focused tests under `backend/tests/`
- Update `WORKFLOW.md` after each verified module batch

## Module Completion Gates

Each module batch must pass:

```bash
cd backend
../.venv/bin/python -m py_compile app/api/v1/catalogs.py app/services/<changed_service>.py
../.venv/bin/python -m pytest <focused-tests> -q -p no:cacheprovider
```

Before final completion:

```bash
cd backend
../.venv/bin/python -m py_compile app/api/v1/catalogs.py app/services/catalog_service.py app/services/catalog_material_service.py app/services/catalog_ingestion_service.py app/services/catalog_kg_service.py app/services/catalog_resource_generation_service.py app/services/catalog_quiz_generation_service.py app/services/catalog_presenters.py
../.venv/bin/python -m pytest tests/test_catalog_presenters.py tests/test_catalog_material_service.py tests/test_catalog_service.py tests/test_course_catalogs.py tests/test_course_catalog_ingestion.py tests/test_admin_catalog_kg_generation.py tests/test_admin_catalog_resource_generation.py tests/test_node_resources.py -q -p no:cacheprovider
```

If MySQL-backed tests require explicit configuration, run with a non-production `TEST_DATABASE_URL` and record the exact value pattern, not secrets.

---

### Task 1: Presenters and Baseline Diff Map

**Files:**
- Create: `backend/app/services/catalog_presenters.py`
- Create: `backend/tests/test_catalog_presenters.py`
- Modify: `backend/app/api/v1/catalogs.py`

- [ ] **Step 1: Write presenter tests**

Create `backend/tests/test_catalog_presenters.py` with tests for:

```python
from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.catalog_presenters import (
    catalog_item,
    knowledge_graph_summary,
    knowledge_graph_task_summary,
    material_item,
)


def test_catalog_item_response_shape():
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


def test_material_item_response_shape_and_storage_uri_flag():
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

    hidden = material_item(material)
    visible = material_item(material, include_storage_uri=True)

    assert "storage_uri" not in hidden
    assert visible["storage_uri"] == "course_catalogs/cat1/mat1/intro.pdf"
    assert visible["file_size"] == 0
    assert visible["chunk_count"] == 0
    assert visible["ingested_at"] == ingested_at.isoformat()


def test_knowledge_graph_presenter_response_shapes():
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

    assert knowledge_graph_summary(graph) == {
        "graph_id": "graph1",
        "course_id": "course1",
        "version": 3,
        "source_type": "route_a",
        "generation_strategy": "route_a_prune",
        "node_count": 1,
        "edge_count": 1,
        "is_active": True,
        "created_at": created_at.isoformat(),
    }
    assert knowledge_graph_task_summary(task)["completed_at"] == completed_at.isoformat()
```

- [ ] **Step 2: Run RED**

```bash
cd backend
../.venv/bin/python -m pytest tests/test_catalog_presenters.py -q -p no:cacheprovider
```

Expected RED: import failure for missing `app.services.catalog_presenters`.

- [ ] **Step 3: Implement `catalog_presenters.py`**

Move the existing presenter logic from `catalogs.py` into `backend/app/services/catalog_presenters.py` as:

```python
from app.models.catalog import CourseCatalog, CourseCatalogMaterial
from app.models.others import AsyncTask


def catalog_item(catalog: CourseCatalog) -> dict:
    ...


def material_item(material: CourseCatalogMaterial, include_storage_uri: bool = False) -> dict:
    ...


def knowledge_graph_summary(graph) -> dict:
    ...


def knowledge_graph_task_summary(task: AsyncTask) -> dict:
    ...
```

Use the exact response keys and fallback values from the current route file.

- [ ] **Step 4: Replace route usages and remove local presenter functions**

Import the new functions in `catalogs.py` and replace:

```text
_catalog_item -> catalog_item
_material_item -> material_item
_knowledge_graph_summary -> knowledge_graph_summary
_knowledge_graph_task_summary -> knowledge_graph_task_summary
```

- [ ] **Step 5: Run GREEN and regression**

```bash
cd backend
../.venv/bin/python -m pytest tests/test_catalog_presenters.py tests/test_course_catalogs.py -q -p no:cacheprovider
../.venv/bin/python -m py_compile app/api/v1/catalogs.py app/services/catalog_presenters.py
```

- [ ] **Step 6: Review diff**

Check:

```bash
git diff -- backend/app/api/v1/catalogs.py backend/app/services/catalog_presenters.py backend/tests/test_catalog_presenters.py
```

Review criteria:

- No response key renamed.
- No status code changes.
- No DB query moved in this task.

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/v1/catalogs.py backend/app/services/catalog_presenters.py backend/tests/test_catalog_presenters.py
git commit -m "refactor: 提取课程资源库响应格式化"
```

---

### Task 2: Catalog and Material Request-Scoped Services

**Files:**
- Modify: `backend/app/services/catalog_service.py`
- Create: `backend/app/services/catalog_material_service.py`
- Modify: `backend/app/api/v1/catalogs.py`
- Modify/Create: `backend/tests/test_catalog_service.py`, `backend/tests/test_catalog_material_service.py`

- [ ] **Step 1: Write RED tests for service style and helpers**

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
```

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

- [ ] **Step 2: Run RED**

```bash
cd backend
../.venv/bin/python -m pytest tests/test_catalog_material_service.py tests/test_catalog_service.py::test_list_ready_catalogs_filters_deleted_and_orders_by_title -q -p no:cacheprovider
```

Expected RED: missing `catalog_material_service` module and missing `CatalogService.list_ready_catalogs`.

- [ ] **Step 3: Implement helper service and ready catalog method**

Create `backend/app/services/catalog_material_service.py` with class style and helpers.

Modify `backend/app/services/catalog_service.py` to add:

```python
    async def list_ready_catalogs(self, status_filter: str | None = "ready") -> list[CourseCatalog]:
        query = select(CourseCatalog).where(CourseCatalog.is_deleted == False)
        if status_filter:
            query = query.where(CourseCatalog.status == status_filter)
        result = await self.db.execute(query.order_by(CourseCatalog.title.asc()))
        return list(result.scalars().all())
```

- [ ] **Step 4: Route delegates helper functions and public catalog list**

Modify `catalogs.py` to import:

```python
from app.services.catalog_material_service import (
    remove_material_dir,
    safe_filename,
    state_after_material_added,
)
```

Replace helper usages and update `list_ready_course_catalogs()` to call `CatalogService(db).list_ready_catalogs(status_filter)`.

- [ ] **Step 5: Run GREEN and regression**

```bash
cd backend
../.venv/bin/python -m pytest tests/test_catalog_material_service.py tests/test_catalog_service.py tests/test_course_catalogs.py tests/test_course_catalog_ingestion.py::test_admin_upload_catalog_material tests/test_course_catalog_ingestion.py::test_upload_removes_material_dir_for_empty_file -q -p no:cacheprovider
../.venv/bin/python -m py_compile app/api/v1/catalogs.py app/services/catalog_service.py app/services/catalog_material_service.py
```

- [ ] **Step 6: Review diff**

Check:

```bash
git diff -- backend/app/api/v1/catalogs.py backend/app/services/catalog_service.py backend/app/services/catalog_material_service.py backend/tests/test_catalog_service.py backend/tests/test_catalog_material_service.py
```

Review criteria:

- `CatalogMaterialService` is class-style.
- `remove_material_dir` tests patch `shutil.rmtree`.
- No real storage path is touched by new unit tests.
- Public ready catalog response remains wrapped as before.

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/v1/catalogs.py backend/app/services/catalog_service.py backend/app/services/catalog_material_service.py backend/tests/test_catalog_service.py backend/tests/test_catalog_material_service.py
git commit -m "refactor: 提取课程资源库基础服务"
```

---

### Task 3: Material CRUD and Upload Service Methods

**Files:**
- Modify: `backend/app/services/catalog_material_service.py`
- Modify: `backend/app/api/v1/catalogs.py`
- Modify: `backend/tests/test_catalog_material_service.py`

- [ ] **Step 1: Write RED service tests for DB behavior**

Add DB-backed tests for:

- `list_materials(catalog_id)` excludes deleted records.
- `delete_material(catalog, material_id)` soft deletes, recomputes `material_count` / `chunk_count`, marks ready/partial knowledge dirty.
- `create_external_material(catalog, req)` preserves current status transitions.

Use the same MySQL guard pattern as `test_catalog_service.py`.

- [ ] **Step 2: Run RED**

```bash
cd backend
../.venv/bin/python -m pytest tests/test_catalog_material_service.py::test_delete_material_recomputes_catalog_counts_and_marks_knowledge_dirty -q -p no:cacheprovider
```

Expected RED: target method missing.

- [ ] **Step 3: Implement methods**

Add methods to `CatalogMaterialService`:

```python
async def list_materials(self, catalog_id: str) -> list[CourseCatalogMaterial]: ...
async def create_external_material(self, catalog: CourseCatalog, req: CourseCatalogMaterialCreateRequest) -> CourseCatalogMaterial: ...
async def delete_material(self, catalog: CourseCatalog, material_id: str) -> dict: ...
```

Use existing route code exactly for SQL conditions and error details.

- [ ] **Step 4: Route delegates create/list/delete material**

Update:

- `admin_create_catalog_material`
- `admin_list_catalog_materials`
- `admin_delete_catalog_material`

Route still performs auth and response wrapping.

- [ ] **Step 5: Run GREEN and regression**

```bash
cd backend
../.venv/bin/python -m pytest tests/test_catalog_material_service.py tests/test_course_catalogs.py tests/test_course_catalog_ingestion.py -q -p no:cacheprovider
../.venv/bin/python -m py_compile app/api/v1/catalogs.py app/services/catalog_material_service.py
```

- [ ] **Step 6: Review diff**

Review criteria:

- DB update conditions still guard against ingesting state.
- Delete response data keys unchanged.
- Commit behavior remains route-owned unless current behavior already commits inside the route.

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/v1/catalogs.py backend/app/services/catalog_material_service.py backend/tests/test_catalog_material_service.py
git commit -m "refactor: 下沉课程资源库资料管理逻辑"
```

---

### Task 4: Catalog Ingestion Service

**Files:**
- Create: `backend/app/services/catalog_ingestion_service.py`
- Modify: `backend/app/api/v1/catalogs.py`
- Modify: `backend/tests/test_course_catalog_ingestion.py`

- [ ] **Step 1: Write RED tests around service boundary**

Add or adapt tests to import and call:

```python
from app.services.catalog_ingestion_service import CatalogIngestionService, run_catalog_ingestion_background
```

Cover:

- no pending materials raises current 40912 error.
- start creates `AsyncTask` with `task_type="catalog_ingestion"`.
- background Agent failure marks task failed and catalog/material statuses correctly.

- [ ] **Step 2: Run RED**

```bash
cd backend
../.venv/bin/python -m pytest tests/test_course_catalog_ingestion.py::test_start_catalog_ingestion_success -q -p no:cacheprovider
```

Expected RED after test import changes: missing `catalog_ingestion_service` or missing methods.

- [ ] **Step 3: Move ingestion start/background code**

Create:

```python
class CatalogIngestionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def start_catalog_ingestion(self, catalog_id: str, user_id: str) -> AsyncTask:
        ...


async def run_catalog_ingestion_background(task_id: str) -> None:
    ...
```

Move `_run_catalog_ingestion_background` body into the module-level function. It must use independent sessions only.

- [ ] **Step 4: Route delegates ingestion**

`admin_start_catalog_ingestion` should:

```python
task = await CatalogIngestionService(db).start_catalog_ingestion(catalog_id, current_user.id)
background_tasks.add_task(run_catalog_ingestion_background, task.id)
return {"code": 202, "message": "accepted", "data": {"task_id": task.id, "catalog_id": catalog_id, "status": "processing"}}
```

- [ ] **Step 5: Run GREEN and regression**

```bash
cd backend
../.venv/bin/python -m pytest tests/test_course_catalog_ingestion.py -q -p no:cacheprovider
../.venv/bin/python -m py_compile app/api/v1/catalogs.py app/services/catalog_ingestion_service.py
```

- [ ] **Step 6: Review diff**

Review criteria:

- No request-scoped `db` leaks into background function.
- All failure paths still set task status to failed.
- Agent patch path in tests updated from `app.api.v1.catalogs.ingestion_agent_client.post_json` to the new module path if needed.

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/v1/catalogs.py backend/app/services/catalog_ingestion_service.py backend/tests/test_course_catalog_ingestion.py
git commit -m "refactor: 下沉课程资源库入库任务逻辑"
```

---

### Task 5: Catalog KG Service

**Files:**
- Create: `backend/app/services/catalog_kg_service.py`
- Modify: `backend/app/api/v1/catalogs.py`
- Modify: `backend/tests/test_admin_catalog_kg_generation.py`

- [ ] **Step 1: Write RED service boundary/concurrency tests**

Add tests for:

- `CatalogKGService.get_or_create_catalog_kg_host_course(...)` reuses existing host course.
- long catalog title truncation still holds.
- duplicate processing task check still prevents double generation.
- IntegrityError fallback path remains covered by a targeted unit test or preserved API test.

For MySQL concurrency-sensitive behavior, mark the test clearly and run it with the existing MySQL test DB. Do not assume SQLite proves production locking behavior.

- [ ] **Step 2: Run RED**

```bash
cd backend
../.venv/bin/python -m pytest tests/test_admin_catalog_kg_generation.py::test_catalog_kg_generation_without_offering_returns_202_not_40915 -q -p no:cacheprovider
```

Expected RED after import/patch update: missing `catalog_kg_service`.

- [ ] **Step 3: Move KG host/status/generation code**

Create class:

```python
class CatalogKGService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_catalog_kg_host_course(...): ...
    async def get_knowledge_graph_status(...): ...
    async def start_kg_generation(...): ...


async def run_catalog_kg_generation_background(task_id: str) -> None:
    ...
```

Move local helpers:

- `_get_or_create_catalog_kg_host_course`
- `_catalog_kg_host_course_name`
- `_run_catalog_kg_generation_background`
- KG status query logic

- [ ] **Step 4: Route delegates KG endpoints**

Update:

- `admin_get_catalog_knowledge_graph_status`
- `admin_generate_catalog_knowledge_graph`

- [ ] **Step 5: Run GREEN and regression**

```bash
cd backend
../.venv/bin/python -m pytest tests/test_admin_catalog_kg_generation.py tests/test_course_knowledge_graph_versions.py -q -p no:cacheprovider
../.venv/bin/python -m py_compile app/api/v1/catalogs.py app/services/catalog_kg_service.py
```

- [ ] **Step 6: Review diff**

Review criteria:

- `with_for_update()` remains on host course creation path.
- IntegrityError fallback still reloads catalog and host course.
- No Agent API payload field changed.

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/v1/catalogs.py backend/app/services/catalog_kg_service.py backend/tests/test_admin_catalog_kg_generation.py
git commit -m "refactor: 下沉课程资源库知识图谱任务逻辑"
```

---

### Task 6: Catalog Resource Generation Service

**Files:**
- Create: `backend/app/services/catalog_resource_generation_service.py`
- Modify: `backend/app/api/v1/catalogs.py`
- Modify: `backend/tests/test_admin_catalog_resource_generation.py`

- [ ] **Step 1: Write RED service boundary tests**

Add or update tests for:

- explicit metadata request still creates single resource_generation task.
- no active KG creates failed parent task with existing error semantics.
- no usable KG targets creates failed parent task.
- KG-node child task result contains `target_node`.
- Agent calls are patched at `app.services.catalog_resource_generation_service.agent_client.post_json`.

- [ ] **Step 2: Run RED**

```bash
cd backend
../.venv/bin/python -m pytest tests/test_admin_catalog_resource_generation.py::test_admin_catalog_generation_without_metadata_fails_parent_when_no_active_kg -q -p no:cacheprovider
```

Expected RED after patch/import update: missing service module or method.

- [ ] **Step 3: Move resource generation/list/delete code**

Create:

```python
class CatalogResourceGenerationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_catalog_resources(...): ...
    async def delete_resource(...): ...
    async def start_resource_generation(...): ...
```

Move KG target selection and explicit metadata branches without changing payload fields.

- [ ] **Step 4: Route delegates resource endpoints**

Update:

- `admin_list_catalog_resources`
- `admin_delete_resource`
- `admin_generate_catalog_resources`

- [ ] **Step 5: Run GREEN and regression**

```bash
cd backend
../.venv/bin/python -m pytest tests/test_admin_catalog_resource_generation.py tests/test_kg_resource_targets.py tests/test_node_resources.py -q -p no:cacheprovider
../.venv/bin/python -m py_compile app/api/v1/catalogs.py app/services/catalog_resource_generation_service.py
```

- [ ] **Step 6: Review diff**

Review criteria:

- Parent/child task result payloads unchanged.
- Agent request path remains `/agent/v1/resources/generate`.
- Existing webhook aggregation expectations remain valid.

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/v1/catalogs.py backend/app/services/catalog_resource_generation_service.py backend/tests/test_admin_catalog_resource_generation.py
git commit -m "refactor: 下沉课程资源库资源生成逻辑"
```

---

### Task 7: Catalog Quiz Generation Service

**Files:**
- Create: `backend/app/services/catalog_quiz_generation_service.py`
- Modify: `backend/app/api/v1/catalogs.py`
- Modify: `backend/tests/test_admin_catalog_resource_generation.py`

- [ ] **Step 1: Write RED concurrency/failure isolation test**

Add a test that proves one child failure does not break parent aggregation. The test should patch the child generation function so:

- child A returns completed with question ids.
- child B raises an exception.
- `run_quiz_generation_background(..., return_exceptions=True path)` marks parent `partial`.

Patch at the new module path:

```python
with patch("app.services.catalog_quiz_generation_service.generate_quiz_for_child", new_callable=AsyncMock) as mock_child:
    ...
```

- [ ] **Step 2: Run RED**

```bash
cd backend
../.venv/bin/python -m pytest tests/test_admin_catalog_resource_generation.py::test_quiz_generation_background_marks_parent_partial_when_one_child_raises -q -p no:cacheprovider
```

Expected RED: missing service module/function or current behavior not routed through new module.

- [ ] **Step 3: Move quiz generation code**

Create:

```python
class CatalogQuizGenerationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def start_quiz_generation(...): ...


async def run_quiz_generation_background(parent_id: str, child_task_ids: list[str], fanout_course_ids: list[str]) -> None: ...
async def generate_quiz_for_child(db: AsyncSession, child_id: str, fanout_course_ids: list[str]) -> dict: ...
```

Move helper functions:

- `_build_baseline_quiz_payload`
- `_request_baseline_quiz_questions`
- `_generate_baseline_quiz_questions`
- `_non_skeleton_quiz_questions`
- `_format_quiz_answer`
- `_quiz_option_text`
- `_is_skeleton_quiz_question`

- [ ] **Step 4: Route delegates quiz endpoint**

Update `admin_generate_catalog_quiz` to call `CatalogQuizGenerationService(db).start_quiz_generation(...)` and schedule `run_quiz_generation_background(...)` with `asyncio.create_task` or the current scheduling mechanism preserved.

- [ ] **Step 5: Run GREEN and regression**

```bash
cd backend
../.venv/bin/python -m pytest tests/test_admin_catalog_resource_generation.py -q -p no:cacheprovider
../.venv/bin/python -m py_compile app/api/v1/catalogs.py app/services/catalog_quiz_generation_service.py
```

- [ ] **Step 6: Review diff**

Review criteria:

- `asyncio.gather(..., return_exceptions=True)` remains.
- Semaphore limit remains `QUIZ_GENERATION_CONCURRENCY = 2`.
- Skeleton rejection behavior unchanged.
- Multi-choice answer remains comma-separated (`A,C`).
- Old baseline questions are not deleted before new child success.

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/v1/catalogs.py backend/app/services/catalog_quiz_generation_service.py backend/tests/test_admin_catalog_resource_generation.py
git commit -m "refactor: 下沉课程资源库题库生成逻辑"
```

---

### Task 8: Final Route Cleanup, Full Review, and Workflow

**Files:**
- Modify: `backend/app/api/v1/catalogs.py`
- Modify: `WORKFLOW.md`

- [ ] **Step 1: Remove dead imports/helpers from `catalogs.py`**

Remove unused imports and local helpers after all services are migrated. Use `rg` to confirm no remaining references:

```bash
cd frontend
rg "_catalog_item|_material_item|_run_catalog_ingestion_background|_run_catalog_kg_generation_background|_run_quiz_generation_background|_generate_quiz_for_child|_safe_filename|_remove_material_dir|_state_after_material_added" ../backend/app/api/v1/catalogs.py
```

Expected: no matches.

- [ ] **Step 2: Final syntax verification**

```bash
cd backend
../.venv/bin/python -m py_compile app/api/v1/catalogs.py app/services/catalog_service.py app/services/catalog_material_service.py app/services/catalog_ingestion_service.py app/services/catalog_kg_service.py app/services/catalog_resource_generation_service.py app/services/catalog_quiz_generation_service.py app/services/catalog_presenters.py
```

- [ ] **Step 3: Full catalogs regression suite**

```bash
cd backend
../.venv/bin/python -m pytest tests/test_catalog_presenters.py tests/test_catalog_material_service.py tests/test_catalog_service.py tests/test_course_catalogs.py tests/test_course_catalog_ingestion.py tests/test_admin_catalog_kg_generation.py tests/test_admin_catalog_resource_generation.py tests/test_node_resources.py -q -p no:cacheprovider
```

- [ ] **Step 4: Diff review**

Run:

```bash
cd frontend
git diff --stat
git diff -- ../backend/app/api/v1/catalogs.py ../backend/app/services ../backend/tests
```

Review checklist:

- `catalogs.py` contains only route glue and response wrapping.
- No response key/path/status code changed.
- No Agent path changed.
- No background runner takes request-scoped `db`.
- No test patches point at deleted route-private helpers.
- No unrelated files changed.

- [ ] **Step 5: Record workflow**

Append to `WORKFLOW.md`:

```markdown
### 2026-06-18 (后端 catalogs.py 模块化分层重构)
- **改了什么文件**: `backend/app/api/v1/catalogs.py`, `backend/app/services/catalog_*.py`, `backend/tests/test_catalog_*.py`, 相关 catalog 回归测试文件。
- **核心改动**: 将 `catalogs.py` 中的响应格式化、Catalog/Material、入库、KG、资源生成、Quiz 生成逻辑整体下沉到 focused service modules。Route 保留 HTTP glue。Request-scoped service 采用类风格，后台任务 runner 采用模块级函数。
- **测试结果**: 实施时写入实际运行的 RED/GREEN/回归命令、退出码和通过/失败数量。
- **是否有接口漂移**: 无。Client API / Agent API 路径、参数、响应字段和状态码语义未改变。
- **代码审查结果**: 实施时写入最终 diff review 结论，至少说明 route 是否只剩 HTTP glue、后台 runner 是否独立 session、测试 patch 路径是否已更新。
```

- [ ] **Step 6: Commit final cleanup**

```bash
git add backend/app/api/v1/catalogs.py WORKFLOW.md
git commit -m "refactor: 收口课程资源库路由模块边界"
```

---

## Self-Review Checklist for Implementer

Before claiming completion, answer with evidence:

- Which RED commands failed as expected?
- Which GREEN commands passed?
- Which full regression command passed?
- What is the final `wc -l backend/app/api/v1/catalogs.py` count?
- Did any Client API or Agent API contract change?
- Which files were committed in each commit?
