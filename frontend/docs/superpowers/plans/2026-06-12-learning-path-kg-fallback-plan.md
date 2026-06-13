# LearningPath KG Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 当 `learning_paths` 表为空时，从 active KG 合成学习路径骨架返回，全节点 recommended。

**Architecture:** 在 `get_learning_path` 无 LP 记录分支中，插入 `_synthesize_kg_fallback_path` 调用。该函数沿 `CourseOffering → CourseCatalog → KG` 链查 active KG，Kahn 拓扑排序节点，组装与真实 LP 兼容的响应格式，标记 `source: "kg_fallback"`。

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, pytest + httpx ASGITransport

---

### Task 1: 单元测试 — 拓扑排序函数

**Files:**
- Create: `tests/test_learning_path_fallback.py`

- [ ] **Step 1: 创建测试文件，写拓扑排序测试**

```python
"""Unit tests for _topo_sort_kg_nodes in learning_path.py fallback path.

Run: python -m pytest tests/test_learning_path_fallback.py -v
"""
import pytest
from app.api.v1.learning_path import _topo_sort_kg_nodes


class TestTopoSortKgNodes:
    def test_sorts_simple_dag(self):
        nodes = [
            {"id": "a", "name": "A", "chapter": "Ch1"},
            {"id": "b", "name": "B", "chapter": "Ch1"},
            {"id": "c", "name": "C", "chapter": "Ch2"},
        ]
        edges = [
            {"from": "a", "to": "b"},
            {"from": "b", "to": "c"},
        ]
        result = _topo_sort_kg_nodes(nodes, edges)
        ids = [n["id"] for n in result]
        assert ids == ["a", "b", "c"]

    def test_multiple_roots(self):
        nodes = [
            {"id": "a", "name": "A", "chapter": "Ch1"},
            {"id": "b", "name": "B", "chapter": "Ch1"},
            {"id": "c", "name": "C", "chapter": "Ch2"},
        ]
        edges = [
            {"from": "a", "to": "c"},
            {"from": "b", "to": "c"},
        ]
        result = _topo_sort_kg_nodes(nodes, edges)
        ids = [n["id"] for n in result]
        assert ids[0] in ("a", "b")
        assert ids[1] in ("a", "b")
        assert ids[2] == "c"

    def test_no_edges_falls_back_to_original_order(self):
        nodes = [
            {"id": "z", "name": "Z", "chapter": "Ch3"},
            {"id": "a", "name": "A", "chapter": "Ch1"},
        ]
        result = _topo_sort_kg_nodes(nodes, [])
        ids = [n["id"] for n in result]
        assert ids == ["z", "a"]

    def test_empty_nodes(self):
        assert _topo_sort_kg_nodes([], []) == []

    def test_preserves_all_node_fields(self):
        nodes = [
            {"id": "n1", "name": "Node1", "chapter": "Ch1"},
        ]
        result = _topo_sort_kg_nodes(nodes, [{"from": "n1", "to": "n2"}])
        assert result[0]["id"] == "n1"
        assert result[0]["name"] == "Node1"
        assert result[0]["chapter"] == "Ch1"

    def test_disjoint_subgraphs(self):
        nodes = [
            {"id": "a", "name": "A", "chapter": "Ch1"},
            {"id": "b", "name": "B", "chapter": "Ch1"},
            {"id": "c", "name": "C", "chapter": "Ch2"},
            {"id": "d", "name": "D", "chapter": "Ch2"},
        ]
        edges = [
            {"from": "a", "to": "b"},
            {"from": "c", "to": "d"},
        ]
        result = _topo_sort_kg_nodes(nodes, edges)
        ids = [n["id"] for n in result]
        assert ids.index("a") < ids.index("b")
        assert ids.index("c") < ids.index("d")
```

