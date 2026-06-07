# Phase B1 Backend CourseCatalog Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Backend middle layer for CourseCatalog knowledge ingestion: upload materials, trigger an AsyncTask, call Agent Service in a background task, and persist catalog/material/task status.

**Architecture:** Backend owns admin permissions, file storage, SQL state, and AsyncTask lifecycle. Agent Service remains a synchronous HTTP dependency inside the Backend background task. Client API returns `202 + task_id` immediately and existing `GET /tasks/{task_id}` handles polling.

**Tech Stack:** FastAPI, SQLAlchemy async, MySQL/aiomysql, Pydantic settings, httpx-based `agent_client`, pytest with `httpx.ASGITransport`, OpenAPI JSON, existing EDUagent Backend models.

---

## File Structure

- Modify `../backend/app/core/config.py`
  - Add upload storage settings.
- Modify `../backend/app/models/catalog.py`
  - Add ingestion state fields on `CourseCatalog` and `CourseCatalogMaterial`.
- Modify `../backend/app/schemas/catalog.py`
  - Extend material response schemas and add ingestion response schema.
- Modify `../backend/migrations/2026-06-07-add-course-catalogs.sql`
  - Keep fresh installs aligned with the model.
- Create `../backend/migrations/2026-06-08-extend-course-catalog-ingestion.sql`
  - Upgrade existing databases created from the earlier Phase A migration.
- Create `../backend/tests/test_course_catalog_ingestion.py`
  - Focused TDD coverage for config/model/upload/orchestration/task polling.
- Modify `../backend/app/api/v1/catalogs.py`
  - Add upload endpoint, ingestion endpoint, helpers, and background task.
  - Fix existing material registration so ready catalogs stay bindable.
- Modify `../backend/app/api/v1/tasks.py`
  - Allow admins to poll `course_catalog_ingestion` tasks even when they do not own them.
- Modify `../docs/10-client-api/Client-API.openapi.json`
  - Add upload and ingestion contract and extend schemas.
- Modify `WORKFLOW.md`
  - Record implementation and verification after the runtime work is complete.

## Task 1: Backend Model, Config, and Migration

**Files:**
- Modify: `../backend/app/core/config.py`
- Modify: `../backend/app/models/catalog.py`
- Modify: `../backend/app/schemas/catalog.py`
- Modify: `../backend/migrations/2026-06-07-add-course-catalogs.sql`
- Create: `../backend/migrations/2026-06-08-extend-course-catalog-ingestion.sql`
- Create: `../backend/tests/test_course_catalog_ingestion.py`

- [ ] **Step 1: Write failing model/config/schema tests**

Create `../backend/tests/test_course_catalog_ingestion.py` with this initial content:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `../backend`:

```bash
pytest tests/test_course_catalog_ingestion.py -q
```

Expected: fails because model fields, config settings, or schema fields are missing.

- [ ] **Step 3: Add storage settings**

Modify `../backend/app/core/config.py` after `AGENT_SERVICE_URL`:

```python
    # CourseCatalog local material storage
    COURSE_CATALOG_STORAGE_ROOT: str = "storage/course_catalogs"
    COURSE_CATALOG_MAX_UPLOAD_BYTES: int = 20 * 1024 * 1024
```

- [ ] **Step 4: Extend catalog models**

Modify `../backend/app/models/catalog.py`.

Change the imports:

```python
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, func
```

Add these fields to `CourseCatalog` after `material_count`:

```python
    last_ingestion_task_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_ingestion_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
```

Add these fields to `CourseCatalogMaterial` after `storage_uri`:

```python
    file_size: Mapped[int] = mapped_column(BigInteger, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ingested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

Keep existing defaults:

```python
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="uploaded")
```

- [ ] **Step 5: Extend catalog schemas**

Modify `../backend/app/schemas/catalog.py`.

Extend `CourseCatalogItem` with:

```python
    last_ingestion_task_id: Optional[str] = None
    last_ingestion_status: Optional[str] = None
    chunk_count: int = 0
    last_error: Optional[str] = None
```

Replace `CourseCatalogMaterialItem` with:

```python
class CourseCatalogMaterialItem(BaseModel):
    id: str
    catalog_id: str
    filename: str
    source_type: str
    file_size: int = 0
    status: str
    chunk_count: int = 0
    last_error: Optional[str] = None
    ingested_at: Optional[str] = None
    created_at: str
```

Add after `CourseCatalogMaterialItem`:

```python
class CourseCatalogIngestionAccepted(BaseModel):
    task_id: str
    catalog_id: str
    status: str
```

- [ ] **Step 6: Update fresh-install migration**

Modify `../backend/migrations/2026-06-07-add-course-catalogs.sql`.

In `course_catalogs`, add after `material_count`:

```sql
    last_ingestion_task_id VARCHAR(32) DEFAULT NULL,
    last_ingestion_status VARCHAR(20) DEFAULT NULL,
    chunk_count INT NOT NULL DEFAULT 0,
    last_error VARCHAR(500) DEFAULT NULL,
```

In `course_catalog_materials`, add after `storage_uri`:

```sql
    file_size BIGINT NOT NULL DEFAULT 0,
    chunk_count INT NOT NULL DEFAULT 0,
    last_error VARCHAR(500) DEFAULT NULL,
    ingested_at DATETIME DEFAULT NULL,
```

- [ ] **Step 7: Add upgrade migration**

Create `../backend/migrations/2026-06-08-extend-course-catalog-ingestion.sql`:

```sql
ALTER TABLE course_catalogs
  ADD COLUMN last_ingestion_task_id VARCHAR(32) DEFAULT NULL,
  ADD COLUMN last_ingestion_status VARCHAR(20) DEFAULT NULL,
  ADD COLUMN chunk_count INT NOT NULL DEFAULT 0,
  ADD COLUMN last_error VARCHAR(500) DEFAULT NULL;

