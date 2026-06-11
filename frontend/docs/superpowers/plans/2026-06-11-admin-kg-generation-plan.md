# Admin KG Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an Admin CourseCatalog drawer workflow that creates active course knowledge graph versions through a Backend async task.

**Architecture:** Extract the reusable KG generation logic from `../backend/tools/generate_knowledge_graph.py` into a Backend service, then expose it through Admin-only CourseCatalog API endpoints. The frontend stays in `CourseCatalogDrawer`, polls existing `/tasks/{task_id}`, and does not call CLI scripts or Agent Service directly.

**Tech Stack:** FastAPI, SQLAlchemy async, MySQL JSON columns, React/Vite, Playwright E2E, pytest/pytest-asyncio.

---

## File Map

- Create: `../backend/app/services/kg_generation.py`
  - Owns KG input validation, LLM outline generation, optional grounding prune, and version creation.
- Modify: `../backend/tools/generate_knowledge_graph.py`
  - Keeps CLI behavior but delegates core logic to `app.services.kg_generation`.
- Modify: `../backend/app/schemas/catalog.py`
  - Adds Admin KG generation/status request and response schemas.
- Modify: `../backend/app/api/v1/catalogs.py`
  - Adds Admin KG status and generation endpoints, CourseOffering resolution, duplicate task guard, and background runner.
- Modify: `../backend/app/api/v1/tasks.py`
  - Allows Admin users to poll `kg_generation` tasks.
- Test: `../backend/tests/test_admin_catalog_kg_generation.py`
  - Covers service/API behavior, validation, permissions, duplicate task guard, and active graph creation.
- Test: `../backend/tests/test_generate_kg.py`
  - Adjusts CLI unit tests after service extraction.
- Modify: `../docs/10-client-api/Client-API.openapi.json`
  - Adds formal Client API contract.
- Modify: `../docs/10-client-api/API_前端接口规范.md`
  - Adds human-readable Client API contract.
- Modify: `src/api/services/admin.js`
  - Adds Admin KG status/generation API methods.
- Modify: `src/components/admin/CourseCatalogDrawer.jsx`
  - Adds KG section, form state, polling, and `kg_not_ready` guidance.
- Modify: `e2e/specs.spec.js`
  - Adds Admin drawer KG generation E2E coverage.
- Modify: `WORKFLOW.md`
  - Records implementation and verification.
- Modify: `docs/feature-ledger.md`
  - Updates status only if the implementation and tests complete.

## Task 1: Backend KG Generation Service

**Files:**
- Create: `../backend/app/services/kg_generation.py`
- Test: `../backend/tests/test_admin_catalog_kg_generation.py`
- Existing reference: `../backend/tools/generate_knowledge_graph.py`
- Existing reference: `../backend/app/services/course_knowledge_graphs.py`

- [ ] **Step 1: Write failing service tests**

Add `../backend/tests/test_admin_catalog_kg_generation.py` with the shared test setup used by `test_admin_catalog_resource_generation.py`, then add pure service tests:

```python
import os
import sys
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "mysql+aiomysql://root:123456@127.0.0.1:3306/admin_catalog_kg_generation_test?charset=utf8mb4",
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.base import Base
from app.db.session import async_session_factory, engine
from app.models.course import Course
from app.models.others import CourseKnowledgeGraph
from app.models.user import User
from app.models.catalog import CourseCatalog, CourseOffering
from app.services.kg_generation import (
    KGGenerationInputError,
    generate_knowledge_graph_version,
    validate_kg_json_payload,
)


@pytest_asyncio.fixture(autouse=True)
async def _dispose_db_engine_after_test():
    yield
    await engine.dispose()


async def _reset_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def _seed_catalog_and_course(
    catalog_id: str = "catalog-kg-gen",
    course_id: str = "course-kg-gen",
) -> tuple[str, str]:
    async with async_session_factory() as db:
        db.add(User(id="teacher-kg-gen", email="teacher@example.com", username="teacher", password_hash="x", role="teacher"))
        db.add(CourseCatalog(id=catalog_id, title="KG Catalog", status="draft", knowledge_status="draft", chunk_count=0))
        db.add(Course(id=course_id, name="KG Course", course_code="KG001", teacher_id="teacher-kg-gen"))
        db.add(CourseOffering(id=course_id, name="KG Course", catalog_id=catalog_id, teacher_id="teacher-kg-gen", class_code="KG001"))
        await db.commit()
    return catalog_id, course_id


def test_validate_kg_json_payload_rejects_missing_node_name():
    with pytest.raises(KGGenerationInputError) as exc:
        validate_kg_json_payload({
            "nodes": [{"id": "pointer", "chapter": "第 6 章"}],
            "edges": [],
        })
    assert "No valid nodes" in str(exc.value)


def test_validate_kg_json_payload_removes_dangling_edges():
    nodes, edges = validate_kg_json_payload({
        "nodes": [{"id": "pointer", "name": "指针", "chapter": "第 6 章"}],
        "edges": [{"from": "missing", "to": "pointer"}],
    })
    assert nodes == [{"id": "pointer", "name": "指针", "chapter": "第 6 章"}]
    assert edges == []


@pytest.mark.asyncio
async def test_generate_kg_json_creates_active_version_without_chunk_ready_gate():
    await _reset_db()
    _, course_id = await _seed_catalog_and_course()

    result = await generate_knowledge_graph_version(
        course_id=course_id,
        source_type="kg_json",
        kg_json={
            "nodes": [{"id": "pointer", "name": "指针", "chapter": "第 6 章"}],
            "edges": [],
        },
        activate=True,
    )

    assert result["course_id"] == course_id
    assert result["version"] == 1
    assert result["node_count"] == 1
    assert result["edge_count"] == 0
    assert result["source_type"] == "manual_import"
    assert result["generation_strategy"] == "manual_kg_json"
    assert result["activated"] is True

    async with async_session_factory() as db:
        graph = (await db.execute(select(CourseKnowledgeGraph))).scalar_one()
        assert graph.course_id == course_id
        assert graph.is_active is True


@pytest.mark.asyncio
async def test_generate_outline_text_uses_llm_and_creates_version():
    await _reset_db()
    _, course_id = await _seed_catalog_and_course()

    with patch("app.services.kg_generation.generate_kg_from_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = {
            "nodes": [{"id": "array", "name": "数组", "chapter": "第 5 章"}],
            "edges": [],
        }
        result = await generate_knowledge_graph_version(
            course_id=course_id,
            source_type="outline_text",
            outline_text="第 5 章 数组",
            activate=True,
        )

    mock_llm.assert_awaited_once_with("第 5 章 数组")
    assert result["source_type"] == "outline_llm"
    assert result["generation_strategy"] == "legacy_outline"
    assert result["node_count"] == 1
```

- [ ] **Step 2: Run service tests and confirm import failure**

Run:

```bash
cd ../backend && TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/admin_catalog_kg_generation_task1?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_admin_catalog_kg_generation.py -q -p no:cacheprovider
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.kg_generation'`.

- [ ] **Step 3: Implement `app/services/kg_generation.py`**

Create `../backend/app/services/kg_generation.py`:

