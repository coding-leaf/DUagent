# Phase B Ready Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gate resource generation and Quiz generation on the bound CourseCatalog knowledge base so generation never silently falls back to generic content when course materials are missing.

**Architecture:** Add one shared backend gate helper that resolves a teaching class `course_id` to `CourseOffering.catalog_id`, validates `CourseCatalog.status/knowledge_status/chunk_count`, and returns the catalog id used for Agent retrieval. Apply it to `/resources/generate` and `/quiz/generate`, keep persisted Backend data scoped to the teaching class id, and update API contracts plus orphan frontend service methods.

**Tech Stack:** FastAPI, SQLAlchemy async ORM, Pydantic, pytest/httpx ASGI tests, OpenAPI 3.0 JSON, React/Vite service modules.

---

## Source Spec

Implement against:

- `docs/superpowers/specs/2026-06-08-course-catalog-ready-gate-baseline.md`
- `docs/superpowers/specs/2026-06-08-phase-b-ready-gate-design.md`
- `AGENTS.md`

Do not add TeacherConsole or Quiz generation UI in this phase.

## File Map

Backend:

- Create `../backend/app/services/course_catalog_gate.py`
  - Owns shared CourseCatalog ready gate and error shapes.
- Create `../backend/tests/test_course_catalog_ready_gate.py`
  - Unit-style async tests for every ready gate state.
- Modify `../backend/app/api/v1/resources.py`
  - Resolve catalog before task creation; send catalog id to Agent.
- Modify `../backend/app/api/v1/quiz.py`
  - Resolve catalog before task creation.
- Modify `../backend/app/services/quiz_service.py`
  - Keep personalization class-scoped while sending Agent catalog id.
- Modify or extend `../backend/tests/test_resources_async.py`
  - Cover resource gate rejection and Agent payload id.
- Modify `../backend/tests/test_agent_integration.py`
  - Cover Quiz gate rejection, Agent payload id, and persisted class id.

Contracts:

- Modify `../docs/10-client-api/Client-API.openapi.json`
  - Update descriptions and 409 responses.
- Modify `../docs/10-client-api/API_前端接口规范.md`
  - Mirror ready gate behavior for frontend integration.

Frontend:

- Modify `src/api/services/learning.js`
  - Remove orphan `triggerResourceGeneration()` and orphan `getTaskStatus()`.

Progress:

- Modify `WORKFLOW.md`
  - Record Phase B implementation, tests, and contract status.

## Pre-Code Review Output Required

Before editing runtime code, output this review summary to the user per `AGENTS.md`:

```text
问题分析：CourseCatalog 入库链路已完成，但资源生成和 Quiz 生成仍直接使用教学班 course_id 调 Agent，没有解析 CourseOffering.catalog_id，也没有校验 CourseCatalog knowledge_status/chunk_count，存在无资料时泛化生成风险。
计划修改的文件：../backend/app/services/course_catalog_gate.py、../backend/app/api/v1/resources.py、../backend/app/api/v1/quiz.py、../backend/app/services/quiz_service.py、后端相关 pytest、../docs/10-client-api/Client-API.openapi.json、../docs/10-client-api/API_前端接口规范.md、src/api/services/learning.js、WORKFLOW.md。
修改方案：先写共享 ready gate 测试和 helper；再分别接入 resources/generate 与 quiz/generate；同步 OpenAPI/接口规范；删除前端孤儿 service；最后运行后端目标测试、OpenAPI JSON 校验、前端 lint/build。
可能影响的功能：legacy 未绑定 CourseCatalog 的课程将不能触发资源生成或 Quiz 生成；已有资源列表、题库读取、提交练习、课程绑定和 Admin 入库 UI 不应改变。
计划运行的测试命令：pytest tests/test_course_catalog_ready_gate.py -q；pytest tests/test_resources_async.py -q；pytest tests/test_agent_integration.py -q；python -m json.tool ../docs/10-client-api/Client-API.openapi.json；npm run lint；npm run build。
```

## Task 1: Shared CourseCatalog Ready Gate

**Files:**

- Create: `../backend/tests/test_course_catalog_ready_gate.py`
- Create: `../backend/app/services/course_catalog_gate.py`

- [ ] **Step 1: Write failing ready gate tests**

Create `../backend/tests/test_course_catalog_ready_gate.py`:

```python
import os
import sys

import pytest
from fastapi import HTTPException

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:////tmp/course_catalog_ready_gate.db",
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.base import Base
from app.db.session import async_engine, async_session_factory
from app.models.catalog import CourseCatalog, CourseOffering
from app.models.course import Course
from app.models.user import User


async def _reset_db():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def _seed_course_with_catalog(
    *,
    catalog_status="ready",
    knowledge_status="ready",
    chunk_count=3,
    with_offering=True,
    with_catalog=True,
    catalog_deleted=False,
):
    async with async_session_factory() as db:
        teacher = User(
            id="teacher-ready-gate",
            email="teacher-ready-gate@example.com",
            username="teacher_ready_gate",
            hashed_password="x",
            role="teacher",
        )
        course = Course(
            id="class-ready-gate",
            name="Ready Gate Class",
            course_code="RGCLASS1",
            teacher_id=teacher.id,
        )
        db.add_all([teacher, course])
        if with_catalog:
            catalog = CourseCatalog(
                id="catalog-ready-gate",
                title="Ready Gate Catalog",
                status=catalog_status,
                knowledge_status=knowledge_status,
                chunk_count=chunk_count,
                is_deleted=catalog_deleted,
            )
            db.add(catalog)
        if with_offering:
            db.add(CourseOffering(
                id=course.id,
                name=course.name,
                catalog_id="catalog-ready-gate",
                teacher_id=teacher.id,
                class_code=course.course_code,
            ))
        await db.commit()
    return "class-ready-gate"


async def _resolve(course_id):
    from app.services.course_catalog_gate import resolve_generation_catalog

    async with async_session_factory() as db:
        return await resolve_generation_catalog(db, course_id)


def _detail(exc: HTTPException):
    return exc.detail


@pytest.mark.asyncio
async def test_missing_course_offering_returns_course_catalog_missing():
    await _reset_db()
    course_id = await _seed_course_with_catalog(with_offering=False)

    with pytest.raises(HTTPException) as exc:
        await _resolve(course_id)

    assert exc.value.status_code == 404
    assert _detail(exc.value)["code"] == "course_catalog_missing"


@pytest.mark.asyncio
async def test_missing_catalog_returns_course_catalog_missing():
    await _reset_db()
    course_id = await _seed_course_with_catalog(with_catalog=False)

    with pytest.raises(HTTPException) as exc:
        await _resolve(course_id)

    assert exc.value.status_code == 404
    assert _detail(exc.value)["code"] == "course_catalog_missing"


@pytest.mark.asyncio
async def test_deleted_catalog_returns_course_catalog_missing():
    await _reset_db()
    course_id = await _seed_course_with_catalog(catalog_deleted=True)

    with pytest.raises(HTTPException) as exc:
        await _resolve(course_id)

    assert exc.value.status_code == 404
    assert _detail(exc.value)["code"] == "course_catalog_missing"


@pytest.mark.asyncio
@pytest.mark.parametrize("catalog_status", ["draft", "ingesting", "failed"])
async def test_non_ready_catalog_status_returns_course_material_missing(catalog_status):
    await _reset_db()
    course_id = await _seed_course_with_catalog(catalog_status=catalog_status)

    with pytest.raises(HTTPException) as exc:
        await _resolve(course_id)

    assert exc.value.status_code == 409
    assert _detail(exc.value)["code"] == "course_material_missing"


@pytest.mark.asyncio
@pytest.mark.parametrize("knowledge_status", ["draft", "dirty", "ingesting", "failed"])
async def test_unusable_knowledge_status_returns_course_material_missing(knowledge_status):
    await _reset_db()
    course_id = await _seed_course_with_catalog(knowledge_status=knowledge_status)

    with pytest.raises(HTTPException) as exc:
        await _resolve(course_id)

    assert exc.value.status_code == 409
    assert _detail(exc.value)["code"] == "course_material_missing"


@pytest.mark.asyncio
@pytest.mark.parametrize("knowledge_status", ["ready", "partial"])
async def test_usable_status_with_zero_chunks_returns_knowledge_base_empty(knowledge_status):
    await _reset_db()
    course_id = await _seed_course_with_catalog(
        knowledge_status=knowledge_status,
        chunk_count=0,
    )

    with pytest.raises(HTTPException) as exc:
        await _resolve(course_id)

    assert exc.value.status_code == 409
    assert _detail(exc.value)["code"] == "knowledge_base_empty"


@pytest.mark.asyncio
async def test_ready_catalog_with_chunks_is_allowed():
    await _reset_db()
    course_id = await _seed_course_with_catalog(knowledge_status="ready", chunk_count=3)

    context = await _resolve(course_id)

    assert context.class_course_id == course_id
    assert context.catalog_id == "catalog-ready-gate"
    assert context.catalog_title == "Ready Gate Catalog"
    assert context.knowledge_status == "ready"
    assert context.chunk_count == 3
    assert context.degraded is False


@pytest.mark.asyncio
async def test_partial_catalog_with_chunks_is_allowed_as_degraded():
    await _reset_db()
    course_id = await _seed_course_with_catalog(knowledge_status="partial", chunk_count=2)

    context = await _resolve(course_id)

    assert context.catalog_id == "catalog-ready-gate"
    assert context.knowledge_status == "partial"
    assert context.chunk_count == 2
    assert context.degraded is True
```