ALTER TABLE course_catalog_materials
  ADD COLUMN file_size BIGINT NOT NULL DEFAULT 0,
  ADD COLUMN chunk_count INT NOT NULL DEFAULT 0,
  ADD COLUMN last_error VARCHAR(500) DEFAULT NULL,
  ADD COLUMN ingested_at DATETIME DEFAULT NULL;
```

- [ ] **Step 8: Run schema tests**

Run from `../backend`:

```bash
pytest tests/test_course_catalog_ingestion.py -q
```

Expected: all four tests pass.

- [ ] **Step 9: Commit model/config/schema**

Run from `frontend`:

```bash
git add ../backend/app/core/config.py ../backend/app/models/catalog.py ../backend/app/schemas/catalog.py ../backend/migrations/2026-06-07-add-course-catalogs.sql ../backend/migrations/2026-06-08-extend-course-catalog-ingestion.sql ../backend/tests/test_course_catalog_ingestion.py
git commit -m "扩展课程资源库入库状态模型"
```

## Task 2: Material Upload API

**Files:**
- Modify: `../backend/app/api/v1/catalogs.py`
- Modify: `../backend/tests/test_course_catalog_ingestion.py`
- Test: `../backend/tests/test_course_catalogs.py`

- [ ] **Step 1: Add upload test helpers and failing tests**

Append to `../backend/tests/test_course_catalog_ingestion.py`:

```python
import asyncio
import re
import uuid

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.session import async_session_factory, engine, init_db
from app.main import app
from app.models.catalog import CourseCatalog, CourseCatalogMaterial
from app.models.user import RegistrationCode


def _captcha_answer(question: str) -> str:
    nums = re.findall(r"\d+", question)
    if "+" in question:
        return str(int(nums[0]) + int(nums[1]))
    return str(int(nums[0]) - int(nums[1]))


async def _register_and_login(client: AsyncClient, role: str):
    code = f"{role}_{uuid.uuid4().hex[:8]}"
    async with async_session_factory() as db:
        db.add(RegistrationCode(code=code, role=role))
        await db.commit()

    email = f"{role}_{uuid.uuid4().hex[:8]}@test.com"
    username = f"{role}_{uuid.uuid4().hex[:8]}"
    captcha = await client.get("/api/v1/auth/captcha")
    captcha_data = captcha.json()["data"]
    register = await client.post("/api/v1/auth/register", json={
        "registration_code": code,
        "email": email,
        "password": "Abc12345",
        "username": username,
        "captcha_token": captcha_data["captcha_token"],
        "captcha_code": _captcha_answer(captcha_data["captcha_question"]),
    })
    assert register.status_code == 201, register.text

    captcha = await client.get("/api/v1/auth/captcha")
    captcha_data = captcha.json()["data"]
    login = await client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "Abc12345",
        "captcha_token": captcha_data["captcha_token"],
        "captcha_code": _captcha_answer(captcha_data["captcha_question"]),
    })
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['data']['token']}"}


async def _create_catalog(client: AsyncClient, admin_headers: dict, title: str = "数据结构") -> str:
    create = await client.post(
        "/api/v1/admin/course-catalogs",
        headers=admin_headers,
        json={"title": title, "description": "Phase B1 test"},
    )
    assert create.status_code == 201, create.text
    return create.json()["data"]["id"]


async def _set_catalog_status(catalog_id: str, status: str, knowledge_status: str):
    async with async_session_factory() as db:
        result = await db.execute(select(CourseCatalog).where(CourseCatalog.id == catalog_id))
        catalog = result.scalar_one()
        catalog.status = status
        catalog.knowledge_status = knowledge_status
        await db.commit()


async def _api_test_admin_upload_catalog_material(tmp_path, monkeypatch):
    await init_db()
    monkeypatch.setattr(
        "app.core.config.settings.COURSE_CATALOG_STORAGE_ROOT",
        str(tmp_path / "course_catalogs"),
    )
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            admin_headers = await _register_and_login(client, "admin")
            catalog_id = await _create_catalog(client, admin_headers)

            response = await client.post(
                f"/api/v1/admin/course-catalogs/{catalog_id}/materials/upload",
                headers=admin_headers,
                files={"file": ("intro.md", b"# Intro\nBinary tree", "text/markdown")},
            )

            assert response.status_code == 201, response.text
            data = response.json()["data"]
            assert data["filename"] == "intro.md"
            assert data["source_type"] == "file"
            assert data["status"] == "uploaded"
            assert data["file_size"] > 0
            assert data["chunk_count"] == 0
            assert "storage_uri" not in data

            expected_path = tmp_path / "course_catalogs" / catalog_id / data["id"] / "intro.md"
            assert expected_path.exists()
            assert expected_path.read_text(encoding="utf-8").startswith("# Intro")
    finally:
        await engine.dispose()


def test_admin_upload_catalog_material(tmp_path, monkeypatch):
    asyncio.run(_api_test_admin_upload_catalog_material(tmp_path, monkeypatch))


async def _api_test_admin_upload_rejects_unsupported_file(tmp_path, monkeypatch):
    await init_db()
    monkeypatch.setattr(
        "app.core.config.settings.COURSE_CATALOG_STORAGE_ROOT",
        str(tmp_path / "course_catalogs"),
    )
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            admin_headers = await _register_and_login(client, "admin")
            catalog_id = await _create_catalog(client, admin_headers)

            response = await client.post(
                f"/api/v1/admin/course-catalogs/{catalog_id}/materials/upload",
                headers=admin_headers,
                files={"file": ("slides.pptx", b"bad", "application/octet-stream")},
            )

            assert response.status_code == 400
            assert response.json()["detail"]["message"] == "不支持的资料类型"
    finally:
        await engine.dispose()


