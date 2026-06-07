# CourseCatalog Knowledge Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Phase B1 CourseCatalog upload and real knowledge ingestion loop: admin uploads `.txt/.md/.pdf`, Backend stores metadata and files, Agent Service ingests into Qdrant using `CourseCatalog.id`, and AdminConsole can start and observe ingestion.

**Architecture:** Backend owns admin-facing API, local file storage, SQL state, and AsyncTask status. Agent Service owns parsing, chunking, embedding, and Qdrant upsert through a new HTTP API that reuses the existing ingestion core. Frontend only talks to Backend and shows upload/material/ingestion state.

**Tech Stack:** FastAPI, SQLAlchemy async, MySQL `duagent_test`, httpx, Agent Service FastAPI, AgentScope readers, Qdrant, React/Vite, existing OpenAPI JSON.

---

## File Structure

Agent Service:

- Modify `../agent_service/memory/course_knowledge_ingestion.py`: allow caller-provided `course_id` so directory name does not become the Qdrant course ID.
- Modify `../agent_service/tools/ingest_knowledge.py`: pass optional `course_id` through to the ingestion function while keeping CLI behavior unchanged.
- Create `../agent_service/schemas/knowledge.py`: request/response schemas for ingestion.
- Create `../agent_service/api/v1/knowledge.py`: `POST /agent/v1/knowledge/ingestions`.
- Modify `../agent_service/api/v1/router.py`: include the knowledge router.
- Test `../agent_service/tests/test_knowledge_ingestion_api.py`: path safety, request validation, success response, `catalog_id` as Qdrant course ID.

Backend:

- Modify `../backend/app/models/catalog.py`: add material metadata and ingestion status fields.
- Modify `../backend/migrations/2026-06-07-add-course-catalogs.sql`: add the new material/catalog columns for fresh environments.
- Create `../backend/migrations/2026-06-07-extend-course-catalog-ingestion.sql`: alter existing Phase A tables for current databases.
- Modify `../backend/app/core/config.py`: add local storage root and upload size setting.
- Modify `../backend/app/schemas/catalog.py`: add upload/material/status/ingestion response schemas.
- Modify `../backend/app/api/v1/catalogs.py`: add upload endpoint, ingestion endpoint, expanded material list and status responses.
- Test `../backend/tests/test_course_catalog_ingestion.py`: upload, status transitions, Agent success/failure, security.

OpenAPI and frontend:

- Modify `../docs/10-client-api/Client-API.openapi.json`: add upload/ingestion paths and expanded schemas.
- Modify `src/api/services/admin.js`: add upload/start ingestion service calls.
- Modify `src/pages/AdminConsole.jsx`: add material management panel, upload control, ingestion button, status messages.
- Modify `WORKFLOW.md`: record Phase B1 progress and verification.

## Task 1: Agent ingestion API

**Files:**
- Modify: `../agent_service/memory/course_knowledge_ingestion.py`
- Modify: `../agent_service/tools/ingest_knowledge.py`
- Create: `../agent_service/schemas/knowledge.py`
- Create: `../agent_service/api/v1/knowledge.py`
- Modify: `../agent_service/api/v1/router.py`
- Test: `../agent_service/tests/test_knowledge_ingestion_api.py`

- [ ] **Step 1: Write failing Agent API tests**

Create `../agent_service/tests/test_knowledge_ingestion_api.py`:

```python
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent_service.main import app


def test_knowledge_ingestion_rejects_path_traversal(monkeypatch, tmp_path):
    monkeypatch.setenv("COURSE_CATALOG_STORAGE_ROOT", str(tmp_path))
    client = TestClient(app)

    response = client.post(
        "/agent/v1/knowledge/ingestions",
        json={
            "catalog_id": "catalog-1",
            "materials": [
                {
                    "material_id": "mat-1",
                    "storage_uri": "../secret.md",
                    "filename": "secret.md",
                }
            ],
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["code"] == 400
    assert "storage_uri" in body["message"]


def test_knowledge_ingestion_uses_catalog_id_as_course_id(monkeypatch, tmp_path):
    root = tmp_path / "course_catalogs"
    material_dir = root / "catalog-1" / "mat-1"
    material_dir.mkdir(parents=True)
    material_path = material_dir / "intro.md"
    material_path.write_text("# Intro\n\nBinary tree basics.", encoding="utf-8")
    monkeypatch.setenv("COURSE_CATALOG_STORAGE_ROOT", str(root))

    captured = {}

    async def fake_ingest_course_knowledge(path, *, course_id=None, **kwargs):
        captured["path"] = Path(path)
        captured["course_id"] = course_id

        class Result:
            chunk_count = 3
            duration_seconds = 0.5

        return Result()

    monkeypatch.setattr(
        "agent_service.api.v1.knowledge.ingest_course_knowledge",
        fake_ingest_course_knowledge,
    )

    client = TestClient(app)
    response = client.post(
        "/agent/v1/knowledge/ingestions",
        json={
            "catalog_id": "catalog-1",
            "materials": [
                {
                    "material_id": "mat-1",
                    "storage_uri": "course_catalogs/catalog-1/mat-1/intro.md",
                    "filename": "intro.md",
                }
            ],
        },
    )

    assert response.status_code == 202
    body = response.json()
    assert body["code"] == 202
    assert body["data"]["catalog_id"] == "catalog-1"
    assert body["data"]["chunk_count"] == 3
    assert body["data"]["materials"][0]["status"] == "ingested"
    assert captured["course_id"] == "catalog-1"
    assert captured["path"] == material_path
```

