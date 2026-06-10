# KG Resource Metadata Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Admin catalog resource generation automatically target active KG core nodes and persist generated resources with KG-aligned `chapter` and `knowledge_point` metadata.

**Architecture:** Backend keeps the public Admin endpoint unchanged. When `chapter/knowledge_point` are omitted, Backend selects a small deterministic subset of active KG nodes, creates one parent `resource_generation` task plus one child task per target node, calls the existing Agent resource API with the node's `chapter/name`, and lets webhook persistence fan out resources to bound classes. Webhook persistence uses child task `result.target_node` as the source of truth for metadata and recomputes the parent task status after every child callback.

**Tech Stack:** FastAPI, SQLAlchemy async ORM, MySQL via `aiomysql`, pytest, existing Agent HTTP client, existing `CourseKnowledgeGraph` and `AsyncTask` models.

---

## Pre-Implementation Gate

Before changing code, output the required project pre-review in Chinese:

1. 问题分析
2. 计划修改的文件
3. 修改方案
4. 可能影响的功能
5. 计划运行的测试命令

Wait for user approval before code edits.

## File Structure

- Create `../backend/app/services/kg_resource_targets.py`
  - Owns deterministic target selection from active KG nodes.
  - Contains no DB access and no Agent calls.

- Modify `../backend/app/api/v1/catalogs.py`
  - Keeps explicit `chapter/knowledge_point` generation path compatible.
  - Adds default KG-node generation path for Admin catalog resource generation.
  - Creates parent and child `AsyncTask` records.
  - Calls Agent once per child task using existing Agent API fields.

- Modify `../backend/app/api/v1/webhooks.py`
  - Detects KG-node child tasks from `task.result.mode == "kg_node_target"`.
  - Overrides persisted `Resource.chapter/knowledge_point` from `task.result.target_node`.
  - Recomputes parent task counts after child completion or failure.

- Test `../backend/tests/test_kg_resource_targets.py`
  - Pure unit tests for target selection.

- Modify `../backend/tests/test_admin_catalog_resource_generation.py`
  - Covers Admin default KG-node mode, explicit metadata compatibility, webhook metadata override, parent aggregation, and failure behavior.

- Modify `../backend/WORKFLOW.md`
  - Records implementation and verification results after code passes.

- Modify `docs/feature-ledger.md`
  - Only update if real KG-Resource probe later proves meaningful nonzero alignment and the main queue status changes.

## Task 1: KG Resource Target Selector

**Files:**
- Create: `../backend/app/services/kg_resource_targets.py`
- Test: `../backend/tests/test_kg_resource_targets.py`

- [ ] **Step 1: Write failing selector tests**

Create `../backend/tests/test_kg_resource_targets.py`:

```python
from app.services.kg_resource_targets import select_core_resource_targets


def _node(node_id, name, chapter, band=None, score=None):
    node = {"id": node_id, "name": name, "chapter": chapter}
    if band is not None:
        node["support_band"] = band
    if score is not None:
        node["body_top1_score"] = score
    return node


def test_select_core_targets_prefers_support_band_before_chapter_balance():
    nodes = [
        _node(f"s{i}", f"Strong {i}", "第一章", "strong", 0.90 - i * 0.01)
        for i in range(12)
    ] + [
        _node("g1", "Good Other Chapter", "第二章", "good", 0.68),
    ]

    result = select_core_resource_targets(nodes, max_targets=10)

    assert [item["support_band"] for item in result["targets"]] == ["strong"] * 10
    assert "Good Other Chapter" not in [item["node_name"] for item in result["targets"]]
    assert result["selection_degraded"] is False


def test_select_core_targets_balances_chapters_within_same_band():
    nodes = [
        _node("a1", "A1", "第一章", "strong", 0.91),
        _node("a2", "A2", "第一章", "strong", 0.90),
        _node("b1", "B1", "第二章", "strong", 0.89),
        _node("b2", "B2", "第二章", "strong", 0.88),
        _node("c1", "C1", "第三章", "strong", 0.87),
    ]

    result = select_core_resource_targets(nodes, max_targets=5)

    assert [item["chapter"] for item in result["targets"]] == [
        "第一章",
        "第二章",
        "第三章",
        "第一章",
        "第二章",
    ]


def test_select_core_targets_drops_unsupported_and_deduplicates_chapter_name():
    nodes = [
        _node("n1", "数组", "第三章", "good", 0.66),
        _node("n1-dup", "数组", "第三章", "strong", 0.82),
        _node("bad", "目录", "附录", "unsupported", 0.40),
        _node("missing-name", "", "第三章", "strong", 0.80),
        _node("missing-chapter", "函数", "", "strong", 0.80),
    ]

    result = select_core_resource_targets(nodes, max_targets=10)

    assert result["targets"] == [
        {
            "node_id": "n1-dup",
            "node_name": "数组",
            "chapter": "第三章",
            "support_band": "strong",
            "body_top1_score": 0.82,
        }
    ]


def test_select_core_targets_degrades_when_nodes_have_no_support_metadata():
    nodes = [
        {"id": "n1", "name": "变量", "chapter": "第一章"},
        {"id": "n2", "name": "指针", "chapter": "第二章"},
        {"id": "n3", "name": "数组", "chapter": "第一章"},
    ]

    result = select_core_resource_targets(nodes, max_targets=2)

    assert result["targets"] == [
        {
            "node_id": "n1",
            "node_name": "变量",
            "chapter": "第一章",
            "support_band": "unknown",
            "body_top1_score": None,
        },
        {
            "node_id": "n2",
            "node_name": "指针",
            "chapter": "第二章",
            "support_band": "unknown",
            "body_top1_score": None,
        },
    ]
    assert result["selection_degraded"] is True
    assert result["degraded_reason"] == "node_support_metadata_missing"
```

