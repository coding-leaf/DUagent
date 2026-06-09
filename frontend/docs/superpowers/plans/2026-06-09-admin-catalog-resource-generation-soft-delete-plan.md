# Admin Catalog Resource Generation And Soft Delete Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Admin-owned CourseCatalog resource generation plus surface-only soft delete for generated resources and source materials.

**Architecture:** Keep generated resources in the existing `resources` table and fan out Agent results to teaching classes bound to the CourseCatalog at generation time. Add Admin-only Client API endpoints, keep the deprecated teacher `/resources/generate` endpoint deprecated for frontend use, and update `CourseCatalogDrawer` to call only declared Admin endpoints. Deletion is soft only: mark rows deleted and refresh visible lists, with no file or Qdrant cleanup.

**Tech Stack:** FastAPI, SQLAlchemy async ORM, Pydantic, OpenAPI 3.0 JSON, React 19 + Vite, Playwright, pytest, existing `{code, message, data}` envelope and AsyncTask polling.

---

## Scope

In scope:

- Admin catalog-scoped resource generation endpoint.
- Admin catalog resource list endpoint.
- Admin resource soft delete endpoint.
- Admin material soft delete endpoint.
- Webhook fan-out persistence for catalog generation tasks.
- Task polling permission for Admin resource generation tasks.
- OpenAPI and Client API Markdown updates.
- Frontend service methods and `CourseCatalogDrawer` UI.
- Backend tests and frontend E2E regression tests.
- Progress documentation updates.

Out of scope:

- Physical file deletion.
- Qdrant deletion.
- `chunk_count` rollback.
- Automatic backfill for classes bound after generation.
- Teacher-facing generation.
- Quiz generation.
- New schema columns or migrations.

## Key Design Decisions

- `Resource.course_id` remains required and points to `courses.id`.
- `CourseOffering.id` already equals `Course.id` when teachers create catalog-bound classes.
- Admin generation resolves all non-deleted `CourseOffering` rows for a catalog and stores their ids in `AsyncTask.result.fanout_course_ids`.
- Agent receives `course_id = catalog_id` for knowledge retrieval.
- Webhook writes one `Resource` per generated resource per `fanout_course_id`.
- If no class is bound to the catalog at generation time, the Admin generation endpoint returns `409` and does not create a task.
- Classes bound after generation do not receive old generated resources automatically.
- Material soft delete sets `knowledge_status = "dirty"` for `ready` or `partial` catalogs, but does not reduce `chunk_count`.

## File Structure

Backend:

- Modify `../backend/app/schemas/operations.py`
  - Add `CatalogResourceGenerateRequest`.
- Modify `../backend/app/api/v1/catalogs.py`
  - Add Admin generation endpoint.
  - Add Admin catalog resource list endpoint.
  - Add Admin resource soft delete endpoint.
  - Add material soft delete endpoint.
  - Add helper functions for catalog ready validation and bound class lookup.
- Modify `../backend/app/api/v1/webhooks.py`
  - Fan out `resource_generation` completed results when task result includes `fanout_course_ids`.
  - Keep old teacher task behavior using `task.course_id` as fallback.
- Modify `../backend/app/api/v1/tasks.py`
  - Allow admins to poll `resource_generation` tasks they created or Admin-visible resource generation tasks.
- Modify `../docs/10-client-api/Client-API.openapi.json`
  - Add Admin generation, Admin catalog resources list, resource soft delete, material soft delete paths and schemas.
- Modify `../docs/10-client-api/API_前端接口规范.md`
  - Mirror OpenAPI changes and keep `/resources/generate` deprecated.

Backend tests:

- Create `../backend/tests/test_admin_catalog_resource_generation.py`
  - Contract tests for Admin generation, fan-out, no-bound-class rejection, resource soft delete, material soft delete.
- Modify `../backend/tests/test_resources_async.py`
  - Keep legacy teacher webhook behavior covered if existing tests are sensitive to webhook fan-out changes.

Frontend:

- Modify `src/api/services/admin.js`
  - Add generation, resource list, resource delete, material delete methods.
- Modify `src/components/admin/CourseCatalogDrawer.jsx`
  - Add generated resource list state.
  - Add generation form and task polling.
  - Add soft delete actions for materials and generated resources.
  - Keep ingestion behavior unchanged.
- Modify `e2e/specs.spec.js`
  - Add Admin drawer test for generation polling and soft delete UI.
  - Assert TeacherConsole still has no generation entry.

Docs:

- Modify `docs/feature-ledger.md`
- Modify `docs/project-direction.md`
- Modify `docs/project-coverage-audit.md`
- Modify `WORKFLOW.md`

---

## Task 1: Backend Tests For Admin Catalog Generation

**Files:**
- Create: `../backend/tests/test_admin_catalog_resource_generation.py`

- [ ] **Step 1: Write failing backend tests**

Create `../backend/tests/test_admin_catalog_resource_generation.py`:

```python
import os
import sys
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:////tmp/admin_catalog_resource_generation.db",
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.base import Base
from app.db.session import async_session_factory, engine
from app.main import app
from app.models.catalog import CourseCatalog, CourseCatalogMaterial, CourseOffering
from app.models.course import Course
from app.models.others import AsyncTask, Resource
from app.models.user import User


async def _reset_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


def _auth_headers(user_id: str, role: str) -> dict:
    from app.core.security import create_token

    token = create_token(user_id, role)
    return {"Authorization": f"Bearer {token}"}


async def _seed_user(user_id: str, role: str) -> None:
    async with async_session_factory() as db:
        db.add(
            User(
                id=user_id,
                email=f"{user_id}@example.com",
                username=user_id,
                password_hash="x",
                role=role,
            )
        )
        await db.commit()


async def _seed_ready_catalog(
    *,
    catalog_id: str = "catalog-admin-gen",
    status: str = "ready",
    knowledge_status: str = "ready",
    chunk_count: int = 5,
) -> str:
    async with async_session_factory() as db:
        db.add(
            CourseCatalog(
                id=catalog_id,
                title="Admin Generation Catalog",
                status=status,
                knowledge_status=knowledge_status,
                material_count=1,
                chunk_count=chunk_count,
            )
        )
        db.add(
            CourseCatalogMaterial(
                id="material-admin-gen",
                catalog_id=catalog_id,
                filename="lesson.md",
                source_type="file",
                storage_uri="course_catalogs/catalog-admin-gen/material-admin-gen/lesson.md",
                status="ingested",
                chunk_count=chunk_count,
            )
        )
        await db.commit()
    return catalog_id


async def _seed_bound_class(
    *,
    catalog_id: str,
    class_id: str,
    teacher_id: str = "teacher-admin-gen",
) -> str:
    async with async_session_factory() as db:
        db.add(
            Course(
                id=class_id,
                name=f"Class {class_id}",
                course_code=f"C{class_id[-6:]}",
                teacher_id=teacher_id,
            )
        )
        db.add(
            CourseOffering(
                id=class_id,
                name=f"Class {class_id}",
                catalog_id=catalog_id,
                teacher_id=teacher_id,
                class_code=f"C{class_id[-6:]}",
            )
        )
        await db.commit()
    return class_id


async def _count_tasks(catalog_id: str) -> int:
    async with async_session_factory() as db:
        result = await db.execute(
            select(AsyncTask).where(AsyncTask.task_type == "resource_generation")
        )
        tasks = result.scalars().all()
        return sum(1 for task in tasks if isinstance(task.result, dict) and task.result.get("catalog_id") == catalog_id)


@pytest.mark.asyncio
async def test_admin_catalog_generation_creates_task_and_sends_catalog_id_to_agent():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    await _seed_user("teacher-admin-gen", "teacher")
    catalog_id = await _seed_ready_catalog()
    class_a = await _seed_bound_class(catalog_id=catalog_id, class_id="class-admin-gen-a")
    class_b = await _seed_bound_class(catalog_id=catalog_id, class_id="class-admin-gen-b")

    with patch("app.api.v1.catalogs.agent_client.post_json", new_callable=AsyncMock) as mock_agent:
        mock_agent.return_value = {"task_id": "ignored"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/course-catalogs/{catalog_id}/resources/generations",
                headers=_auth_headers("admin-admin-gen", "admin"),
                json={
                    "chapter": "树",
                    "knowledge_point": "二叉树",
                    "resource_types": ["document", "mindmap"],
                },
            )

    assert response.status_code == 202, response.text
    data = response.json()["data"]
    assert data["catalog_id"] == catalog_id
    assert data["status"] == "processing"
    assert data["task_id"]

    payload = mock_agent.await_args.args[1]
    assert payload["course_id"] == catalog_id
    assert payload["chapter"] == "树"
    assert payload["knowledge_point"] == "二叉树"
    assert payload["resource_types"] == ["document", "mindmap"]

    async with async_session_factory() as db:
        task = await db.get(AsyncTask, data["task_id"])
        assert task is not None
        assert task.task_type == "resource_generation"
        assert task.user_id == "admin-admin-gen"
        assert task.course_id is None
        assert task.result["catalog_id"] == catalog_id
        assert task.result["fanout_course_ids"] == [class_a, class_b]
        assert task.result["chapter"] == "树"
        assert task.result["knowledge_point"] == "二叉树"


@pytest.mark.asyncio
async def test_admin_catalog_generation_rejects_no_bound_classes_without_task():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    catalog_id = await _seed_ready_catalog()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/admin/course-catalogs/{catalog_id}/resources/generations",
            headers=_auth_headers("admin-admin-gen", "admin"),
            json={"resource_types": ["document"]},
        )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "course_offering_missing"
    assert await _count_tasks(catalog_id) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "knowledge_status", "chunk_count", "expected_code"),
    [
        ("draft", "draft", 0, "course_material_missing"),
        ("ready", "dirty", 5, "course_material_missing"),
        ("ready", "failed", 5, "course_material_missing"),
        ("ready", "ready", 0, "knowledge_base_empty"),
    ],
)
async def test_admin_catalog_generation_rejects_not_ready_catalogs(
    status,
    knowledge_status,
    chunk_count,
    expected_code,
):
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    await _seed_user("teacher-admin-gen", "teacher")
    catalog_id = await _seed_ready_catalog(
        status=status,
        knowledge_status=knowledge_status,
        chunk_count=chunk_count,
    )
    await _seed_bound_class(catalog_id=catalog_id, class_id="class-admin-gen-a")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/admin/course-catalogs/{catalog_id}/resources/generations",
            headers=_auth_headers("admin-admin-gen", "admin"),
            json={"resource_types": ["document"]},
        )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == expected_code


@pytest.mark.asyncio
async def test_non_admin_cannot_generate_catalog_resources():
    await _reset_db()
    await _seed_user("teacher-admin-gen", "teacher")
    catalog_id = await _seed_ready_catalog()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/admin/course-catalogs/{catalog_id}/resources/generations",
            headers=_auth_headers("teacher-admin-gen", "teacher"),
            json={"resource_types": ["document"]},
        )

    assert response.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd ../backend
pytest tests/test_admin_catalog_resource_generation.py -q
```

Expected: FAIL with route not found or mock target missing for `app.api.v1.catalogs.agent_client.post_json`.

- [ ] **Step 3: Commit failing tests**

```bash
git add ../backend/tests/test_admin_catalog_resource_generation.py
git commit -m "新增资源库生成后端测试"
```

---

## Task 2: Backend Admin Generation Endpoint

**Files:**
- Modify: `../backend/app/schemas/operations.py`
- Modify: `../backend/app/api/v1/catalogs.py`
- Test: `../backend/tests/test_admin_catalog_resource_generation.py`

- [ ] **Step 1: Add request schema**

In `../backend/app/schemas/operations.py`, add:

```python
class CatalogResourceGenerateRequest(BaseModel):
    chapter: Optional[str] = None
    knowledge_point: Optional[str] = None
    resource_types: Optional[list[str]] = None
```

- [ ] **Step 2: Add imports and helpers in catalogs route**

In `../backend/app/api/v1/catalogs.py`, add imports:

```python
from fastapi import Request
from app.models.catalog import CourseOffering
from app.models.others import Resource
from app.schemas.operations import CatalogResourceGenerateRequest
from app.services.agent_client import agent_client
```

Integrate those into the existing import lines. Do not remove the existing `AgentClient`, `AgentServiceError`, or `AsyncTask` imports already used by ingestion.

Add helper functions near the existing catalog helpers:

```python
RESOURCE_TYPES = {"document", "mindmap", "reading", "code"}


def _webhook_url(request: Request) -> str:
    base = str(request.base_url).rstrip("/")
    return f"{base}/api/v1/webhooks/agent"


def _course_material_missing() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": "course_material_missing", "message": "课程资料尚未完成入库", "data": None},
    )


def _knowledge_base_empty() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": "knowledge_base_empty", "message": "课程知识库为空", "data": None},
    )


def _course_offering_missing() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": "course_offering_missing", "message": "课程资源库尚未绑定教学班", "data": None},
    )
```

- [ ] **Step 3: Add Admin generation endpoint**

In `../backend/app/api/v1/catalogs.py`, add before `@router.get("/course-catalogs")`:

```python
@router.post("/admin/course-catalogs/{catalog_id}/resources/generations", status_code=202)
async def admin_generate_catalog_resources(
    catalog_id: str,
    req: CatalogResourceGenerateRequest,
    request: Request,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    catalog = await _get_admin_catalog_or_404(db, catalog_id)
    if catalog.status != "ready":
        raise _course_material_missing()
    if catalog.knowledge_status not in {"ready", "partial"}:
        raise _course_material_missing()
    if (catalog.chunk_count or 0) <= 0:
        raise _knowledge_base_empty()

    if req.resource_types:
        invalid_types = [item for item in req.resource_types if item not in RESOURCE_TYPES]
        if invalid_types:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": 42210, "message": "资源类型不合法", "data": {"invalid_types": invalid_types}},
            )

    offerings_result = await db.execute(
        select(CourseOffering)
        .where(
            CourseOffering.catalog_id == catalog.id,
            CourseOffering.is_deleted == False,
        )
        .order_by(CourseOffering.create_time.asc(), CourseOffering.id.asc())
    )
    offerings = offerings_result.scalars().all()
    fanout_course_ids = [offering.id for offering in offerings]
    if not fanout_course_ids:
        raise _course_offering_missing()

    task_result = {
        "catalog_id": catalog.id,
        "catalog_title": catalog.title,
        "fanout_course_ids": fanout_course_ids,
        "knowledge_status": catalog.knowledge_status,
        "degraded": catalog.knowledge_status == "partial",
        "chunk_count": catalog.chunk_count or 0,
    }
    if req.chapter:
        task_result["chapter"] = req.chapter
    if req.knowledge_point:
        task_result["knowledge_point"] = req.knowledge_point
    if req.resource_types:
        task_result["resource_types"] = req.resource_types

    task = AsyncTask(
        task_type="resource_generation",
        status="processing",
        progress=10,
        user_id=current_user.id,
        course_id=None,
        result=task_result,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)

    payload = {
        "task_id": task.id,
        "user_id": current_user.id,
        "course_id": catalog.id,
        "webhook_url": _webhook_url(request),
    }
    if req.chapter:
        payload["chapter"] = req.chapter
    if req.knowledge_point:
        payload["knowledge_point"] = req.knowledge_point
    if req.resource_types:
        payload["resource_types"] = req.resource_types

    try:
        await agent_client.post_json("/agent/v1/resources/generate", payload)
    except AgentServiceError as e:
        task.status = "failed"
        task.error_code = str(e.agent_code or "agent_error")
        task.error_message = e.message
        task.progress = 100
        await db.commit()
        return {
            "code": 202,
            "message": "accepted",
            "data": {"task_id": task.id, "catalog_id": catalog.id, "status": "processing"},
        }

    await db.commit()
    return {
        "code": 202,
        "message": "accepted",
        "data": {"task_id": task.id, "catalog_id": catalog.id, "status": "processing"},
    }
```