```python
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path
from typing import Any

import httpx

from app.db.session import async_session_factory
from app.services.course_knowledge_graphs import (
    create_knowledge_graph_version,
    get_active_knowledge_graph,
)
from app.services.kg_body_grounding import (
    GroundingMatch,
    USABLE_SUPPORT_THRESHOLD,
    filter_supported_knowledge_graph,
)


class KGGenerationInputError(ValueError):
    """Raised when Admin-provided KG generation input is invalid."""


async def generate_kg_from_llm(outline: str) -> dict[str, Any]:
    api_key = os.environ.get("LLM_API_KEY")
    base_url = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com")
    model = os.environ.get("LLM_MODEL", "deepseek-chat")
    if not api_key:
        raise KGGenerationInputError("LLM_API_KEY environment variable is not set")

    prompt = f"""You are a professional educational design expert.
Please extract a course knowledge graph from the given syllabus/outline.
Your output must be a valid JSON object containing "nodes" and "edges".

Requirements for nodes:
- Each node represents a knowledge point.
- Must contain fields: "id", "name", and "chapter".

Requirements for edges:
- Must contain fields: "from" and "to".

Outline text:
\"\"\"
{outline}
\"\"\"

Ensure that the output contains ONLY the valid JSON object without any markdown formatting codeblocks or other explanations.
"""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(f"{base_url.rstrip('/')}/chat/completions", json=payload, headers=headers)
        resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        lines = content.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        content = "\n".join(lines).strip()
    return json.loads(content)


def validate_kg_json_payload(data: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw_nodes = data.get("nodes", [])
    raw_edges = data.get("edges", [])
    if not isinstance(raw_nodes, list) or not isinstance(raw_edges, list):
        raise KGGenerationInputError("KG JSON must contain nodes and edges lists")

    cleaned_nodes: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for node in raw_nodes:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id") or "").strip()
        name = str(node.get("name") or "").strip()
        chapter = str(node.get("chapter") or "").strip()
        if not node_id or not name or not chapter or node_id in seen_ids:
            continue
        seen_ids.add(node_id)
        cleaned_nodes.append({"id": node_id, "name": name, "chapter": chapter})

    if not cleaned_nodes:
        raise KGGenerationInputError("No valid nodes extracted from KG JSON")

    cleaned_edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str]] = set()
    for edge in raw_edges:
        if not isinstance(edge, dict):
            continue
        from_id = str(edge.get("from") or "").strip()
        to_id = str(edge.get("to") or "").strip()
        edge_key = (from_id, to_id)
        if not from_id or not to_id or from_id not in seen_ids or to_id not in seen_ids or edge_key in seen_edges:
            continue
        seen_edges.add(edge_key)
        cleaned_edges.append({"from": from_id, "to": to_id})
    return cleaned_nodes, cleaned_edges


def load_kg_json_file(kg_file: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    data = json.loads(kg_file.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise KGGenerationInputError("KG JSON must be an object containing nodes and edges")
    return validate_kg_json_payload(data)


def load_grounding_matches(grounding_file: Path) -> list[GroundingMatch]:
    data = json.loads(grounding_file.read_text(encoding="utf-8"))
    results = data.get("results") if isinstance(data, dict) else data
    if not isinstance(results, list):
        raise KGGenerationInputError("Grounding file must contain a results list")
    matches: list[GroundingMatch] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        node_id = str(item.get("node_id") or "").strip()
        if not node_id:
            continue
        score_value = item.get("body_top1_score")
        score = float(score_value) if isinstance(score_value, int | float) else 0.0
        matches.append(GroundingMatch(
            node_id=node_id,
            score=score,
            chunk_id=str(item.get("chunk_id") or ""),
            content_preview=str(item.get("preview") or item.get("content_preview") or ""),
        ))
    return matches


def route_a_generation_strategy_for_threshold(threshold: float) -> str:
    if math.isclose(threshold, USABLE_SUPPORT_THRESHOLD, rel_tol=0.0, abs_tol=1e-9):
        return "route_a_prune_usable_060"
    return "route_a_prune_unsupported"


def prune_kg_with_grounding_file(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    grounding_file: Path,
    *,
    threshold: float = USABLE_SUPPORT_THRESHOLD,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    kept_nodes, kept_edges, metrics = filter_supported_knowledge_graph(
        nodes,
        edges,
        load_grounding_matches(grounding_file),
        threshold=threshold,
    )
    metrics["grounding_source_file"] = str(grounding_file)
    if not kept_nodes:
        raise KGGenerationInputError("Route A pruning removed all nodes")
    return kept_nodes, kept_edges, metrics


def _build_import_result(graph) -> dict[str, Any]:
    return {
        "course_id": graph.course_id,
        "graph_id": graph.id,
        "version": graph.version,
        "node_count": len(graph.nodes or []),
        "edge_count": len(graph.edges or []),
        "source_type": graph.source_type,
        "generation_strategy": graph.generation_strategy,
        "metrics": graph.metrics,
        "activated": graph.is_active,
    }


async def save_knowledge_graph_version(
    *,
    course_id: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    source_type: str,
    generation_strategy: str,
    metrics: dict[str, Any] | None = None,
    activate: bool = True,
) -> dict[str, Any]:
    async with async_session_factory() as db:
        active_graph = await get_active_knowledge_graph(db, course_id)
        graph = await create_knowledge_graph_version(
            db,
            course_id=course_id,
            nodes=nodes,
            edges=edges,
            source_type=source_type,
            generation_strategy=generation_strategy,
            metrics=metrics,
            activate=activate,
            parent_graph_id=active_graph.id if active_graph else None,
        )
        await db.commit()
        return _build_import_result(graph)


async def generate_knowledge_graph_version(
    *,
    course_id: str,
    source_type: str,
    outline_text: str | None = None,
    kg_json: dict[str, Any] | None = None,
    grounding_file: Path | None = None,
    grounding_threshold: float = USABLE_SUPPORT_THRESHOLD,
    activate: bool = True,
) -> dict[str, Any]:
    if source_type == "outline_text":
        outline = (outline_text or "").strip()
        if not outline:
            raise KGGenerationInputError("outline_text is required")
        nodes, edges = validate_kg_json_payload(await generate_kg_from_llm(outline))
        graph_source_type = "outline_llm"
        generation_strategy = "legacy_outline"
        metrics: dict[str, Any] = {"node_count": len(nodes), "edge_count": len(edges)}
    elif source_type == "kg_json":
        if kg_json is None:
            raise KGGenerationInputError("kg_json is required")
        nodes, edges = validate_kg_json_payload(kg_json)
        graph_source_type = "manual_import"
        generation_strategy = "manual_kg_json"
        metrics = {"node_count": len(nodes), "edge_count": len(edges)}
    else:
        raise KGGenerationInputError("source_type must be outline_text or kg_json")

    if grounding_file is not None:
        nodes, edges, metrics = prune_kg_with_grounding_file(
            nodes,
            edges,
            grounding_file,
            threshold=grounding_threshold,
        )
        graph_source_type = "route_a_body_grounded"
        generation_strategy = route_a_generation_strategy_for_threshold(grounding_threshold)

    return await save_knowledge_graph_version(
        course_id=course_id,
        nodes=nodes,
        edges=edges,
        source_type=graph_source_type,
        generation_strategy=generation_strategy,
        metrics=metrics,
        activate=activate,
    )
```

- [ ] **Step 4: Run service tests**

Run:

```bash
cd ../backend && TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/admin_catalog_kg_generation_task1?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_admin_catalog_kg_generation.py -q -p no:cacheprovider
```

Expected: PASS for service tests added in this task.

- [ ] **Step 5: Commit Task 1**

```bash
git add ../backend/app/services/kg_generation.py ../backend/tests/test_admin_catalog_kg_generation.py
git commit -m "抽取KG生成服务"
```

## Task 2: Admin KG API and Task Semantics

**Files:**
- Modify: `../backend/app/schemas/catalog.py`
- Modify: `../backend/app/api/v1/catalogs.py`
- Modify: `../backend/app/api/v1/tasks.py`
- Test: `../backend/tests/test_admin_catalog_kg_generation.py`

- [ ] **Step 1: Add failing API tests**

Append these tests to `../backend/tests/test_admin_catalog_kg_generation.py`:

```python
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update

from app.main import app
from app.models.others import AsyncTask


def _auth_headers(user_id: str, role: str) -> dict[str, str]:
    from app.core.security import create_token
    return {"Authorization": f"Bearer {create_token(user_id, role)}"}


async def _seed_user(user_id: str, role: str) -> None:
    async with async_session_factory() as db:
        db.add(User(id=user_id, email=f"{user_id}@example.com", username=user_id, password_hash="x", role=role))
        await db.commit()


@pytest.mark.asyncio
async def test_admin_kg_status_returns_empty_active_graph():
    await _reset_db()
    await _seed_user("admin-kg-gen", "admin")
    catalog_id, course_id = await _seed_catalog_and_course()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            f"/api/v1/admin/course-catalogs/{catalog_id}/knowledge-graphs",
            headers=_auth_headers("admin-kg-gen", "admin"),
        )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["catalog_id"] == catalog_id
    assert data["course_id"] == course_id
    assert data["active_graph"] is None
    assert data["last_generation_task"] is None


@pytest.mark.asyncio
async def test_non_admin_cannot_start_kg_generation():
    await _reset_db()
    await _seed_user("student-kg-gen", "student")
    catalog_id, _ = await _seed_catalog_and_course()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/admin/course-catalogs/{catalog_id}/knowledge-graphs/generations",
            headers=_auth_headers("student-kg-gen", "student"),
            json={"source_type": "kg_json", "kg_json": {"nodes": [], "edges": []}, "activate": True},
        )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_start_kg_generation_rejects_missing_offering():
    await _reset_db()
    await _seed_user("admin-kg-gen", "admin")
    async with async_session_factory() as db:
        db.add(CourseCatalog(id="catalog-no-offering", title="No Offering", status="draft", knowledge_status="draft"))
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/admin/course-catalogs/catalog-no-offering/knowledge-graphs/generations",
            headers=_auth_headers("admin-kg-gen", "admin"),
            json={"source_type": "kg_json", "kg_json": {"nodes": [], "edges": []}, "activate": True},
        )

    assert response.status_code == 409
    assert response.json()["detail"]["data"]["error_code"] == "offering_missing"


@pytest.mark.asyncio
async def test_admin_start_kg_generation_rejects_duplicate_processing_task():
    await _reset_db()
    await _seed_user("admin-kg-gen", "admin")
    catalog_id, course_id = await _seed_catalog_and_course()
    async with async_session_factory() as db:
        db.add(AsyncTask(
            id="task-kg-running",
            task_type="kg_generation",
            status="processing",
            user_id="admin-kg-gen",
            course_id=course_id,
            result={"catalog_id": catalog_id, "course_id": course_id},
        ))
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/admin/course-catalogs/{catalog_id}/knowledge-graphs/generations",
            headers=_auth_headers("admin-kg-gen", "admin"),
            json={"source_type": "kg_json", "kg_json": {"nodes": [], "edges": []}, "activate": True},
        )

    assert response.status_code == 409
    assert response.json()["detail"]["data"]["error_code"] == "kg_task_running"


@pytest.mark.asyncio
async def test_admin_start_kg_generation_creates_task_and_background_creates_graph():
    await _reset_db()
    await _seed_user("admin-kg-gen", "admin")
    catalog_id, course_id = await _seed_catalog_and_course()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/admin/course-catalogs/{catalog_id}/knowledge-graphs/generations",
            headers=_auth_headers("admin-kg-gen", "admin"),
            json={
                "source_type": "kg_json",
                "kg_json": {
                    "nodes": [{"id": "pointer", "name": "指针", "chapter": "第 6 章"}],
                    "edges": [],
                },
                "activate": True,
            },
        )

    assert response.status_code == 202, response.text
    payload = response.json()["data"]
    assert payload["catalog_id"] == catalog_id
    assert payload["course_id"] == course_id
    assert payload["status"] == "processing"

    async with async_session_factory() as db:
        task = await db.get(AsyncTask, payload["task_id"])
        assert task is not None
        assert task.task_type == "kg_generation"
        assert task.result["catalog_id"] == catalog_id
        assert task.result["source_type"] == "kg_json"


@pytest.mark.asyncio
async def test_admin_can_poll_kg_generation_task_owned_by_admin():
    await _reset_db()
    await _seed_user("admin-kg-gen", "admin")
    async with async_session_factory() as db:
        db.add(AsyncTask(
            id="task-kg-poll",
            task_type="kg_generation",
            status="completed",
            user_id="another-admin",
            result={"catalog_id": "catalog-kg-gen"},
        ))
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/tasks/task-kg-poll",
            headers=_auth_headers("admin-kg-gen", "admin"),
        )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["task_type"] == "kg_generation"
```

- [ ] **Step 2: Run API tests and confirm route failure**

Run:

```bash
cd ../backend && TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/admin_catalog_kg_generation_task2?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_admin_catalog_kg_generation.py -q -p no:cacheprovider
```

Expected: FAIL with 404 for the new Admin KG endpoints.

- [ ] **Step 3: Add schemas in `../backend/app/schemas/catalog.py`**

Add imports and models:

```python
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class CatalogKnowledgeGraphGenerationRequest(BaseModel):
    source_type: Literal["outline_text", "kg_json"]
    outline_text: str | None = Field(default=None, max_length=200000)
    kg_json: dict[str, Any] | None = None
    activate: bool = True

    @model_validator(mode="after")
    def validate_source_payload(self):
        if self.source_type == "outline_text" and not (self.outline_text or "").strip():
            raise ValueError("outline_text is required")
        if self.source_type == "kg_json" and self.kg_json is None:
            raise ValueError("kg_json is required")
        return self


class CatalogKnowledgeGraphGenerationData(BaseModel):
    task_id: str
    catalog_id: str
    course_id: str
    status: str


class CatalogKnowledgeGraphGenerationResponse(BaseModel):
    code: int = 202
    message: str = "accepted"
    data: CatalogKnowledgeGraphGenerationData


class CatalogKnowledgeGraphSummary(BaseModel):
    id: str
    version: int
    node_count: int
    edge_count: int
    source_type: str
    generation_strategy: str
    metrics: dict[str, Any] | None = None
    create_time: str
    update_time: str


class CatalogKnowledgeGraphTaskSummary(BaseModel):
    task_id: str
    status: str
    error_code: str | None = None
    error_message: str = ""


class CatalogKnowledgeGraphStatusData(BaseModel):
    catalog_id: str
    course_id: str | None = None
    active_graph: CatalogKnowledgeGraphSummary | None = None
    last_generation_task: CatalogKnowledgeGraphTaskSummary | None = None
```

If `catalog.py` already imports `BaseModel` or `Field`, merge imports instead of duplicating them.

- [ ] **Step 4: Implement API helpers and endpoints in `../backend/app/api/v1/catalogs.py`**

Add imports:

```python
import asyncio

from app.models.others import CourseKnowledgeGraph
from app.schemas.catalog import (
    CatalogKnowledgeGraphGenerationRequest,
)
from app.services.kg_generation import (
    KGGenerationInputError,
    generate_knowledge_graph_version,
)
```

Add helper functions near existing catalog helpers:

```python
KG_TASK_TYPE = "kg_generation"


def _admin_business_error(status_code: int, code: int, message: str, error_code: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message, "data": {"error_code": error_code}},
    )


async def _first_course_offering_for_catalog(db: AsyncSession, catalog_id: str) -> CourseOffering | None:
    result = await db.execute(
        select(CourseOffering)
        .where(CourseOffering.catalog_id == catalog_id, CourseOffering.is_deleted == False)
        .order_by(CourseOffering.create_time.asc(), CourseOffering.id.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _task_catalog_id_expr():
    return AsyncTask.result["catalog_id"].as_string()


async def _processing_kg_task_for_catalog(db: AsyncSession, catalog_id: str) -> AsyncTask | None:
    result = await db.execute(
        select(AsyncTask)
        .where(
            AsyncTask.task_type == KG_TASK_TYPE,
            AsyncTask.status == "processing",
            AsyncTask.is_deleted == False,
            _task_catalog_id_expr() == catalog_id,
        )
        .order_by(AsyncTask.create_time.desc(), AsyncTask.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _last_kg_task_for_catalog(db: AsyncSession, catalog_id: str) -> AsyncTask | None:
    result = await db.execute(
        select(AsyncTask)
        .where(
            AsyncTask.task_type == KG_TASK_TYPE,
            AsyncTask.is_deleted == False,
            _task_catalog_id_expr() == catalog_id,
        )
        .order_by(AsyncTask.create_time.desc(), AsyncTask.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
```