- [ ] **Step 2: 运行测试 — 预期全部 FAIL（函数未定义）**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/backend && python -m pytest tests/test_learning_path_fallback.py -v 2>&1 | tail -20
```

- [ ] **Step 3: 在 `learning_path.py` 中添加 `_topo_sort_kg_nodes` 函数**

在 `_release_learning_path_lock` 之后、`@router.get("")` 之前插入：

```python
def _topo_sort_kg_nodes(
    nodes: list[dict],
    edges: list[dict],
) -> list[dict]:
    """Kahn topological sort of KG nodes based on edges.

    Returns nodes ordered so that prerequisites come before dependents.
    Falls back to original array order if edges is empty.
    """
    if not nodes:
        return []
    if not edges:
        return list(nodes)

    node_ids = {n["id"] for n in nodes}
    in_degree: dict[str, int] = {n["id"]: 0 for n in nodes}
    adj: dict[str, list[str]] = {n["id"]: [] for n in nodes}

    for edge in edges:
        from_id = edge.get("from", "")
        to_id = edge.get("to", "")
        if from_id in node_ids and to_id in node_ids:
            adj[from_id].append(to_id)
            in_degree[to_id] = in_degree.get(to_id, 0) + 1

    # Start with nodes that have zero in-degree, in original array order
    queue = [n["id"] for n in nodes if in_degree.get(n["id"], 0) == 0]
    sorted_ids: list[str] = []
    while queue:
        node_id = queue.pop(0)
        sorted_ids.append(node_id)
        for neighbor in adj.get(node_id, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # Append any remaining nodes not reached (cycles or missing edge refs)
    sorted_set = set(sorted_ids)
    for n in nodes:
        if n["id"] not in sorted_set:
            sorted_ids.append(n["id"])

    # Map back to node dicts preserving all fields
    node_map = {n["id"]: dict(n) for n in nodes}
    return [node_map[nid] for nid in sorted_ids if nid in node_map]
```

- [ ] **Step 4: 运行测试 — 预期全部 PASS**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/backend && python -m pytest tests/test_learning_path_fallback.py -v
```

- [ ] **Step 5: Commit**

```bash
git add tests/test_learning_path_fallback.py backend/app/api/v1/learning_path.py
git commit -m "feat: 添加 KG 节点拓扑排序函数及单元测试"
```

---

### Task 2: `_synthesize_kg_fallback_path` 函数

**Files:**
- Modify: `backend/app/api/v1/learning_path.py`

- [ ] **Step 1: 添加 import**

在文件顶部 import 区域，`from app.models.course import CourseEnrollment` 之后插入：

```python
from app.models.catalog import CourseCatalog, CourseOffering
```

- [ ] **Step 2: 在 `_topo_sort_kg_nodes` 之后、`@router.get("")` 之前插入 fallback 函数**

```python
async def _synthesize_kg_fallback_path(
    db: AsyncSession,
    course_id: str,
) -> dict | None:
    """从 active KG 合成学习路径骨架。

    查找链: CourseOffering(id=course_id) → catalog_id →
            CourseCatalog → kg_host_course_id → active KG.
    返回 KG 节点（拓扑排序）+ 边，全部 status="recommended"。
    如果任一环节查不到，返回 None。
    """
    # 1. CourseOffering → catalog_id
    offering_result = await db.execute(
        select(CourseOffering).where(
            CourseOffering.id == course_id,
            CourseOffering.is_deleted == False,
        )
    )
    offering = offering_result.scalar_one_or_none()
    if offering is None:
        return None

    # 2. CourseCatalog → kg_host_course_id
    catalog_result = await db.execute(
        select(CourseCatalog).where(
            CourseCatalog.id == offering.catalog_id,
            CourseCatalog.is_deleted == False,
        )
    )
    catalog = catalog_result.scalar_one_or_none()
    if catalog is None or not catalog.kg_host_course_id:
        return None

    # 3. Active KG
    kg = await get_active_knowledge_graph(db, catalog.kg_host_course_id)
    if kg is None:
        return None

    kg_nodes = kg.nodes if isinstance(kg.nodes, list) else []
    if not kg_nodes:
        return None

    kg_edges = kg.edges if isinstance(kg.edges, list) else []

    # 4. Topo sort
    sorted_nodes = _topo_sort_kg_nodes(kg_nodes, kg_edges)

    # 5. Assemble nodes with status/mastery/order
    assembled_nodes = []
    for idx, node in enumerate(sorted_nodes):
        assembled_nodes.append({
            "id": node.get("id", ""),
            "name": node.get("name", ""),
            "chapter": node.get("chapter", ""),
            "order": idx + 1,
            "status": "recommended",
            "mastery": 0,
        })

    first_node = assembled_nodes[0]

    return {
        "course_id": course_id,
        "nodes": assembled_nodes,
        "edges": kg_edges,
        "current_position": {
            "node_id": first_node["id"],
            "node_name": first_node["name"],
        },
        "source": "kg_fallback",
        "generated_at": kg.create_time.isoformat() if kg.create_time else None,
    }
```

- [ ] **Step 3: 修改 `get_learning_path` 的空 LP 分支**

替换 `if lp is None:` 块：

原代码（大概 line 64-75）:
```python
    if lp is None:
        return {
            "code": 200,
            "message": "success",
            "data": {
                "course_id": course_id,
                "nodes": [],
                "edges": [],
                "current_position": None,
                "generated_at": None,
            },
        }
```

改为：
```python
    if lp is None:
        fallback = await _synthesize_kg_fallback_path(db, course_id)
        if fallback is not None:
            return {"code": 200, "message": "success", "data": fallback}
        return {
            "code": 200,
            "message": "success",
            "data": {
                "course_id": course_id,
                "nodes": [],
                "edges": [],
                "current_position": None,
                "source": "kg_fallback",
                "generated_at": None,
            },
        }
```

同时修改有 LP 记录的返回，加上 `source` 字段：

原代码（大概 line 77-90）:
```python
    return {
        "code": 200,
        "message": "success",
        "data": {
            "course_id": lp.course_id,
            "nodes": lp.nodes or [],
            "edges": lp.edges or [],
            "current_position": {
                "node_id": lp.current_node_id,
                "node_name": lp.current_node_name,
            } if lp.current_node_id else None,
            "generated_at": lp.generated_at.isoformat() if lp.generated_at else None,
        },
    }
```

改为：
```python
    return {
        "code": 200,
        "message": "success",
        "data": {
            "course_id": lp.course_id,
            "nodes": lp.nodes or [],
            "edges": lp.edges or [],
            "current_position": {
                "node_id": lp.current_node_id,
                "node_name": lp.current_node_name,
            } if lp.current_node_id else None,
            "source": "learning_path",
            "generated_at": lp.generated_at.isoformat() if lp.generated_at else None,
        },
    }
```

- [ ] **Step 4: 确认语法正确**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/backend && python -c "from app.api.v1.learning_path import _topo_sort_kg_nodes, _synthesize_kg_fallback_path; print('Imports OK')"
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/learning_path.py
git commit -m "feat: LearningPath GET 无记录时 fallback 到 KG 骨架合成路径"
```

---

### Task 3: 集成测试

**Files:**
- Modify: `tests/test_learning_path_fallback.py`

- [ ] **Step 1: 追加集成测试（用 SQLite）**

在文件末尾追加：

```python
import asyncio
import os
import re
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///./test_learning_path_fb.db",
)

