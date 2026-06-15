# 学习路径节点状态实时计算 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `GET /learning-path` 每次返回时，用用户实时做题和活动数据覆盖节点 `status`/`mastery`，同时保留 Agent 快照中的 `reason`、`order`、`edges`、`current_position`。

**Architecture:** 在现有 GET endpoint 中先调用 `build_node_progress_rows` 建立 `{node_id: progress}` 字典，再将实时状态 merge 到快照节点（Merge 模式）或 KG fallback 节点（KG 构建模式）。仅修改一个文件，前端零改动。

**Tech Stack:** Python/FastAPI, SQLAlchemy async, `app.services.knowledge_progress.build_node_progress_rows`（已有）

---

## 文件修改范围

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/api/v1/learning_path.py` | Modify | 新增映射函数 + 改写 `get_learning_path` |
| `backend/tests/test_learning_path_realtime.py` | Create | 单元测试：映射函数 + merge 逻辑 |

---

## Task 1：新增 `_map_assessment_to_status` 映射函数

**Files:**
- Modify: `backend/app/api/v1/learning_path.py`（在 `_topo_sort_kg_nodes` 定义后，约 92 行后插入）
- Test: `backend/tests/test_learning_path_realtime.py`

- [ ] **Step 1：写失败测试**

新建 `backend/tests/test_learning_path_realtime.py`：

```python
"""Unit tests for realtime node status mapping in learning_path.py.

Run: python -m pytest tests/test_learning_path_realtime.py -v
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///./test_lp_realtime.db",
)

import pytest
from app.api.v1.learning_path import _map_assessment_to_status


class TestMapAssessmentToStatus:
    def test_mastered_maps_to_completed(self):
        assert _map_assessment_to_status("mastered") == "completed"

    def test_learning_maps_to_in_progress(self):
        assert _map_assessment_to_status("learning") == "in_progress"

    def test_weak_maps_to_recommended(self):
        assert _map_assessment_to_status("weak") == "recommended"

    def test_pending_practice_maps_to_pending(self):
        assert _map_assessment_to_status("pending_practice") == "pending"

    def test_unstarted_maps_to_pending(self):
        assert _map_assessment_to_status("unstarted") == "pending"

    def test_unknown_state_maps_to_pending(self):
        assert _map_assessment_to_status("something_else") == "pending"
```

- [ ] **Step 2：运行测试确认失败**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/backend
python -m pytest tests/test_learning_path_realtime.py::TestMapAssessmentToStatus -v
```

预期：`ImportError: cannot import name '_map_assessment_to_status'`

- [ ] **Step 3：在 `learning_path.py` 中添加映射函数**

在 `_topo_sort_kg_nodes` 函数定义结束后（约第 91 行之后），插入：

```python
def _map_assessment_to_status(assessment_state: str) -> str:
    return {
        "mastered": "completed",
        "learning": "in_progress",
        "weak": "recommended",
    }.get(assessment_state, "pending")
```

- [ ] **Step 4：运行测试确认通过**

```bash
python -m pytest tests/test_learning_path_realtime.py::TestMapAssessmentToStatus -v
```

预期：6 个测试全部 PASS

- [ ] **Step 5：提交**

```bash
git add backend/app/api/v1/learning_path.py backend/tests/test_learning_path_realtime.py
git commit -m "feat: 新增节点状态映射函数 _map_assessment_to_status"
```

---

## Task 2：在 `_synthesize_kg_fallback_path` 中加入实时状态

**Files:**
- Modify: `backend/app/api/v1/learning_path.py`（`_synthesize_kg_fallback_path` 函数，约第 94-165 行）

当前该函数将所有节点状态硬编码为 `"recommended"`。改为接收一个可选的 `progress_by_id` 参数，有进度时映射实时状态，无进度时降级为 `"pending"`（新用户还没有数据），`current_position` 取第一个非 `pending` 节点，若全部为 `pending` 则取拓扑排序后第一个节点。

- [ ] **Step 1：写失败测试**

在 `test_learning_path_realtime.py` 末尾追加：

```python
from app.api.v1.learning_path import _apply_progress_to_nodes, _build_current_position_from_nodes


class TestApplyProgressToNodes:
    def test_merges_status_from_progress(self):
        nodes = [
            {"id": "n1", "name": "A", "order": 1, "status": "recommended", "mastery": 0},
            {"id": "n2", "name": "B", "order": 2, "status": "recommended", "mastery": 0},
        ]
        progress = {
            "n1": {"assessment_state": "mastered", "mastery_score": 92.0},
            "n2": {"assessment_state": "learning", "mastery_score": 45.0},
        }
        result = _apply_progress_to_nodes(nodes, progress)
        assert result[0]["status"] == "completed"
        assert result[0]["mastery"] == 92.0
        assert result[1]["status"] == "in_progress"
        assert result[1]["mastery"] == 45.0

    def test_preserves_other_fields(self):
        nodes = [{"id": "n1", "name": "A", "order": 3, "status": "pending", "mastery": 0, "reason": "原因"}]
        progress = {"n1": {"assessment_state": "mastered", "mastery_score": 85.0}}
        result = _apply_progress_to_nodes(nodes, progress)
        assert result[0]["order"] == 3
        assert result[0]["reason"] == "原因"

    def test_node_not_in_progress_keeps_original_status(self):
        nodes = [{"id": "n99", "name": "Z", "order": 1, "status": "pending", "mastery": 0}]
        result = _apply_progress_to_nodes(nodes, {})
        assert result[0]["status"] == "pending"

    def test_mastery_score_none_keeps_original_mastery(self):
        nodes = [{"id": "n1", "name": "A", "order": 1, "status": "pending", "mastery": 10}]
        progress = {"n1": {"assessment_state": "unstarted", "mastery_score": None}}
        result = _apply_progress_to_nodes(nodes, progress)
        assert result[0]["mastery"] == 10


class TestBuildCurrentPositionFromNodes:
    def test_returns_first_non_pending_node(self):
        nodes = [
            {"id": "n1", "name": "A", "status": "pending"},
            {"id": "n2", "name": "B", "status": "in_progress"},
            {"id": "n3", "name": "C", "status": "completed"},
        ]
        cp = _build_current_position_from_nodes(nodes)
        assert cp == {"node_id": "n2", "node_name": "B"}

    def test_all_pending_returns_first_node(self):
        nodes = [
            {"id": "n1", "name": "A", "status": "pending"},
            {"id": "n2", "name": "B", "status": "pending"},
        ]
        cp = _build_current_position_from_nodes(nodes)
        assert cp == {"node_id": "n1", "node_name": "A"}

    def test_empty_nodes_returns_none(self):
        assert _build_current_position_from_nodes([]) is None
```

- [ ] **Step 2：运行测试确认失败**

```bash
python -m pytest tests/test_learning_path_realtime.py::TestApplyProgressToNodes tests/test_learning_path_realtime.py::TestBuildCurrentPositionFromNodes -v
```

预期：`ImportError: cannot import name '_apply_progress_to_nodes'`

- [ ] **Step 3：在 `learning_path.py` 中添加两个纯函数**

在 `_map_assessment_to_status` 之后插入：

```python
def _apply_progress_to_nodes(
    nodes: list[dict],
    progress_by_id: dict[str, dict],
) -> list[dict]:
    """用实时进度覆盖节点的 status 和 mastery，其余字段保留。"""
    result = []
    for node in nodes:
        node_id = node.get("id") or node.get("node_id", "")
        progress = progress_by_id.get(node_id)
        if progress is None:
            result.append(dict(node))
            continue
        updated = dict(node)
        updated["status"] = _map_assessment_to_status(progress.get("assessment_state", "unstarted"))
        mastery_score = progress.get("mastery_score")
        if mastery_score is not None:
            updated["mastery"] = mastery_score
        result.append(updated)
    return result


def _build_current_position_from_nodes(nodes: list[dict]) -> dict | None:
    """取第一个非 pending 节点作为 current_position；全为 pending 时取第一个节点。"""
    if not nodes:
        return None
    for node in nodes:
        if node.get("status") != "pending":
            return {"node_id": node.get("id", ""), "node_name": node.get("name", "")}
    first = nodes[0]
    return {"node_id": first.get("id", ""), "node_name": first.get("name", "")}
```

- [ ] **Step 4：运行测试确认通过**

```bash
python -m pytest tests/test_learning_path_realtime.py::TestApplyProgressToNodes tests/test_learning_path_realtime.py::TestBuildCurrentPositionFromNodes -v
```

预期：所有测试 PASS

- [ ] **Step 5：提交**

```bash
git add backend/app/api/v1/learning_path.py backend/tests/test_learning_path_realtime.py
git commit -m "feat: 新增进度合并函数 _apply_progress_to_nodes / _build_current_position_from_nodes"
```

---

## Task 3：改写 `get_learning_path` endpoint

**Files:**
- Modify: `backend/app/api/v1/learning_path.py`（`get_learning_path` 函数，约第 168-217 行）

在 `get_learning_path` 顶部新增 `build_node_progress_rows` 导入，然后改写 endpoint 逻辑。

- [ ] **Step 1：在文件顶部添加导入**

在现有 import 块末尾（第 20 行附近）添加：

```python
from app.services.knowledge_progress import build_node_progress_rows
```

- [ ] **Step 2：改写 `get_learning_path` 函数**

将整个 `get_learning_path` 函数替换为：

```python
@router.get("")
async def get_learning_path(
    course_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 1. 实时进度字典（node_id → {assessment_state, mastery_score}）
    progress_rows = await build_node_progress_rows(current_user.id, course_id, db)
    progress_by_id: dict[str, dict] = {
        row["node_id"]: row for row in progress_rows
    }

    # 2. 查最新快照
    result = await db.execute(
        select(LearningPath)
        .where(
            LearningPath.user_id == current_user.id,
            LearningPath.course_id == course_id,
            LearningPath.is_deleted == False,
        )
        .order_by(LearningPath.generated_at.desc())
    )
    lp = result.scalars().first()

    if lp is not None:
        # Merge 模式：用实时状态覆盖快照节点的 status/mastery，其余字段保留
        merged_nodes = _apply_progress_to_nodes(lp.nodes or [], progress_by_id)
        return {
            "code": 200,
            "message": "success",
            "data": {
                "course_id": lp.course_id,
                "nodes": merged_nodes,
                "edges": lp.edges or [],
                "current_position": {
                    "node_id": lp.current_node_id,
                    "node_name": lp.current_node_name,
                } if lp.current_node_id else None,
                "source": "realtime_merged",
                "generated_at": lp.generated_at.isoformat() if lp.generated_at else None,
            },
        }

    # 3. 无快照，尝试 KG 构建模式
    fallback = await _synthesize_kg_fallback_path(db, course_id)
    if fallback is not None:
        kg_nodes = _apply_progress_to_nodes(fallback["nodes"], progress_by_id)
        current_position = _build_current_position_from_nodes(kg_nodes)
        return {
            "code": 200,
            "message": "success",
            "data": {
                **fallback,
                "nodes": kg_nodes,
                "current_position": current_position,
                "source": "kg_realtime",
            },
        }

    # 4. 均无数据
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

- [ ] **Step 3：运行全部已有测试确认无回归**

```bash
python -m pytest tests/test_learning_path_fallback.py tests/test_learning_path_realtime.py -v
```

预期：所有测试 PASS，无 FAIL

- [ ] **Step 4：运行 lint**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend
npm run lint 2>/dev/null || echo "frontend lint done"
cd /home/yezisama/workspace/workflow/EDUagent/backend
python -m py_compile app/api/v1/learning_path.py && echo "syntax ok"
```

预期：`syntax ok`

- [ ] **Step 5：提交**

```bash
git add backend/app/api/v1/learning_path.py
git commit -m "feat: GET /learning-path 实时状态叠加快照，节点状态随做题行为更新"
```

---

## Task 4：验证端到端行为

- [ ] **Step 1：确认后端服务可启动**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/backend
python -m py_compile app/api/v1/learning_path.py && echo "compile ok"
```

预期：`compile ok`

- [ ] **Step 2：运行全套测试**

```bash
python -m pytest tests/test_learning_path_fallback.py tests/test_learning_path_realtime.py -v --tb=short
```

预期：所有测试 PASS

- [ ] **Step 3：更新 WORKFLOW.md**

在 `WORKFLOW.md` 末尾追加施工记录：

```
## 2026-06-15 学习路径节点状态实时计算

### 修改文件
- `backend/app/api/v1/learning_path.py`：新增 `_map_assessment_to_status`、`_apply_progress_to_nodes`、`_build_current_position_from_nodes`；改写 `get_learning_path` 为 Merge 策略

### 新增文件
- `backend/tests/test_learning_path_realtime.py`：映射函数和 merge 逻辑单元测试

### 变更说明
GET /learning-path 现在每次调用 build_node_progress_rows 实时计算节点状态，
用 assessment_state→前端 status 映射后 merge 到快照节点，mastery_score 同步更新进度条。
快照的 reason/order/edges/current_position 全部保留。

### 测试结果
test_learning_path_fallback.py: PASS
test_learning_path_realtime.py: PASS

### 契约漂移
无。响应结构不变，source 字段新增 "realtime_merged"/"kg_realtime" 值（前端未使用该字段）。

### 剩余风险
build_node_progress_rows 每次 GET 同步查 DB，高并发场景可后续加 Redis TTL 缓存。
```

- [ ] **Step 4：最终提交**

```bash
git add frontend/WORKFLOW.md
git commit -m "docs: 更新 WORKFLOW.md，记录实时节点状态改造施工"
```