Keep the JSON predicate centralized in `_task_catalog_id_expr()` and verify it against MySQL. If `as_string()` does not produce the expected MySQL SQL, replace only this helper with the MySQL JSON extraction expression used by the project:

```python
from sqlalchemy import func


def _task_catalog_id_expr():
    return func.json_extract(AsyncTask.result, "$.catalog_id")
```

Use the expression that passes the MySQL tests; do not add alternate database fallbacks.

Add background runner:

```python
async def _run_kg_generation_background(
    *,
    task_id: str,
    course_id: str,
    source_type: str,
    outline_text: str | None,
    kg_json: dict | None,
    activate: bool,
) -> None:
    async with async_session_factory() as db:
        task = await db.get(AsyncTask, task_id)
        if task is None:
            return
        try:
            result = await generate_knowledge_graph_version(
                course_id=course_id,
                source_type=source_type,
                outline_text=outline_text,
                kg_json=kg_json,
                activate=activate,
            )
            task.status = "completed"
            task.progress = 100
            task.result = {**(task.result or {}), **result}
            task.error_code = None
            task.error_message = ""
            task.completed_at = _now_utc()
        except KGGenerationInputError as exc:
            task.status = "failed"
            task.progress = 100
            task.error_code = "kg_invalid_input"
            task.error_message = str(exc)[:500]
            task.completed_at = _now_utc()
        except Exception as exc:
            task.status = "failed"
            task.progress = 100
            task.error_code = "kg_llm_failed"
            task.error_message = str(exc)[:500]
            task.completed_at = _now_utc()
        await db.commit()
```

Add endpoints before the resource generation endpoint:

```python
@router.get("/admin/course-catalogs/{catalog_id}/knowledge-graphs")
async def admin_get_catalog_knowledge_graphs(
    catalog_id: str,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    catalog = await _get_admin_catalog_or_404(db, catalog_id)
    offering = await _first_course_offering_for_catalog(db, catalog.id)
    course_id = offering.id if offering else None
    graph = await get_active_knowledge_graph(db, course_id) if course_id else None
    last_task = await _last_kg_task_for_catalog(db, catalog.id)

    active_graph = None
    if graph is not None:
        active_graph = {
            "id": graph.id,
            "version": graph.version,
            "node_count": len(graph.nodes or []),
            "edge_count": len(graph.edges or []),
            "source_type": graph.source_type,
            "generation_strategy": graph.generation_strategy,
            "metrics": graph.metrics,
            "create_time": graph.create_time.isoformat() if graph.create_time else "",
            "update_time": graph.update_time.isoformat() if graph.update_time else "",
        }

    return {
        "code": 200,
        "message": "success",
        "data": {
            "catalog_id": catalog.id,
            "course_id": course_id,
            "active_graph": active_graph,
            "last_generation_task": (
                {
                    "task_id": last_task.id,
                    "status": last_task.status,
                    "error_code": last_task.error_code,
                    "error_message": last_task.error_message or "",
                }
                if last_task else None
            ),
        },
    }


@router.post("/admin/course-catalogs/{catalog_id}/knowledge-graphs/generations", status_code=202)
async def admin_generate_catalog_knowledge_graph(
    catalog_id: str,
    req: CatalogKnowledgeGraphGenerationRequest,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    catalog = await _get_admin_catalog_or_404(db, catalog_id)
    offering = await _first_course_offering_for_catalog(db, catalog.id)
    if offering is None:
        raise _admin_business_error(status.HTTP_409_CONFLICT, 40916, "课程资源库尚未绑定教学班", "offering_missing")
    existing_task = await _processing_kg_task_for_catalog(db, catalog.id)
    if existing_task is not None:
        raise _admin_business_error(status.HTTP_409_CONFLICT, 40917, "知识图谱生成任务正在进行中", "kg_task_running")

    task = AsyncTask(
        task_type=KG_TASK_TYPE,
        status="processing",
        progress=0,
        user_id=current_user.id,
        course_id=offering.id,
        result={
            "catalog_id": catalog.id,
            "course_id": offering.id,
            "source_type": req.source_type,
            "activate": req.activate,
        },
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)
    await db.commit()

    asyncio.create_task(_run_kg_generation_background(
        task_id=task.id,
        course_id=offering.id,
        source_type=req.source_type,
        outline_text=req.outline_text,
        kg_json=req.kg_json,
        activate=req.activate,
    ))
    return {
        "code": 202,
        "message": "accepted",
        "data": {
            "task_id": task.id,
            "catalog_id": catalog.id,
            "course_id": offering.id,
            "status": "processing",
        },
    }
```

- [ ] **Step 5: Permit Admin polling of KG tasks in `../backend/app/api/v1/tasks.py`**

Change:

```python
allowed_admin_task = current_user.role == "admin" and task.task_type in {
    "course_catalog_ingestion",
    "resource_generation",
}
```

to:

```python
allowed_admin_task = current_user.role == "admin" and task.task_type in {
    "course_catalog_ingestion",
    "resource_generation",
    "kg_generation",
}
```

- [ ] **Step 6: Run API tests**

Run:

```bash
cd ../backend && TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/admin_catalog_kg_generation_task2?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_admin_catalog_kg_generation.py -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 7: Run related backend regressions**

Run:

```bash
cd ../backend && TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/admin_catalog_resource_generation_regression?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_admin_catalog_resource_generation.py tests/test_course_knowledge_graph_versions.py -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 8: Commit Task 2**

```bash
git add ../backend/app/schemas/catalog.py ../backend/app/api/v1/catalogs.py ../backend/app/api/v1/tasks.py ../backend/tests/test_admin_catalog_kg_generation.py
git commit -m "新增管理员KG生成接口"
```

## Task 3: Refactor CLI to Use the Service

**Files:**
- Modify: `../backend/tools/generate_knowledge_graph.py`
- Modify: `../backend/tests/test_generate_kg.py`
- Test: `../backend/tests/test_generate_kg.py`

- [ ] **Step 1: Update failing CLI tests**

In `../backend/tests/test_generate_kg.py`, import the service functions and adjust assertions so the CLI module exposes only CLI parser/runner helpers while validation lives in `app.services.kg_generation`:

```python
from app.services.kg_generation import (
    load_kg_json_file,
    route_a_generation_strategy_for_threshold,
    validate_kg_json_payload,
)


def test_validate_and_clean_kg_success():
    nodes, edges = validate_kg_json_payload({
        "nodes": [{"id": "n1", "name": "Node 1", "chapter": "Chapter 1"}],
        "edges": [],
    })
    assert nodes == [{"id": "n1", "name": "Node 1", "chapter": "Chapter 1"}]
    assert edges == []


def test_load_kg_json_validates_existing_graph_file(tmp_path: Path) -> None:
    kg_file = tmp_path / "kg.json"
    kg_file.write_text(
        json.dumps({
            "nodes": [{"id": "n1", "name": "Node 1", "chapter": "Chapter 1"}],
            "edges": [],
        }),
        encoding="utf-8",
    )
    nodes, edges = load_kg_json_file(kg_file)
    assert nodes[0]["id"] == "n1"
    assert edges == []
```

Keep existing parser tests for `--course-id`, `--file`, `--outline`, `--kg-json`, `--grounding-file`, and `--grounding-threshold`.

- [ ] **Step 2: Run CLI tests and confirm failures**

Run:

```bash
cd ../backend && ../.venv/bin/python -m pytest tests/test_generate_kg.py -q -p no:cacheprovider
```

Expected: FAIL where tests still reference functions removed from `tools.generate_knowledge_graph`.

- [ ] **Step 3: Replace duplicated CLI logic with service calls**

In `../backend/tools/generate_knowledge_graph.py`, keep:

- `build_arg_parser`
- `main_async`
- `_run_cli`
- `main`

Remove duplicate implementations of:

- `generate_kg_from_llm`
- `validate_and_clean_kg`
- `load_kg_json`
- `load_grounding_matches`
- `prune_kg_with_grounding_file`
- `route_a_generation_strategy_for_threshold`
- `save_knowledge_graph_version`