from app.db.session import async_session_factory, init_db

asyncio.run(init_db())

from app.main import app
from app.models.catalog import CourseCatalog, CourseOffering
from app.models.others import CourseKnowledgeGraph
from app.models.user import RegistrationCode
from httpx import AsyncClient, ASGITransport


async def _captcha_answer(client):
    r = await client.get("/api/v1/auth/captcha")
    d = r.json()["data"]
    nums = re.findall(r"\d+", d["captcha_question"])
    ans = str(int(nums[0]) + int(nums[1])) if "+" in d["captcha_question"] else str(int(nums[0]) - int(nums[1]))
    return d["captcha_token"], ans


@pytest.mark.asyncio
async def test_learning_path_kg_fallback_returns_nodes():
    """When no LearningPath exists, GET /learning-path should return KG fallback with nodes."""
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Seed: register+login student
        reg_code = f"lpfb_{uuid.uuid4().hex[:8]}"
        async with async_session_factory() as db:
            db.add(RegistrationCode(code=reg_code, role="student"))
            await db.commit()

        ct_token, ct_ans = await _captcha_answer(client)
        r = await client.post("/api/v1/auth/register", json={
            "registration_code": reg_code, "email": f"lpfb_{uuid.uuid4().hex[:6]}@t.com",
            "password": "Abc12345", "username": f"lpfb_{uuid.uuid4().hex[:6]}",
            "captcha_token": ct_token, "captcha_code": ct_ans,
        })
        assert r.status_code == 201, f"Register failed: {r.json()}"
        user_id = r.json()["data"]["user_id"]

        ct_token, ct_ans = await _captcha_answer(client)
        r = await client.post("/api/v1/auth/login", json={
            "email": f"lpfb_{uuid.uuid4().hex[:6]}@t.com",
            "password": "Abc12345",
            "captcha_token": ct_token, "captcha_code": ct_ans,
        })
        headers = {"Authorization": f"Bearer {r.json()['data']['token']}"}

        # Seed: CourseCatalog + KG + CourseOffering
        catalog_id = f"cat_{uuid.uuid4().hex[:8]}"
        host_course_id = f"hcourse_{uuid.uuid4().hex[:8]}"
        course_id = f"course_{uuid.uuid4().hex[:8]}"

        async with async_session_factory() as db:
            db.add(CourseCatalog(
                id=catalog_id, title="Test Catalog",
                kg_host_course_id=host_course_id,
            ))
            db.add(CourseOffering(
                id=course_id, name="Test Class", catalog_id=catalog_id,
                teacher_id=user_id, class_code=f"CLS_{uuid.uuid4().hex[:6].upper()}",
            ))
            await db.flush()

            db.add(CourseKnowledgeGraph(
                course_id=host_course_id, version=1, is_active=True,
                source_type="catalog_chunks", generation_strategy="catalog_chunks_llm",
                nodes=[{"id": "n1", "name": "Node1", "chapter": "Ch1"},
                       {"id": "n2", "name": "Node2", "chapter": "Ch2"}],
                edges=[{"from": "n1", "to": "n2"}],
            ))
            await db.commit()

        # Test: GET /learning-path
        r = await client.get(f"/api/v1/learning-path?course_id={course_id}", headers=headers)
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["source"] == "kg_fallback"
        assert len(data["nodes"]) == 2
        assert data["nodes"][0]["id"] == "n1"
        assert data["nodes"][0]["status"] == "recommended"
        assert data["nodes"][0]["order"] == 1
        assert data["nodes"][1]["id"] == "n2"
        assert data["current_position"]["node_id"] == "n1"
        assert len(data["edges"]) == 1