def test_admin_upload_rejects_unsupported_file(tmp_path, monkeypatch):
    asyncio.run(_api_test_admin_upload_rejects_unsupported_file(tmp_path, monkeypatch))


async def _api_test_ready_catalog_upload_keeps_status_ready(tmp_path, monkeypatch):
    await init_db()
    monkeypatch.setattr(
        "app.core.config.settings.COURSE_CATALOG_STORAGE_ROOT",
        str(tmp_path / "course_catalogs"),
    )
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            admin_headers = await _register_and_login(client, "admin")
            catalog_id = await _create_catalog(client, admin_headers, title="Ready Catalog")
            await _set_catalog_status(catalog_id, "ready", "ready")

            response = await client.post(
                f"/api/v1/admin/course-catalogs/{catalog_id}/materials/upload",
                headers=admin_headers,
                files={"file": ("delta.txt", b"new material", "text/plain")},
            )
            assert response.status_code == 201, response.text

            status_response = await client.get(
                f"/api/v1/admin/course-catalogs/{catalog_id}/knowledge-status",
                headers=admin_headers,
            )
            assert status_response.status_code == 200, status_response.text
            status_data = status_response.json()["data"]
            assert status_data["status"] == "ready"
            assert status_data["knowledge_status"] == "dirty"
    finally:
        await engine.dispose()


def test_ready_catalog_upload_keeps_status_ready(tmp_path, monkeypatch):
    asyncio.run(_api_test_ready_catalog_upload_keeps_status_ready(tmp_path, monkeypatch))
```

- [ ] **Step 2: Run upload tests to verify they fail**

Run from `../backend`:

```bash
pytest tests/test_course_catalog_ingestion.py::test_admin_upload_catalog_material tests/test_course_catalog_ingestion.py::test_admin_upload_rejects_unsupported_file tests/test_course_catalog_ingestion.py::test_ready_catalog_upload_keeps_status_ready -q
```

Expected: fails because `/materials/upload` does not exist and ready upload state is not implemented.

- [ ] **Step 3: Add upload imports and helpers**

Modify imports at the top of `../backend/app/api/v1/catalogs.py`:

```python
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
```

Add imports:

```python
from app.core.config import settings
```

Add helpers after `_catalog_item`:

```python
SUPPORTED_MATERIAL_SUFFIXES = {".txt", ".md", ".pdf"}


def _safe_filename(filename: str) -> str:
    name = Path(filename or "").name.strip()
    if not name or name in {".", ".."} or ".." in Path(name).parts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 40020, "message": "文件名不合法", "data": None},
        )
    return name


def _material_item(material: CourseCatalogMaterial, include_storage_uri: bool = False) -> dict:
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


def _state_after_material_added(catalog: CourseCatalog) -> tuple[str, str]:
    if catalog.status == "ready":
        return "ready", "dirty"
    return "draft", "draft"
```

- [ ] **Step 4: Implement upload endpoint**

Add this endpoint before existing `/materials` JSON registration:

```python
@router.post("/admin/course-catalogs/{catalog_id}/materials/upload", status_code=201)
async def admin_upload_catalog_material(
    catalog_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    catalog = await _get_admin_catalog_or_404(db, catalog_id)
    if catalog.status == "ingesting" or catalog.knowledge_status == "ingesting":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": 40911, "message": "课程资源库正在入库中", "data": None},
        )

    filename = _safe_filename(file.filename or "")
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_MATERIAL_SUFFIXES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 40021, "message": "不支持的资料类型", "data": None},
        )

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 40022, "message": "资料文件不能为空", "data": None},
        )
    if len(content) > settings.COURSE_CATALOG_MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"code": 41320, "message": "资料文件过大", "data": None},
        )

    material_id = uuid4().hex[:16]
    root = Path(settings.COURSE_CATALOG_STORAGE_ROOT)
    relative_path = Path("course_catalogs") / catalog.id / material_id / filename
    target_path = root / catalog.id / material_id / filename
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(content)

    next_status, next_knowledge_status = _state_after_material_added(catalog)
    catalog.status = next_status
    catalog.knowledge_status = next_knowledge_status
    catalog.last_error = None
    catalog.material_count = (catalog.material_count or 0) + 1

    material = CourseCatalogMaterial(
        id=material_id,
        catalog_id=catalog.id,
        filename=filename,
        source_type="file",
        storage_uri=relative_path.as_posix(),
        file_size=len(content),
        status="uploaded",
    )
    db.add(material)
    await db.flush()
    await db.refresh(material)

    return {"code": 201, "message": "created", "data": _material_item(material)}
```

- [ ] **Step 5: Fix existing material registration state and response**

Before `admin_create_catalog_material`, update `_catalog_item` to include the new response fields:

```python
        "last_ingestion_task_id": catalog.last_ingestion_task_id,
        "last_ingestion_status": catalog.last_ingestion_status,
        "chunk_count": catalog.chunk_count or 0,
        "last_error": catalog.last_error,
```

In `admin_create_catalog_material`, replace `.values(...)` with:

```python
        .values(
            material_count=CourseCatalog.material_count + 1,
            status="ready" if catalog.status == "ready" else "draft",
            knowledge_status="dirty" if catalog.status == "ready" else "draft",
            last_error=None,
        )
```

When creating the material, add:

```python
        file_size=0,
        status="uploaded",
