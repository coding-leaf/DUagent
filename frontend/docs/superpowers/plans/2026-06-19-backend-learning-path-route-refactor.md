# Backend Learning Path Route Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split `backend/app/api/v1/learning_path.py` into focused service modules while preserving the existing API contract and task behavior.

**Architecture:** Keep the current FastAPI monolith and apply the established `Router -> Service -> DB` pattern from the catalogs refactor. Route functions keep HTTP boundary work only; service classes own request-scoped database orchestration; background runners stay module-level functions with independent DB sessions.

**Tech Stack:** FastAPI, SQLAlchemy async ORM, Pytest, MySQL test databases, existing `AsyncTask` background-task model.

---

## Source Spec

Read this before executing any task:

- `frontend/docs/superpowers/specs/2026-06-19-backend-learning-path-route-refactor-design.md`
- `backend/app/api/v1/learning_path.py`
- `backend/app/services/catalog_service.py`
- `backend/app/services/catalog_material_service.py`
- `backend/app/services/resource_scope.py`

## Target File Structure

- Create `backend/app/services/learning_path_service.py`
  - Owns learning path read logic, KG fallback synthesis, realtime progress merge, and pure node helper functions.
- Create `backend/app/services/learning_path_refresh_service.py`
  - Owns Agent payload assembly, `AsyncTask` creation helper, and background refresh runner.
- Create `backend/app/services/node_resource_service.py`
  - Owns node resource lookup and response DTO assembly.
- Modify `backend/app/api/v1/learning_path.py`
  - Keeps only FastAPI route definitions, dependency injection, student enrollment guard, commit point, background dispatch, and response wrapper.
- Modify tests:
  - `backend/tests/test_learning_path_realtime.py`
  - `backend/tests/test_learning_path_fallback.py`
  - `backend/tests/test_node_resources.py`
  - `backend/tests/test_refresh_async.py`
  - `backend/tests/test_lock_async.py`
- Create tests:
  - `backend/tests/test_learning_path_service.py`
  - `backend/tests/test_learning_path_refresh_service.py`
  - `backend/tests/test_node_resource_service.py`
- Modify docs after implementation:
  - `frontend/WORKFLOW.md`
  - `frontend/docs/requirements-coverage.md`

## Pre-Flight

### Task 0: Verify Worktree And Test Databases

**Files:**
- No source changes.

- [ ] **Step 1: Inspect working tree**

Run from `frontend/`:

```bash
git status --short
```

Expected: existing unrelated changes may be present, including `../start_all.sh`, storage folders, or agent tools. Do not stage or modify unrelated files.

- [ ] **Step 2: Create MySQL test databases if missing**

Run from `frontend/`:

```bash
mysql -uroot -p123456 -h127.0.0.1 -e "CREATE DATABASE IF NOT EXISTS learning_path_refactor_test DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; CREATE DATABASE IF NOT EXISTS learning_path_refactor_refresh_test DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

Expected: command exits `0`. If MySQL is unavailable, stop and report the exact connection error before changing code.

- [ ] **Step 3: Run current learning-path baseline**

Run from `backend/`:

```bash
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/learning_path_refactor_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_learning_path_realtime.py tests/test_learning_path_fallback.py tests/test_node_resources.py -q -p no:cacheprovider
```

Expected: tests pass before refactor. If they fail, capture the failing test names and failure text; do not start migration until baseline is understood.

## Implementation

### Task 1: Extract Learning Path Read Service Pure Helpers

**Files:**
- Create: `backend/app/services/learning_path_service.py`
- Create: `backend/tests/test_learning_path_service.py`
- Modify: `backend/tests/test_learning_path_realtime.py`
- Modify: `backend/tests/test_learning_path_fallback.py`
- Test: `backend/tests/test_learning_path_service.py`
- Test: `backend/tests/test_learning_path_realtime.py`
- Test: `backend/tests/test_learning_path_fallback.py`

- [ ] **Step 1: Write failing import changes**

In `backend/tests/test_learning_path_realtime.py`, replace route imports with:

```python
from app.services.learning_path_service import map_assessment_to_status
from app.services.learning_path_service import apply_progress_to_nodes, build_current_position_from_nodes
```

Then replace function calls:

```python
assert map_assessment_to_status("mastered") == "completed"
result = apply_progress_to_nodes(nodes, progress)
cp = build_current_position_from_nodes(nodes)
assert build_current_position_from_nodes([]) is None
```

In `backend/tests/test_learning_path_fallback.py`, replace:

```python
from app.api.v1.learning_path import _topo_sort_kg_nodes
```

with:

```python
from app.services.learning_path_service import topo_sort_kg_nodes
```

Then replace all `_topo_sort_kg_nodes(...)` calls with `topo_sort_kg_nodes(...)`.

- [ ] **Step 2: Run tests to verify RED**

Run from `backend/`:

```bash
../.venv/bin/python -m pytest tests/test_learning_path_realtime.py tests/test_learning_path_fallback.py -q -p no:cacheprovider
```

Expected: import failure for `app.services.learning_path_service`.

- [ ] **Step 3: Add focused service helper tests**

Create `backend/tests/test_learning_path_service.py` with:

```python
from app.services.learning_path_service import (
    apply_progress_to_nodes,
    build_current_position_from_nodes,
    map_assessment_to_status,
    topo_sort_kg_nodes,
)


