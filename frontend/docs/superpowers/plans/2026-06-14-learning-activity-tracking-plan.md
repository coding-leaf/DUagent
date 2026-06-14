# Learning Activity Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add real event-level learning activity tracking so `/learning-effects` can aggregate resource and node study duration from persisted student activity.

**Architecture:** Add a dedicated backend `LearningActivity` table and `POST /api/v1/learning-activities` endpoint. Frontend pages report best-effort activity events through the existing authenticated Axios client, and evaluation aggregation adds activity duration to KG node progress without changing mastery scoring.

**Tech Stack:** FastAPI, SQLAlchemy async ORM, MySQL migration SQL, Pydantic, React 19, React Router, Axios, Playwright, OpenAPI JSON.

---

## File Structure

- Create `../backend/app/schemas/learning_activity.py`
  - Request and response DTOs for single-event activity submission.
- Create `../backend/app/api/v1/learning_activities.py`
  - Authenticated endpoint, course/resource validation, node-name resolution, activity persistence.
- Modify `../backend/app/models/others.py`
  - Add `LearningActivity` model and indexes.
- Create `../backend/migrations/2026-06-14-add-learning-activities.sql`
  - MySQL table creation for production/dev databases.
- Modify `../backend/app/main.py`
  - Include the new router.
- Modify `../backend/app/api/v1/evaluation.py`
  - Aggregate `LearningActivity.duration_seconds`, visit count, and latest activity into node progress.
- Create `../backend/tests/test_learning_activities.py`
  - API validation and authorization integration coverage.
- Modify `../backend/tests/test_refresh_async.py`
  - Evaluation regression proving activity duration feeds `node_progress.study_duration_seconds`.
- Modify `../docs/10-client-api/Client-API.openapi.json`
  - Add `/learning-activities`, request schema, response schema.
- Modify `../docs/10-client-api/API_前端接口规范.md`
  - Document endpoint, event types, duration rules, and evaluation relationship.
- Create `src/api/services/learningActivity.js`
  - Frontend tracking service with non-blocking error handling.
- Modify `src/pages/ResourceDetail.jsx`
  - Send `resource_view` after load and `resource_study` on cleanup when elapsed time is at least 5 seconds.
- Modify `src/pages/LearningPath.jsx`
  - Send `node_view` when a user selects a KG node, excluding the default initial selection.
- Modify `src/pages/Quiz.jsx`
  - Measure quiz elapsed time, submit real `time_spent`, send node practice events.
- Modify `e2e/specs.spec.js`
  - Route-driven tests for frontend activity calls and non-blocking tracking failure.
- Modify `WORKFLOW.md`
  - Record the implementation and verification.
- Modify `docs/feature-ledger.md`
  - Update `/learning-effects` progress and next risk if the feature state changes.

---

## Task 1: Backend Model And Migration

**Files:**
- Modify: `../backend/app/models/others.py`
- Create: `../backend/migrations/2026-06-14-add-learning-activities.sql`
- Test: `../backend/tests/test_learning_activities.py`

- [ ] **Step 1: Write the failing schema/model test**

Create `../backend/tests/test_learning_activities.py` with the initial metadata test:

```python
import os

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "mysql+aiomysql://root:123456@127.0.0.1:3306/duagent?charset=utf8mb4",
)

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_learning_activity_model_shape():
    from app.models.others import LearningActivity

    table = LearningActivity.__table__
    assert table.name == "learning_activities"

    columns = table.columns
    for name in [
        "id",
        "user_id",
        "course_id",
        "node_id",
        "node_name",
        "resource_id",
        "activity_type",
        "duration_seconds",
        "occurred_at",
        "metadata",
        "create_time",
        "update_time",
        "is_deleted",
    ]:
        assert name in columns

    indexes = {index.name: tuple(column.name for column in index.columns) for index in table.indexes}
    assert indexes["idx_learning_activities_user_course_node"] == (
        "user_id",
        "course_id",
        "node_id",
        "is_deleted",
    )
    assert indexes["idx_learning_activities_type_time"] == (
        "user_id",
        "course_id",
        "activity_type",
        "occurred_at",
    )
    assert indexes["idx_learning_activities_resource"] == ("resource_id", "is_deleted")
```

- [ ] **Step 2: Run the test to verify it fails**

Run from `../backend`:

```bash
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/learning_activity_model_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_learning_activities.py::test_learning_activity_model_shape -q -p no:cacheprovider
```

Expected: `ImportError` or `AttributeError` because `LearningActivity` does not exist.

- [ ] **Step 3: Add the ORM model**

In `../backend/app/models/others.py`, add this class after `Resource`:

```python
class LearningActivity(Base):
    __tablename__ = "learning_activities"
    __table_args__ = (
        Index(
            "idx_learning_activities_user_course_node",
            "user_id",
            "course_id",
            "node_id",
            "is_deleted",
        ),
        Index(
            "idx_learning_activities_type_time",
            "user_id",
            "course_id",
            "activity_type",
            "occurred_at",
        ),
        Index("idx_learning_activities_resource", "resource_id", "is_deleted"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False)
    course_id: Mapped[str] = mapped_column(String(32), ForeignKey("courses.id"), nullable=False)
    node_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    node_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("resources.id"), nullable=True)
    activity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    create_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    update_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    update_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
```