- [ ] **Step 4: Run backend generation tests**

Run:

```bash
cd ../backend
pytest tests/test_admin_catalog_resource_generation.py -q
```

Expected: generation endpoint tests pass; webhook and delete tests are not yet present.

- [ ] **Step 5: Commit backend endpoint**

```bash
git add ../backend/app/schemas/operations.py ../backend/app/api/v1/catalogs.py
git commit -m "新增管理员资源库资源生成接口"
```

---

## Task 3: Webhook Fan-Out Persistence And Task Permission

**Files:**
- Modify: `../backend/app/api/v1/webhooks.py`
- Modify: `../backend/app/api/v1/tasks.py`
- Test: `../backend/tests/test_admin_catalog_resource_generation.py`
- Test: `../backend/tests/test_resources_async.py`

- [ ] **Step 1: Add fan-out webhook test**

Append to `../backend/tests/test_admin_catalog_resource_generation.py`:

```python
def _webhook_headers() -> dict:
    from app.core.config import settings

    return {"X-Webhook-Secret": settings.WEBHOOK_SECRET}


@pytest.mark.asyncio
async def test_webhook_fanout_writes_resources_to_bound_classes():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    await _seed_user("teacher-admin-gen", "teacher")
    catalog_id = await _seed_ready_catalog()
    class_a = await _seed_bound_class(catalog_id=catalog_id, class_id="class-admin-gen-a")
    class_b = await _seed_bound_class(catalog_id=catalog_id, class_id="class-admin-gen-b")

    async with async_session_factory() as db:
        task = AsyncTask(
            id="task-admin-gen",
            task_type="resource_generation",
            status="processing",
            user_id="admin-admin-gen",
            course_id=None,
            result={
                "catalog_id": catalog_id,
                "fanout_course_ids": [class_a, class_b],
            },
        )
        db.add(task)
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/webhooks/agent",
            headers=_webhook_headers(),
            json={
                "task_id": "task-admin-gen",
                "task_type": "resource_generation",
                "status": "completed",
                "result": {
                    "resources": [
                        {
                            "title": "Catalog Doc",
                            "type": "document",
                            "description": "doc",
                            "content": "doc content",
                            "chapter": "树",
                            "knowledge_point": "二叉树",
                            "tags": ["catalog"],
                        }
                    ]
                },
            },
        )

    assert response.status_code == 200, response.text
    async with async_session_factory() as db:
        result = await db.execute(select(Resource).where(Resource.title == "Catalog Doc"))
        resources = result.scalars().all()
        assert sorted(resource.course_id for resource in resources) == [class_a, class_b]
        assert len(resources) == 2


@pytest.mark.asyncio
async def test_admin_can_poll_catalog_resource_generation_task():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    async with async_session_factory() as db:
        db.add(
            AsyncTask(
                id="task-admin-gen",
                task_type="resource_generation",
                status="processing",
                user_id="admin-admin-gen",
                course_id=None,
                result={"catalog_id": "catalog-admin-gen", "fanout_course_ids": []},
            )
        )
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/tasks/task-admin-gen",
            headers=_auth_headers("admin-admin-gen", "admin"),
        )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["task_type"] == "resource_generation"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd ../backend
pytest tests/test_admin_catalog_resource_generation.py::test_webhook_fanout_writes_resources_to_bound_classes tests/test_admin_catalog_resource_generation.py::test_admin_can_poll_catalog_resource_generation_task -q
```

Expected: fan-out test fails because webhook writes only `task.course_id`; task permission may already pass for owner admin or fail depending current permission branch.

- [ ] **Step 3: Update webhook fan-out logic**

In `../backend/app/api/v1/webhooks.py`, replace the resource insertion loop with:

```python
        fanout_course_ids = []
        if isinstance(task.result, dict):
            raw_fanout_course_ids = task.result.get("fanout_course_ids") or []
            if isinstance(raw_fanout_course_ids, list):
                fanout_course_ids = [str(course_id) for course_id in raw_fanout_course_ids if course_id]

        target_course_ids = fanout_course_ids or ([task.course_id] if task.course_id else [])
        if not target_course_ids:
            raise _bad_webhook_request("resource_generation 任务缺少 course_id")

        for target_course_id in target_course_ids:
            for r in resources_data:
                resource = Resource(
                    id=uuid.uuid4().hex[:16],
                    course_id=target_course_id,
                    title=r["title"],
                    type=r["type"],
                    description=r["description"],
                    tags=r["tags"],
                    chapter=r["chapter"],
                    knowledge_point=r["knowledge_point"],
                    content=r["content"],
                    url="",
                    create_by=task.user_id,
                )
                db.add(resource)
```

Keep the existing idempotency branch unchanged so completed tasks are not duplicated on repeated webhook calls.

- [ ] **Step 4: Update task polling permission**

In `../backend/app/api/v1/tasks.py`, replace `allowed_admin_task` with:

```python
        allowed_admin_task = current_user.role == "admin" and task.task_type in {
            "course_catalog_ingestion",
            "resource_generation",
        }
```

- [ ] **Step 5: Run webhook and existing resource tests**

Run:

```bash
cd ../backend
pytest tests/test_admin_catalog_resource_generation.py tests/test_resources_async.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit fan-out changes**

```bash
git add ../backend/app/api/v1/webhooks.py ../backend/app/api/v1/tasks.py ../backend/tests/test_admin_catalog_resource_generation.py
git commit -m "接入资源库生成结果班级分发"
```

---

## Task 4: Backend Soft Delete And Admin Resource List

**Files:**
- Modify: `../backend/app/api/v1/catalogs.py`
- Test: `../backend/tests/test_admin_catalog_resource_generation.py`

- [ ] **Step 1: Add failing tests for list and soft delete**

Append to `../backend/tests/test_admin_catalog_resource_generation.py`:

```python
@pytest.mark.asyncio
async def test_admin_catalog_resource_list_aggregates_bound_class_resources():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    await _seed_user("teacher-admin-gen", "teacher")
    catalog_id = await _seed_ready_catalog()
    class_a = await _seed_bound_class(catalog_id=catalog_id, class_id="class-admin-gen-a")
    class_b = await _seed_bound_class(catalog_id=catalog_id, class_id="class-admin-gen-b")
    async with async_session_factory() as db:
        db.add_all([
            Resource(id="resource-a", course_id=class_a, title="Doc A", type="document", description="a", tags=[], chapter="树", knowledge_point="二叉树", content="a"),
            Resource(id="resource-b", course_id=class_b, title="Doc B", type="document", description="b", tags=[], chapter="树", knowledge_point="二叉树", content="b"),
            Resource(id="resource-deleted", course_id=class_a, title="Deleted", type="document", description="d", tags=[], chapter="树", knowledge_point="二叉树", content="d", is_deleted=True),
        ])
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            f"/api/v1/admin/course-catalogs/{catalog_id}/resources",
            headers=_auth_headers("admin-admin-gen", "admin"),
        )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["total"] == 2
    assert [item["id"] for item in data["resources"]] == ["resource-b", "resource-a"]
    assert all(item["course_id"] in {class_a, class_b} for item in data["resources"])