- [ ] **Step 2: Run selector tests and confirm RED**

Run from `../backend`:

```bash
../.venv/bin/python -m pytest tests/test_kg_resource_targets.py -q -p no:cacheprovider
```

Expected: collection fails with `ModuleNotFoundError: No module named 'app.services.kg_resource_targets'`.

- [ ] **Step 3: Implement selector service**

Create `../backend/app/services/kg_resource_targets.py`:

```python
from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

SUPPORT_BAND_ORDER = ("strong", "good", "weak_but_usable")
UNKNOWN_SUPPORT_BAND = "unknown"
DEFAULT_MAX_TARGETS = 10


def select_core_resource_targets(
    nodes: list[dict[str, Any]],
    max_targets: int = DEFAULT_MAX_TARGETS,
) -> dict[str, Any]:
    """Select deterministic KG nodes for resource generation.

    Input: active KG nodes. Output: target_nodes plus selection diagnostics.
    """
    limit = max(0, int(max_targets))
    if limit == 0:
        return {
            "targets": [],
            "selection_degraded": False,
            "degraded_reason": "",
        }

    normalized = _dedupe_nodes(nodes)
    has_support_metadata = any(item["support_band"] != UNKNOWN_SUPPORT_BAND for item in normalized)
    if has_support_metadata:
        targets = _select_with_support_bands(normalized, limit)
        degraded = False
        reason = ""
    else:
        targets = _round_robin_by_chapter(normalized, limit)
        degraded = bool(normalized)
        reason = "node_support_metadata_missing" if normalized else ""

    return {
        "targets": targets,
        "selection_degraded": degraded,
        "degraded_reason": reason,
    }


def _dedupe_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for index, node in enumerate(nodes):
        node_id = str(node.get("id") or node.get("node_id") or "").strip()
        node_name = str(node.get("name") or node.get("node_name") or "").strip()
        chapter = str(node.get("chapter") or "").strip()
        if not node_id or not node_name or not chapter:
            continue
        support_band = _support_band(node)
        if support_band == "unsupported":
            continue
        score = _score(node)
        candidate = {
            "node_id": node_id,
            "node_name": node_name,
            "chapter": chapter,
            "support_band": support_band,
            "body_top1_score": score,
            "_order": index,
        }
        key = (chapter, node_name)
        existing = best_by_key.get(key)
        if existing is None or _sort_key(candidate) < _sort_key(existing):
            best_by_key[key] = candidate
    return [_public(item) for item in sorted(best_by_key.values(), key=lambda item: item["_order"])]


def _support_band(node: dict[str, Any]) -> str:
    raw = node.get("support_band") or node.get("body_support_band")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    score = _score(node)
    if score is None:
        return UNKNOWN_SUPPORT_BAND
    if score >= 0.70:
        return "strong"
    if score >= 0.65:
        return "good"
    if score >= 0.60:
        return "weak_but_usable"
    return "unsupported"


def _score(node: dict[str, Any]) -> float | None:
    raw = node.get("body_top1_score")
    if raw is None:
        raw = node.get("support_score")
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _select_with_support_bands(nodes: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for band in SUPPORT_BAND_ORDER:
        band_nodes = [item for item in nodes if item["support_band"] == band]
        selected.extend(_round_robin_by_chapter(band_nodes, limit - len(selected)))
        if len(selected) >= limit:
            break
    return selected[:limit]


def _round_robin_by_chapter(nodes: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in sorted(nodes, key=_sort_key):
        grouped[item["chapter"]].append(item)
    queues = deque((chapter, deque(items)) for chapter, items in sorted(grouped.items()))
    selected: list[dict[str, Any]] = []
    while queues and len(selected) < limit:
        chapter, items = queues.popleft()
        selected.append(_public(items.popleft()))
        if items:
            queues.append((chapter, items))
    return selected


def _sort_key(item: dict[str, Any]) -> tuple[int, float, int]:
    band_rank = {
        "strong": 0,
        "good": 1,
        "weak_but_usable": 2,
        UNKNOWN_SUPPORT_BAND: 3,
    }.get(item["support_band"], 4)
    score = item["body_top1_score"]
    score_rank = -score if score is not None else 0.0
    return (band_rank, score_rank, int(item.get("_order", 0)))


def _public(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "node_id": item["node_id"],
        "node_name": item["node_name"],
        "chapter": item["chapter"],
        "support_band": item["support_band"],
        "body_top1_score": item["body_top1_score"],
    }
```

- [ ] **Step 4: Run selector tests and confirm GREEN**

Run from `../backend`:

```bash
../.venv/bin/python -m pytest tests/test_kg_resource_targets.py -q -p no:cacheprovider
```

Expected: `4 passed`.