- [ ] **Step 2: Run ready gate tests and verify they fail**

Run:

```bash
cd ../backend
pytest tests/test_course_catalog_ready_gate.py -q
```

Expected: fail with `ModuleNotFoundError: No module named 'app.services.course_catalog_gate'`.

- [ ] **Step 3: Implement the shared gate helper**

Create `../backend/app/services/course_catalog_gate.py`:

```python
from pydantic import BaseModel
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import CourseCatalog, CourseOffering


class GenerationCatalogContext(BaseModel):
    class_course_id: str
    catalog_id: str
    catalog_title: str
    knowledge_status: str
    degraded: bool
    chunk_count: int


def _catalog_missing() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "course_catalog_missing",
            "message": "课程未绑定可用资源库",
            "data": None,
        },
    )


def _material_missing() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "course_material_missing",
            "message": "课程资料尚未完成入库",
            "data": None,
        },
    )


def _knowledge_empty() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "knowledge_base_empty",
            "message": "课程知识库为空",
            "data": None,
        },
    )


async def resolve_generation_catalog(
    db: AsyncSession,
    course_id: str,
) -> GenerationCatalogContext:
    offering_result = await db.execute(
        select(CourseOffering).where(
            CourseOffering.id == course_id,
            CourseOffering.is_deleted == False,
        )
    )
    offering = offering_result.scalar_one_or_none()
    if offering is None:
        raise _catalog_missing()

    catalog_result = await db.execute(
        select(CourseCatalog).where(
            CourseCatalog.id == offering.catalog_id,
            CourseCatalog.is_deleted == False,
        )
    )
    catalog = catalog_result.scalar_one_or_none()
    if catalog is None:
        raise _catalog_missing()

    if catalog.status != "ready":
        raise _material_missing()
    if catalog.knowledge_status not in {"ready", "partial"}:
        raise _material_missing()

    chunk_count = catalog.chunk_count or 0
    if chunk_count <= 0:
        raise _knowledge_empty()

    return GenerationCatalogContext(
        class_course_id=course_id,
        catalog_id=catalog.id,
        catalog_title=catalog.title,
        knowledge_status=catalog.knowledge_status,
        degraded=catalog.knowledge_status == "partial",
        chunk_count=chunk_count,
    )
```

- [ ] **Step 4: Run ready gate tests and verify they pass**

Run:

```bash
cd ../backend
pytest tests/test_course_catalog_ready_gate.py -q
```

Expected: pass.

- [ ] **Step 5: Commit Task 1**

```bash
git add ../backend/app/services/course_catalog_gate.py ../backend/tests/test_course_catalog_ready_gate.py
git commit -m "新增课程资源库生成前置校验"
```

## Task 2: Resource Generation Ready Gate

**Files:**

- Modify: `../backend/app/api/v1/resources.py`
- Modify: `../backend/tests/test_resources_async.py`

- [ ] **Step 1: Add resource generation gate regression tests**

Append these helpers and tests near the top-level helpers in `../backend/tests/test_resources_async.py`. Keep existing tests intact.