```

Replace the manual response `data` object with:

```python
    return {"code": 201, "message": "created", "data": _material_item(material)}
```

In `admin_list_catalog_materials`, replace the manual list item mapping with:

```python
                _material_item(m) for m in materials
```

- [ ] **Step 6: Run upload and existing catalog tests**

Run from `../backend`:

```bash
pytest tests/test_course_catalog_ingestion.py tests/test_course_catalogs.py -q
```

Expected: tests pass. If `test_course_catalogs.py` still expects ready material registration to reset status to `draft`, update that expectation to `ready/dirty` because the old behavior breaks class binding.

- [ ] **Step 7: Commit upload API**

Run from `frontend`:

```bash
git add ../backend/app/api/v1/catalogs.py ../backend/tests/test_course_catalog_ingestion.py ../backend/tests/test_course_catalogs.py
git commit -m "新增课程资源库资料上传接口"
```

## Task 3: Async Ingestion Orchestration

**Files:**
- Modify: `../backend/app/api/v1/catalogs.py`
- Modify: `../backend/app/api/v1/tasks.py`
- Modify: `../backend/tests/test_course_catalog_ingestion.py`

- [ ] **Step 1: Add failing ingestion orchestration tests**

Append to `../backend/tests/test_course_catalog_ingestion.py`:

```python
from unittest.mock import AsyncMock, patch

from app.models.others import AsyncTask


async def _wait_for_task_status(client: AsyncClient, headers: dict, task_id: str, expected: set[str]):
    for _ in range(20):
        response = await client.get(f"/api/v1/tasks/{task_id}", headers=headers)
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        if data["status"] in expected:
            return data
        await asyncio.sleep(0.05)
    raise AssertionError(f"task {task_id} did not reach {expected}")