Add imports:

```python
from app.db.session import engine
from app.services.kg_generation import (
    KGGenerationInputError,
    generate_kg_from_llm,
    load_kg_json_file,
    prune_kg_with_grounding_file,
    route_a_generation_strategy_for_threshold,
    save_knowledge_graph_version,
    validate_kg_json_payload,
)
from app.services.kg_body_grounding import USABLE_SUPPORT_THRESHOLD
```

Inside `main_async`, replace direct DB save with:

```python
    if args.kg_json:
        nodes, edges = load_kg_json_file(args.kg_json)
        graph_source_type = "manual_import"
        generation_strategy = "manual_kg_json"
        metrics = {"node_count": len(nodes), "edge_count": len(edges)}
    else:
        if args.file:
            file_path = Path(args.file)
            if not file_path.exists():
                print(f"ERROR: Outline file does not exist: {file_path}", file=sys.stderr)
                sys.exit(1)
            outline_text = file_path.read_text(encoding="utf-8")
        else:
            outline_text = args.outline
        if not outline_text.strip():
            print("ERROR: Syllabus/Outline content is empty.", file=sys.stderr)
            sys.exit(1)
        raw_data = await generate_kg_from_llm(outline_text)
        nodes, edges = validate_kg_json_payload(raw_data)
        graph_source_type = "outline_llm"
        generation_strategy = "legacy_outline"
        metrics = {"node_count": len(nodes), "edge_count": len(edges)}

    if args.grounding_file:
        nodes, edges, metrics = prune_kg_with_grounding_file(
            nodes,
            edges,
            args.grounding_file,
            threshold=args.grounding_threshold,
        )
        graph_source_type = "route_a_body_grounded"
        generation_strategy = route_a_generation_strategy_for_threshold(args.grounding_threshold)

    print("\n================ KG EXTRACTED PREVIEW ================")
    print(f"Course ID: {course_id}")
    print(f"Nodes count: {len(nodes)}")
    for node in nodes:
        print(f"  Node: [{node['id']}] {node['name']} (Chapter: {node['chapter']})")
    print(f"\nEdges count: {len(edges)}")
    for edge in edges:
        print(f"  Dependency: {edge['from']} -> {edge['to']}")
    print("======================================================")

    if not args.auto:
        confirm = input("\nDo you want to import this knowledge graph into the database? (y/n): ").strip().lower()
        if confirm != "y":
            print("Import cancelled by user.")
            sys.exit(0)

    result = await save_knowledge_graph_version(
        course_id=course_id,
        nodes=nodes,
        edges=edges,
        source_type=graph_source_type,
        generation_strategy=generation_strategy,
        metrics=metrics,
        activate=True,
    )
```
The final implementation must create exactly one active KG version per CLI invocation. LLM generation, grounding pruning, and database save each happen at most once.

- [ ] **Step 4: Run CLI tests**

Run:

```bash
cd ../backend && ../.venv/bin/python -m pytest tests/test_generate_kg.py -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 5: Run combined KG regression**

Run:

```bash
cd ../backend && TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/kg_cli_service_regression?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_generate_kg.py tests/test_course_knowledge_graph_versions.py tests/test_admin_catalog_kg_generation.py -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 6: Commit Task 3**

```bash
git add ../backend/tools/generate_knowledge_graph.py ../backend/tests/test_generate_kg.py
git commit -m "复用KG生成服务改造命令行工具"
```

## Task 4: Client API Contract Updates

**Files:**
- Modify: `../docs/10-client-api/Client-API.openapi.json`
- Modify: `../docs/10-client-api/API_前端接口规范.md`

- [ ] **Step 1: Update OpenAPI paths**

In `../docs/10-client-api/Client-API.openapi.json`, add:

```json
"/admin/course-catalogs/{catalog_id}/knowledge-graphs": {
  "get": {
    "tags": ["CourseCatalogs"],
    "summary": "管理员查看课程资源库知识图谱状态",
    "description": "Admin-only。返回 CourseCatalog 当前绑定 CourseOffering 的 active KG 摘要和最近一次 kg_generation 任务状态。",
    "parameters": [
      {
        "name": "catalog_id",
        "in": "path",
        "required": true,
        "schema": { "type": "string" }
      }
    ],
    "responses": {
      "200": {
        "description": "成功",
        "content": {
          "application/json": {
            "schema": { "$ref": "#/components/schemas/AdminCatalogKnowledgeGraphStatusResponse" }
          }
        }
      }
    },
    "security": [{ "bearerAuth": [] }]
  }
},
"/admin/course-catalogs/{catalog_id}/knowledge-graphs/generations": {
  "post": {
    "tags": ["CourseCatalogs"],
    "summary": "管理员触发课程资源库知识图谱生成",
    "description": "Admin-only。基于大纲文本或 KG JSON 创建新的 course_knowledge_graphs 版本。该接口不触发学生个性化 LearningPath 刷新，也不要求 CourseCatalog chunk ready。",
    "parameters": [
      {
        "name": "catalog_id",
        "in": "path",
        "required": true,
        "schema": { "type": "string" }
      }
    ],
    "requestBody": {
      "required": true,
      "content": {
        "application/json": {
          "schema": { "$ref": "#/components/schemas/AdminCatalogKnowledgeGraphGenerationRequest" }
        }
      }
    },
    "responses": {
      "202": {
        "description": "已接受",
        "content": {
          "application/json": {
            "schema": { "$ref": "#/components/schemas/AdminCatalogKnowledgeGraphGenerationResponse" }
          }
        }
      },
      "409": { "description": "未绑定教学班或已有 KG 生成任务进行中" },
      "422": { "description": "source_type 或输入内容不合法" }
    },
    "security": [{ "bearerAuth": [] }]
  }
}
```

Add schemas:

```json
"AdminCatalogKnowledgeGraphGenerationRequest": {
  "type": "object",
  "required": ["source_type"],
  "properties": {
    "source_type": { "type": "string", "enum": ["outline_text", "kg_json"] },
    "outline_text": { "type": "string", "nullable": true },
    "kg_json": { "type": "object", "nullable": true },
    "activate": { "type": "boolean", "default": true }
  }
},
"AdminCatalogKnowledgeGraphGenerationResponse": {
  "type": "object",
  "properties": {
    "code": { "type": "integer", "example": 202 },
    "message": { "type": "string", "example": "accepted" },
    "data": {
      "type": "object",
      "properties": {
        "task_id": { "type": "string" },
        "catalog_id": { "type": "string" },
        "course_id": { "type": "string" },
        "status": { "type": "string", "example": "processing" }
      }
    }
  }
},
"AdminCatalogKnowledgeGraphStatusResponse": {
  "type": "object",
  "properties": {
    "code": { "type": "integer", "example": 200 },
    "message": { "type": "string", "example": "success" },
    "data": { "$ref": "#/components/schemas/AdminCatalogKnowledgeGraphStatusData" }
  }
},
"AdminCatalogKnowledgeGraphStatusData": {
  "type": "object",
  "properties": {
    "catalog_id": { "type": "string" },
    "course_id": { "type": "string", "nullable": true },
    "active_graph": { "$ref": "#/components/schemas/AdminCatalogKnowledgeGraphSummary", "nullable": true },
    "last_generation_task": { "$ref": "#/components/schemas/AdminCatalogKnowledgeGraphTaskSummary", "nullable": true }
  }
},
"AdminCatalogKnowledgeGraphSummary": {
  "type": "object",
  "properties": {
    "id": { "type": "string" },
    "version": { "type": "integer" },
    "node_count": { "type": "integer" },
    "edge_count": { "type": "integer" },
    "source_type": { "type": "string" },
    "generation_strategy": { "type": "string" },
    "metrics": { "type": "object", "nullable": true },
    "create_time": { "type": "string" },
    "update_time": { "type": "string" }
  }
},
"AdminCatalogKnowledgeGraphTaskSummary": {
  "type": "object",
  "properties": {
    "task_id": { "type": "string" },
    "status": { "type": "string" },
    "error_code": { "type": "string", "nullable": true },
    "error_message": { "type": "string" }
  }
}
```