def test_topo_sort_preserves_prerequisite_order():
    nodes = [
        {"id": "b", "name": "B"},
        {"id": "a", "name": "A"},
        {"id": "c", "name": "C"},
    ]
    edges = [{"from": "a", "to": "b"}, {"from": "b", "to": "c"}]

    result = topo_sort_kg_nodes(nodes, edges)

    assert [node["id"] for node in result] == ["a", "b", "c"]


def test_apply_progress_to_nodes_preserves_unknown_nodes():
    nodes = [{"id": "n1", "name": "Node 1", "status": "pending", "mastery": 10, "reason": "keep"}]

    result = apply_progress_to_nodes(nodes, {})

    assert result == [{"id": "n1", "name": "Node 1", "status": "pending", "mastery": 10, "reason": "keep"}]
    assert result is not nodes


def test_apply_progress_to_nodes_maps_status_and_mastery():
    nodes = [{"id": "n1", "name": "Node 1", "status": "pending", "mastery": 0}]
    progress = {"n1": {"assessment_state": "mastered", "mastery_score": 93.5}}

    result = apply_progress_to_nodes(nodes, progress)

    assert result[0]["status"] == "completed"
    assert result[0]["mastery"] == 93.5


def test_status_mapping_defaults_to_pending():
    assert map_assessment_to_status("unknown") == "pending"


def test_current_position_uses_first_non_pending_node():
    nodes = [
        {"id": "n1", "name": "Node 1", "status": "pending"},
        {"id": "n2", "name": "Node 2", "status": "recommended"},
    ]

    assert build_current_position_from_nodes(nodes) == {"node_id": "n2", "node_name": "Node 2"}
```

Run from `backend/`:

```bash
../.venv/bin/python -m pytest tests/test_learning_path_service.py -q -p no:cacheprovider
```

Expected: import failure for `app.services.learning_path_service` until the service module exists.

- [ ] **Step 4: Create service module with pure helpers**

Create `backend/app/services/learning_path_service.py` with:

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import CourseCatalog, CourseOffering
from app.models.others import LearningPath
from app.services.course_knowledge_graphs import get_active_knowledge_graph
from app.services.knowledge_progress import build_node_progress_rows


def topo_sort_kg_nodes(nodes: list[dict], edges: list[dict]) -> list[dict]:
    if not nodes:
        return []
    if not edges:
        return list(nodes)

    node_ids = {node["id"] for node in nodes}
    in_degree: dict[str, int] = {node["id"]: 0 for node in nodes}
    adjacency: dict[str, list[str]] = {node["id"]: [] for node in nodes}

    for edge in edges:
        from_id = edge.get("from", "")
        to_id = edge.get("to", "")
        if from_id in node_ids and to_id in node_ids:
            adjacency[from_id].append(to_id)
            in_degree[to_id] = in_degree.get(to_id, 0) + 1

    queue = [node["id"] for node in nodes if in_degree.get(node["id"], 0) == 0]
    sorted_ids: list[str] = []
    while queue:
        node_id = queue.pop(0)
        sorted_ids.append(node_id)
        for neighbor in adjacency.get(node_id, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    sorted_set = set(sorted_ids)
    for node in nodes:
        if node["id"] not in sorted_set:
            sorted_ids.append(node["id"])

    node_map = {node["id"]: dict(node) for node in nodes}
    return [node_map[node_id] for node_id in sorted_ids if node_id in node_map]


def map_assessment_to_status(assessment_state: str) -> str:
    return {
        "mastered": "completed",
        "learning": "in_progress",
        "weak": "recommended",
        "pending_practice": "pending",
        "unstarted": "pending",
    }.get(assessment_state, "pending")


def apply_progress_to_nodes(nodes: list[dict], progress_by_id: dict[str, dict]) -> list[dict]:
    result = []
    for node in nodes:
        node_id = node.get("id") or node.get("node_id", "")
        progress = progress_by_id.get(node_id)
        if progress is None:
            result.append(dict(node))
            continue
        updated = dict(node)
        updated["status"] = map_assessment_to_status(progress.get("assessment_state", "unstarted"))
        mastery_score = progress.get("mastery_score")
        if mastery_score is not None:
            updated["mastery"] = mastery_score
        result.append(updated)
    return result


def build_current_position_from_nodes(nodes: list[dict]) -> dict | None:
    if not nodes:
        return None
    for node in nodes:
        if node.get("status") != "pending":
            return {"node_id": node.get("id", ""), "node_name": node.get("name", "")}
    first = nodes[0]
    return {"node_id": first.get("id", ""), "node_name": first.get("name", "")}
```

- [ ] **Step 5: Run pure helper tests to verify GREEN**

Run from `backend/`:

```bash
../.venv/bin/python -m pytest tests/test_learning_path_service.py tests/test_learning_path_realtime.py tests/test_learning_path_fallback.py -q -p no:cacheprovider
```

Expected: all tests in the three files pass.

- [ ] **Step 6: Commit Task 1**

Run from `frontend/`:

```bash
git add ../backend/app/services/learning_path_service.py ../backend/tests/test_learning_path_service.py ../backend/tests/test_learning_path_realtime.py ../backend/tests/test_learning_path_fallback.py
git commit -m "refactor: 提取学习路径纯逻辑"
```

### Task 2: Move GET Learning Path Read Flow Into LearningPathService