- [ ] **Step 5: Commit Task 1**

```bash
git add ../backend/app/services/kg_resource_targets.py ../backend/tests/test_kg_resource_targets.py
git commit -m "新增KG资源目标选择器"
```

## Task 2: Admin KG-Node Parent And Child Tasks

**Files:**
- Modify: `../backend/app/api/v1/catalogs.py`
- Test: `../backend/tests/test_admin_catalog_resource_generation.py`

- [ ] **Step 1: Add failing Admin default KG-node generation test**

Append imports in `../backend/tests/test_admin_catalog_resource_generation.py`:

```python
from app.models.others import AsyncTask, CourseKnowledgeGraph, Resource
```

If `AsyncTask` and `Resource` are already imported from the same module, merge `CourseKnowledgeGraph` into the existing import.

Add helper:

```python
async def _seed_active_kg(course_id: str, nodes: list[dict], edges: list[dict] | None = None) -> str:
    async with async_session_factory() as db:
        graph = CourseKnowledgeGraph(
            id=f"kg-{course_id}",
            course_id=course_id,
            version=1,
            is_active=True,
            source_type="route_a_body_grounded",
            generation_strategy="route_a_prune_usable_060",
            nodes=nodes,
            edges=edges or [],
            metrics={"support_band_counts": {"strong": 1, "good": 1, "weak_but_usable": 0, "unsupported": 0}},
        )
        db.add(graph)
        await db.commit()
        return graph.id
```

Add test:

```python
@pytest.mark.asyncio
async def test_admin_catalog_generation_without_metadata_creates_parent_and_child_tasks_from_active_kg():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    await _seed_user("teacher-admin-gen", "teacher")
    catalog_id = await _seed_ready_catalog()
    class_a = await _seed_bound_class(catalog_id=catalog_id, class_id="class-admin-gen-a")
    await _seed_active_kg(
        class_a,
        [
            {"id": "node-1", "name": "变量", "chapter": "第一章", "support_band": "strong", "body_top1_score": 0.82},
            {"id": "node-2", "name": "指针", "chapter": "第二章", "support_band": "good", "body_top1_score": 0.67},
        ],
    )

    with patch("app.api.v1.catalogs.agent_client.post_json", new_callable=AsyncMock) as mock_agent:
        mock_agent.return_value = {"task_id": "accepted"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/course-catalogs/{catalog_id}/resources/generations",
                headers=_auth_headers("admin-admin-gen", "admin"),
                json={"resource_types": ["document"]},
            )

    assert response.status_code == 202, response.text
    parent_task_id = response.json()["data"]["task_id"]
    assert mock_agent.await_count == 2
    payloads = [call.args[1] for call in mock_agent.await_args_list]
    assert [payload["course_id"] for payload in payloads] == [catalog_id, catalog_id]
    assert [(payload["chapter"], payload["knowledge_point"]) for payload in payloads] == [
        ("第一章", "变量"),
        ("第二章", "指针"),
    ]

    async with async_session_factory() as db:
        parent = await db.get(AsyncTask, parent_task_id)
        assert parent is not None
        assert parent.status == "processing"
        assert parent.result["mode"] == "kg_node_targets"
        assert parent.result["fanout_course_ids"] == [class_a]
        assert parent.result["target_node_count"] == 2
        assert parent.result["total_child_count"] == 2
        assert parent.result["selection_degraded"] is False

        result = await db.execute(select(AsyncTask).where(AsyncTask.id != parent_task_id))
        children = sorted(result.scalars().all(), key=lambda task: task.result["target_node"]["node_id"])
        assert len(children) == 2
        assert [child.result["parent_task_id"] for child in children] == [parent_task_id, parent_task_id]
        assert [child.result["target_node"]["node_name"] for child in children] == ["变量", "指针"]
        assert [child.result["fanout_course_ids"] for child in children] == [[class_a], [class_a]]
```

- [ ] **Step 2: Run the new Admin test and confirm RED**

Run from `../backend` with MySQL:

```bash
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/kg_resource_metadata_alignment_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_admin_catalog_resource_generation.py::test_admin_catalog_generation_without_metadata_creates_parent_and_child_tasks_from_active_kg -q -p no:cacheprovider
```

Expected: FAIL because current endpoint creates one task and one Agent call using catalog-level fallback metadata.

- [ ] **Step 3: Add route imports and helper functions**

Modify imports in `../backend/app/api/v1/catalogs.py`:

```python
from app.services.course_knowledge_graphs import get_active_knowledge_graph
from app.services.kg_resource_targets import select_core_resource_targets
```

Add helper functions near existing private helpers:

```python
KG_RESOURCE_TARGET_LIMIT = 10


def _is_explicit_resource_target(req: CatalogResourceGenerateRequest) -> bool:
    return bool((req.chapter or "").strip() or (req.knowledge_point or "").strip())


def _resource_types_or_default(req: CatalogResourceGenerateRequest) -> list[str]:
    return req.resource_types or ["document", "mindmap", "reading", "code"]


async def _active_kg_for_catalog_generation(
    db: AsyncSession,
    fanout_course_ids: list[str],
):
    for course_id in fanout_course_ids:
        kg = await get_active_knowledge_graph(db, course_id)
        if kg is not None:
            return kg
    return None
```