```python
from app.models.catalog import CourseCatalog, CourseOffering
from app.models.course import Course


async def _create_ready_catalog_bound_course(
    teacher_id: str,
    *,
    catalog_status: str = "ready",
    knowledge_status: str = "ready",
    chunk_count: int = 3,
):
    suffix = uuid.uuid4().hex[:8]
    async with async_session_factory() as db:
        course = Course(
            id=f"rg-course-{suffix}",
            name="Resource Gate Course",
            course_code=f"RG{suffix[:6]}",
            teacher_id=teacher_id,
        )
        catalog = CourseCatalog(
            id=f"rg-catalog-{suffix}",
            title="Resource Gate Catalog",
            status=catalog_status,
            knowledge_status=knowledge_status,
            chunk_count=chunk_count,
        )
        offering = CourseOffering(
            id=course.id,
            name=course.name,
            catalog_id=catalog.id,
            teacher_id=teacher_id,
            class_code=course.course_code,
        )
        db.add_all([course, catalog, offering])
        await db.commit()
        return course.id, catalog.id
```

Add these checks inside the existing `test()` coroutine after teacher login and before the current resource success section:

```python
        # =============================================
        # 1a. resources/generate rejects missing CourseCatalog binding
        # =============================================
        print("\n-- 1a. resources/generate ready gate rejects legacy course --")
        r = await client.post("/api/v1/courses", json={"name": "Legacy Generate Course"}, headers=headers)
        legacy_course_id = r.json()["data"]["id"]
        before_tasks = await _count_tasks("resource_generation")
        r = await client.post("/api/v1/resources/generate", json={
            "course_id": legacy_course_id,
        }, headers=headers)
        after_tasks = await _count_tasks("resource_generation")
        chk("generate legacy course → 404", r.status_code == 404)
        chk("generate legacy course → course_catalog_missing",
            r.json()["detail"]["code"] == "course_catalog_missing")
        chk("generate legacy course → no task created", after_tasks == before_tasks)

        # =============================================
        # 1b. resources/generate rejects dirty catalog
        # =============================================
        print("\n-- 1b. resources/generate ready gate rejects dirty catalog --")
        dirty_course_id, _ = await _create_ready_catalog_bound_course(
            user_id,
            knowledge_status="dirty",
            chunk_count=3,
        )
        before_tasks = await _count_tasks("resource_generation")
        r = await client.post("/api/v1/resources/generate", json={
            "course_id": dirty_course_id,
        }, headers=headers)
        after_tasks = await _count_tasks("resource_generation")
        chk("generate dirty catalog → 409", r.status_code == 409)
        chk("generate dirty catalog → course_material_missing",
            r.json()["detail"]["code"] == "course_material_missing")
        chk("generate dirty catalog → no task created", after_tasks == before_tasks)

        # =============================================
        # 1c. resources/generate sends catalog id to Agent
        # =============================================
        print("\n-- 1c. resources/generate sends catalog id to Agent --")
        ready_course_id, ready_catalog_id = await _create_ready_catalog_bound_course(
            user_id,
            knowledge_status="partial",
            chunk_count=4,
        )
        with patch("app.api.v1.resources.agent_client.post_json", new_callable=AsyncMock) as mock_agent:
            mock_agent.return_value = {"task_id": "ignored", "estimated_duration": 60}
            r = await client.post("/api/v1/resources/generate", json={
                "course_id": ready_course_id,
                "resource_types": ["document"],
            }, headers=headers)
            chk("generate ready catalog → 202", r.status_code == 202)
            payload = mock_agent.await_args.args[1]
            chk("generate ready catalog → Agent course_id is catalog id",
                payload.get("course_id") == ready_catalog_id)
            task_id = r.json()["data"]["task_id"]
            rt = await client.get(f"/api/v1/tasks/{task_id}", headers=headers)
            td = rt.json()["data"]
            chk("generate ready catalog → task course context class id",
                td["result"]["class_course_id"] == ready_course_id)
            chk("generate ready catalog → task catalog id recorded",
                td["result"]["catalog_id"] == ready_catalog_id)
            chk("generate partial catalog → degraded recorded",
                td["result"]["degraded"] is True)
```

Also add this helper near the existing `chk` helper:

```python
    async def _count_tasks(task_type):
        async with async_session_factory() as db:
            result = await db.execute(
                select(AsyncTask).where(
                    AsyncTask.task_type == task_type,
                    AsyncTask.is_deleted == False,
                )
            )
            return len(result.scalars().all())
```

Then change the existing current resource success setup so it uses a bound ready catalog:

```python
        course_id, _ = await _create_ready_catalog_bound_course(user_id)
```

instead of creating a legacy course through `POST /api/v1/courses`.