@pytest.mark.asyncio
async def test_admin_soft_deletes_resource_and_hides_from_reads():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    await _seed_user("teacher-admin-gen", "teacher")
    catalog_id = await _seed_ready_catalog()
    class_id = await _seed_bound_class(catalog_id=catalog_id, class_id="class-admin-gen-a")
    async with async_session_factory() as db:
        db.add(Resource(id="resource-soft-delete", course_id=class_id, title="Delete Me", type="document", description="d", tags=[], chapter="树", knowledge_point="二叉树", content="d"))
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete(
            "/api/v1/admin/resources/resource-soft-delete",
            headers=_auth_headers("admin-admin-gen", "admin"),
        )
        list_response = await client.get(
            f"/api/v1/admin/course-catalogs/{catalog_id}/resources",
            headers=_auth_headers("admin-admin-gen", "admin"),
        )

    assert response.status_code == 200, response.text
    assert response.json()["data"] == {"id": "resource-soft-delete", "deleted": True}
    assert list_response.json()["data"]["resources"] == []
    async with async_session_factory() as db:
        resource = await db.get(Resource, "resource-soft-delete")
        assert resource.is_deleted is True
        assert resource.update_by == "admin-admin-gen"


@pytest.mark.asyncio
async def test_admin_soft_deletes_material_marks_catalog_dirty_without_changing_chunks():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    catalog_id = await _seed_ready_catalog(chunk_count=7)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete(
            f"/api/v1/admin/course-catalogs/{catalog_id}/materials/material-admin-gen",
            headers=_auth_headers("admin-admin-gen", "admin"),
        )
        materials_response = await client.get(
            f"/api/v1/admin/course-catalogs/{catalog_id}/materials",
            headers=_auth_headers("admin-admin-gen", "admin"),
        )
        status_response = await client.get(
            f"/api/v1/admin/course-catalogs/{catalog_id}/knowledge-status",
            headers=_auth_headers("admin-admin-gen", "admin"),
        )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["knowledge_status"] == "dirty"
    assert materials_response.json()["data"]["materials"] == []
    status_data = status_response.json()["data"]
    assert status_data["material_count"] == 0
    assert status_data["knowledge_status"] == "dirty"
    assert status_data["chunk_count"] == 7
    async with async_session_factory() as db:
        material = await db.get(CourseCatalogMaterial, "material-admin-gen")
        catalog = await db.get(CourseCatalog, catalog_id)
        assert material.is_deleted is True
        assert catalog.chunk_count == 7
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd ../backend
pytest tests/test_admin_catalog_resource_generation.py::test_admin_catalog_resource_list_aggregates_bound_class_resources tests/test_admin_catalog_resource_generation.py::test_admin_soft_deletes_resource_and_hides_from_reads tests/test_admin_catalog_resource_generation.py::test_admin_soft_deletes_material_marks_catalog_dirty_without_changing_chunks -q
```

Expected: FAIL with missing endpoints.

- [ ] **Step 3: Add catalog resource list endpoint**

In `../backend/app/api/v1/catalogs.py`, add:

```python
@router.get("/admin/course-catalogs/{catalog_id}/resources")
async def admin_list_catalog_resources(
    catalog_id: str,
    type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    await _get_admin_catalog_or_404(db, catalog_id)
    offering_result = await db.execute(
        select(CourseOffering.id).where(
            CourseOffering.catalog_id == catalog_id,
            CourseOffering.is_deleted == False,
        )
    )
    course_ids = list(offering_result.scalars().all())
    if not course_ids:
        return {
            "code": 200,
            "message": "success",
            "data": {"resources": [], "total": 0, "page": page, "page_size": page_size},
        }

    query = select(Resource).where(
        Resource.course_id.in_(course_ids),
        Resource.is_deleted == False,
    )
    if type:
        query = query.where(Resource.type == type)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
    result = await db.execute(
        query.order_by(Resource.create_time.desc(), Resource.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    resources = result.scalars().all()
    return {
        "code": 200,
        "message": "success",
        "data": {
            "resources": [
                {
                    "id": r.id,
                    "course_id": r.course_id,
                    "title": r.title,
                    "type": r.type,
                    "description": r.description or "",
                    "tags": r.tags or [],
                    "chapter": r.chapter,
                    "knowledge_point": r.knowledge_point,
                    "view_count": r.view_count,
                    "created_at": r.create_time.isoformat() if r.create_time else "",
                }
                for r in resources
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }
```

- [ ] **Step 4: Add material soft delete endpoint**

In `../backend/app/api/v1/catalogs.py`, add:

```python
@router.delete("/admin/course-catalogs/{catalog_id}/materials/{material_id}")
async def admin_delete_catalog_material(
    catalog_id: str,
    material_id: str,
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
            CourseCatalogMaterial.id == material_id,
            CourseCatalogMaterial.catalog_id == catalog.id,
            CourseCatalogMaterial.is_deleted == False,
        )
    )
    material = result.scalar_one_or_none()
    if material is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40400, "message": "课程资源库资料不存在", "data": None},
        )

    material.is_deleted = True
    remaining_count = (
        await db.execute(
            select(func.count())
            .select_from(CourseCatalogMaterial)
            .where(
                CourseCatalogMaterial.catalog_id == catalog.id,
                CourseCatalogMaterial.is_deleted == False,
                CourseCatalogMaterial.id != material.id,
            )
        )
    ).scalar() or 0
    catalog.material_count = remaining_count
    if catalog.knowledge_status in {"ready", "partial"}:
        catalog.knowledge_status = "dirty"
    catalog.last_error = None
    await db.commit()

    return {
        "code": 200,
        "message": "deleted",
        "data": {
            "id": material.id,
            "catalog_id": catalog.id,
            "deleted": True,
            "knowledge_status": catalog.knowledge_status,
        },
    }
```

- [ ] **Step 5: Add Admin resource soft delete endpoint**

In `../backend/app/api/v1/catalogs.py`, add this endpoint near the other Admin catalog management endpoints. This route belongs in `catalogs.py` because that router prefix is `/api/v1`; adding it to `resources.py` would place it under `/api/v1/resources/...` and create the wrong URL.

```python
@router.delete("/admin/resources/{resource_id}")
async def admin_delete_resource(
    resource_id: str,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Resource).where(Resource.id == resource_id, Resource.is_deleted == False)
    )
    resource = result.scalar_one_or_none()
    if resource is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40400, "message": "资源不存在", "data": None},
        )

    resource.is_deleted = True
    resource.update_by = current_user.id
    await db.commit()
    return {"code": 200, "message": "deleted", "data": {"id": resource.id, "deleted": True}}
```

- [ ] **Step 6: Run backend tests**

Run:

```bash
cd ../backend
pytest tests/test_admin_catalog_resource_generation.py tests/test_course_catalog_ingestion.py tests/test_resources_async.py -q
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit soft delete and list endpoints**

```bash
git add ../backend/app/api/v1/catalogs.py ../backend/tests/test_admin_catalog_resource_generation.py
git commit -m "接入资源库资源列表和软删除接口"
```

---

## Task 5: OpenAPI And Client API Markdown

**Files:**
- Modify: `../docs/10-client-api/Client-API.openapi.json`
- Modify: `../docs/10-client-api/API_前端接口规范.md`

- [ ] **Step 1: Update OpenAPI paths**

In `../docs/10-client-api/Client-API.openapi.json`, add these paths:

```json
{
  "/admin/course-catalogs/{catalog_id}/resources": {
    "get": {
      "tags": ["CourseCatalogs"],
      "summary": "管理员课程资源库生成资源列表",
      "parameters": [
        {"name": "catalog_id", "in": "path", "required": true, "schema": {"type": "string"}},
        {"name": "type", "in": "query", "schema": {"type": "string"}},
        {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}},
        {"name": "page_size", "in": "query", "schema": {"type": "integer", "default": 20}}
      ],
      "responses": {
        "200": {
          "description": "成功",
          "content": {
            "application/json": {
              "schema": {"$ref": "#/components/schemas/AdminCatalogResourcesResponse"}
            }
          }
        }
      },
      "security": [{"bearerAuth": []}]
    }
  },
  "/admin/course-catalogs/{catalog_id}/resources/generations": {
    "post": {
      "tags": ["CourseCatalogs"],
      "summary": "管理员触发课程资源库学习资源生成",
      "description": "Admin-only。基于 CourseCatalog 已入库知识生成标准学习资源。生成结果按当前绑定该 CourseCatalog 的教学班 fan-out 写入 resources；生成后才绑定的教学班不会自动回补。无绑定教学班时返回 409。",
      "parameters": [
        {"name": "catalog_id", "in": "path", "required": true, "schema": {"type": "string"}}
      ],
      "requestBody": {
        "required": true,
        "content": {
          "application/json": {
            "schema": {"$ref": "#/components/schemas/CatalogResourceGenerateRequest"}
          }
        }
      },
      "responses": {
        "202": {
          "description": "已接受",
          "content": {
            "application/json": {
              "schema": {"$ref": "#/components/schemas/CatalogResourceGenerationResponse"}
            }
          }
        },
        "409": {"description": "资源库未就绪、知识库为空或尚未绑定教学班"},
        "422": {"description": "资源类型不合法"}
      },
      "security": [{"bearerAuth": []}]
    }
  },
  "/admin/course-catalogs/{catalog_id}/materials/{material_id}": {
    "delete": {
      "tags": ["CourseCatalogs"],
      "summary": "管理员软删除课程资源库资料",
      "description": "仅软删除资料记录，不删除上传文件，不删除 Qdrant chunks，不回滚 chunk_count。ready/partial 资源库删除资料后 knowledge_status 变为 dirty。",
      "parameters": [
        {"name": "catalog_id", "in": "path", "required": true, "schema": {"type": "string"}},
        {"name": "material_id", "in": "path", "required": true, "schema": {"type": "string"}}
      ],
      "responses": {
        "200": {
          "description": "已删除",
          "content": {
            "application/json": {
              "schema": {"$ref": "#/components/schemas/CourseCatalogMaterialDeleteResponse"}
            }
          }
        },
        "409": {"description": "课程资源库正在入库中"}
      },
      "security": [{"bearerAuth": []}]
    }
  },
  "/admin/resources/{resource_id}": {
    "delete": {
      "tags": ["Resources"],
      "summary": "管理员软删除学习资源",
      "description": "仅设置 Resource.is_deleted=true，不删除数据库行、文件、Qdrant chunks 或 Agent 产物。",
      "parameters": [
        {"name": "resource_id", "in": "path", "required": true, "schema": {"type": "string"}}
      ],
      "responses": {
        "200": {
          "description": "已删除",
          "content": {
            "application/json": {
              "schema": {"$ref": "#/components/schemas/AdminResourceDeleteResponse"}
            }
          }
        },
        "404": {"description": "资源不存在"}
      },
      "security": [{"bearerAuth": []}]
    }
  }
}
```

- [ ] **Step 2: Add OpenAPI schemas**

Add component schemas:

```json
{
  "CatalogResourceGenerateRequest": {
    "type": "object",
    "properties": {
      "chapter": {"type": "string"},
      "knowledge_point": {"type": "string"},
      "resource_types": {
        "type": "array",
        "items": {"type": "string", "enum": ["document", "mindmap", "reading", "code"]}
      }
    }
  },
  "CatalogResourceGenerationAccepted": {
    "type": "object",
    "properties": {
      "task_id": {"type": "string"},
      "catalog_id": {"type": "string"},
      "status": {"type": "string"}
    }
  },
  "CatalogResourceGenerationResponse": {
    "type": "object",
    "properties": {
      "code": {"type": "integer"},
      "message": {"type": "string"},
      "data": {"$ref": "#/components/schemas/CatalogResourceGenerationAccepted"}
    }
  },
  "AdminCatalogResourceItem": {
    "type": "object",
    "properties": {
      "id": {"type": "string"},
      "course_id": {"type": "string"},
      "title": {"type": "string"},
      "type": {"type": "string"},
      "description": {"type": "string"},
      "tags": {"type": "array", "items": {"type": "string"}},
      "chapter": {"type": "string"},
      "knowledge_point": {"type": "string"},
      "view_count": {"type": "integer"},
      "created_at": {"type": "string", "format": "date-time"}
    }
  },
  "AdminCatalogResourcesResponse": {
    "type": "object",
    "properties": {
      "code": {"type": "integer"},
      "message": {"type": "string"},
      "data": {
        "type": "object",
        "properties": {
          "resources": {
            "type": "array",
            "items": {"$ref": "#/components/schemas/AdminCatalogResourceItem"}
          },
          "total": {"type": "integer"},
          "page": {"type": "integer"},
          "page_size": {"type": "integer"}
        }
      }
    }
  },
  "AdminResourceDeleteResponse": {
    "type": "object",
    "properties": {
      "code": {"type": "integer"},
      "message": {"type": "string"},
      "data": {
        "type": "object",
        "properties": {
          "id": {"type": "string"},
          "deleted": {"type": "boolean"}
        }
      }
    }
  },
  "CourseCatalogMaterialDeleteResponse": {
    "type": "object",
    "properties": {
      "code": {"type": "integer"},
      "message": {"type": "string"},
      "data": {
        "type": "object",
        "properties": {
          "id": {"type": "string"},
          "catalog_id": {"type": "string"},
          "deleted": {"type": "boolean"},
          "knowledge_status": {"type": "string", "enum": ["draft", "ingesting", "ready", "dirty", "partial", "failed"]}
        }
      }
    }
  }
}
```

Ensure `CourseCatalogKnowledgeStatusResponse.data.knowledge_status` description or enum includes `dirty`.

- [ ] **Step 3: Update API Markdown**

In `../docs/10-client-api/API_前端接口规范.md`, add sections under CourseCatalog/Admin:

```markdown
### 管理员触发课程资源库学习资源生成

POST /api/v1/admin/course-catalogs/:catalog_id/resources/generations

说明：Admin-only。基于 CourseCatalog 已入库知识生成标准学习资源。Backend 将生成结果 fan-out 写入当前绑定该资源库的教学班 resources；生成后才绑定的教学班不会自动回补。无绑定教学班时返回 409。

### 管理员课程资源库生成资源列表

GET /api/v1/admin/course-catalogs/:catalog_id/resources

说明：聚合当前绑定教学班下未软删除的生成资源，供 Admin 在资源库抽屉中管理。

### 管理员软删除学习资源

DELETE /api/v1/admin/resources/:resource_id

说明：仅设置 Resource.is_deleted=true，不删除数据库行、文件、Qdrant chunks 或 Agent 产物。

### 管理员软删除课程资源库资料

DELETE /api/v1/admin/course-catalogs/:catalog_id/materials/:material_id

说明：仅隐藏资料记录，不删除上传文件，不删除 Qdrant chunks，不回滚 chunk_count。ready/partial 资源库删除资料后 knowledge_status=dirty。
```

- [ ] **Step 4: Validate OpenAPI JSON**