**Files:**
- Modify: `backend/app/services/learning_path_service.py`
- Modify: `backend/app/api/v1/learning_path.py`
- Test: `backend/tests/test_learning_path_fallback.py`
- Test: `backend/tests/test_learning_path_realtime.py`

- [ ] **Step 1: Add service integration method**

Append this class to `backend/app/services/learning_path_service.py`:

```python
class LearningPathService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_learning_path(self, user_id: str, course_id: str) -> dict:
        progress_rows = await build_node_progress_rows(user_id, course_id, self.db)
        progress_by_id: dict[str, dict] = {row["node_id"]: row for row in progress_rows}

        result = await self.db.execute(
            select(LearningPath)
            .where(
                LearningPath.user_id == user_id,
                LearningPath.course_id == course_id,
                LearningPath.is_deleted == False,
            )
            .order_by(LearningPath.generated_at.desc())
        )
        learning_path = result.scalars().first()

        if learning_path is not None:
            merged_nodes = apply_progress_to_nodes(learning_path.nodes or [], progress_by_id)
            current_position = (
                {"node_id": learning_path.current_node_id, "node_name": learning_path.current_node_name}
                if merged_nodes and learning_path.current_node_id
                else None
            )
            return {
                "course_id": learning_path.course_id,
                "nodes": merged_nodes,
                "edges": learning_path.edges or [],
                "current_position": current_position,
                "source": "realtime_merged",
                "generated_at": learning_path.generated_at.isoformat() if learning_path.generated_at else None,
            }

        fallback = await self._synthesize_kg_fallback_path(course_id)
        if fallback is not None:
            kg_nodes = apply_progress_to_nodes(fallback["nodes"], progress_by_id)
            return {
                "course_id": fallback["course_id"],
                "nodes": kg_nodes,
                "edges": fallback.get("edges") or [],
                "current_position": build_current_position_from_nodes(kg_nodes),
                "source": "kg_realtime",
                "generated_at": fallback.get("generated_at"),
            }

        return {
            "course_id": course_id,
            "nodes": [],
            "edges": [],
            "current_position": None,
            "source": "kg_fallback",
            "generated_at": None,
        }

    async def _synthesize_kg_fallback_path(self, course_id: str) -> dict | None:
        offering_result = await self.db.execute(
            select(CourseOffering).where(
                CourseOffering.id == course_id,
                CourseOffering.is_deleted == False,
            )
        )
        offering = offering_result.scalar_one_or_none()
        if offering is None:
            return None

        catalog_result = await self.db.execute(
            select(CourseCatalog).where(
                CourseCatalog.id == offering.catalog_id,
                CourseCatalog.is_deleted == False,
            )
        )
        catalog = catalog_result.scalar_one_or_none()
        if catalog is None or not catalog.kg_host_course_id:
            return None

        kg = await get_active_knowledge_graph(self.db, catalog.kg_host_course_id)
        if kg is None:
            return None

        kg_nodes = kg.nodes if isinstance(kg.nodes, list) else []
        if not kg_nodes:
            return None

        kg_edges = kg.edges if isinstance(kg.edges, list) else []
        sorted_nodes = topo_sort_kg_nodes(kg_nodes, kg_edges)
        assembled_nodes = [
            {
                "id": node.get("id", ""),
                "name": node.get("name", ""),
                "chapter": node.get("chapter", ""),
                "order": index + 1,
                "status": "recommended",
                "mastery": 0,
            }
            for index, node in enumerate(sorted_nodes)
        ]
        first_node = assembled_nodes[0]
        return {
            "course_id": course_id,
            "nodes": assembled_nodes,
            "edges": kg_edges or [],
            "current_position": {"node_id": first_node["id"], "node_name": first_node["name"]},
            "source": "kg_fallback",
            "generated_at": kg.create_time.isoformat() if kg.create_time else None,
        }
```

- [ ] **Step 2: Update GET route to delegate to service**

In `backend/app/api/v1/learning_path.py`, add:

```python
from app.services.learning_path_service import LearningPathService
```

Replace the body of `get_learning_path(...)` with:

```python
    data = await LearningPathService(db).get_learning_path(current_user.id, course_id)
    return {"code": 200, "message": "success", "data": data}
```

- [ ] **Step 3: Remove migrated read helpers from route**

Delete these definitions from `backend/app/api/v1/learning_path.py`:

```python
async def _acquire_learning_path_lock(...)
async def _release_learning_path_lock(...)
def _topo_sort_kg_nodes(...)
def _map_assessment_to_status(...)
def _apply_progress_to_nodes(...)
def _build_current_position_from_nodes(...)
async def _synthesize_kg_fallback_path(...)
```

Keep imports required by refresh and node-resource code for now.

- [ ] **Step 4: Run GET route regression**

Run from `backend/`:

```bash
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/learning_path_refactor_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_learning_path_realtime.py tests/test_learning_path_fallback.py -q -p no:cacheprovider
```

Expected: all tests pass; `test_learning_path_kg_fallback_returns_nodes` still reports `source == "kg_fallback"` for raw fallback and API still returns the same wrapper.

- [ ] **Step 5: Commit Task 2**

Run from `frontend/`:

```bash
git add ../backend/app/services/learning_path_service.py ../backend/app/api/v1/learning_path.py
git commit -m "refactor: 委托学习路径读取服务"
```