Add `kg_generation` to task type descriptions near existing `TaskResponse` documentation.

- [ ] **Step 2: Update Markdown contract**

In `../docs/10-client-api/API_前端接口规范.md`, add a subsection under Admin CourseCatalog:

```markdown
### 管理员查看课程资源库知识图谱状态

GET /api/v1/admin/course-catalogs/:catalog_id/knowledge-graphs

返回当前资源库通过 CourseOffering 绑定的 course_id、active KG 摘要和最近一次 `kg_generation` 任务状态。没有 active KG 时 `active_graph=null`。

### 管理员触发课程资源库知识图谱生成

POST /api/v1/admin/course-catalogs/:catalog_id/knowledge-graphs/generations

请求：

```json
{
  "source_type": "outline_text",
  "outline_text": "课程大纲文本",
  "activate": true
}
```

或：

```json
{
  "source_type": "kg_json",
  "kg_json": { "nodes": [], "edges": [] },
  "activate": true
}
```

说明：

- 该接口 Admin-only。
- KG 生成写入 `course_knowledge_graphs` 新版本。
- 第一版不触发学生个性化 LearningPath 刷新。
- `outline_text` / `kg_json` 模式不要求 CourseCatalog `chunk_count > 0`。
- 无绑定 CourseOffering 返回 `409 offering_missing`。
- 已有进行中的 KG 生成任务返回 `409 kg_task_running`。
```

Add `kg_generation` to the async task type table.

- [ ] **Step 3: Validate contract files**

Run:

```bash
python -m json.tool ../docs/10-client-api/Client-API.openapi.json >/tmp/client-api-openapi-kg-check.json
git diff --check -- ../docs/10-client-api/Client-API.openapi.json ../docs/10-client-api/API_前端接口规范.md
```

Expected: both commands exit 0.

- [ ] **Step 4: Commit Task 4**

```bash
git add ../docs/10-client-api/Client-API.openapi.json ../docs/10-client-api/API_前端接口规范.md
git commit -m "补充管理员KG生成接口契约"
```

## Task 5: Frontend Admin Drawer KG Section

**Files:**
- Modify: `src/api/services/admin.js`
- Modify: `src/components/admin/CourseCatalogDrawer.jsx`
- Modify: `e2e/specs.spec.js`

- [ ] **Step 1: Add failing E2E test**

Append or place near the existing Admin catalog resource generation E2E in `e2e/specs.spec.js`:

```javascript
test('Admin course catalog KG generation uses declared admin endpoints', async ({ page }) => {
  let kgGenerationStarted = false;
  let kgPollCount = 0;
  let activeGraph = null;

  await page.addInitScript(() => {
    localStorage.setItem('access_token', 'e2e-admin-token');
  });

  await page.route('**/api/v1/users/me', async (route) => {
    await route.fulfill(jsonResponse({
      code: 200,
      message: 'success',
      data: { id: 'admin-e2e', email: 'admin@example.com', username: 'Admin E2E', role: 'admin' },
    }));
  });

  await page.route('**/api/v1/admin/users**', async (route) => {
    await route.fulfill(jsonResponse({ code: 200, message: 'success', data: { users: [] } }));
  });

  await page.route('**/api/v1/admin/logs/**', async (route) => {
    await route.fulfill(jsonResponse({ code: 200, message: 'success', data: { logs: [] } }));
  });

  await page.route('**/api/v1/admin/course-catalogs', async (route) => {
    if (route.request().method() !== 'GET') {
      await route.fallback();
      return;
    }
    await route.fulfill(jsonResponse({
      code: 200,
      message: 'success',
      data: {
        catalogs: [{
          id: 'catalog-e2e',
          title: 'C 语言资源库',
          description: '用于 KG 生成',
          status: 'ready',
          knowledge_status: 'ready',
          material_count: 1,
          chunk_count: 6,
        }],
        total: 1,
      },
    }));
  });

  await page.route('**/api/v1/admin/course-catalogs/catalog-e2e/materials', async (route) => {
    await route.fulfill(jsonResponse({ code: 200, message: 'success', data: { materials: [] } }));
  });

  await page.route('**/api/v1/admin/course-catalogs/catalog-e2e/knowledge-status', async (route) => {
    await route.fulfill(jsonResponse({
      code: 200,
      message: 'success',
      data: {
        status: 'ready',
        knowledge_status: 'ready',
        material_count: 1,
        chunk_count: 6,
        pending_material_count: 0,
        failed_material_count: 0,
      },
    }));
  });

  await page.route(/\/api\/v1\/admin\/course-catalogs\/catalog-e2e\/resources(\?.*)?$/, async (route) => {
    await route.fulfill(jsonResponse({
      code: 200,
      message: 'success',
      data: { resources: [], total: 0, page: 1, page_size: 20 },
    }));
  });

  await page.route('**/api/v1/admin/course-catalogs/catalog-e2e/knowledge-graphs', async (route) => {
    await route.fulfill(jsonResponse({
      code: 200,
      message: 'success',
      data: {
        catalog_id: 'catalog-e2e',
        course_id: 'class-e2e',
        active_graph: activeGraph,
        last_generation_task: kgGenerationStarted ? { task_id: 'kg-task-e2e', status: activeGraph ? 'completed' : 'processing', error_code: null, error_message: '' } : null,
      },
    }));
  });

  await page.route('**/api/v1/admin/course-catalogs/catalog-e2e/knowledge-graphs/generations', async (route) => {
    kgGenerationStarted = true;
    expect(route.request().postDataJSON()).toEqual({
      source_type: 'outline_text',
      outline_text: '第 1 章 C 语言概述',
      activate: true,
    });
    await route.fulfill(jsonResponse({
      code: 202,
      message: 'accepted',
      data: { task_id: 'kg-task-e2e', catalog_id: 'catalog-e2e', course_id: 'class-e2e', status: 'processing' },
    }, 202));
  });

  await page.route('**/api/v1/tasks/kg-task-e2e', async (route) => {
    kgPollCount += 1;
    if (kgPollCount >= 2) {
      activeGraph = {
        id: 'kg-active-e2e',
        version: 1,
        node_count: 12,
        edge_count: 10,
        source_type: 'outline_llm',
        generation_strategy: 'legacy_outline',
        metrics: {},
        create_time: '2026-06-11T10:00:00Z',
        update_time: '2026-06-11T10:00:00Z',
      };
    }
    await route.fulfill(jsonResponse({
      code: 200,
      message: 'success',
      data: {
        task_id: 'kg-task-e2e',
        task_type: 'kg_generation',
        status: activeGraph ? 'completed' : 'processing',
        progress: activeGraph ? 100 : 50,
        result: activeGraph ? { graph_id: 'kg-active-e2e', version: 1, node_count: 12, edge_count: 10 } : {},
        error_code: null,
        error_message: '',
      },
    }));
  });

  await page.goto('/admin');
  await page.getByRole('button', { name: '课程资源库' }).click();
  await page.getByRole('button', { name: '管理资料' }).click();

  await expect(page.getByText('知识图谱')).toBeVisible();
  await expect(page.getByText('未生成')).toBeVisible();
  await page.getByTestId('kg-outline-text').fill('第 1 章 C 语言概述');
  await page.getByTestId('catalog-start-kg-generation').click();

  await expect(page.getByTestId('catalog-kg-task-status').getByText('已完成')).toBeVisible({ timeout: 7000 });
  await expect(page.getByText('版本 1')).toBeVisible();
  await expect(page.getByText('12')).toBeVisible();
  expect(kgGenerationStarted).toBe(true);
  expect(kgPollCount).toBeGreaterThanOrEqual(2);
});
```

- [ ] **Step 2: Run E2E test and confirm selector failure**

Run:

```bash
npm run test:e2e -- e2e/specs.spec.js -g "Admin course catalog KG generation"
```