- [ ] **Step 4: Implement KG-node branch in Admin generation route**

In `admin_generate_catalog_resources()`, keep all existing validation and offering lookup. After `fanout_course_ids` is computed, branch before current single-task creation:

```python
    resource_types = _resource_types_or_default(req)

    if not _is_explicit_resource_target(req):
        kg = await _active_kg_for_catalog_generation(db, fanout_course_ids)
        if kg is None:
            task = AsyncTask(
                task_type="resource_generation",
                status="failed",
                progress=100,
                user_id=current_user.id,
                course_id=None,
                result={
                    "catalog_id": catalog.id,
                    "catalog_title": catalog.title,
                    "fanout_course_ids": fanout_course_ids,
                    "mode": "kg_node_targets",
                    "resource_types": resource_types,
                },
                error_code="kg_not_ready",
                error_message="课程知识图谱未就绪",
                completed_at=_now_utc(),
            )
            db.add(task)
            await db.commit()
            return {
                "code": 202,
                "message": "accepted",
                "data": {"task_id": task.id, "catalog_id": catalog.id, "status": "processing"},
            }

        selection = select_core_resource_targets(
            kg.nodes if isinstance(kg.nodes, list) else [],
            max_targets=KG_RESOURCE_TARGET_LIMIT,
        )
        target_nodes = selection["targets"]
        if not target_nodes:
            task = AsyncTask(
                task_type="resource_generation",
                status="failed",
                progress=100,
                user_id=current_user.id,
                course_id=None,
                result={
                    "catalog_id": catalog.id,
                    "catalog_title": catalog.title,
                    "fanout_course_ids": fanout_course_ids,
                    "mode": "kg_node_targets",
                    "resource_types": resource_types,
                    "target_node_count": 0,
                    "total_child_count": 0,
                    "selection_degraded": selection["selection_degraded"],
                    "selection_degraded_reason": selection["degraded_reason"],
                },
                error_code="kg_target_empty",
                error_message="没有可用于资源挂载的 KG 节点",
                completed_at=_now_utc(),
            )
            db.add(task)
            await db.commit()
            return {
                "code": 202,
                "message": "accepted",
                "data": {"task_id": task.id, "catalog_id": catalog.id, "status": "processing"},
            }

        parent = AsyncTask(
            task_type="resource_generation",
            status="processing",
            progress=10,
            user_id=current_user.id,
            course_id=None,
            result={
                "catalog_id": catalog.id,
                "catalog_title": catalog.title,
                "fanout_course_ids": fanout_course_ids,
                "mode": "kg_node_targets",
                "knowledge_status": catalog.knowledge_status,
                "degraded": catalog.knowledge_status == "partial",
                "chunk_count": catalog.chunk_count or 0,
                "resource_types": resource_types,
                "target_node_count": len(target_nodes),
                "total_child_count": len(target_nodes),
                "target_nodes": target_nodes,
                "selection_degraded": selection["selection_degraded"],
                "selection_degraded_reason": selection["degraded_reason"],
                "completed_child_count": 0,
                "failed_child_count": 0,
                "successful_node_count": 0,
                "failed_node_count": 0,
            },
        )
        db.add(parent)
        await db.flush()
        await db.refresh(parent)

        children: list[AsyncTask] = []
        for target_node in target_nodes:
            child = AsyncTask(
                task_type="resource_generation",
                status="processing",
                progress=10,
                user_id=current_user.id,
                course_id=None,
                result={
                    "catalog_id": catalog.id,
                    "catalog_title": catalog.title,
                    "parent_task_id": parent.id,
                    "fanout_course_ids": fanout_course_ids,
                    "mode": "kg_node_target",
                    "target_node": target_node,
                    "resource_types": resource_types,
                },
            )
            db.add(child)
            children.append(child)
        await db.flush()

        for child in children:
            target_node = child.result["target_node"]
            payload = {
                "task_id": child.id,
                "user_id": current_user.id,
                "course_id": catalog.id,
                "chapter": target_node["chapter"],
                "knowledge_point": target_node["node_name"],
                "resource_types": resource_types,
                "webhook_url": _webhook_url(request),
            }
            try:
                await agent_client.post_json("/agent/v1/resources/generate", payload)
            except AgentServiceError as e:
                child.status = "failed"
                child.error_code = str(e.agent_code or "agent_error")
                child.error_message = e.message
                child.progress = 100
                child.completed_at = _now_utc()

        await db.commit()
        return {
            "code": 202,
            "message": "accepted",
            "data": {"task_id": parent.id, "catalog_id": catalog.id, "status": "processing"},
        }
```

Then update the existing single-target path to use `resource_types` instead of reading `req.resource_types` directly.

- [ ] **Step 5: Run Admin default KG-node test and confirm GREEN**

Run from `../backend`:

```bash
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/kg_resource_metadata_alignment_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_admin_catalog_resource_generation.py::test_admin_catalog_generation_without_metadata_creates_parent_and_child_tasks_from_active_kg -q -p no:cacheprovider
```

Expected: `1 passed`.

- [ ] **Step 6: Run compatibility test for explicit metadata**

Run from `../backend`:

```bash
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/kg_resource_metadata_alignment_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_admin_catalog_resource_generation.py::test_admin_catalog_generation_creates_task_and_sends_catalog_id_to_agent -q -p no:cacheprovider
```