### Task 3: Extract Learning Path Refresh Service

**Files:**
- Create: `backend/app/services/learning_path_refresh_service.py`
- Create: `backend/tests/test_learning_path_refresh_service.py`
- Modify: `backend/tests/test_node_resources.py`
- Test: `backend/tests/test_learning_path_refresh_service.py`
- Test: `backend/tests/test_node_resources.py`

- [ ] **Step 1: Change payload test import to fail**

In `backend/tests/test_node_resources.py`, replace:

```python
from app.api.v1.learning_path import _assemble_learning_path_payload
```

with:

```python
from app.services.learning_path_refresh_service import LearningPathRefreshService
```

Then replace:

```python
payload = await _assemble_learning_path_payload(user_id, course_id, db)
```

with:

```python
payload = await LearningPathRefreshService(db).assemble_payload(user_id, course_id)
```

- [ ] **Step 2: Run test to verify RED**

Run from `backend/`:

```bash
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/learning_path_refactor_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_node_resources.py::test_learning_path_payload_uses_active_knowledge_graph -q -p no:cacheprovider
```

Expected: import failure for `app.services.learning_path_refresh_service`.

- [ ] **Step 3: Add focused refresh service test**

Create `backend/tests/test_learning_path_refresh_service.py` with:

```python
import asyncio
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///./test_learning_path_refresh_service.db",
)

from app.db.session import async_session_factory, engine, init_db

asyncio.run(init_db())
asyncio.run(engine.dispose())

from app.models.others import AsyncTask
from app.services.learning_path_refresh_service import LearningPathRefreshService


@pytest.mark.asyncio
async def test_create_refresh_task_uses_learning_path_task_type():
    suffix = uuid.uuid4().hex[:8]
    user_id = f"user_{suffix}"
    course_id = f"course_{suffix}"

    async with async_session_factory() as db:
        task = await LearningPathRefreshService(db).create_refresh_task(user_id, course_id)
        await db.commit()

        persisted = await db.get(AsyncTask, task.id)

    assert persisted is not None
    assert persisted.task_type == "learning_path_refresh"
    assert persisted.status == "processing"
    assert persisted.user_id == user_id
    assert persisted.course_id == course_id
```

Run from `backend/`:

```bash
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/learning_path_refactor_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_learning_path_refresh_service.py -q -p no:cacheprovider
```

Expected: import failure for `app.services.learning_path_refresh_service` until the service module exists.

- [ ] **Step 4: Create refresh service module**

Create `backend/app/services/learning_path_refresh_service.py` with:

```python
import logging
from datetime import datetime, timezone

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models.others import AsyncTask, Evaluation, LearningPath, UserProfile
from app.services.agent_client import AgentServiceError, agent_client
from app.services.course_knowledge_graphs import get_active_knowledge_graph

logger = logging.getLogger(__name__)


class LearningPathRefreshService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def assemble_payload(self, user_id: str, course_id: str) -> dict:
        payload: dict = {"user_id": user_id, "course_id": course_id}

        evaluation_result = await self.db.execute(
            select(Evaluation)
            .where(
                Evaluation.user_id == user_id,
                Evaluation.course_id == course_id,
                Evaluation.is_deleted == False,
            )
            .order_by(Evaluation.generated_at.desc())
        )
        evaluation = evaluation_result.scalars().first()
        payload["evaluation"] = {
            "progress_table": evaluation.progress_table,
            "mastery_table": evaluation.mastery_table,
            "summary_text": evaluation.summary_text,
        } if evaluation else {}

        profile_result = await self.db.execute(
            select(UserProfile)
            .where(
                UserProfile.user_id == user_id,
                UserProfile.course_id == course_id,
                UserProfile.is_deleted == False,
            )
            .order_by(UserProfile.generated_at.desc())
        )
        profile = profile_result.scalars().first()
        payload["profile"] = {
            "modal_preference": profile.modal_preference,
            "guidance_level": profile.guidance_level_current,
            "knowledge_coordinates": profile.knowledge_coordinates,
        } if profile else {}

        kg = await get_active_knowledge_graph(self.db, course_id)
        payload["knowledge_graph"] = {"nodes": kg.nodes or [], "edges": kg.edges or []} if kg else {"nodes": [], "edges": []}
        return payload

    async def create_refresh_task(self, user_id: str, course_id: str) -> AsyncTask:
        task = AsyncTask(
            task_type="learning_path_refresh",
            status="processing",
            user_id=user_id,
            course_id=course_id,
        )
        self.db.add(task)
        await self.db.flush()
        await self.db.refresh(task)
        return task


async def run_learning_path_refresh_background(
    task_id: str,
    user_id: str,
    course_id: str,
    payload: dict,
) -> None:
    async with async_session_factory() as db:
        try:
            data = await agent_client.post_json("/agent/v1/learning-path/generate", payload)
            lock_name = f"learningpath_{user_id}_{course_id}"
            if db.bind.dialect.name == "sqlite":
                locked = 1
            else:
                lock_result = await db.execute(text("SELECT GET_LOCK(:name, 5)"), {"name": lock_name})
                locked = lock_result.scalar()
            if not locked:
                raise RuntimeError(f"GET_LOCK timeout: {lock_name}")

            try:
                now = datetime.now(timezone.utc)
                old_result = await db.execute(
                    select(LearningPath).where(
                        LearningPath.user_id == user_id,
                        LearningPath.course_id == course_id,
                        LearningPath.is_deleted == False,
                    )
                )
                for old_path in old_result.scalars().all():
                    old_path.is_deleted = True

                current_position = data.get("current_position") or {}
                db.add(
                    LearningPath(
                        user_id=user_id,
                        course_id=course_id,
                        nodes=data.get("nodes", []),
                        edges=data.get("edges", []),
                        current_node_id=current_position.get("node_id", ""),
                        current_node_name=current_position.get("node_name", ""),
                        generated_at=now,
                    )
                )
                await db.execute(
                    update(AsyncTask)
                    .where(AsyncTask.id == task_id)
                    .values(
                        status="completed",
                        result={"updated_at": now.isoformat()},
                        completed_at=now,
                    )
                )
                await db.commit()
                logger.info(
                    "Learning path refresh background: completed task_id=%s user_id=%s course_id=%s",
                    task_id,
                    user_id,
                    course_id,
                )
            finally:
                try:
                    if db.bind.dialect.name != "sqlite":
                        await db.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": lock_name})
                except Exception:
                    logger.warning("Learning path refresh background: RELEASE_LOCK failed lock_name=%s", lock_name)
        except AgentServiceError as exc:
            await db.rollback()
            await db.execute(
                update(AsyncTask)
                .where(AsyncTask.id == task_id)
                .values(
                    status="failed",
                    error_code=str(exc.agent_code or "agent_error"),
                    error_message=exc.message,
                    completed_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()
            logger.error(
                "Learning path refresh background: AgentServiceError task_id=%s user_id=%s course_id=%s status=%s agent_code=%s message=%s",
                task_id,
                user_id,
                course_id,
                exc.status_code,
                exc.agent_code,
                exc.message,
            )
        except Exception as exc:
            await db.rollback()
            error_message = str(exc)[:500]
            await db.execute(
                update(AsyncTask)
                .where(AsyncTask.id == task_id)
                .values(
                    status="failed",
                    error_code="lock_timeout" if "GET_LOCK timeout" in str(exc) else "internal_error",
                    error_message=error_message,
                    completed_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()
            logger.error(
                "Learning path refresh background: unexpected error task_id=%s user_id=%s course_id=%s type=%s message=%s",
                task_id,
                user_id,
                course_id,
                type(exc).__name__,
                error_message,
            )
```