- [ ] **Step 4: Add the MySQL migration**

Create `../backend/migrations/2026-06-14-add-learning-activities.sql`:

```sql
CREATE TABLE IF NOT EXISTS learning_activities (
  id VARCHAR(32) NOT NULL PRIMARY KEY,
  user_id VARCHAR(32) NOT NULL,
  course_id VARCHAR(32) NOT NULL,
  node_id VARCHAR(64) NULL,
  node_name VARCHAR(100) NULL,
  resource_id VARCHAR(32) NULL,
  activity_type VARCHAR(40) NOT NULL,
  duration_seconds INT NULL,
  occurred_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  metadata JSON NULL,
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  create_by VARCHAR(32) NULL,
  update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  update_by VARCHAR(32) NULL,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT fk_learning_activities_user FOREIGN KEY (user_id) REFERENCES users(id),
  CONSTRAINT fk_learning_activities_course FOREIGN KEY (course_id) REFERENCES courses(id),
  CONSTRAINT fk_learning_activities_resource FOREIGN KEY (resource_id) REFERENCES resources(id),
  INDEX idx_learning_activities_user_course_node (user_id, course_id, node_id, is_deleted),
  INDEX idx_learning_activities_type_time (user_id, course_id, activity_type, occurred_at),
  INDEX idx_learning_activities_resource (resource_id, is_deleted)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

- [ ] **Step 5: Run the model test**

Run from `../backend`:

```bash
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/learning_activity_model_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_learning_activities.py::test_learning_activity_model_shape -q -p no:cacheprovider
```

Expected: `1 passed`.

- [ ] **Step 6: Commit**

```bash
git add ../backend/app/models/others.py ../backend/migrations/2026-06-14-add-learning-activities.sql ../backend/tests/test_learning_activities.py
git commit -m "新增学习行为记录模型"
```

---

## Task 2: Backend Activity Endpoint

**Files:**
- Create: `../backend/app/schemas/learning_activity.py`
- Create: `../backend/app/api/v1/learning_activities.py`
- Modify: `../backend/app/main.py`
- Modify: `../backend/tests/test_learning_activities.py`

- [ ] **Step 1: Add failing API tests**

Append these helpers and tests to `../backend/tests/test_learning_activities.py`:

```python
import asyncio
import re
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.base import Base
from app.db.session import async_session_factory, engine
from app.main import app
from app.models.course import CourseEnrollment
from app.models.others import CourseKnowledgeGraph, LearningActivity, Resource
from app.models.user import RegistrationCode, User


async def _register_and_login(client, code, email, username):
    def _captcha_ans(data):
        nums = re.findall(r"\d+", data["captcha_question"])
        return str(int(nums[0]) + int(nums[1])) if "+" in data["captcha_question"] else str(int(nums[0]) - int(nums[1]))

    captcha = (await client.get("/api/v1/auth/captcha")).json()["data"]
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "registration_code": code,
            "email": email,
            "password": "Abc12345",
            "username": username,
            "captcha_token": captcha["captcha_token"],
            "captcha_code": _captcha_ans(captcha),
        },
    )
    assert response.status_code == 201, response.text

    captcha = (await client.get("/api/v1/auth/captcha")).json()["data"]
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "Abc12345",
            "captcha_token": captcha["captcha_token"],
            "captcha_code": _captcha_ans(captcha),
        },
    )
    token = response.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_student_can_create_learning_activity_for_enrolled_course():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        teacher_code = f"tea_{uuid.uuid4().hex[:8]}"
        student_code = f"stu_{uuid.uuid4().hex[:8]}"
        async with async_session_factory() as db:
            db.add_all([
                RegistrationCode(code=teacher_code, role="teacher"),
                RegistrationCode(code=student_code, role="student"),
            ])
            await db.commit()

        teacher_headers = await _register_and_login(client, teacher_code, f"t_{uuid.uuid4().hex}@test.com", "Teacher")
        student_headers = await _register_and_login(client, student_code, f"s_{uuid.uuid4().hex}@test.com", "Student")

        course_response = await client.post("/api/v1/courses", headers=teacher_headers, json={"name": "Activity Course"})
        course_id = course_response.json()["data"]["id"]

        async with async_session_factory() as db:
            student = (await db.execute(select(User).where(User.email.like("s_%@test.com")))).scalars().first()
            db.add(CourseEnrollment(student_id=student.id, course_id=course_id))
            db.add(Resource(id="res_activity_1", course_id=course_id, title="Pointer Reading", type="reading", knowledge_point="指针基础"))
            db.add(CourseKnowledgeGraph(
                course_id=course_id,
                version=1,
                is_active=True,
                nodes=[{"id": "node_pointer", "name": "指针基础"}],
                edges=[],
            ))
            await db.commit()

        response = await client.post(
            "/api/v1/learning-activities",
            headers=student_headers,
            json={
                "course_id": course_id,
                "activity_type": "resource_study",
                "node_id": "node_pointer",
                "resource_id": "res_activity_1",
                "duration_seconds": 180,
                "occurred_at": "2026-06-14T10:00:00Z",
                "metadata": {"source": "resource_detail"},
            },
        )

        assert response.status_code == 200, response.text
        activity_id = response.json()["data"]["id"]
        async with async_session_factory() as db:
            activity = await db.get(LearningActivity, activity_id)
            assert activity is not None
            assert activity.user_id == student.id
            assert activity.course_id == course_id
            assert activity.node_name == "指针基础"
            assert activity.duration_seconds == 180