Expected: `1 passed`.

- [ ] **Step 7: Commit Task 2**

```bash
git add ../backend/app/api/v1/catalogs.py ../backend/tests/test_admin_catalog_resource_generation.py
git commit -m "接入KG节点资源生成父子任务"
```

## Task 3: Webhook Metadata Override And Parent Aggregation

**Files:**
- Modify: `../backend/app/api/v1/webhooks.py`
- Test: `../backend/tests/test_admin_catalog_resource_generation.py`

- [ ] **Step 1: Add failing webhook metadata override test**

Add to `../backend/tests/test_admin_catalog_resource_generation.py`:

```python
@pytest.mark.asyncio
async def test_webhook_kg_node_child_overrides_agent_metadata_and_updates_parent_completed():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    await _seed_user("teacher-admin-gen", "teacher")
    catalog_id = await _seed_ready_catalog()
    class_a = await _seed_bound_class(catalog_id=catalog_id, class_id="class-admin-gen-a")

    async with async_session_factory() as db:
        parent = AsyncTask(
            id="parent-kg-node",
            task_type="resource_generation",
            status="processing",
            user_id="admin-admin-gen",
            course_id=None,
            result={
                "catalog_id": catalog_id,
                "fanout_course_ids": [class_a],
                "mode": "kg_node_targets",
                "total_child_count": 1,
                "target_node_count": 1,
                "completed_child_count": 0,
                "failed_child_count": 0,
                "successful_node_count": 0,
                "failed_node_count": 0,
            },
        )
        child = AsyncTask(
            id="child-kg-node",
            task_type="resource_generation",
            status="processing",
            user_id="admin-admin-gen",
            course_id=None,
            result={
                "catalog_id": catalog_id,
                "parent_task_id": parent.id,
                "fanout_course_ids": [class_a],
                "mode": "kg_node_target",
                "target_node": {
                    "node_id": "node-pointer",
                    "node_name": "指针",
                    "chapter": "第二章",
                    "support_band": "good",
                    "body_top1_score": 0.67,
                },
                "resource_types": ["document"],
            },
        )
        db.add_all([parent, child])
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/webhooks/agent",
            headers=_webhook_headers(),
            json={
                "task_id": "child-kg-node",
                "task_type": "resource_generation",
                "status": "completed",
                "result": {
                    "resources": [
                        {
                            "title": "Pointer Doc",
                            "type": "document",
                            "description": "doc",
                            "content": "doc content",
                            "chapter": "课程整体",
                            "knowledge_point": "综合知识点",
                            "tags": ["agent"],
                        }
                    ]
                },
            },
        )

    assert response.status_code == 200, response.text
    async with async_session_factory() as db:
        result = await db.execute(select(Resource).where(Resource.title == "Pointer Doc"))
        resource = result.scalar_one()
        assert resource.course_id == class_a
        assert resource.chapter == "第二章"
        assert resource.knowledge_point == "指针"
        assert "kg_node:node-pointer" in resource.tags
        assert "support_band:good" in resource.tags

        parent = await db.get(AsyncTask, "parent-kg-node")
        assert parent.status == "completed"
        assert parent.progress == 100
        assert parent.result["completed_child_count"] == 1
        assert parent.result["failed_child_count"] == 0
        assert parent.result["successful_node_count"] == 1
        assert parent.result["failed_node_count"] == 0
        assert parent.result.get("degraded") is False
```

- [ ] **Step 2: Add failing parent degraded and failed tests**

Add:

```python
@pytest.mark.asyncio
async def test_webhook_parent_aggregation_marks_degraded_when_one_child_failed():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    async with async_session_factory() as db:
        parent = AsyncTask(
            id="parent-degraded",
            task_type="resource_generation",
            status="processing",
            user_id="admin-admin-gen",
            result={"mode": "kg_node_targets", "total_child_count": 2},
        )
        completed_child = AsyncTask(
            id="child-completed",
            task_type="resource_generation",
            status="completed",
            user_id="admin-admin-gen",
            result={"mode": "kg_node_target", "parent_task_id": "parent-degraded"},
        )
        failed_child = AsyncTask(
            id="child-failed",
            task_type="resource_generation",
            status="processing",
            user_id="admin-admin-gen",
            result={"mode": "kg_node_target", "parent_task_id": "parent-degraded"},
        )
        db.add_all([parent, completed_child, failed_child])
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/webhooks/agent",
            headers=_webhook_headers(),
            json={
                "task_id": "child-failed",
                "task_type": "resource_generation",
                "status": "failed",
                "error_code": "agent_error",
                "error_message": "model failed",
            },
        )

    assert response.status_code == 200, response.text
    async with async_session_factory() as db:
        parent = await db.get(AsyncTask, "parent-degraded")
        assert parent.status == "completed"
        assert parent.result["degraded"] is True
        assert parent.result["completed_child_count"] == 1
        assert parent.result["failed_child_count"] == 1
        assert parent.result["successful_node_count"] == 1
        assert parent.result["failed_node_count"] == 1


@pytest.mark.asyncio
async def test_webhook_parent_aggregation_marks_failed_when_all_children_failed():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    async with async_session_factory() as db:
        parent = AsyncTask(
            id="parent-failed",
            task_type="resource_generation",
            status="processing",
            user_id="admin-admin-gen",
            result={"mode": "kg_node_targets", "total_child_count": 1},
        )
        child = AsyncTask(
            id="child-failed-only",
            task_type="resource_generation",
            status="processing",
            user_id="admin-admin-gen",
            result={"mode": "kg_node_target", "parent_task_id": "parent-failed"},
        )
        db.add_all([parent, child])
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/webhooks/agent",
            headers=_webhook_headers(),
            json={
                "task_id": "child-failed-only",
                "task_type": "resource_generation",
                "status": "failed",
                "error_code": "agent_error",
                "error_message": "model failed",
            },
        )

    assert response.status_code == 200, response.text
    async with async_session_factory() as db:
        parent = await db.get(AsyncTask, "parent-failed")
        assert parent.status == "failed"
        assert parent.progress == 100
        assert parent.error_code == "all_child_tasks_failed"
        assert parent.result["completed_child_count"] == 0
        assert parent.result["failed_child_count"] == 1
```