Run:

```bash
python -m json.tool ../docs/10-client-api/Client-API.openapi.json >/tmp/client-api-openapi-check.json
```

Expected: command exits 0.

- [ ] **Step 5: Commit contract updates**

```bash
git add ../docs/10-client-api/Client-API.openapi.json ../docs/10-client-api/API_前端接口规范.md
git commit -m "同步资源库生成软删除接口契约"
```

---

## Task 6: Frontend Services And Drawer UI

**Files:**
- Modify: `src/api/services/admin.js`
- Modify: `src/components/admin/CourseCatalogDrawer.jsx`
- Test: `e2e/specs.spec.js`

- [ ] **Step 1: Add admin service methods**

In `src/api/services/admin.js`, add:

```javascript
  getCourseCatalogResources: async (catalogId, params) => {
    return apiClient.get(`/admin/course-catalogs/${catalogId}/resources`, { params });
  },

  startCourseCatalogResourceGeneration: async (catalogId, data) => {
    return apiClient.post(`/admin/course-catalogs/${catalogId}/resources/generations`, data);
  },

  deleteCourseCatalogMaterial: async (catalogId, materialId) => {
    return apiClient.delete(`/admin/course-catalogs/${catalogId}/materials/${materialId}`);
  },

  deleteResource: async (resourceId) => {
    return apiClient.delete(`/admin/resources/${resourceId}`);
  },
```

Keep the existing methods unchanged.

- [ ] **Step 2: Add drawer state**

In `src/components/admin/CourseCatalogDrawer.jsx`, add state:

```javascript
  const [resources, setResources] = useState([]);
  const [resourceLoading, setResourceLoading] = useState(false);
  const [resourceError, setResourceError] = useState('');
  const [generationForm, setGenerationForm] = useState({
    chapter: '',
    knowledge_point: '',
    resource_types: ['document', 'mindmap', 'reading', 'code']
  });
  const [generationTask, setGenerationTask] = useState(null);
  const [generating, setGenerating] = useState(false);
  const generationOperationSeqRef = useRef(0);
```

Reset these fields in the existing `useEffect` that resets drawer state when `open/catalogId` changes.

- [ ] **Step 3: Fetch resources with details**

Add callback:

```javascript
  const refreshResources = useCallback(async () => {
    if (!catalogId || !open) return false;
    setResourceLoading(true);
    setResourceError('');
    try {
      const res = await adminService.getCourseCatalogResources(catalogId);
      setResources(res.data?.resources || []);
      return true;
    } catch (err) {
      console.error('course catalog resources fetch error', err);
      setResourceError(getErrorMessage(err, '课程资源加载失败'));
      setResources([]);
      return false;
    } finally {
      setResourceLoading(false);
    }
  }, [catalogId, open]);
```

Call `refreshResources()` in the drawer open effect after `refreshDetails()`.

- [ ] **Step 4: Add generation handlers**

Add:

```javascript
  const canGenerateResources = (
    !generating
    && !taskProcessing
    && !catalogIngesting
    && (knowledgeStatus?.status || catalog?.status) === 'ready'
    && ['ready', 'partial'].includes(knowledgeStatus?.knowledge_status || catalog?.knowledge_status)
    && Number(summary.chunk_count || 0) > 0
  );

  const handleResourceTypeToggle = (type) => {
    setGenerationForm((prev) => {
      const selected = new Set(prev.resource_types);
      if (selected.has(type)) {
        selected.delete(type);
      } else {
        selected.add(type);
      }
      return { ...prev, resource_types: Array.from(selected) };
    });
  };

  const handleStartResourceGeneration = async () => {
    if (!catalogId || !canGenerateResources || generationForm.resource_types.length === 0) return;
    const operationSeq = generationOperationSeqRef.current + 1;
    generationOperationSeqRef.current = operationSeq;
    setGenerating(true);
    setTaskError('');
    setError('');
    try {
      const payload = {
        resource_types: generationForm.resource_types
      };
      if (generationForm.chapter.trim()) payload.chapter = generationForm.chapter.trim();
      if (generationForm.knowledge_point.trim()) payload.knowledge_point = generationForm.knowledge_point.trim();
      const res = await adminService.startCourseCatalogResourceGeneration(catalogId, payload);
      if (generationOperationSeqRef.current !== operationSeq) return;
      const task = normalizeTask({
        ...res.data,
        task_type: 'resource_generation',
        progress: 10
      });
      setGenerationTask(task);
    } catch (err) {
      console.error('course catalog resource generation start error', err);
      if (generationOperationSeqRef.current !== operationSeq) return;
      setTaskError(getErrorMessage(err, '学习资源生成启动失败'));
      setGenerating(false);
    }
  };
```

- [ ] **Step 5: Poll generation task**

Add a `useEffect` similar to ingestion polling:

```javascript
  useEffect(() => {
    if (!open || !generationTask?.task_id || generationTask.status === 'completed' || generationTask.status === 'failed') return;

    let cancelled = false;
    let timeoutId;

    const pollGenerationTask = async () => {
      try {
        const res = await taskService.getTaskStatus(generationTask.task_id);
        if (cancelled) return;
        const task = normalizeTask(res.data, generationTask.task_id);
        setGenerationTask(task);
        if (task.status === 'completed' || task.status === 'failed') {
          setGenerating(false);
          if (task.status === 'failed') {
            setTaskError(task.error_message || '学习资源生成失败');
          }
          await refreshResources();
          if (!cancelled && onChanged) onChanged();
        } else {
          timeoutId = setTimeout(pollGenerationTask, 2000);
        }
      } catch (err) {
        if (cancelled) return;
        console.error('course catalog resource generation task poll error', err);
        setTaskError(getErrorMessage(err, '生成任务状态查询失败，正在重试'));
        timeoutId = setTimeout(pollGenerationTask, 2000);
      }
    };

    timeoutId = setTimeout(pollGenerationTask, 2000);
    return () => {
      cancelled = true;
      clearTimeout(timeoutId);
    };
  }, [generationTask?.status, generationTask?.task_id, onChanged, open, refreshResources]);
```

- [ ] **Step 6: Add soft delete handlers**

Add:

```javascript
  const handleDeleteMaterial = async (material) => {
    if (!catalogId || !material?.id) return;
    const confirmed = window.confirm('仅隐藏资料记录，不删除上传文件或历史向量切片。确定删除？');
    if (!confirmed) return;
    try {
      await adminService.deleteCourseCatalogMaterial(catalogId, material.id);
      await refreshDetails();
      if (onChanged) onChanged();
    } catch (err) {
      console.error('course catalog material delete error', err);
      setError(getErrorMessage(err, '资料删除失败'));
    }
  };

  const handleDeleteResource = async (resource) => {
    if (!resource?.id) return;
    const confirmed = window.confirm('仅隐藏学习资源，不删除底层产物。确定删除？');
    if (!confirmed) return;
    try {
      await adminService.deleteResource(resource.id);
      await refreshResources();
    } catch (err) {
      console.error('course catalog resource delete error', err);
      setResourceError(getErrorMessage(err, '资源删除失败'));
    }
  };
```

- [ ] **Step 7: Add UI sections**

In the drawer body, insert a "生成学习资源" section after the ingestion task section:

```jsx
          <section className="mt-5 rounded-lg border border-slate-200 bg-white p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 className="text-sm font-bold text-slate-900">生成学习资源</h3>
                <p className="mt-1 text-xs text-slate-500">基于已入库资料生成资源库标准学习资源。</p>
              </div>
              <button
                data-testid="catalog-start-resource-generation"
                type="button"
                onClick={handleStartResourceGeneration}
                disabled={!canGenerateResources || generationForm.resource_types.length === 0}
                className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  !canGenerateResources || generationForm.resource_types.length === 0
                    ? 'cursor-not-allowed bg-slate-100 text-slate-400'
                    : 'cursor-pointer bg-cyan-600 text-white hover:bg-cyan-700'
                }`}
              >
                <span className={`material-symbols-outlined text-[18px] ${generating ? 'animate-spin' : ''}`}>
                  {generating ? 'progress_activity' : 'auto_awesome'}
                </span>
                {generating ? '生成中' : '生成学习资源'}
              </button>
            </div>
            <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
              <input
                value={generationForm.chapter}
                onChange={(event) => setGenerationForm((prev) => ({ ...prev, chapter: event.target.value }))}
                placeholder="章节，可选"
                className="rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-cyan-500"
              />
              <input
                value={generationForm.knowledge_point}
                onChange={(event) => setGenerationForm((prev) => ({ ...prev, knowledge_point: event.target.value }))}
                placeholder="知识点，可选"
                className="rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-cyan-500"
              />
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {[
                ['document', '讲义'],
                ['mindmap', '思维导图'],
                ['reading', '拓展阅读'],
                ['code', '代码示例']
              ].map(([type, label]) => (
                <button
                  key={type}
                  type="button"
                  onClick={() => handleResourceTypeToggle(type)}
                  className={`rounded border px-3 py-1.5 text-xs font-bold ${
                    generationForm.resource_types.includes(type)
                      ? 'border-cyan-200 bg-cyan-50 text-cyan-700'
                      : 'border-slate-200 bg-white text-slate-500'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
            {generationTask && (
              <div data-testid="catalog-generation-task-status" className="mt-4 rounded-lg bg-slate-50 p-3 text-sm">
                <div className="flex justify-between gap-3">
                  <span className="text-slate-500">status</span>
                  <span className={`rounded border px-2 py-0.5 text-xs font-bold ${getBadgeClass(generationTask.status)}`}>{formatTaskStatus(generationTask.status)}</span>
                </div>
              </div>
            )}
          </section>
```

Add a "生成资源" list section after that:

```jsx
          <section className="mt-5 rounded-lg border border-slate-200 bg-white">
            <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-4 py-3">
              <h3 className="text-sm font-bold text-slate-900">生成资源</h3>
              {resourceLoading && <span className="text-xs text-slate-400">加载中...</span>}
            </div>
            {resourceError && <div className="mx-4 mt-3 rounded bg-red-50 px-3 py-2 text-xs text-red-700">{resourceError}</div>}
            <div className="max-h-72 overflow-y-auto">
              {resources.length === 0 ? (
                <div className="px-4 py-8 text-center text-sm text-slate-400">暂无生成资源</div>
              ) : (
                <div className="divide-y divide-slate-100">
                  {resources.map((resource) => (
                    <div key={resource.id} data-testid="catalog-resource-row" className="flex items-start justify-between gap-3 px-4 py-3">
                      <div className="min-w-0">
                        <div className="break-words text-sm font-semibold text-slate-900">{resource.title || '未命名资源'}</div>
                        <div className="mt-1 flex flex-wrap gap-2 text-xs text-slate-500">
                          <span>{resource.type}</span>
                          <span>{resource.chapter || '未分章节'}</span>
                          <span>{resource.knowledge_point || '未分知识点'}</span>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleDeleteResource(resource)}
                        className="flex-shrink-0 rounded-lg px-2 py-1 text-xs font-bold text-red-600 hover:bg-red-50"
                      >
                        删除
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>
```

Add a delete button to each material row:

```jsx
                        <button
                          type="button"
                          onClick={() => handleDeleteMaterial(material)}
                          disabled={catalogIngesting || ingesting || taskProcessing}
                          className="ml-2 flex-shrink-0 rounded-lg px-2 py-1 text-xs font-bold text-red-600 hover:bg-red-50 disabled:cursor-not-allowed disabled:text-slate-300"
                        >
                          删除
                        </button>
```

- [ ] **Step 8: Run frontend checks**

Run:

```bash
npm run lint
npm run build
```

Expected: lint passes; build passes with only existing Vite chunk size warning if present.

- [ ] **Step 9: Commit frontend drawer UI**

```bash
git add src/api/services/admin.js src/components/admin/CourseCatalogDrawer.jsx
git commit -m "接入资源库生成和软删除界面"
```

---

## Task 7: Frontend E2E Coverage

**Files:**
- Modify: `e2e/specs.spec.js`

- [ ] **Step 1: Add E2E test for generation and soft delete**

Append to `e2e/specs.spec.js`:

```javascript
  test('Admin course catalog resource generation and soft delete controls', async ({ page }) => {
    let generationStarted = false;
    let generationPollCount = 0;
    let materialDeleted = false;
    let resourceDeleted = false;

    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'e2e-admin-token');
    });

    await page.route('**/api/v1/users/me', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          id: 'admin-e2e',
          email: 'admin@example.com',
          username: 'Admin E2E',
          role: 'admin',
        },
      }));
    });

    await page.route('**/api/v1/admin/users**', async (route) => {
      await route.fulfill(jsonResponse({ code: 200, message: 'success', data: { users: [] } }));
    });

    await page.route('**/api/v1/admin/logs/**', async (route) => {
      await route.fulfill(jsonResponse({ code: 200, message: 'success', data: { logs: [] } }));
    });

    await page.route('**/api/v1/admin/course-catalogs', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          catalogs: [{
            id: 'catalog-e2e-gen',
            title: 'E2E 生成资源库',
            description: '资源生成回归测试',
            status: 'ready',
            knowledge_status: materialDeleted ? 'dirty' : 'ready',
            material_count: materialDeleted ? 0 : 1,
            chunk_count: 6,
            created_at: '2026-06-09T10:00:00Z',
          }],
          total: 1,
          page: 1,
          page_size: 20,
        },
      }));
    });

    await page.route('**/api/v1/admin/course-catalogs/catalog-e2e-gen/materials', async (route) => {
      if (route.request().method() === 'DELETE') {
        materialDeleted = true;
        await route.fulfill(jsonResponse({
          code: 200,
          message: 'deleted',
          data: { id: 'material-e2e-gen', catalog_id: 'catalog-e2e-gen', deleted: true, knowledge_status: 'dirty' },
        }));
        return;
      }

      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          materials: materialDeleted ? [] : [{
            id: 'material-e2e-gen',
            filename: 'lesson.md',
            source_type: 'file',
            file_size: 256,
            status: 'ingested',
            chunk_count: 6,
            created_at: '2026-06-09T10:01:00Z',
          }],
        },
      }));
    });

    await page.route('**/api/v1/admin/course-catalogs/catalog-e2e-gen/materials/material-e2e-gen', async (route) => {
      materialDeleted = true;
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'deleted',
        data: { id: 'material-e2e-gen', catalog_id: 'catalog-e2e-gen', deleted: true, knowledge_status: 'dirty' },
      }));
    });

    await page.route('**/api/v1/admin/course-catalogs/catalog-e2e-gen/knowledge-status', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          status: 'ready',
          knowledge_status: materialDeleted ? 'dirty' : 'ready',
          material_count: materialDeleted ? 0 : 1,
          chunk_count: 6,
          pending_material_count: 0,
          failed_material_count: 0,
          last_ingestion_task_id: null,
          last_ingestion_status: null,
        },
      }));
    });

    await page.route('**/api/v1/admin/course-catalogs/catalog-e2e-gen/resources', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          resources: generationStarted && !resourceDeleted ? [{
            id: 'resource-e2e-gen',
            course_id: 'class-e2e-gen',
            title: '二叉树讲义',
            type: 'document',
            description: '生成讲义',
            tags: [],
            chapter: '树',
            knowledge_point: '二叉树',
            view_count: 0,
            created_at: '2026-06-09T10:02:00Z',
          }] : [],
          total: generationStarted && !resourceDeleted ? 1 : 0,
          page: 1,
          page_size: 20,
        },
      }));
    });

    await page.route('**/api/v1/admin/course-catalogs/catalog-e2e-gen/resources/generations', async (route) => {
      generationStarted = true;
      await route.fulfill(jsonResponse({
        code: 202,
        message: 'accepted',
        data: { task_id: 'task-e2e-gen', catalog_id: 'catalog-e2e-gen', status: 'processing' },
      }, 202));
    });

    await page.route('**/api/v1/tasks/task-e2e-gen', async (route) => {
      generationPollCount += 1;
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          task_id: 'task-e2e-gen',
          task_type: 'resource_generation',
          status: generationPollCount >= 1 ? 'completed' : 'processing',
          progress: 100,
        },
      }));
    });

    await page.route('**/api/v1/admin/resources/resource-e2e-gen', async (route) => {
      resourceDeleted = true;
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'deleted',
        data: { id: 'resource-e2e-gen', deleted: true },
      }));
    });

    page.on('dialog', async (dialog) => {
      await dialog.accept();
    });

    await page.goto('/admin');
    await page.getByRole('button', { name: '课程资源库' }).click();
    await page.getByRole('button', { name: '管理资料' }).click();

    await expect(page.getByTestId('catalog-drawer')).toBeVisible();
    await expect(page.getByText('生成学习资源')).toBeVisible();
    await page.getByTestId('catalog-start-resource-generation').click();
    await expect(page.getByTestId('catalog-generation-task-status').getByText('已完成')).toBeVisible({ timeout: 7000 });
    await expect(page.getByText('二叉树讲义')).toBeVisible();

    await page.getByTestId('catalog-resource-row').getByRole('button', { name: '删除' }).click();
    await expect(page.getByText('暂无生成资源')).toBeVisible();

    await page.getByTestId('catalog-material-row').getByRole('button', { name: '删除' }).click();
    await expect(page.getByText('暂无资料')).toBeVisible();
  });
```

- [ ] **Step 2: Add TeacherConsole no-generation assertion**

Append to `e2e/specs.spec.js`:

```javascript
  test('Teacher console does not expose resource generation entry', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'e2e-teacher-token');
    });

    await page.route('**/api/v1/users/me', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          id: 'teacher-e2e',
          email: 'teacher@example.com',
          username: 'Teacher E2E',
          role: 'teacher',
        },
      }));
    });

    await page.route('**/api/v1/courses**', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          courses: [{
            id: 'class-e2e',
            name: 'E2E 教学班',
            title: 'E2E 教学班',
            topic: '数据结构',
            students: 0,
            catalog_id: 'catalog-e2e',
            catalog_title: 'E2E 资源库',
          }],
        },
      }));
    });

    await page.route('**/api/v1/teaching/classes/class-e2e/students', async (route) => {
      await route.fulfill(jsonResponse({ code: 200, message: 'success', data: [] }));
    });

    await page.route('**/api/v1/teaching/classes/class-e2e/insights', async (route) => {
      await route.fulfill(jsonResponse({ code: 200, message: 'success', data: {} }));
    });

    await page.goto('/teacher');
    await expect(page.getByText('教学控制台')).toBeVisible();
    await expect(page.getByRole('button', { name: /生成学习资源|生成资源|资源生成/ })).toHaveCount(0);
  });
```

- [ ] **Step 3: Run targeted E2E**

Run:

```bash
npm run test:e2e -- e2e/specs.spec.js -g "Admin course catalog resource generation|Teacher console does not expose"
```

Expected: both tests pass.

- [ ] **Step 4: Commit E2E coverage**

```bash
git add e2e/specs.spec.js
git commit -m "补充资源库生成软删除前端回归"
```

---

## Task 8: Documentation And Final Verification

**Files:**
- Modify: `docs/feature-ledger.md`
- Modify: `docs/project-direction.md`
- Modify: `docs/project-coverage-audit.md`
- Modify: `WORKFLOW.md`

- [ ] **Step 1: Update feature ledger**

In `docs/feature-ledger.md`:

- Change Admin row to mention generated resource management.
- Add `CourseCatalogDrawer.jsx` calls:
  - `GET /admin/course-catalogs/{catalog_id}/resources`
  - `POST /admin/course-catalogs/{catalog_id}/resources/generations`
  - `DELETE /admin/resources/{resource_id}`
  - `DELETE /admin/course-catalogs/{catalog_id}/materials/{material_id}`
- Keep `/resources/generate` and `/quiz/generate` marked as frontend deprecated/not connected.
- Add note that Admin generation fan-outs only to currently bound teaching classes and does not backfill later classes.

- [ ] **Step 2: Update project direction and coverage audit**

In `docs/project-direction.md`:

- Add Admin catalog resource generation to completed/current direction after implementation.
- Keep teacher no-generation constraint.
- Add fan-out boundary.

In `docs/project-coverage-audit.md`:

- Add evidence row for Admin catalog resource generation.
- Add evidence for soft delete.
- Record that deletion is surface-only and does not clean files/Qdrant.

- [ ] **Step 3: Update workflow**

In `WORKFLOW.md`, add a dated entry:

```markdown
- 2026-06-09：Admin CourseCatalog 资源生成与软删除接入：
  - 新增 Admin 资源库侧学习资源生成入口，生成结果按当前绑定教学班 fan-out 写入 `resources`。
  - 新增 Admin 生成资源列表、资源软删除、资料软删除；删除均为表面软删除，不删除文件、不删除 Qdrant、不回滚 `chunk_count`。
  - 教师端仍不提供资源生成入口，历史 `/resources/generate` 仍为前端不接入。
  - 验证：填写本轮实际运行命令和结果。
```

Replace the final verification line with actual command results after Step 4.

- [ ] **Step 4: Run final verification**

Run:

```bash
cd ../backend
pytest tests/test_admin_catalog_resource_generation.py tests/test_course_catalog_ingestion.py tests/test_resources_async.py tests/test_course_catalog_ready_gate.py -q
```

Run:

```bash
python -m json.tool ../docs/10-client-api/Client-API.openapi.json >/tmp/client-api-openapi-check.json
```

Run:

```bash
npm run lint
npm run build
npm run test:e2e -- e2e/specs.spec.js -g "Admin course catalog resource generation|Admin course catalog ingestion polling|Teacher console does not expose"
```

Expected:

- Backend selected tests pass.
- OpenAPI JSON validates.
- Frontend lint passes.
- Frontend build passes, allowing existing Vite chunk size warning.
- Targeted E2E tests pass.

- [ ] **Step 5: Commit docs**

```bash
git add docs/feature-ledger.md docs/project-direction.md docs/project-coverage-audit.md WORKFLOW.md
git commit -m "记录资源库生成软删除进度"
```

- [ ] **Step 6: Final status check**

Run:

```bash
git status --short --branch
git log --oneline -5
```

Expected:

- Only pre-existing unrelated untracked files remain.
- Recent commits show the implementation batches from this plan.

## Execution Notes

- Before any code edit, output the AGENTS.md-required review block: problem analysis, planned files, modification approach, affected features, and planned test commands.
- Do not modify `.env`, upload files, storage output, Qdrant data, MySQL volume, build output, caches, or `node_modules`.
- Do not commit `../backend/storage/`, uploaded files, or unrelated untracked files.
- Do not push.
- If a test fails because MySQL or other services are unavailable, record the exact failure and run the closest SQLite-compatible targeted tests where possible.