async def _get_catalog_status(client: AsyncClient, headers: dict, catalog_id: str) -> dict:
    response = await client.get(
        f"/api/v1/admin/course-catalogs/{catalog_id}/knowledge-status",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def _get_material_from_list(client: AsyncClient, headers: dict, catalog_id: str, material_id: str) -> dict:
    response = await client.get(
        f"/api/v1/admin/course-catalogs/{catalog_id}/materials",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    materials = response.json()["data"]["materials"]
    matches = [material for material in materials if material["id"] == material_id]
    assert matches, f"material {material_id} not found"
    return matches[0]


async def _api_test_start_catalog_ingestion_success(tmp_path, monkeypatch):
    await init_db()
    monkeypatch.setattr(
        "app.core.config.settings.COURSE_CATALOG_STORAGE_ROOT",
        str(tmp_path / "course_catalogs"),
    )
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            admin_headers = await _register_and_login(client, "admin")
            catalog_id = await _create_catalog(client, admin_headers)
            upload = await client.post(
                f"/api/v1/admin/course-catalogs/{catalog_id}/materials/upload",
                headers=admin_headers,
                files={"file": ("intro.md", b"# Intro", "text/markdown")},
            )
            material_id = upload.json()["data"]["id"]

            with patch("app.api.v1.catalogs.ingestion_agent_client.post_json", new_callable=AsyncMock) as mock_agent:
                mock_agent.return_value = {
                    "catalog_id": catalog_id,
                    "chunk_count": 2,
                    "materials": [
                        {
                            "storage_uri": f"course_catalogs/{catalog_id}/{material_id}/intro.md",
                            "status": "ingested",
                            "chunk_count": 2,
                            "error": None,
                        }
                    ],
                }
                response = await client.post(
                    f"/api/v1/admin/course-catalogs/{catalog_id}/ingestions",
                    headers=admin_headers,
                )
                assert response.status_code == 202, response.text
                task_id = response.json()["data"]["task_id"]

            task_data = await _wait_for_task_status(client, admin_headers, task_id, {"completed"})
            assert task_data["task_type"] == "course_catalog_ingestion"
            assert task_data["status"] == "completed"
            assert task_data["result"]["catalog_id"] == catalog_id
            assert task_data["result"]["chunk_count"] == 2

            status_data = await _get_catalog_status(client, admin_headers, catalog_id)
            material = await _get_material_from_list(client, admin_headers, catalog_id, material_id)
            assert status_data["status"] == "ready"
            assert status_data["knowledge_status"] == "ready"
            assert status_data["chunk_count"] == 2
            assert status_data["last_ingestion_task_id"] == task_id
            assert material["status"] == "ingested"
            assert material["chunk_count"] == 2
            assert material["ingested_at"] is not None
    finally:
        await engine.dispose()


def test_start_catalog_ingestion_success(tmp_path, monkeypatch):
    asyncio.run(_api_test_start_catalog_ingestion_success(tmp_path, monkeypatch))


async def _api_test_start_catalog_ingestion_without_uploaded_materials_returns_409():
    await init_db()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            admin_headers = await _register_and_login(client, "admin")
            catalog_id = await _create_catalog(client, admin_headers)

            response = await client.post(
                f"/api/v1/admin/course-catalogs/{catalog_id}/ingestions",
                headers=admin_headers,
            )

            assert response.status_code == 409
            assert response.json()["detail"]["message"] == "没有待入库资料"
    finally:
        await engine.dispose()


def test_start_catalog_ingestion_without_uploaded_materials_returns_409():
    asyncio.run(_api_test_start_catalog_ingestion_without_uploaded_materials_returns_409())


async def _api_test_incremental_ingestion_partial_failure_keeps_catalog_ready(tmp_path, monkeypatch):
    await init_db()
    monkeypatch.setattr(
        "app.core.config.settings.COURSE_CATALOG_STORAGE_ROOT",
        str(tmp_path / "course_catalogs"),
    )
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            admin_headers = await _register_and_login(client, "admin")
            catalog_id = await _create_catalog(client, admin_headers, title="Incremental Catalog")
            await _set_catalog_status(catalog_id, "ready", "ready")
            upload = await client.post(
                f"/api/v1/admin/course-catalogs/{catalog_id}/materials/upload",
                headers=admin_headers,
                files={"file": ("delta.md", b"# Delta", "text/markdown")},
            )
            material_id = upload.json()["data"]["id"]

            with patch("app.api.v1.catalogs.ingestion_agent_client.post_json", new_callable=AsyncMock) as mock_agent:
                mock_agent.return_value = {
                    "catalog_id": catalog_id,
                    "chunk_count": 0,
                    "materials": [
                        {
                            "storage_uri": f"course_catalogs/{catalog_id}/{material_id}/delta.md",
                            "status": "failed",
                            "chunk_count": 0,
                            "error": "embedding failed",
                        }
                    ],
                }
                response = await client.post(
                    f"/api/v1/admin/course-catalogs/{catalog_id}/ingestions",
                    headers=admin_headers,
                )
                assert response.status_code == 202, response.text
                task_id = response.json()["data"]["task_id"]

            task_data = await _wait_for_task_status(client, admin_headers, task_id, {"failed"})
            assert task_data["status"] == "failed"
            assert task_data["error_code"] == "material_ingestion_failed"

            status_data = await _get_catalog_status(client, admin_headers, catalog_id)
            material = await _get_material_from_list(client, admin_headers, catalog_id, material_id)
            assert status_data["status"] == "ready"
            assert status_data["knowledge_status"] == "partial"
            assert status_data["last_error"] == "embedding failed"
            assert material["status"] == "failed"
            assert material["last_error"] == "embedding failed"
    finally:
        await engine.dispose()


def test_incremental_ingestion_partial_failure_keeps_catalog_ready(tmp_path, monkeypatch):
    asyncio.run(_api_test_incremental_ingestion_partial_failure_keeps_catalog_ready(tmp_path, monkeypatch))


async def _api_test_first_ingestion_partial_success_marks_catalog_ready_partial(tmp_path, monkeypatch):
    await init_db()
    monkeypatch.setattr(
        "app.core.config.settings.COURSE_CATALOG_STORAGE_ROOT",
        str(tmp_path / "course_catalogs"),
    )
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            admin_headers = await _register_and_login(client, "admin")
            catalog_id = await _create_catalog(client, admin_headers, title="First Partial Catalog")
            upload_ok = await client.post(
                f"/api/v1/admin/course-catalogs/{catalog_id}/materials/upload",
                headers=admin_headers,
                files={"file": ("ok.md", b"# OK", "text/markdown")},
            )
            upload_fail = await client.post(
                f"/api/v1/admin/course-catalogs/{catalog_id}/materials/upload",
                headers=admin_headers,
                files={"file": ("bad.md", b"# BAD", "text/markdown")},
            )
            ok_material_id = upload_ok.json()["data"]["id"]
            fail_material_id = upload_fail.json()["data"]["id"]

            with patch("app.api.v1.catalogs.ingestion_agent_client.post_json", new_callable=AsyncMock) as mock_agent:
                mock_agent.return_value = {
                    "catalog_id": catalog_id,
                    "chunk_count": 4,
                    "materials": [
                        {
                            "storage_uri": f"course_catalogs/{catalog_id}/{ok_material_id}/ok.md",
                            "status": "ingested",
                            "chunk_count": 4,
                            "error": None,
                        },
                        {
                            "storage_uri": f"course_catalogs/{catalog_id}/{fail_material_id}/bad.md",
                            "status": "failed",
                            "chunk_count": 0,
                            "error": "parse failed",
                        },
                    ],
                }
                response = await client.post(
                    f"/api/v1/admin/course-catalogs/{catalog_id}/ingestions",
                    headers=admin_headers,
                )
                assert response.status_code == 202, response.text
                task_id = response.json()["data"]["task_id"]

            task_data = await _wait_for_task_status(client, admin_headers, task_id, {"failed"})
            assert task_data["status"] == "failed"
            assert task_data["error_code"] == "material_ingestion_failed"

            status_data = await _get_catalog_status(client, admin_headers, catalog_id)
            ok_material = await _get_material_from_list(client, admin_headers, catalog_id, ok_material_id)
            fail_material = await _get_material_from_list(client, admin_headers, catalog_id, fail_material_id)
            assert status_data["status"] == "ready"
            assert status_data["knowledge_status"] == "partial"
            assert status_data["chunk_count"] == 4
            assert status_data["last_error"] == "parse failed"
            assert ok_material["status"] == "ingested"
            assert fail_material["status"] == "failed"
    finally:
        await engine.dispose()


def test_first_ingestion_partial_success_marks_catalog_ready_partial(tmp_path, monkeypatch):
    asyncio.run(_api_test_first_ingestion_partial_success_marks_catalog_ready_partial(tmp_path, monkeypatch))
```

- [ ] **Step 2: Run ingestion tests to verify they fail**

Run from `../backend`:

```bash
pytest tests/test_course_catalog_ingestion.py::test_start_catalog_ingestion_success tests/test_course_catalog_ingestion.py::test_start_catalog_ingestion_without_uploaded_materials_returns_409 tests/test_course_catalog_ingestion.py::test_incremental_ingestion_partial_failure_keeps_catalog_ready tests/test_course_catalog_ingestion.py::test_first_ingestion_partial_success_marks_catalog_ready_partial -q
```

Expected: fails because ingestion endpoint and task permission are missing.

- [ ] **Step 3: Add async orchestration imports**

Modify `../backend/app/api/v1/catalogs.py` imports:

```python
import asyncio
import logging
from datetime import datetime, timezone
```

Add imports:

```python
from app.db.session import async_session_factory
from app.models.others import AsyncTask
from app.services.agent_client import AgentClient, AgentServiceError
```

Add logger after router:

```python
logger = logging.getLogger(__name__)
ingestion_agent_client = AgentClient(timeout=300.0)
```

- [ ] **Step 4: Add ingestion helper functions**

Add to `../backend/app/api/v1/catalogs.py` after `_state_after_material_added`:

```python
def _is_initial_ingestion(catalog: CourseCatalog) -> bool:
    return catalog.status != "ready"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


async def _run_catalog_ingestion_background(task_id: str) -> None:
    async with async_session_factory() as db:
        task = None
        try:
            result = await db.execute(
                select(AsyncTask).where(AsyncTask.id == task_id, AsyncTask.is_deleted == False)
            )
            task = result.scalar_one_or_none()
            if task is None:
                logger.error("Course catalog ingestion background: missing task_id=%s", task_id)
                return

            task_context = task.result or {}
            catalog_id = task_context.get("catalog_id")
            material_ids = task_context.get("material_ids") or []
            initial = bool(task_context.get("initial"))

            catalog_result = await db.execute(
                select(CourseCatalog).where(
                    CourseCatalog.id == catalog_id,
                    CourseCatalog.is_deleted == False,
                )
            )
            catalog = catalog_result.scalar_one_or_none()
            if catalog is None:
                task.status = "failed"
                task.progress = 100
                task.error_code = "catalog_not_found"
                task.error_message = "课程资源库不存在"
                task.completed_at = _now_utc()
                await db.commit()
                return

            material_result = await db.execute(
                select(CourseCatalogMaterial).where(
                    CourseCatalogMaterial.id.in_(material_ids),
                    CourseCatalogMaterial.catalog_id == catalog.id,
                    CourseCatalogMaterial.is_deleted == False,
                )
            )
            materials = material_result.scalars().all()
            payload = {
                "catalog_id": catalog.id,
                "materials": [{"storage_uri": material.storage_uri or ""} for material in materials],
            }

            try:
                agent_data = await ingestion_agent_client.post_json("/agent/v1/knowledge/ingestions", payload)
            except AgentServiceError as exc:
                for material in materials:
                    material.status = "failed"
                    material.last_error = exc.message
                catalog.status = "failed" if initial else "ready"
                catalog.knowledge_status = "failed" if initial else "partial"
                catalog.last_ingestion_status = "failed"
                catalog.last_error = exc.message
                task.status = "failed"
                task.progress = 100
                task.error_code = "agent_ingestion_failed"
                task.error_message = exc.message
                task.completed_at = _now_utc()
                task.result = {**task_context, "agent_error": exc.message}
                await db.commit()
                return

            results_by_uri = {
                item.get("storage_uri"): item
                for item in (agent_data.get("materials") or [])
                if item.get("storage_uri")
            }
            failed_errors: list[str] = []
            total_chunks = 0
            completed_at = _now_utc()

            for material in materials:
                item = results_by_uri.get(material.storage_uri or "")
                if item and item.get("status") == "ingested":
                    chunk_count = int(item.get("chunk_count") or 0)
                    material.status = "ingested"
                    material.chunk_count = chunk_count
                    material.ingested_at = completed_at
                    material.last_error = None
                    total_chunks += chunk_count
                else:
                    error = (item or {}).get("error") or "资料入库失败"
                    material.status = "failed"
                    material.last_error = error
                    failed_errors.append(error)

            agent_chunks = agent_data.get("chunk_count")
            added_chunks = int(agent_chunks) if agent_chunks is not None else total_chunks
            if added_chunks > 0:
                catalog.chunk_count = (catalog.chunk_count or 0) + added_chunks

            if failed_errors:
                has_ingested_chunks = total_chunks > 0
                if initial and not has_ingested_chunks:
                    catalog.status = "failed"
                    catalog.knowledge_status = "failed"
                else:
                    catalog.status = "ready"
                    catalog.knowledge_status = "partial"
                catalog.last_ingestion_status = "failed"
                catalog.last_error = failed_errors[0]
                task.status = "failed"
                task.error_code = "material_ingestion_failed"
                task.error_message = failed_errors[0]
            else:
                catalog.status = "ready"
                catalog.knowledge_status = "ready"
                catalog.last_ingestion_status = "completed"
                catalog.last_error = None
                task.status = "completed"
                task.error_code = None
                task.error_message = ""

            task.progress = 100
            task.completed_at = completed_at
            task.result = {**task_context, **agent_data}
            await db.commit()
        except Exception as exc:
            logger.exception(
                "Course catalog ingestion background: unexpected error task_id=%s",
                task_id,
            )
            if task is not None:
                task.status = "failed"
                task.progress = 100
                task.error_code = "unexpected_error"
                task.error_message = str(exc)[:500]
                task.completed_at = _now_utc()
                await db.commit()
```

- [ ] **Step 5: Add ingestion endpoint**

Add to `../backend/app/api/v1/catalogs.py` before `list_ready_course_catalogs`:

```python
@router.post("/admin/course-catalogs/{catalog_id}/ingestions", status_code=202)
async def admin_start_catalog_ingestion(
    catalog_id: str,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    catalog = await _get_admin_catalog_or_404(db, catalog_id)
    if catalog.status == "ingesting" or catalog.knowledge_status == "ingesting":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": 40911, "message": "课程资源库正在入库中", "data": None},
        )

    result = await db.execute(
        select(CourseCatalogMaterial).where(
            CourseCatalogMaterial.catalog_id == catalog.id,
            CourseCatalogMaterial.is_deleted == False,
            CourseCatalogMaterial.status.in_(["uploaded", "failed"]),
        )
    )
    materials = result.scalars().all()
    if not materials:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": 40912, "message": "没有待入库资料", "data": None},
        )

    initial = _is_initial_ingestion(catalog)
    if initial:
        catalog.status = "ingesting"
    else:
        catalog.status = "ready"
    catalog.knowledge_status = "ingesting"
    catalog.last_error = None
    for material in materials:
        material.status = "ingesting"
        material.last_error = None

    task = AsyncTask(
        task_type="course_catalog_ingestion",
        status="processing",
        progress=10,
        user_id=current_user.id,
        result={
            "catalog_id": catalog.id,
            "material_ids": [material.id for material in materials],
            "storage_uris": [material.storage_uri for material in materials],
            "initial": initial,
        },
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)
    catalog.last_ingestion_task_id = task.id
    catalog.last_ingestion_status = "processing"
    await db.commit()

    asyncio.create_task(_run_catalog_ingestion_background(task.id))

    return {
        "code": 202,
        "message": "accepted",
        "data": {"task_id": task.id, "catalog_id": catalog.id, "status": "processing"},
    }
```

- [ ] **Step 6: Extend knowledge status response**

In `admin_get_catalog_knowledge_status`, before `return`, add:

```python
    pending_count = (
        await db.execute(
            select(func.count())
            .select_from(CourseCatalogMaterial)
            .where(
                CourseCatalogMaterial.catalog_id == catalog.id,
                CourseCatalogMaterial.is_deleted == False,
                CourseCatalogMaterial.status == "uploaded",
            )
        )
    ).scalar() or 0
    failed_count = (
        await db.execute(
            select(func.count())
            .select_from(CourseCatalogMaterial)
            .where(
                CourseCatalogMaterial.catalog_id == catalog.id,
                CourseCatalogMaterial.is_deleted == False,
                CourseCatalogMaterial.status == "failed",
            )
        )
    ).scalar() or 0
```

Extend the `data` object:

```python
            "chunk_count": catalog.chunk_count or 0,
            "pending_material_count": pending_count,
            "failed_material_count": failed_count,
            "last_ingestion_task_id": catalog.last_ingestion_task_id,
            "last_ingestion_status": catalog.last_ingestion_status,
            "last_error": catalog.last_error,
```

- [ ] **Step 7: Allow admin task polling**

Modify `../backend/app/api/v1/tasks.py` permission block:

```python
    if task.user_id and task.user_id != current_user.id:
        allowed_teacher_task = current_user.role == "teacher" and task.task_type == "resource_generation"
        allowed_admin_task = current_user.role == "admin" and task.task_type == "course_catalog_ingestion"
        if not (allowed_teacher_task or allowed_admin_task):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": 40400, "message": "任务不存在", "data": None},
            )