- [ ] **Step 3: Run webhook tests and confirm RED**

Run from `../backend`:

```bash
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/kg_resource_metadata_alignment_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_admin_catalog_resource_generation.py::test_webhook_kg_node_child_overrides_agent_metadata_and_updates_parent_completed tests/test_admin_catalog_resource_generation.py::test_webhook_parent_aggregation_marks_degraded_when_one_child_failed tests/test_admin_catalog_resource_generation.py::test_webhook_parent_aggregation_marks_failed_when_all_children_failed -q -p no:cacheprovider
```

Expected: FAIL because webhook currently trusts Agent metadata and does not update parent tasks.

- [ ] **Step 4: Implement metadata override helpers**

Modify `../backend/app/api/v1/webhooks.py`.

Add helpers near validation helpers:

```python
def _target_node_from_task(task: AsyncTask) -> dict | None:
    if not isinstance(task.result, dict):
        return None
    if task.result.get("mode") != "kg_node_target":
        return None
    target_node = task.result.get("target_node")
    return target_node if isinstance(target_node, dict) else None


def _metadata_for_resource(task: AsyncTask, resource: dict) -> tuple[str, str, list]:
    target_node = _target_node_from_task(task)
    if target_node is None:
        return resource["chapter"], resource["knowledge_point"], resource["tags"]
    node_id = str(target_node.get("node_id") or "")
    support_band = str(target_node.get("support_band") or "")
    tags = list(resource["tags"])
    if node_id:
        tags.append(f"kg_node:{node_id}")
    if support_band:
        tags.append(f"support_band:{support_band}")
    return (
        str(target_node.get("chapter") or resource["chapter"]),
        str(target_node.get("node_name") or resource["knowledge_point"]),
        tags,
    )
```

In the resource creation loop, replace:

```python
                    tags=r["tags"],
                    chapter=r["chapter"],
                    knowledge_point=r["knowledge_point"],
```

with:

```python
                    tags=resource_tags,
                    chapter=resource_chapter,
                    knowledge_point=resource_knowledge_point,
```

and compute just before constructing `Resource`:

```python
                resource_chapter, resource_knowledge_point, resource_tags = _metadata_for_resource(task, r)
```

- [ ] **Step 5: Implement parent aggregation helper**

Add imports:

```python
from sqlalchemy import select
```

`select` already exists in the file. Keep one import only.

Add helper:

```python
async def _recompute_parent_resource_generation_task(db: AsyncSession, child_task: AsyncTask) -> None:
    if not isinstance(child_task.result, dict):
        return
    parent_task_id = child_task.result.get("parent_task_id")
    if not parent_task_id:
        return

    parent_result = await db.execute(
        select(AsyncTask)
        .where(
            AsyncTask.id == str(parent_task_id),
            AsyncTask.task_type == "resource_generation",
            AsyncTask.is_deleted == False,
        )
        .with_for_update()
    )
    parent = parent_result.scalar_one_or_none()
    if parent is None or parent.status in {"completed", "failed"}:
        return

    children_result = await db.execute(
        select(AsyncTask).where(
            AsyncTask.task_type == "resource_generation",
            AsyncTask.is_deleted == False,
        )
    )
    children = [
        item
        for item in children_result.scalars().all()
        if isinstance(item.result, dict)
        and item.result.get("parent_task_id") == str(parent_task_id)
    ]
    completed_count = sum(1 for item in children if item.status == "completed")
    failed_count = sum(1 for item in children if item.status == "failed")
    total_count = int((parent.result or {}).get("total_child_count") or len(children))

    merged_result = dict(parent.result or {})
    merged_result.update(
        {
            "completed_child_count": completed_count,
            "failed_child_count": failed_count,
            "successful_node_count": completed_count,
            "failed_node_count": failed_count,
        }
    )

    if completed_count + failed_count < total_count:
        parent.result = merged_result
        return

    parent.progress = 100
    parent.completed_at = datetime.now(timezone.utc)
    if completed_count > 0:
        merged_result["degraded"] = failed_count > 0 or bool(merged_result.get("degraded"))
        parent.status = "completed"
        parent.error_code = None
        parent.error_message = ""
    else:
        parent.status = "failed"
        parent.error_code = "all_child_tasks_failed"
        parent.error_message = "所有 KG 节点资源生成子任务均失败"
        merged_result["degraded"] = True
    parent.result = merged_result
```