Expected: FAIL because KG section/test IDs do not exist.

- [ ] **Step 3: Add Admin API service methods**

Modify `src/api/services/admin.js`:

```javascript
  getCourseCatalogKnowledgeGraphStatus: async (catalogId) => {
    return apiClient.get(`/admin/course-catalogs/${catalogId}/knowledge-graphs`);
  },

  startCourseCatalogKnowledgeGraphGeneration: async (catalogId, data) => {
    return apiClient.post(`/admin/course-catalogs/${catalogId}/knowledge-graphs/generations`, data);
  },
```

Place these near existing CourseCatalog resource methods.

- [ ] **Step 4: Add KG state and form helpers in `CourseCatalogDrawer.jsx`**

Add helper:

```javascript
const createKgForm = () => ({
  source_type: 'outline_text',
  outline_text: '',
  kg_json_text: '',
  activate: true
});
```

Add state near existing generation state:

```javascript
  const [knowledgeGraphStatus, setKnowledgeGraphStatus] = useState(null);
  const [kgForm, setKgForm] = useState(createKgForm);
  const [kgGenerating, setKgGenerating] = useState(false);
  const [kgTask, setKgTask] = useState(null);
  const [kgTaskError, setKgTaskError] = useState('');
  const kgTaskRef = useRef(null);
  const kgGenerationOperationSeqRef = useRef(0);
```

Add formatter:

```javascript
const formatKgSourceType = createStatusLabelFormatter({
  outline_llm: '大纲生成',
  manual_import: 'JSON 导入',
  route_a_body_grounded: '正文支撑裁剪'
}, 'UNKNOWN');
```

Add operation guard:

```javascript
  const canWriteKgGenerationOperation = useCallback((operationSeq, operationCatalogId) => (
    isMountedRef.current
    && openRef.current
    && catalogIdRef.current === operationCatalogId
    && kgGenerationOperationSeqRef.current === operationSeq
  ), []);
```

Reset state when opening/closing:

```javascript
    setKnowledgeGraphStatus(null);
    setKgForm(createKgForm());
    setKgGenerating(false);
    setKgTask(null);
    setKgTaskError('');
    kgTaskRef.current = null;
```

Update cleanup blocks:

```javascript
      kgGenerationOperationSeqRef.current += 1;
```

- [ ] **Step 5: Load KG status in `refreshDetails`**

Change the `Promise.all` call:

```javascript
      const [materialsRes, statusRes, resourcesRes, kgStatusRes] = await Promise.all([
        adminService.getCourseCatalogMaterials(catalogId),
        adminService.getCourseCatalogStatus(catalogId),
        adminService.getCourseCatalogResources(catalogId, { page: 1, page_size: 50 }),
        adminService.getCourseCatalogKnowledgeGraphStatus(catalogId)
      ]);
```

Then set state:

```javascript
      setKnowledgeGraphStatus(kgStatusRes.data || null);
```

In catch, reset:

```javascript
      setKnowledgeGraphStatus(null);
```

- [ ] **Step 6: Add KG polling effect**

Add effect after resource generation polling effect:

```javascript
  useEffect(() => {
    if (
      !open
      || !kgTask?.task_id
      || kgTask.status === 'completed'
      || kgTask.status === 'failed'
    ) return;

    let cancelled = false;
    let timeoutId;

    const handleTerminalTask = async (task) => {
      if (cancelled) return;
      setKgGenerating(false);
      if (task.status === 'failed') {
        setKgTaskError(task.error_message || '知识图谱生成失败');
      }
      const refreshed = await refreshDetails();
      if (!cancelled && refreshed && onChanged) onChanged();
    };

    const pollTask = async () => {
      try {
        const res = await taskService.getTaskStatus(kgTask.task_id);
        if (cancelled) return;
        const task = normalizeTask(res.data, kgTask.task_id, 'kg_generation');
        kgTaskRef.current = task;
        setKgTask(task);
        setKgTaskError('');
        if (task.status === 'completed' || task.status === 'failed') {
          await handleTerminalTask(task);
        } else if (!cancelled) {
          timeoutId = setTimeout(pollTask, 2000);
        }
      } catch (err) {
        if (cancelled) return;
        console.error('course catalog kg generation task poll error', err);
        const detail = getErrorMessage(err, '');
        setKgTaskError(detail ? `知识图谱任务状态查询失败：${detail}，正在重试` : '知识图谱任务状态查询失败，正在重试');
        timeoutId = setTimeout(pollTask, 2000);
      }
    };

    timeoutId = setTimeout(pollTask, 2000);
    return () => {
      cancelled = true;
      clearTimeout(timeoutId);
    };
  }, [kgTask?.status, kgTask?.task_id, onChanged, open, refreshDetails]);
```

- [ ] **Step 7: Add KG start handler**

Add:

```javascript
  const handleKgFormChange = (field, value) => {
    setKgForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleStartKgGeneration = async () => {
    if (!catalogId || kgGenerating || kgTask?.status === 'processing') return;

    const operationCatalogId = catalogId;
    const operationSeq = kgGenerationOperationSeqRef.current + 1;
    kgGenerationOperationSeqRef.current = operationSeq;
    if (!canWriteKgGenerationOperation(operationSeq, operationCatalogId)) return;

    let payload;
    try {
      if (kgForm.source_type === 'kg_json') {
        payload = {
          source_type: 'kg_json',
          kg_json: JSON.parse(kgForm.kg_json_text),
          activate: kgForm.activate
        };
      } else {
        payload = {
          source_type: 'outline_text',
          outline_text: kgForm.outline_text.trim(),
          activate: kgForm.activate
        };
      }
    } catch (err) {
      setKgTaskError('KG JSON 格式不正确');
      return;
    }

    if (payload.source_type === 'outline_text' && !payload.outline_text) {
      setKgTaskError('请填写课程大纲文本');
      return;
    }

    setKgGenerating(true);
    setKgTaskError('');
    setError('');
    try {
      const res = await adminService.startCourseCatalogKnowledgeGraphGeneration(operationCatalogId, payload);
      if (!canWriteKgGenerationOperation(operationSeq, operationCatalogId)) return;
      const task = normalizeTask(res.data, res.data?.task_id, 'kg_generation');
      kgTaskRef.current = task;
      setKgTask(task);
    } catch (err) {
      console.error('course catalog kg generation start error', err);
      if (!canWriteKgGenerationOperation(operationSeq, operationCatalogId)) return;
      setKgTaskError(getErrorMessage(err, '知识图谱生成启动失败'));
      setKgGenerating(false);
    }
  };
```

- [ ] **Step 8: Add KG UI section**

Add before the existing learning resource generation section:

```jsx
          <section className="mb-5 rounded-lg border border-slate-200 bg-white p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 className="text-sm font-bold text-slate-900">知识图谱</h3>
                <p className="mt-1 text-xs text-slate-500">用于学习路径和 KG 节点资源挂载。</p>
              </div>
              <span className={`rounded border px-2.5 py-1 text-xs font-bold ${getBadgeClass(kgTask?.status || (knowledgeGraphStatus?.active_graph ? 'ready' : 'draft'))}`}>
                {kgTask?.status === 'processing'
                  ? '生成中'
                  : knowledgeGraphStatus?.active_graph
                    ? '已就绪'
                    : '未生成'}
              </span>
            </div>

            <div className="mt-4 grid grid-cols-3 gap-3">
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                <div className="text-xs font-bold text-slate-500">版本</div>
                <div className="mt-1 text-sm font-bold text-slate-900">
                  {knowledgeGraphStatus?.active_graph ? `版本 ${knowledgeGraphStatus.active_graph.version}` : '—'}
                </div>
              </div>
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                <div className="text-xs font-bold text-slate-500">节点</div>
                <div className="mt-1 text-sm font-bold text-slate-900">{knowledgeGraphStatus?.active_graph?.node_count ?? '—'}</div>
              </div>
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                <div className="text-xs font-bold text-slate-500">边</div>
                <div className="mt-1 text-sm font-bold text-slate-900">{knowledgeGraphStatus?.active_graph?.edge_count ?? '—'}</div>
              </div>
            </div>

            {knowledgeGraphStatus?.active_graph && (
              <p className="mt-3 text-xs text-slate-500">
                来源：{formatKgSourceType(knowledgeGraphStatus.active_graph.source_type)}
                <span className="mx-2">·</span>
                策略：{knowledgeGraphStatus.active_graph.generation_strategy || '—'}
              </p>
            )}

            <div className="mt-4 flex rounded-lg border border-slate-200 bg-slate-50 p-1">
              {[
                ['outline_text', '大纲文本'],
                ['kg_json', 'KG JSON']
              ].map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  className={`flex-1 rounded-md px-3 py-2 text-sm font-bold ${kgForm.source_type === value ? 'bg-white text-cyan-700 shadow-sm' : 'text-slate-500'}`}
                  onClick={() => handleKgFormChange('source_type', value)}
                >
                  {label}
                </button>
              ))}
            </div>

            {kgForm.source_type === 'outline_text' ? (
              <textarea
                data-testid="kg-outline-text"
                rows={4}
                value={kgForm.outline_text}
                onChange={(event) => handleKgFormChange('outline_text', event.target.value)}
                className="mt-3 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-cyan-400"
                placeholder="粘贴课程大纲文本"
              />
            ) : (
              <textarea
                data-testid="kg-json-text"
                rows={4}
                value={kgForm.kg_json_text}
                onChange={(event) => handleKgFormChange('kg_json_text', event.target.value)}
                className="mt-3 w-full rounded-lg border border-slate-200 px-3 py-2 font-mono text-xs outline-none focus:border-cyan-400"
                placeholder='{"nodes":[],"edges":[]}'
              />
            )}

            <label className="mt-3 flex items-center gap-2 text-sm text-slate-600">
              <input
                type="checkbox"
                checked={kgForm.activate}
                onChange={(event) => handleKgFormChange('activate', event.target.checked)}
              />
              生成后设为当前 active 版本
            </label>

            <div className="mt-4 flex items-center justify-between gap-3">
              <button
                data-testid="catalog-start-kg-generation"
                type="button"
                disabled={kgGenerating || kgTask?.status === 'processing'}
                onClick={handleStartKgGeneration}
                className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-bold text-white transition-colors hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-300"
              >
                {kgGenerating || kgTask?.status === 'processing' ? '生成中...' : '刷新知识图谱'}
              </button>
              {kgTask && (
                <span data-testid="catalog-kg-task-status" className={`rounded border px-2.5 py-1 text-xs font-bold ${getBadgeClass(kgTask.status)}`}>
                  {formatTaskStatus(kgTask.status)}
                </span>
              )}
            </div>

            {kgTaskError && (
              <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {kgTaskError}
              </div>
            )}
          </section>
```

- [ ] **Step 9: Surface `kg_not_ready` in resource generation errors**

In `handleStartGeneration` catch block, parse error code if available through existing error utilities. If the code is not directly available, match the backend message safely:

```javascript
      const message = getErrorMessage(err, '学习资源生成启动失败');
      const detailCode = err?.response?.data?.detail?.data?.error_code || err?.response?.data?.detail?.error_code;
      if (detailCode === 'kg_not_ready' || message.includes('知识图谱未就绪')) {
        setGenerationTaskError('课程知识图谱未就绪，请先在上方刷新知识图谱。');
      } else {
        setGenerationTaskError(message);
      }
```

- [ ] **Step 10: Run frontend checks**

Run:

```bash
npm run test:e2e -- e2e/specs.spec.js -g "Admin course catalog KG generation"
npm run test:e2e -- e2e/specs.spec.js -g "Admin course catalog resource generation"
npm run lint
npm run build
```

Expected:

- KG E2E PASS.
- Existing Admin catalog resource generation E2E PASS.
- `npm run lint` PASS.
- `npm run build` PASS, allowing existing Vite chunk size warning if unchanged.

- [ ] **Step 11: Commit Task 5**

```bash
git add src/api/services/admin.js src/components/admin/CourseCatalogDrawer.jsx e2e/specs.spec.js
git commit -m "接入管理员KG生成抽屉入口"
```

## Task 6: Final Verification and Progress Records

**Files:**
- Modify: `WORKFLOW.md`
- Modify: `docs/feature-ledger.md`

- [ ] **Step 1: Run full focused backend verification**

Run:

```bash
cd ../backend && TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/admin_kg_final_backend?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_admin_catalog_kg_generation.py tests/test_admin_catalog_resource_generation.py tests/test_generate_kg.py tests/test_course_knowledge_graph_versions.py -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 2: Run contract verification**

Run:

```bash
python -m json.tool ../docs/10-client-api/Client-API.openapi.json >/tmp/client-api-openapi-kg-final.json
```

Expected: exit 0.

- [ ] **Step 3: Run frontend verification**

Run:

```bash
npm run test:e2e -- e2e/specs.spec.js -g "Admin course catalog"
npm run lint
npm run build
```

Expected:

- Admin CourseCatalog E2E tests PASS.
- `npm run lint` PASS.
- `npm run build` PASS, allowing existing Vite chunk size warning if unchanged.

- [ ] **Step 4: Update `WORKFLOW.md`**

Add a new entry under "最近验证":

```markdown
- 2026-06-11：Admin CourseCatalog 知识图谱生成入口接入：
  - 新增 Admin KG generation 设计落地：`POST /admin/course-catalogs/{catalog_id}/knowledge-graphs/generations` 创建 `kg_generation` 异步任务，`GET /admin/course-catalogs/{catalog_id}/knowledge-graphs` 返回 active KG 摘要和最近任务状态。
  - Backend 抽取 KG 生成 service，CLI 与 Admin API 复用同一套校验、LLM 大纲生成、KG JSON 导入和版本落库逻辑；API 不 shell 调 CLI。
  - KG 生成通过 `CourseOffering.create_time ASC, id ASC` 解析 catalog 对应 course，不要求 CourseCatalog chunk ready；资源生成仍保留知识库 ready/chunk gate。
  - Admin `CourseCatalogDrawer` 新增“知识图谱”区块，支持大纲文本 / KG JSON 触发生成、轮询任务并刷新 active KG 状态；资源生成 `kg_not_ready` 时引导先刷新知识图谱。
  - 验证：填写本轮实际运行命令和结果。
  - Commit：填写本轮 commit id / message。
```

- [ ] **Step 5: Update `docs/feature-ledger.md`**

Update these areas only if Task 1-5 are complete:

- In "当前主线结论", add that Admin KG generation now has a formal Admin entry.
- In "页面真实调用核查", update `CourseCatalogDrawer.jsx` row to include:
  - `GET /admin/course-catalogs/{catalog_id}/knowledge-graphs`
  - `POST /admin/course-catalogs/{catalog_id}/knowledge-graphs/generations`
- In "Agent 依赖能力", change KG generation from CLI/manual-only to Admin-operable for first version, while keeping LearningPath ready gate as later design.
- In "当前下一步队列", make the next item "用 Admin KG 入口重新跑 C 样本 KG 生成 / 资源生成 / LearningPath probe" if it is still outstanding.

- [ ] **Step 6: Check final diff**

Run:

```bash
git status --short
git diff --check
```

Expected:

- Only intended files are modified.
- `git diff --check` exits 0.
- Existing unrelated untracked files remain uncommitted.

- [ ] **Step 7: Commit Task 6**

```bash
git add WORKFLOW.md docs/feature-ledger.md
git commit -m "记录管理员KG生成进度"
```

## Post-Implementation Notes

After this plan is complete, do not claim LearningPath ready gate completion. The feature only makes Admin KG generation product-visible. The next separate work item is a real C sample smoke path:

1. Admin creates or opens C CourseCatalog.
2. Admin triggers KG generation.
3. Admin triggers KG-node resource generation.
4. Run LearningPath-KG resource probe after a LearningPath exists.