- [ ] **Step 2: Run the Agent API tests and verify they fail**

Run from `../agent_service`:

```bash
pytest tests/test_knowledge_ingestion_api.py -q
```

Expected: fail because `agent_service.api.v1.knowledge` and `/agent/v1/knowledge/ingestions` do not exist.

- [ ] **Step 3: Add Agent schemas**

Create `../agent_service/schemas/knowledge.py`:

```python
from pydantic import BaseModel, Field


class KnowledgeIngestionMaterial(BaseModel):
    material_id: str = Field(..., min_length=1)
    storage_uri: str = Field(..., min_length=1)
    filename: str = Field(..., min_length=1)


class KnowledgeIngestionRequest(BaseModel):
    catalog_id: str = Field(..., min_length=1)
    materials: list[KnowledgeIngestionMaterial] = Field(..., min_length=1)


class KnowledgeIngestionMaterialResult(BaseModel):
    material_id: str
    status: str
    chunk_count: int = 0
    error: str | None = None


class KnowledgeIngestionResultData(BaseModel):
    catalog_id: str
    chunk_count: int
    materials: list[KnowledgeIngestionMaterialResult]
    duration_seconds: float


class KnowledgeIngestionAcceptedResponse(BaseModel):
    code: int = 202
    message: str = "accepted"
    data: KnowledgeIngestionResultData
```

- [ ] **Step 4: Let ingestion accept explicit course_id**

Modify `../agent_service/memory/course_knowledge_ingestion.py` signatures and calls:

```python
async def load_course_knowledge_chunks(
    course_dir: Path | str,
    *,
    reader: AgentScopeReader | None = None,
    ingested_files: set[str] | None = None,
    course_id: str | None = None,
) -> list[CourseKnowledgeChunk]:
    root = Path(course_dir)
    if not root.exists():
        raise ValueError(f"course path does not exist: {root}")

    resolved_course_id = course_id or (root.stem if root.is_file() else root.name)
    source_root = root.parent if root.is_file() else root
    skipped_files = ingested_files or set()
    chunks: list[CourseKnowledgeChunk] = []
    for source_path in _iter_supported_sources(root):
        if not source_path.is_file() or source_path.suffix.lower() not in {".md", ".txt", ".pdf"}:
            continue
        relative_path = source_path.relative_to(source_root).as_posix()
        if relative_path in skipped_files:
            continue
        file_reader = reader or _build_reader_for_file(source_path)
        documents = await file_reader(str(source_path))
        chunks.extend(
            _documents_to_chunks(
                course_id=resolved_course_id,
                root=source_root,
                source_path=source_path,
                documents=documents,
            )
        )
    return chunks
```

Modify `../agent_service/tools/ingest_knowledge.py`:

```python
async def ingest_course_knowledge(
    course_dir: Path | str,
    *,
    course_id: str | None = None,
    embedding_provider: EmbeddingProvider | None = None,
    store: QdrantCourseKnowledgeStore | None = None,
    chunk_loader: ChunkLoader | None = None,
) -> KnowledgeIngestionResult:
    start_time = time.time()
    root = Path(course_dir)
    resolved_course_id = course_id or (root.stem if root.suffix else root.name)
    target_store = store or QdrantCourseKnowledgeStore()

    logger.debug(f"Checking previously ingested files for course_id: {resolved_course_id}")
    ingested_files = await target_store.list_ingested_source_files(resolved_course_id)

    loader = chunk_loader or load_course_knowledge_chunks
    logger.debug(f"Loading chunks from: {root}")
    chunks = await loader(root, ingested_files=ingested_files, course_id=resolved_course_id)
    if not chunks:
        duration = time.time() - start_time
        return KnowledgeIngestionResult(course_id=resolved_course_id, chunk_count=0, duration_seconds=duration)

    provider = embedding_provider or get_ai_providers().embedding
    vectors = await _embed_texts_in_batches(
        provider,
        [chunk.content for chunk in chunks],
        batch_size=_EMBEDDING_BATCH_SIZE,
    )
    await target_store.upsert_chunks(chunks=chunks, vectors=vectors)

    duration = time.time() - start_time
    return KnowledgeIngestionResult(course_id=resolved_course_id, chunk_count=len(chunks), duration_seconds=duration)
```

- [ ] **Step 5: Add Agent API route**

Create `../agent_service/api/v1/knowledge.py`:

```python
from pathlib import Path
from time import perf_counter

from fastapi import APIRouter, HTTPException, status

from agent_service.schemas.knowledge import (
    KnowledgeIngestionAcceptedResponse,
    KnowledgeIngestionMaterialResult,
    KnowledgeIngestionRequest,
    KnowledgeIngestionResultData,
)
from agent_service.tools.ingest_knowledge import ingest_course_knowledge

router = APIRouter(prefix="/knowledge", tags=["Knowledge"])

SUPPORTED_SUFFIXES = {".txt", ".md", ".pdf"}


def _storage_root() -> Path:
    from os import getenv

    return Path(getenv("COURSE_CATALOG_STORAGE_ROOT", "storage/course_catalogs")).resolve()


def _resolve_storage_uri(storage_uri: str) -> Path:
    root = _storage_root()
    if storage_uri.startswith("/") or ".." in Path(storage_uri).parts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 400, "message": "storage_uri 必须是共享目录内的相对路径", "data": None},
        )
    relative = Path(storage_uri)
    if relative.parts and relative.parts[0] == root.name:
        relative = Path(*relative.parts[1:])
    target = (root / relative).resolve()
    if root != target and root not in target.parents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 400, "message": "storage_uri 超出共享目录", "data": None},
        )
    return target


@router.post(
    "/ingestions",
    response_model=KnowledgeIngestionAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_knowledge_ingestion(
    request: KnowledgeIngestionRequest,
) -> KnowledgeIngestionAcceptedResponse:
    started = perf_counter()
    results: list[KnowledgeIngestionMaterialResult] = []
    total_chunks = 0

    for material in request.materials:
        path = _resolve_storage_uri(material.storage_uri)
        if not path.exists() or not path.is_file():
            results.append(
                KnowledgeIngestionMaterialResult(
                    material_id=material.material_id,
                    status="failed",
                    chunk_count=0,
                    error="资料文件不存在",
                )
            )
            continue
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            results.append(
                KnowledgeIngestionMaterialResult(
                    material_id=material.material_id,
                    status="failed",
                    chunk_count=0,
                    error="不支持的资料类型",
                )
            )
            continue

        try:
            result = await ingest_course_knowledge(path, course_id=request.catalog_id)
        except Exception as exc:
            results.append(
                KnowledgeIngestionMaterialResult(
                    material_id=material.material_id,
                    status="failed",
                    chunk_count=0,
                    error=str(exc),
                )
            )
            continue

        total_chunks += result.chunk_count
        results.append(
            KnowledgeIngestionMaterialResult(
                material_id=material.material_id,
                status="ingested",
                chunk_count=result.chunk_count,
                error=None,
            )
        )

    return KnowledgeIngestionAcceptedResponse(
        data=KnowledgeIngestionResultData(
            catalog_id=request.catalog_id,
            chunk_count=total_chunks,
            materials=results,
            duration_seconds=perf_counter() - started,
        )
    )
```

Modify `../agent_service/api/v1/router.py`:

```python
from agent_service.api.v1 import assessment, evaluation, health, knowledge, learning_path, memory, profile, resources, tutoring

api_router.include_router(knowledge.router)
```

- [ ] **Step 6: Run Agent tests**

Run from `../agent_service`:

```bash
pytest tests/test_knowledge_ingestion_api.py tests/test_ingest_knowledge.py tests/test_course_knowledge_ingestion.py -q
```

Expected: all pass.

- [ ] **Step 7: Commit Agent API**

```bash
git add ../agent_service/memory/course_knowledge_ingestion.py ../agent_service/tools/ingest_knowledge.py ../agent_service/schemas/knowledge.py ../agent_service/api/v1/knowledge.py ../agent_service/api/v1/router.py ../agent_service/tests/test_knowledge_ingestion_api.py
git commit -m "新增智能体课程知识入库接口"
```

## Task 2: Backend schema, migration, and config

**Files:**
- Modify: `../backend/app/models/catalog.py`
- Modify: `../backend/app/schemas/catalog.py`
- Modify: `../backend/app/core/config.py`
- Modify: `../backend/migrations/2026-06-07-add-course-catalogs.sql`
- Create: `../backend/migrations/2026-06-07-extend-course-catalog-ingestion.sql`
- Test: `../backend/tests/test_course_catalog_ingestion.py`

- [ ] **Step 1: Write failing model/config tests**

Create `../backend/tests/test_course_catalog_ingestion.py` with initial assertions:

```python
from app.core.config import settings
from app.models.catalog import CourseCatalogMaterial


def test_course_catalog_material_has_ingestion_fields():
    columns = CourseCatalogMaterial.__table__.columns

    assert "storage_type" in columns
    assert "file_size" in columns
    assert "last_error" in columns
    assert "ingested_at" in columns
    assert "chunk_count" in columns


def test_course_catalog_storage_settings_exist():
    assert hasattr(settings, "COURSE_CATALOG_STORAGE_ROOT")
    assert hasattr(settings, "COURSE_CATALOG_MAX_UPLOAD_BYTES")
```

- [ ] **Step 2: Run tests and verify they fail**

Run from `../backend`:

```bash
pytest tests/test_course_catalog_ingestion.py -q
```

Expected: fail because fields/settings do not exist.

- [ ] **Step 3: Add Backend config**

Modify `../backend/app/core/config.py` settings class:

```python
COURSE_CATALOG_STORAGE_ROOT: str = "storage/course_catalogs"
COURSE_CATALOG_MAX_UPLOAD_BYTES: int = 20 * 1024 * 1024
```

- [ ] **Step 4: Extend catalog model**

Modify `../backend/app/models/catalog.py` imports:

```python
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, func
```

Extend `CourseCatalog`:

```python
last_ingestion_task_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
last_ingestion_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
chunk_count: Mapped[int] = mapped_column(Integer, default=0)
last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
```

Extend `CourseCatalogMaterial`:

```python
storage_type: Mapped[str] = mapped_column(String(20), nullable=False, default="local")
file_size: Mapped[int] = mapped_column(BigInteger, default=0)
last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
ingested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
chunk_count: Mapped[int] = mapped_column(Integer, default=0)
```

- [ ] **Step 5: Extend schemas**

Modify `../backend/app/schemas/catalog.py`:

```python
from datetime import datetime

from pydantic import BaseModel, Field


class CourseCatalogMaterialItem(BaseModel):
    id: str
    catalog_id: str
    filename: str
    source_type: str
    storage_type: str = "local"
    file_size: int = 0
    status: str
    chunk_count: int = 0
    last_error: str | None = None
    ingested_at: str | None = None
    created_at: str


class CourseCatalogIngestionAccepted(BaseModel):
    task_id: str
    catalog_id: str
    status: str
```

Preserve existing request classes and avoid removing Phase A fields.