Call this helper after completed and failed task updates, before `await db.flush()`:

```python
    await _recompute_parent_resource_generation_task(db, task)
```

- [ ] **Step 6: Run webhook tests and confirm GREEN**

Run from `../backend`:

```bash
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/kg_resource_metadata_alignment_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_admin_catalog_resource_generation.py::test_webhook_kg_node_child_overrides_agent_metadata_and_updates_parent_completed tests/test_admin_catalog_resource_generation.py::test_webhook_parent_aggregation_marks_degraded_when_one_child_failed tests/test_admin_catalog_resource_generation.py::test_webhook_parent_aggregation_marks_failed_when_all_children_failed -q -p no:cacheprovider
```

Expected: `3 passed`.

- [ ] **Step 7: Run existing webhook compatibility tests**

Run from `../backend`:

```bash
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/kg_resource_metadata_alignment_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_admin_catalog_resource_generation.py::test_webhook_fans_out_catalog_resources_to_bound_classes tests/test_agent_integration.py::TestResourceGenerateIntegration::test_webhook_resource_generation_writes_resources -q -p no:cacheprovider
```

Expected: `2 passed`.

- [ ] **Step 8: Commit Task 3**

```bash
git add ../backend/app/api/v1/webhooks.py ../backend/tests/test_admin_catalog_resource_generation.py
git commit -m "对齐KG节点资源落库元数据"
```

## Task 4: Error Paths, Regression Suite, And Progress Docs

**Files:**
- Modify: `../backend/tests/test_admin_catalog_resource_generation.py`
- Modify: `../backend/WORKFLOW.md`
- Modify only if real probe passes: `docs/feature-ledger.md`

- [ ] **Step 1: Add no-active-KG and no-target tests**

Add:

```python
@pytest.mark.asyncio
async def test_admin_catalog_generation_without_metadata_fails_parent_when_no_active_kg():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    await _seed_user("teacher-admin-gen", "teacher")
    catalog_id = await _seed_ready_catalog()
    await _seed_bound_class(catalog_id=catalog_id, class_id="class-admin-gen-a")

    with patch("app.api.v1.catalogs.agent_client.post_json", new_callable=AsyncMock) as mock_agent:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/course-catalogs/{catalog_id}/resources/generations",
                headers=_auth_headers("admin-admin-gen", "admin"),
                json={"resource_types": ["document"]},
            )

    assert response.status_code == 202, response.text
    mock_agent.assert_not_awaited()
    async with async_session_factory() as db:
        task = await db.get(AsyncTask, response.json()["data"]["task_id"])
        assert task.status == "failed"
        assert task.error_code == "kg_not_ready"
        assert task.error_message == "课程知识图谱未就绪"


@pytest.mark.asyncio
async def test_admin_catalog_generation_without_metadata_fails_parent_when_no_usable_targets():
    await _reset_db()
    await _seed_user("admin-admin-gen", "admin")
    await _seed_user("teacher-admin-gen", "teacher")
    catalog_id = await _seed_ready_catalog()
    class_a = await _seed_bound_class(catalog_id=catalog_id, class_id="class-admin-gen-a")
    await _seed_active_kg(
        class_a,
        [
            {"id": "bad", "name": "目录", "chapter": "附录", "support_band": "unsupported", "body_top1_score": 0.40}
        ],
    )

    with patch("app.api.v1.catalogs.agent_client.post_json", new_callable=AsyncMock) as mock_agent:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/admin/course-catalogs/{catalog_id}/resources/generations",
                headers=_auth_headers("admin-admin-gen", "admin"),
                json={"resource_types": ["document"]},
            )

    assert response.status_code == 202, response.text
    mock_agent.assert_not_awaited()
    async with async_session_factory() as db:
        task = await db.get(AsyncTask, response.json()["data"]["task_id"])
        assert task.status == "failed"
        assert task.error_code == "kg_target_empty"
        assert task.error_message == "没有可用于资源挂载的 KG 节点"
```

- [ ] **Step 2: Run error path tests**

Run from `../backend`:

```bash
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/kg_resource_metadata_alignment_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_admin_catalog_resource_generation.py::test_admin_catalog_generation_without_metadata_fails_parent_when_no_active_kg tests/test_admin_catalog_resource_generation.py::test_admin_catalog_generation_without_metadata_fails_parent_when_no_usable_targets -q -p no:cacheprovider
```

Expected: `2 passed`.

- [ ] **Step 3: Run focused backend suite**

Run from `../backend`:

```bash
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/kg_resource_metadata_alignment_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_kg_resource_targets.py tests/test_admin_catalog_resource_generation.py tests/test_agent_integration.py::TestResourceGenerateIntegration::test_webhook_resource_generation_writes_resources -q -p no:cacheprovider
```

Expected: all selected tests pass.

- [ ] **Step 4: Run KG and node resource regression suite**

Run from `../backend`:

```bash
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/kg_resource_metadata_alignment_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_node_resources.py tests/test_kg_resource_alignment_probe.py tests/test_course_knowledge_graph_versions.py -q -p no:cacheprovider
```

Expected: all selected tests pass.