- [ ] **Step 2: Run resource tests and verify they fail**

Run:

```bash
cd ../backend
pytest tests/test_resources_async.py -q
```

Expected: fail because `/resources/generate` still does not use the gate and sends class `course_id` to Agent.

- [ ] **Step 3: Apply ready gate in resources endpoint**

Modify `../backend/app/api/v1/resources.py`.

Add import:

```python
from app.services.course_catalog_gate import resolve_generation_catalog
```

At the start of `generate_resources()`, before creating `AsyncTask`, add:

```python
    catalog_context = await resolve_generation_catalog(db, req.course_id)
```

When creating `AsyncTask`, keep `course_id=req.course_id` and add initial `result`:

```python
        result={
            "class_course_id": catalog_context.class_course_id,
            "catalog_id": catalog_context.catalog_id,
            "catalog_title": catalog_context.catalog_title,
            "knowledge_status": catalog_context.knowledge_status,
            "degraded": catalog_context.degraded,
            "chunk_count": catalog_context.chunk_count,
        },
```

In Agent payload, change:

```python
        "course_id": req.course_id,
```

to:

```python
        "course_id": catalog_context.catalog_id,
```

Keep `task.course_id` as the class id.

- [ ] **Step 4: Run ready gate and resource tests**

Run:

```bash
cd ../backend
pytest tests/test_course_catalog_ready_gate.py tests/test_resources_async.py -q
```

Expected: pass.

- [ ] **Step 5: Commit Task 2**

```bash
git add ../backend/app/api/v1/resources.py ../backend/tests/test_resources_async.py
git commit -m "接入资源生成资源库 ready 校验"
```

## Task 3: Quiz Generation Ready Gate

**Files:**

- Modify: `../backend/app/api/v1/quiz.py`
- Modify: `../backend/app/services/quiz_service.py`
- Modify: `../backend/tests/test_agent_integration.py`

- [ ] **Step 1: Add Quiz generation gate tests**

In `../backend/tests/test_agent_integration.py`, import catalog models near other model imports:

```python
from app.models.catalog import CourseCatalog, CourseOffering
```

Add helper inside `TestQuizGenerateIntegration`:

```python
    async def _setup_student_with_bound_catalog_course(
        self,
        client,
        *,
        knowledge_status="ready",
        chunk_count=3,
    ):
        s_h, course_id = await self._setup_student_with_course(client)
        async with async_session_factory() as db:
            course_result = await db.execute(select(Course).where(Course.id == course_id))
            course = course_result.scalar_one()
            catalog = CourseCatalog(
                id=f"quiz-catalog-{uuid.uuid4().hex[:8]}",
                title="Quiz Catalog",
                status="ready",
                knowledge_status=knowledge_status,
                chunk_count=chunk_count,
            )
            offering = CourseOffering(
                id=course.id,
                name=course.name,
                catalog_id=catalog.id,
                teacher_id=course.teacher_id,
                class_code=course.course_code,
            )
            db.add_all([catalog, offering])
            await db.commit()
            return s_h, course_id, catalog.id
```

If `Course` and `select` are not already imported in the file, add:

```python
from sqlalchemy import select
from app.models.course import Course
```

Add tests inside `TestQuizGenerateIntegration`:

```python
    @pytest.mark.asyncio
    async def test_quiz_generate_rejects_legacy_course_without_catalog(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            s_h, course_id = await self._setup_student_with_course(client)

            before_count = await self._count_tasks("quiz_generation")
            r = await client.post("/api/v1/quiz/generate", headers=s_h, json={
                "course_id": course_id,
                "count": 3,
                "personalized": True,
            })
            after_count = await self._count_tasks("quiz_generation")

            assert r.status_code == 404
            assert r.json()["detail"]["code"] == "course_catalog_missing"
            assert after_count == before_count

    @pytest.mark.asyncio
    async def test_quiz_generate_rejects_empty_knowledge_base(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            s_h, course_id, _ = await self._setup_student_with_bound_catalog_course(
                client,
                knowledge_status="ready",
                chunk_count=0,
            )

            r = await client.post("/api/v1/quiz/generate", headers=s_h, json={
                "course_id": course_id,
                "count": 3,
                "personalized": True,
            })

            assert r.status_code == 409
            assert r.json()["detail"]["code"] == "knowledge_base_empty"

    @pytest.mark.asyncio
    async def test_quiz_generate_sends_catalog_id_to_agent_and_persists_class_id(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            s_h, course_id, catalog_id = await self._setup_student_with_bound_catalog_course(
                client,
                knowledge_status="partial",
                chunk_count=5,
            )

            with patch("app.api.v1.quiz.agent_client.post_json", new_callable=AsyncMock) as mock_agent:
                mock_agent.return_value = {
                    "questions": [{
                        "chapter": "树",
                        "knowledge_point": "红黑树",
                        "type": "single_choice",
                        "difficulty": "medium",
                        "content": "红黑树的根节点是什么颜色？",
                        "options": ["红色", "黑色"],
                        "answer": "B",
                        "explanation": "根节点必须为黑色。",
                    }]
                }

                r = await client.post("/api/v1/quiz/generate", headers=s_h, json={
                    "course_id": course_id,
                    "count": 1,
                    "personalized": True,
                })

            assert r.status_code == 202
            payload = mock_agent.await_args.args[1]
            assert payload["course_id"] == catalog_id
            assert payload["class_course_id"] == course_id

            async with async_session_factory() as db:
                result = await db.execute(
                    select(QuizQuestion).where(
                        QuizQuestion.course_id == course_id,
                        QuizQuestion.knowledge_point == "红黑树",
                        QuizQuestion.is_deleted == False,
                    )
                )
                assert result.scalar_one_or_none() is not None
```

Add `_count_tasks()` method in `TestQuizGenerateIntegration`:

```python
    async def _count_tasks(self, task_type):
        async with async_session_factory() as db:
            result = await db.execute(
                select(AsyncTask).where(
                    AsyncTask.task_type == task_type,
                    AsyncTask.is_deleted == False,
                )
            )
            return len(result.scalars().all())
```

Ensure these imports exist:

```python
from unittest.mock import AsyncMock, patch
from app.models.others import AsyncTask
from app.models.quiz import QuizQuestion
```

- [ ] **Step 2: Run Quiz tests and verify they fail**

Run:

```bash
cd ../backend
pytest tests/test_agent_integration.py::TestQuizGenerateIntegration -q
```

Expected: fail because `/quiz/generate` does not gate and does not send catalog id.

- [ ] **Step 3: Apply ready gate in quiz endpoint**

Modify `../backend/app/api/v1/quiz.py`.

Add import:

```python
from app.services.course_catalog_gate import resolve_generation_catalog
```

At the start of `generate_questions()`, before creating `AsyncTask`, add:

```python
    catalog_context = await resolve_generation_catalog(db, req.course_id)
```

Change payload assembly call from:

```python
        payload = await quiz_service.assemble_generate_payload(current_user.id, req.course_id, req, db)
```

to:

```python
        payload = await quiz_service.assemble_generate_payload(
            current_user.id,
            req.course_id,
            req,
            db,
            knowledge_course_id=catalog_context.catalog_id,
            catalog_context={
                "class_course_id": catalog_context.class_course_id,
                "catalog_id": catalog_context.catalog_id,
                "catalog_title": catalog_context.catalog_title,
                "knowledge_status": catalog_context.knowledge_status,
                "degraded": catalog_context.degraded,
                "chunk_count": catalog_context.chunk_count,
            },
        )
```

When creating `AsyncTask`, keep `course_id=req.course_id` and add:

```python
        result={
            "class_course_id": catalog_context.class_course_id,
            "catalog_id": catalog_context.catalog_id,
            "catalog_title": catalog_context.catalog_title,
            "knowledge_status": catalog_context.knowledge_status,
            "degraded": catalog_context.degraded,
            "chunk_count": catalog_context.chunk_count,
        },
```

- [ ] **Step 4: Update quiz payload assembly**

Modify signature in `../backend/app/services/quiz_service.py`:

```python
async def assemble_generate_payload(
    user_id: str,
    course_id: str,
    req: QuizGenerateRequest,
    db: AsyncSession,
    *,
    knowledge_course_id: str | None = None,
    catalog_context: dict | None = None,
) -> dict:
```

Change initial payload from:

```python
    payload: dict = {
        "user_id": user_id,
        "course_id": course_id,
    }
```

to:

```python
    payload: dict = {
        "user_id": user_id,
        "course_id": knowledge_course_id or course_id,
    }
    if catalog_context:
        payload["class_course_id"] = catalog_context["class_course_id"]
        payload["catalog_id"] = catalog_context["catalog_id"]
        payload["knowledge_status"] = catalog_context["knowledge_status"]
        payload["degraded"] = catalog_context["degraded"]
```