- [ ] **Step 5: Run refresh service tests to verify GREEN**

Run from `backend/`:

```bash
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/learning_path_refactor_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_learning_path_refresh_service.py tests/test_node_resources.py::test_learning_path_payload_uses_active_knowledge_graph -q -p no:cacheprovider
```

Expected: tests pass.

- [ ] **Step 6: Commit Task 3**

Run from `frontend/`:

```bash
git add ../backend/app/services/learning_path_refresh_service.py ../backend/tests/test_learning_path_refresh_service.py ../backend/tests/test_node_resources.py
git commit -m "refactor: 提取学习路径刷新服务"
```

### Task 4: Delegate POST Refresh Route To Refresh Service

**Files:**
- Modify: `backend/app/api/v1/learning_path.py`
- Modify: `backend/tests/test_refresh_async.py`
- Modify: `backend/tests/test_lock_async.py`
- Test: `backend/tests/test_refresh_async.py`
- Test: `backend/tests/test_lock_async.py`

- [ ] **Step 1: Update route imports**

In `backend/app/api/v1/learning_path.py`, add:

```python
from app.services.learning_path_refresh_service import (
    LearningPathRefreshService,
    run_learning_path_refresh_background,
)
```

- [ ] **Step 2: Replace refresh route body service calls**

Inside `refresh_learning_path(...)`, replace payload/task/background sections with:

```python
    refresh_service = LearningPathRefreshService(db)
    payload = await refresh_service.assemble_payload(current_user.id, course_id)
    task = await refresh_service.create_refresh_task(current_user.id, course_id)
    # commit point: task persisted before background dispatch
    await db.commit()

    asyncio.create_task(run_learning_path_refresh_background(
        task_id=task.id,
        user_id=current_user.id,
        course_id=course_id,
        payload=payload,
    ))
```

Keep the existing student enrollment guard and existing `JSONResponse(202)` wrapper.

- [ ] **Step 3: Delete migrated refresh helpers and imports**

Delete these from `backend/app/api/v1/learning_path.py`:

```python
async def _assemble_learning_path_payload(...)
async def _run_learning_path_refresh_background(...)
```

Remove imports no longer used by the route after this task:

```python
import logging
from datetime import datetime, timezone
from sqlalchemy import text, update
from app.db.session import async_session_factory
from app.models.others import AsyncTask, Evaluation, UserProfile
from app.services.agent_client import AgentServiceError, agent_client
```

If `AsyncTask` is still used only in deleted code, remove it from the `app.models.others` import list.

- [ ] **Step 4: Update test patch paths**

In `backend/tests/test_refresh_async.py` and `backend/tests/test_lock_async.py`, replace:

```python
patch("app.api.v1.learning_path.agent_client.post_json", new_callable=AsyncMock)
```

with:

```python
patch("app.services.learning_path_refresh_service.agent_client.post_json", new_callable=AsyncMock)
```

- [ ] **Step 5: Run refresh route regression**

Run from `backend/`:

```bash
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/learning_path_refactor_refresh_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_refresh_async.py tests/test_lock_async.py -q -p no:cacheprovider
```

Expected: learning-path refresh scenarios pass. If profile or evaluation scenarios fail independently in these broad files, rerun and report the exact failing sections before changing unrelated modules.

- [ ] **Step 6: Commit Task 4**

Run from `frontend/`:

```bash
git add ../backend/app/api/v1/learning_path.py ../backend/tests/test_refresh_async.py ../backend/tests/test_lock_async.py
git commit -m "refactor: 委托学习路径刷新路由"
```

### Task 5: Extract Node Resource Service

**Files:**
- Create: `backend/app/services/node_resource_service.py`
- Create: `backend/tests/test_node_resource_service.py`
- Modify: `backend/app/api/v1/learning_path.py`
- Test: `backend/tests/test_node_resources.py`
- Test: `backend/tests/test_node_resource_service.py`

- [ ] **Step 1: Add service test for LP name overriding KG name**

Create `backend/tests/test_node_resource_service.py` with:

```python
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///./test_node_resource_service.db",
)

from app.db.session import async_session_factory, engine, init_db

import asyncio

asyncio.run(init_db())
asyncio.run(engine.dispose())

from app.models.course import Course, CourseEnrollment
from app.models.others import CourseKnowledgeGraph, LearningPath, Resource
from app.models.quiz import QuizQuestion
from app.models.user import User
from app.services.node_resource_service import NodeResourceService


@pytest.mark.asyncio
async def test_node_resource_service_prefers_learning_path_node_name():
    suffix = uuid.uuid4().hex[:8]
    teacher_id = f"teacher_{suffix}"
    student_id = f"student_{suffix}"
    course_id = f"course_{suffix}"
    node_id = "node_1"

    async with async_session_factory() as db:
        teacher = User(id=teacher_id, username=f"teacher_{suffix}", email=f"teacher_{suffix}@test.com", password_hash="hash", role="teacher")
        student = User(id=student_id, username=f"student_{suffix}", email=f"student_{suffix}@test.com", password_hash="hash", role="student")
        db.add_all([teacher, student])
        db.add(Course(id=course_id, name="Node Service Course", course_code=f"NS{suffix}", teacher_id=teacher_id))
        db.add(CourseEnrollment(student_id=student_id, course_id=course_id))
        db.add(CourseKnowledgeGraph(
            course_id=course_id,
            version=1,
            is_active=True,
            nodes=[{"id": node_id, "name": "KG Name", "chapter": "chapter_1"}],
            edges=[],
        ))
        db.add(LearningPath(
            user_id=student_id,
            course_id=course_id,
            nodes=[{"id": node_id, "name": "LP Name", "status": "in_progress", "mastery": 50}],
            edges=[],
            current_node_id=node_id,
            current_node_name="LP Name",
        ))
        db.add(Resource(id=f"res_{suffix}", course_id=course_id, title="LP Resource", type="document", knowledge_point="LP Name", chapter="chapter_1", content="content"))
        db.add(QuizQuestion(course_id=course_id, chapter="chapter_1", knowledge_point="LP Name", type="single_choice", content="Question", options=["A", "B"], correct_answer="A"))
        await db.commit()

        data = await NodeResourceService(db).get_node_resources(student, course_id, node_id)

    assert data["node_id"] == node_id
    assert data["node_name"] == "LP Name"
    assert data["weak_point_tutorials"][0]["title"] == "LP Resource"
    assert data["exercises"][0]["content"] == "Question"
```

- [ ] **Step 2: Run service test to verify RED**

Run from `backend/`:

```bash
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/learning_path_refactor_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_node_resource_service.py -q -p no:cacheprovider
```

Expected: import failure for `app.services.node_resource_service`.

- [ ] **Step 3: Create node resource service**

Create `backend/app/services/node_resource_service.py` with:

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import CourseCatalog, CourseOffering
from app.models.others import LearningPath, Resource
from app.models.quiz import QuizQuestion
from app.models.user import User
from app.services.course_knowledge_graphs import get_active_knowledge_graph
from app.services.resource_scope import (
    ensure_course_resource_access,
    resolve_course_resource_scope,
    resource_scope_clause,
)


class NodeResourceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_node_resources(self, current_user: User, course_id: str, node_id: str) -> dict:
        await ensure_course_resource_access(self.db, current_user, course_id)
        resource_scope = await resolve_course_resource_scope(self.db, course_id)

        node_name = node_id
        chapter = ""

        kg = await self._resolve_active_kg(course_id)
        if kg and kg.nodes:
            kg_nodes = kg.nodes if isinstance(kg.nodes, list) else []
            for kg_node in kg_nodes:
                if isinstance(kg_node, dict) and kg_node.get("id") == node_id:
                    node_name = kg_node.get("name", node_id)
                    chapter = kg_node.get("chapter", "")
                    break

        latest_path = await self._latest_learning_path(current_user.id, course_id)
        if latest_path and latest_path.nodes:
            nodes = latest_path.nodes if isinstance(latest_path.nodes, list) else []
            for node in nodes:
                if isinstance(node, dict) and node.get("id") == node_id:
                    node_name = node.get("name", node_name)
                    break

        weak_point_tutorials = await self._weak_point_tutorials(course_id, resource_scope.catalog_id, node_name)
        exercises = await self._node_exercises(course_id, node_name)
        chapter_materials = await self._chapter_materials(course_id, resource_scope.catalog_id, chapter)
        full_exercise_set = await self._full_exercise_set(course_id)

        return {
            "node_id": node_id,
            "node_name": node_name,
            "weak_point_tutorials": weak_point_tutorials,
            "exercises": exercises,
            "chapter_materials": chapter_materials,
            "full_exercise_set": full_exercise_set,
        }

    async def _resolve_active_kg(self, course_id: str):
        kg = None
        offering_result = await self.db.execute(
            select(CourseOffering).where(
                CourseOffering.id == course_id,
                CourseOffering.is_deleted == False,
            )
        )
        offering = offering_result.scalar_one_or_none()
        if offering is not None:
            catalog_result = await self.db.execute(
                select(CourseCatalog).where(
                    CourseCatalog.id == offering.catalog_id,
                    CourseCatalog.is_deleted == False,
                )
            )
            catalog = catalog_result.scalar_one_or_none()
            if catalog is not None and catalog.kg_host_course_id:
                kg = await get_active_knowledge_graph(self.db, catalog.kg_host_course_id)
        if kg is None:
            kg = await get_active_knowledge_graph(self.db, course_id)
        return kg

    async def _latest_learning_path(self, user_id: str, course_id: str) -> LearningPath | None:
        result = await self.db.execute(
            select(LearningPath)
            .where(
                LearningPath.user_id == user_id,
                LearningPath.course_id == course_id,
                LearningPath.is_deleted == False,
            )
            .order_by(LearningPath.generated_at.desc())
        )
        return result.scalars().first()

    async def _weak_point_tutorials(self, course_id: str, catalog_id: str | None, node_name: str) -> list[dict]:
        result = await self.db.execute(
            select(Resource).where(
                resource_scope_clause(course_id, catalog_id),
                Resource.knowledge_point == node_name,
                Resource.is_deleted == False,
            )
        )
        return [
            {"id": resource.id, "title": resource.title, "content": (resource.content or "")[:160]}
            for resource in result.scalars().all()
        ]

    async def _node_exercises(self, course_id: str, node_name: str) -> list[dict]:
        result = await self.db.execute(
            select(QuizQuestion).where(
                QuizQuestion.course_id == course_id,
                QuizQuestion.knowledge_point == node_name,
                QuizQuestion.is_deleted == False,
            )
        )
        return [
            {"id": question.id, "type": question.type, "content": question.content}
            for question in result.scalars().all()
        ]

    async def _chapter_materials(self, course_id: str, catalog_id: str | None, chapter: str) -> list[dict]:
        if not chapter:
            return []
        result = await self.db.execute(
            select(Resource).where(
                resource_scope_clause(course_id, catalog_id),
                Resource.chapter == chapter,
                Resource.is_deleted == False,
            )
        )
        return [
            {"id": resource.id, "title": resource.title, "type": resource.type, "url": resource.url or ""}
            for resource in result.scalars().all()
        ]

    async def _full_exercise_set(self, course_id: str) -> list[dict]:
        result = await self.db.execute(
            select(QuizQuestion)
            .where(
                QuizQuestion.course_id == course_id,
                QuizQuestion.is_deleted == False,
            )
            .limit(50)
        )
        return [
            {"id": question.id, "type": question.type, "content": question.content}
            for question in result.scalars().all()
        ]
```

- [ ] **Step 4: Delegate route to node resource service**

In `backend/app/api/v1/learning_path.py`, add:

```python
from app.services.node_resource_service import NodeResourceService
```

Replace the body of `get_node_resources(...)` with:

```python
    data = await NodeResourceService(db).get_node_resources(current_user, course_id, node_id)
    return {"code": 200, "message": "success", "data": data}