- [ ] **Step 5: Update backend workflow**

Append a dated entry to `../backend/WORKFLOW.md` containing:

```markdown
- 2026-06-11：KG 资源生成 metadata 对齐实现：
  - Admin catalog resource generation 在未显式传 `chapter/knowledge_point` 时读取 active KG，选择核心节点子集生成资源。
  - Backend 创建父 `resource_generation` 任务和 KG-node 子任务；Agent 仍使用现有 `/agent/v1/resources/generate` 契约，`course_id` 继续传 catalog id 以匹配 Qdrant payload。
  - Webhook 对 KG-node 子任务使用 `target_node` 覆盖 `Resource.chapter/knowledge_point`，并重算父任务 `completed/degraded/failed`。
  - 验证：写入本轮实际运行的 pytest 命令和结果。
```

- [ ] **Step 6: Commit Task 4**

```bash
git add ../backend/tests/test_admin_catalog_resource_generation.py ../backend/WORKFLOW.md
git commit -m "完善KG资源生成异常与验证记录"
```

## Task 5: Real MySQL Probe Verification

**Files:**
- Modify if probe result changes main status: `docs/feature-ledger.md`
- Modify if run evidence needs frontend handoff: `WORKFLOW.md`

- [ ] **Step 1: Generate KG-node resources on the real C catalog**

Use the existing live Backend and Agent Service only after confirming both are configured with MySQL and shared storage. Trigger Admin catalog generation through the Client API or existing smoke helper. The request body must omit `chapter` and `knowledge_point`:

```json
{
  "resource_types": ["document", "mindmap"]
}
```

Expected:

- Parent task created with `mode=kg_node_targets`.
- Child tasks created with `mode=kg_node_target`.
- Agent payload `course_id` equals catalog id `b2444963f0e54587`.
- Child payloads contain concrete KG node `chapter/knowledge_point`.

- [ ] **Step 2: Run inventory probe**

Run from `../backend`:

```bash
DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/duagent?charset=utf8mb4 ../.venv/bin/python tools/probe_kg_resource_alignment.py inventory --format json --out /tmp/kg-resource-probe/inventory-after-kg-resource-metadata-alignment.json
```

Expected:

- Command exits 0.
- C catalog/course remains `eligible_for_formal_probe=true`.
- `resource_count` increased after generation.

- [ ] **Step 3: Run all-node KG-Resource probe**

Run from `../backend`:

```bash
DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/duagent?charset=utf8mb4 ../.venv/bin/python tools/probe_kg_resource_alignment.py probe --catalog-id b2444963f0e54587 --course-id 6c698badb60a4809 --sample-mode all --format csv --out /tmp/kg-resource-probe/c-language-kg-resource-metadata-alignment.csv
```

Expected:

- Command exits 0.
- At least one row has `candidate_count > 0`.
- Rows for generated target nodes show candidate resources whose `chapter/knowledge_point` match KG node chapter/name.

- [ ] **Step 4: Update frontend progress docs only if probe is meaningful**

If probe shows nonzero meaningful alignment, update:

- `WORKFLOW.md`
- `docs/feature-ledger.md`

Add evidence:

```markdown
- 2026-06-11：KG 资源 metadata 对齐探针复验：
  - 通过 KG-node 默认资源生成，资源 metadata 写入 KG 标准 `chapter/knowledge_point`。
  - inventory 输出：`/tmp/kg-resource-probe/inventory-after-kg-resource-metadata-alignment.json`。
  - probe 输出：`/tmp/kg-resource-probe/c-language-kg-resource-metadata-alignment.csv`。
  - 结果：写入实际 `candidate_count>0` 节点数和抽查结论。
```

Do not mark LearningPath ready gate ready in this task. The next decision is LearningPath active KG resource attachment evaluation.

- [ ] **Step 5: Commit Task 5 docs**

```bash
git add WORKFLOW.md docs/feature-ledger.md
git commit -m "记录KG资源元数据对齐探针结果"
```

Skip this commit if probe did not produce meaningful nonzero alignment; instead record failure details in `../backend/WORKFLOW.md` in the Task 4 commit scope or a new backend workflow-only commit.

## Final Verification

Run from `../backend`:

```bash
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/kg_resource_metadata_alignment_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_kg_resource_targets.py tests/test_admin_catalog_resource_generation.py tests/test_agent_integration.py::TestResourceGenerateIntegration::test_webhook_resource_generation_writes_resources tests/test_node_resources.py tests/test_kg_resource_alignment_probe.py tests/test_course_knowledge_graph_versions.py -q -p no:cacheprovider
```

Expected: all selected tests pass.

Run from `frontend`:

```bash
git status --short
git log --oneline -5
```

Expected:

- Only unrelated pre-existing dirty files remain.
- New commits are present for each completed batch.

## Spec Coverage Self-Review

- KG-node default path: Task 2.
- Explicit metadata compatibility: Task 2 Step 6.
- Parent and child tasks: Task 2.
- `total_child_count` and status recompute: Task 3.
- Metadata override from `target_node`: Task 3.
- Support band vs chapter balance rule: Task 1.
- Catalog id as Agent RAG key: Task 2 payload checks and Task 5 live checks.
- Error paths: Task 4.
- Probe validation: Task 5.