Do not change any SQL queries in this function; they must continue using the teaching class `course_id`.

- [ ] **Step 5: Run gate/resource/Quiz tests**

Run:

```bash
cd ../backend
pytest tests/test_course_catalog_ready_gate.py tests/test_resources_async.py tests/test_agent_integration.py::TestQuizGenerateIntegration -q
```

Expected: pass.

- [ ] **Step 6: Commit Task 3**

```bash
git add ../backend/app/api/v1/quiz.py ../backend/app/services/quiz_service.py ../backend/tests/test_agent_integration.py
git commit -m "接入题目生成资源库 ready 校验"
```

## Task 4: Contract And Frontend Cleanup

**Files:**

- Modify: `../docs/10-client-api/Client-API.openapi.json`
- Modify: `../docs/10-client-api/API_前端接口规范.md`
- Modify: `src/api/services/learning.js`

- [ ] **Step 1: Update OpenAPI JSON**

Modify `../docs/10-client-api/Client-API.openapi.json`:

For `/resources/generate`:

- Replace stale description with:

```text
仅教师，异步生成课程级学习资料，Agent 完成后通过 Webhook 回调。该接口不生成个性化题目；个性化题目走 /quiz/generate。Backend 会根据教学班 course_id 解析绑定的 CourseCatalog，并要求课程资源库知识库可用：status=ready 且 knowledge_status=ready，或 status=ready、knowledge_status=partial 且 chunk_count>0。请求通过校验后，Backend 保持任务 course_id 为教学班 ID，并将 CourseCatalog.id 作为 Agent 知识检索 course_id。若资源库未绑定、资料未完成入库或知识库为空，请求在创建任务前失败。
```

- Add `409` response:

```json
"409": {
  "description": "课程资源库未就绪或知识库为空",
  "content": {
    "application/json": {
      "schema": {
        "$ref": "#/components/schemas/ErrorResponse"
      },
      "examples": {
        "course_material_missing": {
          "summary": "课程资料尚未完成入库",
          "value": {
            "detail": {
              "code": "course_material_missing",
              "message": "课程资料尚未完成入库",
              "data": null
            }
          }
        },
        "knowledge_base_empty": {
          "summary": "课程知识库为空",
          "value": {
            "detail": {
              "code": "knowledge_base_empty",
              "message": "课程知识库为空",
              "data": null
            }
          }
        }
      }
    }
  }
}
```

For `/quiz/generate`:

- Add description text explaining the same CourseCatalog ready gate.
- Add equivalent `409` response.
- Ensure a `404` response documents `course_catalog_missing` where the endpoint response map allows it.

Add a new schema named `BusinessHTTPErrorResponse` because existing `HTTPErrorResponse.detail.code` is numeric while Phase B errors use string codes:

```json
"BusinessHTTPErrorResponse": {
  "type": "object",
  "properties": {
    "detail": {
      "type": "object",
      "properties": {
        "code": {
          "type": "string",
          "description": "业务错误码"
        },
        "message": {
          "type": "string",
          "description": "错误信息"
        },
        "data": {
          "type": "object",
          "nullable": true,
          "description": "固定为 null",
          "example": null
        }
      }
    }
  }
}
```

Use `#/components/schemas/BusinessHTTPErrorResponse` for the new `/resources/generate` and `/quiz/generate` 404/409 ready gate responses.

- [ ] **Step 2: Validate OpenAPI JSON**

Run from `frontend/`:

```bash
python -m json.tool ../docs/10-client-api/Client-API.openapi.json >/tmp/client-api-openapi-check.json
```

Expected: exits 0.

- [ ] **Step 3: Update frontend API markdown spec**

Modify `../docs/10-client-api/API_前端接口规范.md` sections for:

- `POST /api/v1/quiz/generate`
- `POST /api/v1/resources/generate`

Add this shared note to both sections:

```markdown
**CourseCatalog ready gate：**

Backend 会先根据教学班 `course_id` 解析绑定的 `CourseOffering.catalog_id`，再检查对应 `CourseCatalog`：

- `status=ready` 且 `knowledge_status=ready`，允许生成；
- `status=ready` 且 `knowledge_status=partial` 且 `chunk_count>0`，允许降级生成；
- `knowledge_status=dirty/draft/failed/ingesting`，拒绝生成；
- `chunk_count<=0`，拒绝生成。

拒绝发生在创建异步任务前，因此不会返回 `task_id`。

错误：

- `404 course_catalog_missing`：课程未绑定可用资源库；
- `409 course_material_missing`：课程资料尚未完成入库；
- `409 knowledge_base_empty`：课程知识库为空。
```

- [ ] **Step 4: Remove orphan frontend learning service methods**

Modify `src/api/services/learning.js` to remove:

```js
  triggerResourceGeneration(params) {
    return apiClient.post('/resources/generate', params);
  },
  getTaskStatus(taskId) {
    return apiClient.get(`/tasks/${taskId}`);
  },
```

Keep the rest of `learningService` unchanged.

- [ ] **Step 5: Run contract and frontend checks**

Run:

```bash
python -m json.tool ../docs/10-client-api/Client-API.openapi.json >/tmp/client-api-openapi-check.json
npm run lint
npm run build
```

Expected: JSON check passes; lint passes; build passes with only the existing Vite chunk-size warning.

- [ ] **Step 6: Commit Task 4**

```bash
git add ../docs/10-client-api/Client-API.openapi.json ../docs/10-client-api/API_前端接口规范.md src/api/services/learning.js
git commit -m "同步生成 ready 校验契约"
```

## Task 5: Final Verification And Workflow

**Files:**

- Modify: `WORKFLOW.md`

- [ ] **Step 1: Run final targeted backend tests**

Run:

```bash
cd ../backend
pytest tests/test_course_catalog_ready_gate.py tests/test_resources_async.py tests/test_agent_integration.py::TestQuizGenerateIntegration -q
```

Expected: pass.

- [ ] **Step 2: Run final frontend and contract checks**

Run from `frontend/`:

```bash
python -m json.tool ../docs/10-client-api/Client-API.openapi.json >/tmp/client-api-openapi-check.json
npm run lint
npm run build
```

Expected: JSON check passes; lint passes; build passes with only the existing Vite chunk-size warning.

- [ ] **Step 3: Update WORKFLOW.md**

Add a `2026-06-08` entry under `## 最近验证`:

```markdown
- 2026-06-08：Phase B 资源生成 / Quiz 生成前置 CourseCatalog ready 校验完成：
  - Backend 新增共享 CourseCatalog ready gate：教学班 `course_id` 先解析 `CourseOffering.catalog_id`，仅 `status=ready` 且 `knowledge_status=ready` 或 `partial+chunk_count>0` 允许生成；`dirty/draft/failed/ingesting` 和空知识库在创建任务前拒绝。
  - `POST /resources/generate` 与 `POST /quiz/generate` 共用该校验；Backend task 仍记录教学班 course_id，Agent payload 使用 CourseCatalog id 作为知识检索 course_id。
  - OpenAPI 与前端接口规范已同步 `course_catalog_missing`、`course_material_missing`、`knowledge_base_empty` 错误语义；前端删除未使用的 `learningService.triggerResourceGeneration()` / `getTaskStatus()` 孤儿方法。
  - 验证：`pytest tests/test_course_catalog_ready_gate.py tests/test_resources_async.py tests/test_agent_integration.py::TestQuizGenerateIntegration -q` 通过；`python -m json.tool ../docs/10-client-api/Client-API.openapi.json` 通过；`npm run lint` / `npm run build` 通过，仍有既有 Vite chunk size warning。
  - 契约状态：Client API 已同步；未新增 Client API 请求字段；Agent API 未新增字段，沿用 `course_id` 承载知识检索 id。
```

Update `## 下一步建议`:

```markdown
- Phase B ready gate 已完成后，下一主线仍不应直接扩 UI；优先单独设计 LearningPath/KG 与 CourseCatalog 同源化，或设计 `source_refs` 记录和 ResourceDetail 来源展示。
```

- [ ] **Step 4: Check workflow diff**

Run:

```bash
git diff --check -- WORKFLOW.md
```

Expected: pass.

- [ ] **Step 5: Commit Task 5**

```bash
git add WORKFLOW.md
git commit -m "记录生成 ready 校验完成"
```

## Final Review

After all tasks:

- Run `git status --short`.
- Verify only unrelated pre-existing untracked files remain.
- Run final code review over the full implementation.