- [ ] **Step 6: Add migrations**

Modify `../backend/migrations/2026-06-07-add-course-catalogs.sql` so fresh installs include:

```sql
ALTER TABLE course_catalogs
  ADD COLUMN last_ingestion_task_id VARCHAR(32) NULL,
  ADD COLUMN last_ingestion_status VARCHAR(20) NULL,
  ADD COLUMN chunk_count INT NOT NULL DEFAULT 0,
  ADD COLUMN last_error VARCHAR(500) NULL;

ALTER TABLE course_catalog_materials
  ADD COLUMN storage_type VARCHAR(20) NOT NULL DEFAULT 'local',
  ADD COLUMN file_size BIGINT NOT NULL DEFAULT 0,
  ADD COLUMN last_error VARCHAR(500) NULL,
  ADD COLUMN ingested_at DATETIME NULL,
  ADD COLUMN chunk_count INT NOT NULL DEFAULT 0;
```

If the original file uses `CREATE TABLE`, prefer adding these columns directly inside the table definitions rather than appending duplicate `ALTER TABLE`.

Create `../backend/migrations/2026-06-07-extend-course-catalog-ingestion.sql`:

```sql
ALTER TABLE course_catalogs
  ADD COLUMN last_ingestion_task_id VARCHAR(32) NULL,
  ADD COLUMN last_ingestion_status VARCHAR(20) NULL,
  ADD COLUMN chunk_count INT NOT NULL DEFAULT 0,
  ADD COLUMN last_error VARCHAR(500) NULL;

ALTER TABLE course_catalog_materials
  ADD COLUMN storage_type VARCHAR(20) NOT NULL DEFAULT 'local',
  ADD COLUMN file_size BIGINT NOT NULL DEFAULT 0,
  ADD COLUMN last_error VARCHAR(500) NULL,
  ADD COLUMN ingested_at DATETIME NULL,
  ADD COLUMN chunk_count INT NOT NULL DEFAULT 0;
```

- [ ] **Step 7: Run schema tests**

Run from `../backend`:

```bash
pytest tests/test_course_catalog_ingestion.py::test_course_catalog_material_has_ingestion_fields tests/test_course_catalog_ingestion.py::test_course_catalog_storage_settings_exist -q
```

Expected: pass.

- [ ] **Step 8: Commit schema/config**

```bash
git add ../backend/app/models/catalog.py ../backend/app/schemas/catalog.py ../backend/app/core/config.py ../backend/migrations/2026-06-07-add-course-catalogs.sql ../backend/migrations/2026-06-07-extend-course-catalog-ingestion.sql ../backend/tests/test_course_catalog_ingestion.py
git commit -m "扩展课程资源库入库状态模型"
```

## Task 3: Backend material upload API

**Files:**
- Modify: `../backend/app/api/v1/catalogs.py`
- Modify: `../backend/tests/test_course_catalog_ingestion.py`

- [ ] **Step 1: Add failing upload tests**

Append tests in `../backend/tests/test_course_catalog_ingestion.py` following existing `tests/test_course_catalogs.py` async client patterns:

```python
async def test_admin_upload_catalog_material_txt(async_client, admin_headers, tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.COURSE_CATALOG_STORAGE_ROOT", str(tmp_path))
    create = await async_client.post(
        "/api/v1/admin/course-catalogs",
        headers=admin_headers,
        json={"title": "数据结构", "description": "DS"},
    )
    catalog_id = create.json()["data"]["id"]

    response = await async_client.post(
        f"/api/v1/admin/course-catalogs/{catalog_id}/materials/upload",
        headers=admin_headers,
        files={"file": ("intro.md", b"# Intro\nBinary tree", "text/markdown")},
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["filename"] == "intro.md"
    assert data["storage_type"] == "local"
    assert data["status"] == "pending_ingest"
    assert data["file_size"] > 0
    assert "storage_uri" not in data


async def test_admin_upload_catalog_material_rejects_unsupported_file(async_client, admin_headers):
    create = await async_client.post(
        "/api/v1/admin/course-catalogs",
        headers=admin_headers,
        json={"title": "数据结构", "description": "DS"},
    )
    catalog_id = create.json()["data"]["id"]

    response = await async_client.post(
        f"/api/v1/admin/course-catalogs/{catalog_id}/materials/upload",
        headers=admin_headers,
        files={"file": ("slides.pptx", b"bad", "application/octet-stream")},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["message"] == "不支持的资料类型"
```

If fixtures are named differently, copy exact fixture names from `../backend/tests/test_course_catalogs.py`.

- [ ] **Step 2: Run upload tests and verify they fail**

Run from `../backend`:

```bash
pytest tests/test_course_catalog_ingestion.py -q
```

Expected: fail because upload endpoint does not exist.

- [ ] **Step 3: Add upload helpers**

In `../backend/app/api/v1/catalogs.py`, add imports:

```python
from pathlib import Path
from uuid import uuid4

from fastapi import File, UploadFile

from app.core.config import settings
```

Add helpers:

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


def _material_item(material: CourseCatalogMaterial) -> dict:
    return {
        "id": material.id,
        "catalog_id": material.catalog_id,
        "filename": material.filename,
        "source_type": material.source_type,
        "storage_type": material.storage_type,
        "file_size": material.file_size or 0,
        "status": material.status,
        "chunk_count": material.chunk_count or 0,
        "last_error": material.last_error,
        "ingested_at": material.ingested_at.isoformat() if material.ingested_at else None,
        "created_at": material.create_time.isoformat() if material.create_time else "",
    }