@pytest.mark.asyncio
async def test_learning_activity_rejects_invalid_type_and_duration():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        teacher_code = f"tea_{uuid.uuid4().hex[:8]}"
        async with async_session_factory() as db:
            db.add(RegistrationCode(code=teacher_code, role="teacher"))
            await db.commit()

        headers = await _register_and_login(client, teacher_code, f"t_{uuid.uuid4().hex}@test.com", "Teacher")
        course_response = await client.post("/api/v1/courses", headers=headers, json={"name": "Validation Course"})
        course_id = course_response.json()["data"]["id"]

        bad_type = await client.post(
            "/api/v1/learning-activities",
            headers=headers,
            json={"course_id": course_id, "activity_type": "made_up"},
        )
        assert bad_type.status_code == 422

        excessive = await client.post(
            "/api/v1/learning-activities",
            headers=headers,
            json={"course_id": course_id, "activity_type": "resource_study", "duration_seconds": 14401},
        )
        assert excessive.status_code == 422
```

- [ ] **Step 2: Run the API tests to verify they fail**

Run from `../backend`:

```bash
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/learning_activity_api_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_learning_activities.py -q -p no:cacheprovider
```

Expected: endpoint returns `404` because the router does not exist.

- [ ] **Step 3: Add schemas**

Create `../backend/app/schemas/learning_activity.py`:

```python
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


ActivityType = Literal[
    "resource_view",
    "resource_study",
    "node_view",
    "node_practice_start",
    "node_practice_submit",
]