```

- [ ] **Step 8: Run ingestion tests**

Run from `../backend`:

```bash
pytest tests/test_course_catalog_ingestion.py tests/test_course_catalogs.py -q
```

Expected: all tests pass.

- [ ] **Step 9: Commit ingestion orchestration**

Run from `frontend`:

```bash
git add ../backend/app/api/v1/catalogs.py ../backend/app/api/v1/tasks.py ../backend/tests/test_course_catalog_ingestion.py
git commit -m "接入课程资源库知识入库后台任务"
```

## Task 4: OpenAPI Contract

**Files:**
- Modify: `../docs/10-client-api/Client-API.openapi.json`

- [ ] **Step 1: Add upload path**

In `../docs/10-client-api/Client-API.openapi.json`, add this path near existing `/admin/course-catalogs/{catalog_id}/materials`:

```json
    "/admin/course-catalogs/{catalog_id}/materials/upload": {
      "post": {
        "tags": ["CourseCatalogs"],
        "summary": "上传课程资源库资料",
        "parameters": [
          {
            "name": "catalog_id",
            "in": "path",
            "required": true,
            "schema": {"type": "string"}
          }
        ],
        "requestBody": {
          "required": true,
          "content": {
            "multipart/form-data": {
              "schema": {
                "type": "object",
                "required": ["file"],
                "properties": {
                  "file": {"type": "string", "format": "binary"}
                }
              }
            }
          }
        },
        "responses": {
          "201": {
            "description": "已创建",
            "content": {
              "application/json": {
                "schema": {"$ref": "#/components/schemas/CourseCatalogMaterialResponse"}
              }
            }
          },
          "400": {"description": "文件名、类型或内容非法"},
          "409": {"description": "课程资源库正在入库中"},
          "413": {"description": "资料文件过大"}
        },
        "security": [{"bearerAuth": []}]
      }
    },