```

- [ ] **Step 4: Implement upload endpoint**

Add to `../backend/app/api/v1/catalogs.py`:

```python
@router.post("/admin/course-catalogs/{catalog_id}/materials/upload", status_code=201)
async def admin_upload_catalog_material(
    catalog_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    catalog = await _get_admin_catalog_or_404(db, catalog_id)
    if catalog.knowledge_status == "ingesting" or catalog.status == "ingesting":
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

    next_knowledge_status = "dirty" if catalog.status == "ready" else "pending_ingest"
    catalog.knowledge_status = next_knowledge_status
    catalog.last_error = None
    catalog.material_count = (catalog.material_count or 0) + 1

    material = CourseCatalogMaterial(
        id=material_id,
        catalog_id=catalog.id,
        filename=filename,
        source_type="file",
        storage_type="local",
        storage_uri=relative_path.as_posix(),
        file_size=len(content),
        status="pending_ingest",
    )
    db.add(material)
    await db.flush()
    await db.refresh(material)

    return {"code": 201, "message": "created", "data": _material_item(material)}
```

- [ ] **Step 5: Update material list to use `_material_item`**

Replace material list mapping in `admin_list_catalog_materials`:

```python
"materials": [_material_item(m) for m in materials]
```

- [ ] **Step 6: Run upload tests**

Run from `../backend`:

```bash
pytest tests/test_course_catalog_ingestion.py tests/test_course_catalogs.py -q
```

Expected: all pass.

- [ ] **Step 7: Commit upload API**

```bash
git add ../backend/app/api/v1/catalogs.py ../backend/tests/test_course_catalog_ingestion.py
git commit -m "新增课程资源库资料上传接口"
```

## Task 4: Backend ingestion orchestration

**Files:**
- Modify: `../backend/app/api/v1/catalogs.py`
- Modify: `../backend/tests/test_course_catalog_ingestion.py`

- [ ] **Step 1: Add failing ingestion orchestration tests**

Append tests:

```python
from unittest.mock import AsyncMock, patch


async def test_admin_start_catalog_ingestion_success(async_client, admin_headers, tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.COURSE_CATALOG_STORAGE_ROOT", str(tmp_path))
    create = await async_client.post(
        "/api/v1/admin/course-catalogs",
        headers=admin_headers,
        json={"title": "数据结构", "description": "DS"},
    )
    catalog_id = create.json()["data"]["id"]
    upload = await async_client.post(
        f"/api/v1/admin/course-catalogs/{catalog_id}/materials/upload",
        headers=admin_headers,
        files={"file": ("intro.md", b"# Intro", "text/markdown")},
    )
    material_id = upload.json()["data"]["id"]

    with patch("app.api.v1.catalogs.agent_client.post_json", new_callable=AsyncMock) as mock_agent:
        mock_agent.return_value = {
            "catalog_id": catalog_id,
            "chunk_count": 2,
            "materials": [{"material_id": material_id, "status": "ingested", "chunk_count": 2, "error": None}],
            "duration_seconds": 0.1,
        }
        response = await async_client.post(
            f"/api/v1/admin/course-catalogs/{catalog_id}/ingestions",
            headers=admin_headers,
        )

    assert response.status_code == 202
    data = response.json()["data"]
    assert data["catalog_id"] == catalog_id
    assert data["status"] == "completed"

    status_response = await async_client.get(
        f"/api/v1/admin/course-catalogs/{catalog_id}/knowledge-status",
        headers=admin_headers,
    )
    status_data = status_response.json()["data"]
    assert status_data["status"] == "ready"
    assert status_data["knowledge_status"] == "ready"
    assert status_data["chunk_count"] == 2


async def test_admin_start_catalog_ingestion_without_pending_materials_returns_409(async_client, admin_headers):
    create = await async_client.post(
        "/api/v1/admin/course-catalogs",
        headers=admin_headers,
        json={"title": "空资源库", "description": ""},
    )
    catalog_id = create.json()["data"]["id"]

    response = await async_client.post(
        f"/api/v1/admin/course-catalogs/{catalog_id}/ingestions",
        headers=admin_headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"]["message"] == "没有待入库资料"
```

- [ ] **Step 2: Run tests and verify they fail**

Run from `../backend`:

```bash
pytest tests/test_course_catalog_ingestion.py -q
```

Expected: fail because ingestion endpoint does not exist.

- [ ] **Step 3: Add imports and helpers**

In `../backend/app/api/v1/catalogs.py`, add imports:

```python
from datetime import datetime

from app.models.others import AsyncTask
from app.services.agent_client import AgentServiceError, agent_client
```

Add helper:

```python
def _is_initial_ingestion(catalog: CourseCatalog) -> bool:
    return catalog.status != "ready"
```

- [ ] **Step 4: Implement ingestion endpoint**

Add:

```python
@router.post("/admin/course-catalogs/{catalog_id}/ingestions", status_code=202)
async def admin_start_catalog_ingestion(
    catalog_id: str,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    catalog = await _get_admin_catalog_or_404(db, catalog_id)
    if catalog.knowledge_status == "ingesting" or catalog.status == "ingesting":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": 40911, "message": "课程资源库正在入库中", "data": None},
        )

    result = await db.execute(
        select(CourseCatalogMaterial).where(
            CourseCatalogMaterial.catalog_id == catalog.id,
            CourseCatalogMaterial.is_deleted == False,
            CourseCatalogMaterial.status.in_(["pending_ingest", "failed"]),
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
        result={"catalog_id": catalog.id, "material_ids": [m.id for m in materials]},
    )
    db.add(task)
    await db.flush()
    catalog.last_ingestion_task_id = task.id
    catalog.last_ingestion_status = "processing"

    payload = {
        "catalog_id": catalog.id,
        "materials": [
            {"material_id": m.id, "storage_uri": m.storage_uri or "", "filename": m.filename}
            for m in materials
        ],
    }

    try:
        agent_data = await agent_client.post_json("/agent/v1/knowledge/ingestions", payload)
    except AgentServiceError as exc:
        task.status = "failed"
        task.progress = 100
        task.error_code = "agent_ingestion_failed"
        task.error_message = exc.message
        task.completed_at = datetime.utcnow()
        catalog.last_ingestion_status = "failed"
        catalog.knowledge_status = "failed"
        catalog.last_error = exc.message
        if initial:
            catalog.status = "failed"
        else:
            catalog.status = "ready"
        for material in materials:
            material.status = "failed"
            material.last_error = exc.message
        await db.flush()
        return {
            "code": 202,
            "message": "accepted",
            "data": {"task_id": task.id, "catalog_id": catalog.id, "status": "failed"},
        }

    material_results = {item.get("material_id"): item for item in agent_data.get("materials", [])}
    failed_errors = []
    chunk_count = int(agent_data.get("chunk_count") or 0)
    for material in materials:
        item = material_results.get(material.id, {})
        if item.get("status") == "ingested":
            material.status = "ingested"
            material.chunk_count = int(item.get("chunk_count") or 0)
            material.ingested_at = datetime.utcnow()
            material.last_error = None
        else:
            error = item.get("error") or "资料入库失败"
            material.status = "failed"
            material.last_error = error
            failed_errors.append(error)

    if failed_errors:
        catalog.knowledge_status = "failed"
        catalog.last_ingestion_status = "failed"
        catalog.last_error = failed_errors[0]
        catalog.status = "failed" if initial else "ready"
        task.status = "failed"
        task.error_code = "material_ingestion_failed"
        task.error_message = failed_errors[0]
    else:
        catalog.status = "ready"
        catalog.knowledge_status = "ready"
        catalog.last_ingestion_status = "completed"
        catalog.last_error = None
        catalog.chunk_count = (catalog.chunk_count or 0) + chunk_count
        task.status = "completed"
        task.progress = 100

    task.result = agent_data
    task.completed_at = datetime.utcnow()
    await db.flush()

    return {
        "code": 202,
        "message": "accepted",
        "data": {"task_id": task.id, "catalog_id": catalog.id, "status": task.status},
    }
```

- [ ] **Step 5: Expand knowledge status response**

Update `admin_get_catalog_knowledge_status` data:

```python
pending_count = (
    await db.execute(
        select(func.count())
        .select_from(CourseCatalogMaterial)
        .where(
            CourseCatalogMaterial.catalog_id == catalog.id,
            CourseCatalogMaterial.is_deleted == False,
            CourseCatalogMaterial.status == "pending_ingest",
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

Return:

```python
"last_ingestion_task_id": catalog.last_ingestion_task_id,
"last_ingestion_status": catalog.last_ingestion_status,
"chunk_count": catalog.chunk_count or 0,
"pending_material_count": pending_count,
"failed_material_count": failed_count,
"last_error": catalog.last_error,
```

- [ ] **Step 6: Run Backend ingestion tests**

Run from `../backend`:

```bash
pytest tests/test_course_catalog_ingestion.py tests/test_course_catalogs.py -q
```

Expected: all pass.

- [ ] **Step 7: Commit ingestion orchestration**

```bash
git add ../backend/app/api/v1/catalogs.py ../backend/tests/test_course_catalog_ingestion.py
git commit -m "接入课程资源库知识入库任务"
```

## Task 5: OpenAPI contract

**Files:**
- Modify: `../docs/10-client-api/Client-API.openapi.json`

- [ ] **Step 1: Add contract entries**

Add paths:

```json
"/api/v1/admin/course-catalogs/{catalog_id}/materials/upload": {
  "post": {
    "tags": ["course-catalogs"],
    "summary": "上传课程资源库资料",
    "parameters": [
      {"name": "catalog_id", "in": "path", "required": true, "schema": {"type": "string"}}
    ],
    "requestBody": {
      "required": true,
      "content": {
        "multipart/form-data": {
          "schema": {
            "type": "object",
            "required": ["file"],
            "properties": {"file": {"type": "string", "format": "binary"}}
          }
        }
      }
    },
    "responses": {
      "201": {
        "description": "created",
        "content": {
          "application/json": {
            "schema": {"$ref": "#/components/schemas/CourseCatalogMaterialResponse"}
          }
        }
      },
      "400": {"description": "bad request", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/HTTPErrorResponse"}}}},
      "409": {"description": "conflict", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/HTTPErrorResponse"}}}}
    }
  }
}
```

Add:

```json
"/api/v1/admin/course-catalogs/{catalog_id}/ingestions": {
  "post": {
    "tags": ["course-catalogs"],
    "summary": "触发课程资源库知识入库",
    "parameters": [
      {"name": "catalog_id", "in": "path", "required": true, "schema": {"type": "string"}}
    ],
    "responses": {
      "202": {
        "description": "accepted",
        "content": {
          "application/json": {
            "schema": {"$ref": "#/components/schemas/CourseCatalogIngestionResponse"}
          }
        }
      },
      "409": {"description": "conflict", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/HTTPErrorResponse"}}}}
    }
  }
}
```

Add or extend schemas:

```json
"CourseCatalogMaterialItem": {
  "type": "object",
  "required": ["id", "catalog_id", "filename", "source_type", "storage_type", "file_size", "status", "chunk_count", "created_at"],
  "properties": {
    "id": {"type": "string"},
    "catalog_id": {"type": "string"},
    "filename": {"type": "string"},
    "source_type": {"type": "string"},
    "storage_type": {"type": "string"},
    "file_size": {"type": "integer"},
    "status": {"type": "string"},
    "chunk_count": {"type": "integer"},
    "last_error": {"type": "string", "nullable": true},
    "ingested_at": {"type": "string", "nullable": true},
    "created_at": {"type": "string"}
  }
}
```

- [ ] **Step 2: Validate OpenAPI JSON**

Run from `frontend`:

```bash
python -m json.tool ../docs/10-client-api/Client-API.openapi.json >/tmp/client-api-openapi-check.json
```

Expected: exits 0.

- [ ] **Step 3: Commit OpenAPI**

```bash
git add ../docs/10-client-api/Client-API.openapi.json
git commit -m "更新课程资源库入库接口契约"
```

## Task 6: Admin frontend upload and ingestion UI

**Files:**
- Modify: `src/api/services/admin.js`
- Modify: `src/pages/AdminConsole.jsx`

- [ ] **Step 1: Add admin service methods**

Modify `src/api/services/admin.js`:

```javascript
  uploadCourseCatalogMaterial: async (catalogId, file) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post(`/admin/course-catalogs/${catalogId}/materials/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
  },

  startCourseCatalogIngestion: async (catalogId) => apiClient.post(`/admin/course-catalogs/${catalogId}/ingestions`),
```

Keep existing `getCourseCatalogStatus` and `createCourseCatalogMaterial` until call sites are migrated. Do not remove existing methods unless no code references them.

- [ ] **Step 2: Add UI state**

In `src/pages/AdminConsole.jsx`, inside the component:

```javascript
const [selectedCatalog, setSelectedCatalog] = useState(null);
const [catalogMaterials, setCatalogMaterials] = useState([]);
const [materialsLoading, setMaterialsLoading] = useState(false);
const [uploadingMaterial, setUploadingMaterial] = useState(false);
const [ingestingCatalog, setIngestingCatalog] = useState(false);
const [catalogStatus, setCatalogStatus] = useState(null);
const [catalogActionError, setCatalogActionError] = useState('');
```

- [ ] **Step 3: Add material/status loaders**

Add functions:

```javascript
const loadCatalogMaterials = async (catalog) => {
  if (!catalog?.id) return;
  setMaterialsLoading(true);
  setCatalogActionError('');
  try {
    const res = await adminService.getCourseCatalogMaterials(catalog.id);
    setCatalogMaterials(res.data?.materials || []);
  } catch (err) {
    setCatalogActionError(err.response?.data?.detail?.message || err.message || '资料列表加载失败');
  } finally {
    setMaterialsLoading(false);
  }
};

const loadCatalogStatus = async (catalog) => {
  if (!catalog?.id) return;
  try {
    const res = await adminService.getCourseCatalogStatus(catalog.id);
    setCatalogStatus(res.data || null);
  } catch (err) {
    setCatalogActionError(err.response?.data?.detail?.message || err.message || '知识库状态加载失败');
  }
};
```

- [ ] **Step 4: Add upload handler**

```javascript
const handleCatalogMaterialUpload = async (event) => {
  const file = event.target.files?.[0];
  event.target.value = '';
  if (!file || !selectedCatalog?.id) return;
  setUploadingMaterial(true);
  setCatalogActionError('');
  try {
    await adminService.uploadCourseCatalogMaterial(selectedCatalog.id, file);
    await loadCatalogMaterials(selectedCatalog);
    await loadCatalogStatus(selectedCatalog);
    await fetchCatalogs();
  } catch (err) {
    setCatalogActionError(err.response?.data?.detail?.message || err.message || '资料上传失败');
  } finally {
    setUploadingMaterial(false);
  }
};
```

- [ ] **Step 5: Add ingestion handler**

```javascript
const handleStartCatalogIngestion = async () => {
  if (!selectedCatalog?.id) return;
  setIngestingCatalog(true);
  setCatalogActionError('');
  try {
    await adminService.startCourseCatalogIngestion(selectedCatalog.id);
    await loadCatalogMaterials(selectedCatalog);
    await loadCatalogStatus(selectedCatalog);
    await fetchCatalogs();
  } catch (err) {
    setCatalogActionError(err.response?.data?.detail?.message || err.message || '入库启动失败');
  } finally {
    setIngestingCatalog(false);
  }
};
```

- [ ] **Step 6: Render material management panel**

In the CourseCatalog tab, add a panel below the catalog table:

```jsx
{selectedCatalog && (
  <section className="mt-6 border border-slate-200 rounded-lg p-4 bg-white">
    <div className="flex items-center justify-between gap-3 mb-4">
      <div>
        <h3 className="font-semibold text-slate-900">{selectedCatalog.title} 资料管理</h3>
        <p className="text-sm text-slate-500">
          {catalogStatus ? `状态：${catalogStatus.status} / ${catalogStatus.knowledge_status}` : '状态加载中'}
        </p>
      </div>
      <div className="flex items-center gap-2">
        <label className="px-3 py-2 text-sm rounded-md border border-slate-300 cursor-pointer hover:bg-slate-50">
          上传资料
          <input
            type="file"
            accept=".txt,.md,.pdf"
            className="hidden"
            disabled={uploadingMaterial || ingestingCatalog || catalogStatus?.knowledge_status === 'ingesting'}
            onChange={handleCatalogMaterialUpload}
          />
        </label>
        <button
          type="button"
          className="px-3 py-2 text-sm rounded-md bg-slate-900 text-white disabled:opacity-50"
          disabled={ingestingCatalog || catalogStatus?.knowledge_status === 'ingesting'}
          onClick={handleStartCatalogIngestion}
        >
          开始入库
        </button>
      </div>
    </div>
    {catalogActionError && <p className="text-sm text-red-600 mb-3">{catalogActionError}</p>}
    {materialsLoading ? (
      <p className="text-sm text-slate-500">资料加载中...</p>
    ) : catalogMaterials.length === 0 ? (
      <p className="text-sm text-slate-500">暂无资料</p>
    ) : (
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-500 border-b">
              <th className="py-2">文件</th>
              <th className="py-2">状态</th>
              <th className="py-2">大小</th>
              <th className="py-2">切片</th>
              <th className="py-2">错误</th>
            </tr>
          </thead>
          <tbody>
            {catalogMaterials.map((material) => (
              <tr key={material.id} className="border-b last:border-b-0">
                <td className="py-2 break-words">{material.filename}</td>
                <td className="py-2">{material.status}</td>
                <td className="py-2">{material.file_size || 0}</td>
                <td className="py-2">{material.chunk_count || 0}</td>
                <td className="py-2 text-red-600 break-words">{material.last_error || '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )}
  </section>
)}
```

- [ ] **Step 7: Wire row selection**

Add a button in each catalog row:

```jsx
<button
  type="button"
  className="text-sm text-slate-700 underline"
  onClick={() => {
    setSelectedCatalog(catalog);
    loadCatalogMaterials(catalog);
    loadCatalogStatus(catalog);
  }}
>
  管理资料
</button>
```

- [ ] **Step 8: Run frontend checks**

Run from `frontend`:

```bash
npm run lint
npm run build
```

Expected: lint passes; build passes with only existing Vite chunk size warning.

- [ ] **Step 9: Commit frontend UI**

```bash
git add src/api/services/admin.js src/pages/AdminConsole.jsx
git commit -m "新增管理员课程资料入库界面"
```

## Task 7: Verification, workflow, and manual smoke

**Files:**
- Modify: `WORKFLOW.md`

- [ ] **Step 1: Run focused backend tests**

Run from `../backend`:

```bash
pytest tests/test_course_catalog_ingestion.py tests/test_course_catalogs.py -q
```

Expected: pass.

- [ ] **Step 2: Run focused Agent tests**

Run from `../agent_service`:

```bash
pytest tests/test_knowledge_ingestion_api.py tests/test_ingest_knowledge.py tests/test_course_knowledge_ingestion.py -q
```

Expected: pass.

- [ ] **Step 3: Validate OpenAPI**

Run from `frontend`:

```bash
python -m json.tool ../docs/10-client-api/Client-API.openapi.json >/tmp/client-api-openapi-check.json
```

Expected: exits 0.

- [ ] **Step 4: Run frontend checks**

Run from `frontend`:

```bash
npm run lint
npm run build
```

Expected: pass; existing Vite chunk warning is acceptable if unchanged.

- [ ] **Step 5: Manual smoke against local services**

With Backend, Agent Service, MySQL `duagent_test`, and Qdrant available:

```text
1. Admin creates CourseCatalog.
2. Admin uploads intro.md.
3. Admin clicks start ingestion.
4. Admin sees status ready.
5. Teacher create-class dialog shows the catalog.
6. Admin uploads supplement.txt.
7. Catalog remains bindable and shows dirty / pending ingestion.
8. Admin starts ingestion again.
9. Status returns ready.
10. Qdrant course_knowledge contains payload.course_id equal to CourseCatalog.id.
```

- [ ] **Step 6: Update WORKFLOW.md**

Append under recent verification:

```markdown
- 2026-06-07：CourseCatalog 资料上传与知识库真实入库 Phase B1 完成：
  - Admin 可上传 `.txt` / `.md` / `.pdf` 到 Backend 共享目录。
  - Backend 记录资料元数据、入库状态和 AsyncTask。
  - Agent Service 新增知识入库 API，读取共享目录资料并以 `CourseCatalog.id` 写入 Qdrant。
  - AdminConsole 可管理资料、触发入库并查看状态。
  - 验证：`pytest tests/test_course_catalog_ingestion.py tests/test_course_catalogs.py -q` 通过；Agent ingestion 相关 pytest 通过；`npm run lint` / `npm run build` 通过；OpenAPI JSON 校验通过。
  - 契约状态：Client API 已同步；Agent API 新增知识入库接口；教师/学生消费链路仍进入后续 Phase B2/C。
```

- [ ] **Step 7: Commit workflow**

```bash
git add WORKFLOW.md
git commit -m "记录课程资源库知识入库进度"
```

## Self-Review Checklist

- [ ] Spec coverage: upload, shared local storage, Agent-owned ingestion, Qdrant `course_id=CourseCatalog.id`, manual incremental ingestion, first-failure vs incremental-failure status, Admin UI, OpenAPI, tests.
- [ ] Placeholder scan: plan contains no unresolved placeholder markers, vague generic error-handling instructions, or cross-task shorthand.
- [ ] Type consistency: status names match spec (`pending_ingest`, `ingesting`, `ingested`, `dirty`, `failed`, `ready`); API paths match spec; frontend service names match UI calls.
- [ ] Documentation boundary: only `../docs/10-client-api/Client-API.openapi.json` is modified during contract task, which requires user permission at implementation time because it is outside `frontend/`.