class LearningActivityCreateRequest(BaseModel):
    course_id: str
    activity_type: ActivityType
    node_id: str | None = None
    node_name: str | None = None
    resource_id: str | None = None
    quiz_id: str | None = None
    duration_seconds: int | None = Field(default=None, ge=0, le=14400)
    occurred_at: datetime | None = None
    metadata: dict[str, Any] | None = None

    @field_validator("metadata")
    @classmethod
    def metadata_must_be_object(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is None:
            return None
        return {str(key): item for key, item in value.items()}


class LearningActivityCreateResponse(BaseModel):
    id: str
```

- [ ] **Step 4: Add the router**

Create `../backend/app/api/v1/learning_activities.py`:

```python
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.course import Course, CourseEnrollment
from app.models.others import CourseKnowledgeGraph, LearningActivity, Resource
from app.models.user import User
from app.schemas.learning_activity import LearningActivityCreateRequest
from app.services.course_knowledge_graphs import get_active_knowledge_graph
from app.services.resource_scope import resolve_course_resource_scope, resource_scope_clause

router = APIRouter(prefix="/api/v1/learning-activities", tags=["learning-activities"])

_DURATION_EVENT_TYPES = {"resource_study", "node_practice_submit"}


async def _ensure_course_access(db: AsyncSession, user: User, course_id: str) -> None:
    if user.role == "teacher":
        result = await db.execute(
            select(Course.id).where(Course.id == course_id, Course.teacher_id == user.id, Course.is_deleted == False)
        )
        if result.scalar_one_or_none():
            return

    result = await db.execute(
        select(CourseEnrollment.id).where(
            CourseEnrollment.course_id == course_id,
            CourseEnrollment.student_id == user.id,
            CourseEnrollment.is_deleted == False,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40400, "message": "课程不存在或无权访问", "data": None},
        )


async def _ensure_resource_in_scope(db: AsyncSession, course_id: str, resource_id: str | None) -> None:
    if not resource_id:
        return
    scope = await resolve_course_resource_scope(db, course_id)
    result = await db.execute(
        select(Resource.id).where(
            Resource.id == resource_id,
            resource_scope_clause(scope),
            Resource.is_deleted == False,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40400, "message": "资源不存在或无权访问", "data": None},
        )


async def _resolve_node_name(
    db: AsyncSession,
    course_id: str,
    node_id: str | None,
    node_name: str | None,
) -> str | None:
    if node_name or not node_id:
        return node_name
    kg = await get_active_knowledge_graph(db, course_id)
    nodes = kg.nodes if kg and isinstance(kg.nodes, list) else []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        current_id = str(node.get("id") or node.get("node_id") or "")
        if current_id == node_id:
            return str(node.get("name") or current_id)
    return node_name


@router.post("")
async def create_learning_activity(
    payload: LearningActivityCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if payload.activity_type in _DURATION_EVENT_TYPES and payload.duration_seconds is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": 42200, "message": "duration_seconds 不能为空", "data": None},
        )

    await _ensure_course_access(db, current_user, payload.course_id)
    await _ensure_resource_in_scope(db, payload.course_id, payload.resource_id)
    node_name = await _resolve_node_name(db, payload.course_id, payload.node_id, payload.node_name)

    metadata = dict(payload.metadata or {})
    if payload.quiz_id:
        metadata["quiz_id"] = payload.quiz_id

    activity = LearningActivity(
        user_id=current_user.id,
        course_id=payload.course_id,
        node_id=payload.node_id,
        node_name=node_name,
        resource_id=payload.resource_id,
        activity_type=payload.activity_type,
        duration_seconds=payload.duration_seconds,
        occurred_at=payload.occurred_at or datetime.now(timezone.utc),
        metadata=metadata or None,
        create_by=current_user.id,
        update_by=current_user.id,
    )
    db.add(activity)
    await db.commit()
    await db.refresh(activity)
    return {"code": 200, "message": "success", "data": {"id": activity.id}}
```

- [ ] **Step 5: Register the router**

Modify `../backend/app/main.py` imports:

```python
from app.api.v1 import (
    admin, auth, catalogs, courses, evaluation, learning_activities, learning_path,
    profile, quiz, resources, tasks, teaching, tutoring,
    users, webhooks,
)
```

Add the router near `evaluation`:

```python
app.include_router(evaluation.router)
app.include_router(learning_activities.router)
app.include_router(profile.router)
```

- [ ] **Step 6: Run the API tests**

Run from `../backend`:

```bash
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/learning_activity_api_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_learning_activities.py -q -p no:cacheprovider
```

Expected: all tests in `test_learning_activities.py` pass.

- [ ] **Step 7: Commit**

```bash
git add ../backend/app/schemas/learning_activity.py ../backend/app/api/v1/learning_activities.py ../backend/app/main.py ../backend/tests/test_learning_activities.py
git commit -m "新增学习行为采集接口"
```

---

## Task 3: Evaluation Aggregates Learning Activity

**Files:**
- Modify: `../backend/app/api/v1/evaluation.py`
- Modify: `../backend/tests/test_refresh_async.py`

- [ ] **Step 1: Add failing evaluation regression**

Modify `../backend/tests/test_refresh_async.py` imports:

```python
from app.models.others import UserProfile, Evaluation, LearningPath, CourseKnowledgeGraph, LearningActivity
```

In the existing evaluation refresh success setup, after the `QuizSession` seed, add:

```python
            db.add(LearningActivity(
                user_id=user_id,
                course_id=course_id,
                node_id="kg_node_pointer",
                node_name="指针基础",
                resource_id=None,
                activity_type="resource_study",
                duration_seconds=420,
                metadata={"source": "test_refresh_async"},
            ))
```

Update the assertion for the pointer node:

```python
            pointer_row = next(row for row in rows if row["node_name"] == "指针基础")
            chk("node progress uses activity duration", pointer_row["study_duration_seconds"] == 540)
            chk("node progress includes resource visit count", pointer_row["resource_visit_count"] == 1)
            chk("node progress includes latest activity timestamp", pointer_row["last_activity_at"] is not None)
```

The expected `540` is existing quiz session `120` plus new activity `420`.

- [ ] **Step 2: Run the regression to verify it fails**

Run from `../backend`:

```bash
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/evaluation_activity_duration_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_refresh_async.py -q -p no:cacheprovider
```

Expected: failure because `study_duration_seconds` remains quiz-only and visit metadata is `null`.

- [ ] **Step 3: Add activity aggregation**

Modify `../backend/app/api/v1/evaluation.py` imports:

```python
from app.models.others import AsyncTask, CourseKnowledgeGraph, Evaluation, LearningActivity, Resource
```

Inside `_build_node_progress_rows`, after quiz `attempts` are built and before `rows`, add:

```python
    node_ids = [
        str(node.get("id") or node.get("node_id") or f"node_{index}")
        for index, node in enumerate(nodes)
        if isinstance(node, dict)
    ]
    activity_by_node: dict[str, dict] = defaultdict(
        lambda: {"duration": 0, "visit_count": 0, "last_activity_at": None}
    )
    if node_ids:
        activity_result = await db.execute(
            select(LearningActivity).where(
                LearningActivity.user_id == user_id,
                LearningActivity.course_id == course_id,
                LearningActivity.node_id.in_(node_ids),
                LearningActivity.is_deleted == False,
            )
        )
        for activity in activity_result.scalars().all():
            stats = activity_by_node[activity.node_id]
            stats["duration"] += activity.duration_seconds or 0
            if activity.activity_type in ("resource_view", "resource_study"):
                stats["visit_count"] += 1
            if activity.occurred_at and (
                stats["last_activity_at"] is None or activity.occurred_at > stats["last_activity_at"]
            ):
                stats["last_activity_at"] = activity.occurred_at
```

Replace the existing `duration = ...` line in the row loop with:

```python
        quiz_duration = int(attempt_stats["duration"]) if attempt_stats and attempt_stats["duration"] else 0
        activity_stats = activity_by_node.get(node_id)
        activity_duration = int(activity_stats["duration"]) if activity_stats and activity_stats["duration"] else 0
        duration_total = quiz_duration + activity_duration
        last_activity_at = activity_stats["last_activity_at"] if activity_stats else None
        resource_visit_count = activity_stats["visit_count"] if activity_stats else None
```

Set row fields:

```python
                "study_duration_seconds": duration_total if duration_total else None,
                "resource_visit_count": resource_visit_count,
                "last_activity_at": last_activity_at.isoformat() if last_activity_at else None,
```

- [ ] **Step 4: Run backend regressions**

Run from `../backend`:

```bash
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/evaluation_activity_duration_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_refresh_async.py tests/test_learning_activities.py -q -p no:cacheprovider
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```bash
git add ../backend/app/api/v1/evaluation.py ../backend/tests/test_refresh_async.py
git commit -m "接入学习行为耗时聚合"
```

---

## Task 4: API Contract Documentation

**Files:**
- Modify: `../docs/10-client-api/Client-API.openapi.json`
- Modify: `../docs/10-client-api/API_前端接口规范.md`

- [ ] **Step 1: Add OpenAPI path and schemas**

In `../docs/10-client-api/Client-API.openapi.json`, add path `/learning-activities`:

```json
"/learning-activities": {
  "post": {
    "tags": ["learning-activities"],
    "summary": "Create Learning Activity",
    "description": "记录当前用户在课程内的学习行为事件。用于后续 /evaluation 节点学习耗时聚合；失败不应阻断资源浏览、学习路径或练习提交主流程。",
    "security": [{ "BearerAuth": [] }],
    "requestBody": {
      "required": true,
      "content": {
        "application/json": {
          "schema": { "$ref": "#/components/schemas/LearningActivityCreateRequest" }
        }
      }
    },
    "responses": {
      "200": {
        "description": "Activity recorded",
        "content": {
          "application/json": {
            "schema": {
              "allOf": [
                { "$ref": "#/components/schemas/ApiResponse" },
                {
                  "type": "object",
                  "properties": {
                    "data": { "$ref": "#/components/schemas/LearningActivityCreateResponse" }
                  }
                }
              ]
            }
          }
        }
      },
      "401": { "description": "Unauthorized" },
      "404": { "description": "Course or resource not found" },
      "422": { "description": "Invalid activity payload" }
    }
  }
}
```

Add schemas:

```json
"LearningActivityCreateRequest": {
  "type": "object",
  "required": ["course_id", "activity_type"],
  "properties": {
    "course_id": { "type": "string" },
    "activity_type": {
      "type": "string",
      "enum": ["resource_view", "resource_study", "node_view", "node_practice_start", "node_practice_submit"]
    },
    "node_id": { "type": "string", "nullable": true },
    "node_name": { "type": "string", "nullable": true },
    "resource_id": { "type": "string", "nullable": true },
    "quiz_id": { "type": "string", "nullable": true },
    "duration_seconds": { "type": "integer", "minimum": 0, "maximum": 14400, "nullable": true },
    "occurred_at": { "type": "string", "format": "date-time", "nullable": true },
    "metadata": { "type": "object", "nullable": true, "additionalProperties": true }
  }
},
"LearningActivityCreateResponse": {
  "type": "object",
  "required": ["id"],
  "properties": {
    "id": { "type": "string" }
  }
}
```

- [ ] **Step 2: Update markdown API spec**

In `../docs/10-client-api/API_前端接口规范.md`, add a section before the resources or quiz section:

```markdown
## 学习行为采集 `/api/v1/learning-activities`

POST /api/v1/learning-activities

用于记录当前用户在课程内的真实学习行为事件。该接口只接收单条事件，不提供批量提交；前端调用失败时不阻断资源浏览、学习路径或练习提交。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| course_id | string | 是 | 教学班 / 课程上下文 |
| activity_type | string | 是 | resource_view / resource_study / node_view / node_practice_start / node_practice_submit |
| node_id | string/null | 否 | KG 节点 ID |
| node_name | string/null | 否 | KG 节点名称；为空时 Backend 可按 active KG 解析 |
| resource_id | string/null | 否 | 资源 ID |
| quiz_id | string/null | 否 | 练习 ID |
| duration_seconds | integer/null | 否 | 学习/练习耗时；0 到 14400 秒 |
| occurred_at | string/null | 否 | 客户端事件时间，ISO 8601 |
| metadata | object/null | 否 | 小型结构化上下文，不存题目答案文本 |

约束：

- `resource_study` 和 `node_practice_submit` 必须带 `duration_seconds`。
- 单条事件耗时超过 14400 秒或为负数返回 422。
- 课程不可访问或资源不在课程资源范围内返回 404。
- `/evaluation.node_progress[].study_duration_seconds` 可聚合本接口的真实耗时；掌握评分仍以答题结果为准。
```

- [ ] **Step 3: Validate docs**

Run from `frontend`:

```bash
python3 -m json.tool ../docs/10-client-api/Client-API.openapi.json >/tmp/client-api-openapi-check.json
```

Expected: exit code `0`.

- [ ] **Step 4: Commit**

```bash
git add ../docs/10-client-api/Client-API.openapi.json ../docs/10-client-api/API_前端接口规范.md
git commit -m "同步学习行为采集接口契约"
```

---

## Task 5: Frontend Tracking Service

**Files:**
- Create: `src/api/services/learningActivity.js`
- Modify: `e2e/specs.spec.js`

- [ ] **Step 1: Add failing route-driven service expectation through E2E**

Append this test to `e2e/specs.spec.js`:

```javascript
  test('Resource detail reports view and study activity without blocking display', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'e2e-student-token');
      localStorage.setItem('course_id', 'course-activity-e2e');
    });

    await page.route('**/api/v1/users/me', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: { id: 'student-activity-e2e', email: 'student@example.com', username: 'Student E2E', role: 'student' },
      }));
    });

    await page.route('**/api/v1/courses**', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: { courses: [{ id: 'course-activity-e2e', name: '行为采集课程' }] },
      }));
    });

    await page.route('**/api/v1/resources/res-activity-e2e', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          id: 'res-activity-e2e',
          course_id: 'course-activity-e2e',
          title: '指针阅读',
          type: 'reading',
          content: '指针学习内容',
          knowledge_point: '指针基础',
        },
      }));
    });

    const activityPayloads = [];
    await page.route('**/api/v1/learning-activities', async (route) => {
      activityPayloads.push(route.request().postDataJSON());
      await route.fulfill(jsonResponse({ code: 200, message: 'success', data: { id: `activity-${activityPayloads.length}` } }));
    });

    await page.goto('/resource/res-activity-e2e');
    await expect(page.getByText('指针阅读')).toBeVisible();
    await page.waitForTimeout(5200);
    await page.goto('/dashboard');

    expect(activityPayloads.some((payload) => payload.activity_type === 'resource_view')).toBeTruthy();
    expect(activityPayloads.some((payload) => payload.activity_type === 'resource_study' && payload.duration_seconds >= 5)).toBeTruthy();
  });
```

- [ ] **Step 2: Run the E2E test to verify it fails**

Run from `frontend`:

```bash
npm run test:e2e -- e2e/specs.spec.js -g "Resource detail reports view"
```

Expected: failure because no request is sent to `/learning-activities`.

- [ ] **Step 3: Add the tracking service**

Create `src/api/services/learningActivity.js`:

```javascript
import apiClient from '../client';

export const learningActivityService = {
  async trackActivity(payload) {
    try {
      return await apiClient.post('/learning-activities', {
        ...payload,
        occurred_at: payload.occurred_at || new Date().toISOString(),
      });
    } catch (error) {
      console.warn('Learning activity tracking failed:', error);
      return null;
    }
  },
};
```

- [ ] **Step 4: Commit**

```bash
git add src/api/services/learningActivity.js e2e/specs.spec.js
git commit -m "新增前端学习行为采集服务"
```

---

## Task 6: Resource Detail Activity Capture

**Files:**
- Modify: `src/pages/ResourceDetail.jsx`
- Modify: `e2e/specs.spec.js`

- [ ] **Step 1: Implement resource view/study tracking**

Modify imports in `src/pages/ResourceDetail.jsx`:

```javascript
import { useState, useEffect, useRef } from 'react';
import { learningActivityService } from '../api/services/learningActivity';
```

Inside `ResourceDetail`, add:

```javascript
  const studySessionRef = useRef(null);
```

After the existing resource-load effect, add:

```javascript
  useEffect(() => {
    if (!resource?.id || !resource?.course_id) return;

    const session = {
      resourceId: resource.id,
      courseId: resource.course_id,
      nodeName: resource.knowledge_point || null,
      startedAt: Date.now(),
    };
    studySessionRef.current = session;

    learningActivityService.trackActivity({
      course_id: session.courseId,
      activity_type: 'resource_view',
      resource_id: session.resourceId,
      node_name: session.nodeName,
      metadata: { source: 'resource_detail' },
    });

    return () => {
      const activeSession = studySessionRef.current;
      if (!activeSession || activeSession.resourceId !== session.resourceId) return;
      const durationSeconds = Math.floor((Date.now() - activeSession.startedAt) / 1000);
      studySessionRef.current = null;
      if (durationSeconds < 5) return;

      learningActivityService.trackActivity({
        course_id: activeSession.courseId,
        activity_type: 'resource_study',
        resource_id: activeSession.resourceId,
        node_name: activeSession.nodeName,
        duration_seconds: durationSeconds,
        metadata: { source: 'resource_detail' },
      });
    };
  }, [resource]);
```

- [ ] **Step 2: Run resource E2E**

Run from `frontend`:

```bash
npm run test:e2e -- e2e/specs.spec.js -g "Resource detail reports view"
```

Expected: pass.

- [ ] **Step 3: Commit**

```bash
git add src/pages/ResourceDetail.jsx e2e/specs.spec.js
git commit -m "接入资源学习行为采集"
```

---

## Task 7: Learning Path Node View Capture

**Files:**
- Modify: `src/pages/LearningPath.jsx`
- Modify: `e2e/specs.spec.js`

- [ ] **Step 1: Add route-driven E2E expectation**

Append a test that routes `/learning-path`, clicks a non-default node, and expects one `node_view` payload:

```javascript
  test('Learning path reports node view when student selects a node', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'e2e-student-token');
      localStorage.setItem('course_id', 'course-path-activity-e2e');
    });

    await page.route('**/api/v1/users/me', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: { id: 'student-path-e2e', email: 'student@example.com', username: 'Student E2E', role: 'student' },
      }));
    });
    await page.route('**/api/v1/courses**', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: { courses: [{ id: 'course-path-activity-e2e', name: '路径行为课程' }] },
      }));
    });
    await page.route('**/api/v1/learning-path?**', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          current_position: { node_id: 'node_a' },
          nodes: [
            { id: 'node_a', name: '数组', order: 1, status: 'in_progress', mastery: 50 },
            { id: 'node_b', name: '指针', order: 2, status: 'recommended', mastery: 0 },
          ],
          edges: [],
        },
      }));
    });
    await page.route('**/api/v1/learning-path/nodes/**/resources**', async (route) => {
      await route.fulfill(jsonResponse({ code: 200, message: 'success', data: { weak_point_tutorials: [], exercises: [], chapter_materials: [] } }));
    });

    const activityPayloads = [];
    await page.route('**/api/v1/learning-activities', async (route) => {
      activityPayloads.push(route.request().postDataJSON());
      await route.fulfill(jsonResponse({ code: 200, message: 'success', data: { id: `activity-${activityPayloads.length}` } }));
    });

    await page.goto('/learning-path');
    await page.getByText('指针').click();
    await expect.poll(() => activityPayloads.length).toBe(1);
    expect(activityPayloads[0]).toMatchObject({
      course_id: 'course-path-activity-e2e',
      activity_type: 'node_view',
      node_id: 'node_b',
      node_name: '指针',
    });
  });
```

- [ ] **Step 2: Run the E2E test to verify it fails**

Run from `frontend`:

```bash
npm run test:e2e -- e2e/specs.spec.js -g "Learning path reports node view"
```

Expected: failure because no node activity is sent.

- [ ] **Step 3: Implement node view tracking**

Modify imports:

```javascript
import { useState, useEffect, useCallback, useRef } from 'react';
import { learningActivityService } from '../api/services/learningActivity';
```

Inside `LearningPath`, add:

```javascript
  const hasInitializedSelectionRef = useRef(false);
```

Add this effect after the resource-fetch effect:

```javascript
  useEffect(() => {
    if (!activeCourseId || !selectedNodeId || !learningPath?.nodes?.length) return;
    const selectedNode = learningPath.nodes.find((node) => node.id === selectedNodeId);
    if (!selectedNode) return;

    if (!hasInitializedSelectionRef.current) {
      hasInitializedSelectionRef.current = true;
      return;
    }

    learningActivityService.trackActivity({
      course_id: activeCourseId,
      activity_type: 'node_view',
      node_id: selectedNode.id,
      node_name: selectedNode.name,
      metadata: { source: 'learning_path' },
    });
  }, [activeCourseId, learningPath, selectedNodeId]);
```

- [ ] **Step 4: Run path E2E**

Run from `frontend`:

```bash
npm run test:e2e -- e2e/specs.spec.js -g "Learning path reports node view"
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/pages/LearningPath.jsx e2e/specs.spec.js
git commit -m "接入学习路径节点访问采集"
```

---

## Task 8: Quiz Practice Activity And Real Time Spent

**Files:**
- Modify: `src/pages/Quiz.jsx`
- Modify: `e2e/specs.spec.js`

- [ ] **Step 1: Add route-driven quiz E2E expectation**

Append a test that opens `/quiz?node_id=...`, submits, and asserts real `time_spent` and node practice payloads:

```javascript
  test('Quiz reports node practice activity and submits measured time', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'e2e-student-token');
      localStorage.setItem('course_id', 'course-quiz-activity-e2e');
    });

    await page.route('**/api/v1/users/me', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: { id: 'student-quiz-e2e', email: 'student@example.com', username: 'Student E2E', role: 'student' },
      }));
    });
    await page.route('**/api/v1/courses**', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: { courses: [{ id: 'course-quiz-activity-e2e', name: '练习行为课程' }] },
      }));
    });
    await page.route('**/api/v1/quiz/questions**', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          quiz_id: 'quiz-activity-e2e',
          questions: [{
            id: 'question-activity-e2e',
            type: 'single_choice',
            question: 'C 指针题',
            options: ['A', 'B'],
            knowledge_point: '指针基础',
            difficulty: 'easy',
            source: 'common',
          }],
        },
      }));
    });

    let submitPayload = null;
    await page.route('**/api/v1/quiz/submit', async (route) => {
      submitPayload = route.request().postDataJSON();
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: { quiz_id: 'quiz-activity-e2e', score: 100, per_question_results: [] },
      }));
    });

    const activityPayloads = [];
    await page.route('**/api/v1/learning-activities', async (route) => {
      activityPayloads.push(route.request().postDataJSON());
      await route.fulfill(jsonResponse({ code: 200, message: 'success', data: { id: `activity-${activityPayloads.length}` } }));
    });

    await page.goto('/quiz?node_id=node_pointer');
    await page.waitForTimeout(1200);
    await page.getByText('A').click();
    await page.getByText('提交答案').click();

    await expect.poll(() => submitPayload).not.toBe(null);
    expect(submitPayload.time_spent).toBeGreaterThanOrEqual(1);
    expect(activityPayloads.some((payload) => payload.activity_type === 'node_practice_start')).toBeTruthy();
    expect(activityPayloads.some((payload) => payload.activity_type === 'node_practice_submit' && payload.duration_seconds >= 1)).toBeTruthy();
  });
```

- [ ] **Step 2: Run quiz E2E to verify it fails**

Run from `frontend`:

```bash
npm run test:e2e -- e2e/specs.spec.js -g "Quiz reports node practice"
```

Expected: failure because `time_spent` is fixed at `120` and no activity payloads are sent.

- [ ] **Step 3: Implement quiz elapsed time and activity tracking**

Modify imports in `src/pages/Quiz.jsx`:

```javascript
import { useState, useEffect, useRef } from 'react';
import { learningActivityService } from '../api/services/learningActivity';
```

Inside `Quiz`, add:

```javascript
  const quizStartedAtRef = useRef(null);
```

After `setQuizData(res.data);` in the question-load success block, add:

```javascript
          quizStartedAtRef.current = Date.now();
          if (nodeId) {
            learningActivityService.trackActivity({
              course_id: activeCourseId,
              activity_type: 'node_practice_start',
              node_id: nodeId,
              node_name: res.data?.questions?.[0]?.knowledge_point || null,
              quiz_id: res.data?.quiz_id,
              metadata: { source: 'quiz' },
            });
          }
```

Replace the submit `time_spent` field:

```javascript
        time_spent: Math.max(1, Math.floor((Date.now() - (quizStartedAtRef.current || Date.now())) / 1000)),
```

After `const res = await quizService.submitQuiz(submitData);`, add:

```javascript
      if (nodeId) {
        learningActivityService.trackActivity({
          course_id: activeCourseId,
          activity_type: 'node_practice_submit',
          node_id: nodeId,
          node_name: quizData.questions[0]?.knowledge_point || null,
          quiz_id: quizData.quiz_id,
          duration_seconds: submitData.time_spent,
          metadata: { source: 'quiz' },
        });
      }
```

- [ ] **Step 4: Run quiz E2E**

Run from `frontend`:

```bash
npm run test:e2e -- e2e/specs.spec.js -g "Quiz reports node practice"
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/pages/Quiz.jsx e2e/specs.spec.js
git commit -m "接入练习学习行为采集"
```

---

## Task 9: Full Verification And Progress Docs

**Files:**
- Modify: `WORKFLOW.md`
- Modify: `docs/feature-ledger.md`

- [ ] **Step 1: Run backend tests**

Run from `../backend`:

```bash
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/learning_activity_full_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_learning_activities.py tests/test_refresh_async.py -q -p no:cacheprovider
```

Expected: selected tests pass.

- [ ] **Step 2: Validate API contract**

Run from `frontend`:

```bash
python3 -m json.tool ../docs/10-client-api/Client-API.openapi.json >/tmp/client-api-openapi-check.json
```

Expected: exit code `0`.

- [ ] **Step 3: Run frontend checks**

Run from `frontend`:

```bash
npm run lint
npm run build
npm run test:e2e -- e2e/specs.spec.js -g "activity|Learning effects"
```

Expected:

- `npm run lint` passes.
- `npm run build` passes; existing Vite chunk-size warning is acceptable if unchanged.
- Targeted Playwright tests pass.

- [ ] **Step 4: Update progress docs**

Add a `2026-06-14` entry to `WORKFLOW.md` with:

```markdown
### 2026-06-14 Learning Activity Tracking

- 新增学习行为采集模型、迁移和 `POST /api/v1/learning-activities`。
- `/evaluation.node_progress` 聚合真实学习行为耗时、资源访问次数和最近活动时间。
- 前端资源详情、学习路径节点选择、节点练习开始/提交接入非阻塞采集。
- 已验证：后端 MySQL 集成测试、OpenAPI JSON 解析、前端 lint/build、目标 E2E。
- 契约漂移：已同步 OpenAPI 与前端接口规范。
```

Update `docs/feature-ledger.md` `/learning-effects` or learning analytics row to mention:

```markdown
- 学习耗时来源已从 quiz-only 扩展为真实 learning_activities 事件聚合；剩余风险是资源与 KG 节点仍依赖 resource.knowledge_point / node_id 关联质量。
```

- [ ] **Step 5: Final diff and whitespace check**

Run from `frontend`:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors; status contains only intended modified files plus existing unrelated untracked files.

- [ ] **Step 6: Commit docs**

```bash
git add WORKFLOW.md docs/feature-ledger.md
git commit -m "记录学习行为采集实施进度"
```

---

## Final Completion Checklist

- [ ] `LearningActivity` model exists and MySQL migration is present.
- [ ] `POST /api/v1/learning-activities` requires auth and validates course/resource access.
- [ ] Invalid activity type, negative duration, and duration over 14400 seconds return validation errors.
- [ ] `/evaluation.node_progress[].study_duration_seconds` includes quiz duration plus learning activity duration.
- [ ] `resource_visit_count` and `last_activity_at` use real activity rows when present.
- [ ] Frontend activity calls are best-effort and do not block resource display, node selection, or quiz submission.
- [ ] `Quiz.jsx` no longer submits fixed `time_spent: 120`.
- [ ] OpenAPI JSON and markdown API spec document the new endpoint.
- [ ] Backend MySQL tests pass.
- [ ] Frontend lint, build, and targeted Playwright tests pass.
- [ ] `WORKFLOW.md` and `docs/feature-ledger.md` reflect the implementation.