```

- [ ] **Step 2: Add ingestion path**

Add this path near the upload path:

```json
    "/admin/course-catalogs/{catalog_id}/ingestions": {
      "post": {
        "tags": ["CourseCatalogs"],
        "summary": "触发课程资源库知识入库",
        "parameters": [
          {
            "name": "catalog_id",
            "in": "path",
            "required": true,
            "schema": {"type": "string"}
          }
        ],
        "responses": {
          "202": {
            "description": "已接受",
            "content": {
              "application/json": {
                "schema": {"$ref": "#/components/schemas/CourseCatalogIngestionResponse"}
              }
            }
          },
          "409": {"description": "正在入库或没有待入库资料"}
        },
        "security": [{"bearerAuth": []}]
      }
    },
```

- [ ] **Step 3: Extend CourseCatalog schemas**

Update `CourseCatalogItem.knowledge_status.enum` to include:

```json
              "dirty",
              "partial",
```

Add these properties to `CourseCatalogItem`:

```json
          "last_ingestion_task_id": {"type": "string", "nullable": true},
          "last_ingestion_status": {"type": "string", "nullable": true},
          "chunk_count": {"type": "integer"},
          "last_error": {"type": "string", "nullable": true},
```

Extend `CourseCatalogMaterialItem.properties` with:

```json
          "file_size": {"type": "integer"},
          "chunk_count": {"type": "integer"},
          "last_error": {"type": "string", "nullable": true},
          "ingested_at": {"type": "string", "nullable": true, "format": "date-time"},