@pytest.mark.asyncio
async def test_learning_path_kg_fallback_no_course_offering_returns_empty():
    """When CourseOffering doesn't exist, return empty nodes."""
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        reg_code = f"lpfb2_{uuid.uuid4().hex[:8]}"
        async with async_session_factory() as db:
            db.add(RegistrationCode(code=reg_code, role="student"))
            await db.commit()

        ct_token, ct_ans = await _captcha_answer(client)
        await client.post("/api/v1/auth/register", json={
            "registration_code": reg_code, "email": f"lpfb2_{uuid.uuid4().hex[:6]}@t.com",
            "password": "Abc12345", "username": f"lpfb2_{uuid.uuid4().hex[:6]}",
            "captcha_token": ct_token, "captcha_code": ct_ans,
        })
        ct_token, ct_ans = await _captcha_answer(client)
        r = await client.post("/api/v1/auth/login", json={
            "email": f"lpfb2_{uuid.uuid4().hex[:6]}@t.com",
            "password": "Abc12345",
            "captcha_token": ct_token, "captcha_code": ct_ans,
        })
        headers = {"Authorization": f"Bearer {r.json()['data']['token']}"}

        r = await client.get("/api/v1/learning-path?course_id=nonexistent_course", headers=headers)
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["source"] == "kg_fallback"
        assert data["nodes"] == []
        assert data["current_position"] is None
```

- [ ] **Step 2: 运行集成测试**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/backend && python -m pytest tests/test_learning_path_fallback.py -v
```

预期：8 个测试全部 PASS（6 个单元 + 2 个集成）。

- [ ] **Step 3: Commit**

```bash
git add tests/test_learning_path_fallback.py
git commit -m "test: 添加 LearningPath KG fallback 集成测试"
```

---

### Task 4: 更新进度文档

**Files:**
- Modify: `WORKFLOW.md`

- [ ] **Step 1: 在 WORKFLOW.md 末尾追加施工记录**

```markdown
## 2026-06-12 LearningPath KG Fallback

- **问题**: learning_paths 表为空，LearningPath 页面始终空白
- **方案**: GET /learning-path 无 LP 记录时，从 active KG 拓扑排序合成路径骨架
- **改动**:
  - `backend/app/api/v1/learning_path.py`: 新增 `_topo_sort_kg_nodes()` + `_synthesize_kg_fallback_path()`，修改 `get_learning_path()` 空 LP 分支
  - `tests/test_learning_path_fallback.py`: 6 单元测试 + 2 集成测试
- **验证**: 单元测试全部通过，集成测试覆盖有 KG / 无 Offering 场景
- **前端**: 零改动
```

- [ ] **Step 2: Commit**

```bash
git add WORKFLOW.md
git commit -m "docs: 记录 LearningPath KG fallback 施工"
```