```

Remove imports no longer used by the route after this replacement:

```python
CourseCatalog
CourseOffering
LearningPath
Resource
QuizQuestion
get_active_knowledge_graph
ensure_course_resource_access
resolve_course_resource_scope
resource_scope_clause
```

- [ ] **Step 5: Run node resource regressions**

Run from `backend/`:

```bash
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/learning_path_refactor_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_node_resource_service.py tests/test_node_resources.py -q -p no:cacheprovider
```

Expected: tests pass, including 403 access guard, content truncation, chapter materials, and LP node-name precedence.

- [ ] **Step 6: Commit Task 5**

Run from `frontend/`:

```bash
git add ../backend/app/services/node_resource_service.py ../backend/tests/test_node_resource_service.py ../backend/app/api/v1/learning_path.py
git commit -m "refactor: 提取节点资源服务"
```

### Task 6: Final Route Cleanup And Full Regression

**Files:**
- Modify: `backend/app/api/v1/learning_path.py`
- Modify: `frontend/WORKFLOW.md`
- Modify: `frontend/docs/requirements-coverage.md`

- [ ] **Step 1: Inspect route size and residual helpers**

Run from `frontend/`:

```bash
wc -l ../backend/app/api/v1/learning_path.py
rg "_topo_sort_kg_nodes|_map_assessment_to_status|_apply_progress_to_nodes|_build_current_position_from_nodes|_synthesize_kg_fallback_path|_assemble_learning_path_payload|_run_learning_path_refresh_background|resource_scope_clause|QuizQuestion|Resource|CourseCatalog|CourseOffering" ../backend/app/api/v1/learning_path.py
rg "select\\(|CourseEnrollment" ../backend/app/api/v1/learning_path.py
```

Expected: first `rg` command has no matches. Second `rg` command only shows the student enrollment guard in `refresh_learning_path`.

- [ ] **Step 2: Keep route imports minimal**

`backend/app/api/v1/learning_path.py` should only need these imports after cleanup:

```python
import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.course import CourseEnrollment
from app.models.user import User
from app.schemas.ai_features import RefreshRequest
from app.services.learning_path_refresh_service import (
    LearningPathRefreshService,
    run_learning_path_refresh_background,
)
from app.services.learning_path_service import LearningPathService
from app.services.node_resource_service import NodeResourceService
```

The `select` and `CourseEnrollment` imports remain because route still performs the student enrollment guard.

- [ ] **Step 3: Run py_compile**

Run from `backend/`:

```bash
PYTHONPYCACHEPREFIX=/tmp/eduagent_pycache ../.venv/bin/python -m py_compile app/api/v1/learning_path.py app/services/learning_path_service.py app/services/learning_path_refresh_service.py app/services/node_resource_service.py
```

Expected: command exits `0`.

- [ ] **Step 4: Run full learning-path regression**

Run from `backend/`:

```bash
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/learning_path_refactor_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_learning_path_realtime.py tests/test_learning_path_fallback.py tests/test_node_resources.py tests/test_node_resource_service.py -q -p no:cacheprovider
```

Expected: all tests pass.

- [ ] **Step 5: Run refresh and lock regression**

Run from `backend/`:

```bash
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/learning_path_refactor_refresh_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_refresh_async.py tests/test_lock_async.py -q -p no:cacheprovider
```

Expected: all tests pass, or only unrelated profile/evaluation failures already present before this plan. If unrelated failures appear, include exact failing test names in `WORKFLOW.md`.

- [ ] **Step 6: Update WORKFLOW.md**

Append this entry to `frontend/WORKFLOW.md`:

```markdown

### 2026-06-19 (后端 learning_path.py 路由分层重构)

- **改了什么文件**: `backend/app/api/v1/learning_path.py`, `backend/app/services/learning_path_service.py`, `backend/app/services/learning_path_refresh_service.py`, `backend/app/services/node_resource_service.py`, `backend/tests/test_learning_path_realtime.py`, `backend/tests/test_learning_path_fallback.py`, `backend/tests/test_node_resources.py`, `backend/tests/test_node_resource_service.py`, `backend/tests/test_refresh_async.py`, `backend/tests/test_lock_async.py`
- **核心改动**: 按 `Router -> Service -> DB` 分层拆分学习路径胖路由。读取路径、KG fallback、实时进度合并迁入 `LearningPathService`；Agent payload 组装、refresh task 创建、后台 runner 迁入 `LearningPathRefreshService`；节点资源聚合迁入 `NodeResourceService`。Route 保留鉴权、参数、commit point、后台调度和响应包装。
- **测试结果**: `py_compile` 通过；learning path 局部回归通过；refresh/lock 回归通过。
- **是否有接口漂移**: 无。`GET /api/v1/learning-path`、`POST /api/v1/learning-path/refresh`、`GET /api/v1/learning-path/nodes/{node_id}/resources` 的响应字段、状态码、task_type 和 Agent 路径保持不变。
```

If a broad regression has unrelated existing failures, replace `refresh/lock 回归通过` with the exact command and failure names.

- [ ] **Step 7: Update requirements coverage**

In `frontend/docs/requirements-coverage.md`, add or adjust the learning path backend implementation note with this sentence:

```markdown
- 2026-06-19：`learning_path.py` 已按 `Router -> Service -> DB` 拆分为 `LearningPathService`、`LearningPathRefreshService`、`NodeResourceService`，接口契约不变。
```

Place it near the existing learning-path/resource coverage section.

- [ ] **Step 8: Final commit**

Run from `frontend/`:

```bash
git add ../backend/app/api/v1/learning_path.py ../backend/app/services/learning_path_service.py ../backend/app/services/learning_path_refresh_service.py ../backend/app/services/node_resource_service.py ../backend/tests/test_learning_path_realtime.py ../backend/tests/test_learning_path_fallback.py ../backend/tests/test_node_resources.py ../backend/tests/test_node_resource_service.py ../backend/tests/test_refresh_async.py ../backend/tests/test_lock_async.py WORKFLOW.md docs/requirements-coverage.md
git commit -m "refactor: 完成学习路径路由分层"
```

## Self-Review Checklist For Implementer

- [ ] `backend/app/api/v1/learning_path.py` no longer contains learning path sorting, progress merge, KG fallback synthesis, Agent payload assembly, background write logic, or node resource SQL aggregation.
- [ ] Route contains `# commit point: task persisted before background dispatch` before dispatching refresh background task.
- [ ] `NodeResourceService` imports scope helpers from `app.services.resource_scope`; no new shared folder was introduced.
- [ ] `GET /learning-path` returns the same wrapper and data keys.
- [ ] `POST /learning-path/refresh` returns HTTP 202 and keeps `task_type="learning_path_refresh"`.
- [ ] `GET /learning-path/nodes/{node_id}/resources` returns the same data keys.
- [ ] All changed tests import from service modules, not private route helpers.
- [ ] `WORKFLOW.md` states whether there was interface drift; expected value is no drift.