```

Extend `CourseCatalogKnowledgeStatusResponse.data.properties` with:

```json
              "chunk_count": {"type": "integer"},
              "pending_material_count": {"type": "integer"},
              "failed_material_count": {"type": "integer"},
              "last_ingestion_task_id": {"type": "string", "nullable": true},
              "last_ingestion_status": {"type": "string", "nullable": true},
              "last_error": {"type": "string", "nullable": true}
```

Add `CourseCatalogIngestionResponse` under `components.schemas`:

```json
      "CourseCatalogIngestionResponse": {
        "type": "object",
        "properties": {
          "code": {"type": "integer"},
          "message": {"type": "string"},
          "data": {
            "type": "object",
            "properties": {
              "task_id": {"type": "string"},
              "catalog_id": {"type": "string"},
              "status": {"type": "string"}
            }
          }
        }
      }
```

- [ ] **Step 4: Validate OpenAPI JSON**

Run from `frontend`:

```bash
python -m json.tool ../docs/10-client-api/Client-API.openapi.json >/tmp/client-api-openapi-check.json
```

Expected: exits 0.

- [ ] **Step 5: Commit OpenAPI**

Run from `frontend`:

```bash
git add ../docs/10-client-api/Client-API.openapi.json
git commit -m "更新课程资源库入库接口契约"
```

## Task 5: Workflow and Final Verification

**Files:**
- Modify: `WORKFLOW.md`

- [ ] **Step 1: Run focused Backend verification**

Run from `../backend`:

```bash
pytest tests/test_course_catalog_ingestion.py tests/test_course_catalogs.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Validate OpenAPI**

Run from `frontend`:

```bash
python -m json.tool ../docs/10-client-api/Client-API.openapi.json >/tmp/client-api-openapi-check.json
```

Expected: exits 0.

- [ ] **Step 3: Run diff whitespace check for touched files**

Run from `frontend`:

```bash
git diff --check -- ../backend/app/core/config.py ../backend/app/models/catalog.py ../backend/app/schemas/catalog.py ../backend/app/api/v1/catalogs.py ../backend/app/api/v1/tasks.py ../backend/tests/test_course_catalog_ingestion.py ../backend/tests/test_course_catalogs.py ../docs/10-client-api/Client-API.openapi.json WORKFLOW.md
```

Expected: exits 0.

- [ ] **Step 4: Update WORKFLOW.md**

Append a new entry under `最近验证`:

```markdown
- 2026-06-08：Phase B1 CourseCatalog 后端入库编排完成：
  - Backend 支持管理员上传 `.txt` / `.md` / `.pdf` 资料到受控本地共享目录，数据库仅保存相对 `storage_uri`。
  - 新增 `POST /admin/course-catalogs/{catalog_id}/ingestions`，立即返回 `202 + task_id`，后台任务调用 Agent Service `/agent/v1/knowledge/ingestions`。
  - 入库结果按 `storage_uri` 回写 `CourseCatalogMaterial`，并同步更新 `CourseCatalog.status`、`knowledge_status`、`AsyncTask.status`。
  - 状态语义：`status` 控制教学班是否可绑定，`knowledge_status` 控制知识库质量；ready 资源库新增资料保持 `status=ready` 并标记 `dirty`，增量失败标记 `partial`。
  - 验证：`pytest tests/test_course_catalog_ingestion.py tests/test_course_catalogs.py -q` 通过；`python -m json.tool ../docs/10-client-api/Client-API.openapi.json >/tmp/client-api-openapi-check.json` 通过；相关文件 `git diff --check` 通过。
  - 契约状态：Client API 已同步；Agent API 使用既有知识入库接口，无新增 Agent 契约；AdminConsole 上传/触发入库 UI 进入后续切片。
```

- [ ] **Step 5: Commit workflow**

Run from `frontend`:

```bash
git add WORKFLOW.md
git commit -m "记录课程资源库入库后端编排进度"
```

## Self-Review Checklist

- [ ] Spec coverage: model/config, upload, async ingestion, `storage_uri` mapping, `AsyncTask.result` catalog context, task polling permission, OpenAPI, workflow.
- [ ] No placeholders: every step includes concrete files, commands, code, and expected outcome.
- [ ] Type consistency: `uploaded`, `ingesting`, `ingested`, `failed`, `dirty`, `partial` names match the approved spec.
- [ ] Scope discipline: no AdminConsole UI, no Agent webhook, no student/teacher CourseCatalog consumption changes.
- [ ] Contract discipline: Client API changes are limited to Backend-facing admin endpoints; Agent API is reused as-is.

## Execution Handoff

Plan complete. Recommended execution mode is Subagent-Driven because tasks are separable and each task has focused tests:

1. Task 1: model/config/schema/migration.
2. Task 2: upload endpoint.
3. Task 3: async ingestion orchestration.
4. Task 4: OpenAPI.
5. Task 5: workflow and final verification.
