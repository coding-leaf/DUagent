# 学习路径节点状态实时计算设计

**日期**：2026-06-15  
**状态**：已审核  
**范围**：Backend `GET /learning-path` 实时返回节点状态

---

## 问题背景

当前 `GET /learning-path` 返回的节点状态全部为 `pending`，原因：

1. **历史快照路径**：有 LearningPath 记录时直接返回快照，节点 `status` 由上次 Agent 生成时写入，不随后续行为更新。
2. **kg_fallback 路径**：无快照时从 KG 合成，全部节点硬编码 `status="recommended"`，不反映任何行为。
3. **手动刷新入口已移除**：`/learning-path/refresh` 路由不再被前端使用，用户无法触发 Agent 重规划。

结果：无论学生做了多少题、浏览了多少资源，节点状态始终不变，学习进度无法在闯关节点规划中体现。

---

## 设计目标

每次前端打开 `/learning-path` 页面时，节点状态实时反映：

- 做题正确率（QuizAnswer）
- 学习活动记录（LearningActivity）

不依赖 Agent，不需要手动刷新。

---

## 数据流架构

```
前端 GET /learning-path?course_id=xxx
  ↓
Backend GET /api/v1/learning-path
  ├─ 1. 解析 KG（CourseOffering → CourseCatalog → kg_host_course_id → active KG）
  ├─ 2. KG 存在 → 进入实时计算路径
  │       a. build_node_progress_rows(user_id, course_id, db)
  │          ↳ 查 QuizAnswer + QuizSession → 计算各节点正确率
  │          ↳ 查 LearningActivity → 计算学习时长和活动次数
  │          ↳ evaluate_mastery_state() → assessment_state
  │       b. _map_assessment_to_status(assessment_state) → 前端 status
  │       c. 拓扑排序节点（复用 _topo_sort_kg_nodes）
  │       d. 组装 nodes 列表，返回 source="realtime"
  │
  ├─ 3. KG 不存在，有历史快照 → 返回快照（source="snapshot"，兜底）
  └─ 4. KG 不存在，无快照 → 返回空节点列表
```

---

## 状态映射规则

| `assessment_state`（内部） | 前端 `status` | 语义 |
|---|---|---|
| `mastered` | `completed` | 正确率 ≥80% 且答题次数充足 |
| `learning` | `in_progress` | 有答题/活动但未达掌握门槛 |
| `weak` | `recommended` | 正确率低，需优先复习 |
| `pending_practice` | `pending` | 有题目但从未做 |
| `unstarted` | `pending` | 无任何记录 |

`mastery_score`（0-100）直接映射到前端 `mastery` 字段（进度条）。

---

## 修改范围

**仅修改一个文件**：`backend/app/api/v1/learning_path.py`

### 新增导入

```python
from app.services.knowledge_progress import build_node_progress_rows
```

### 新增映射函数

```python
def _map_assessment_to_status(assessment_state: str) -> str:
    return {
        "mastered": "completed",
        "learning": "in_progress",
        "weak": "recommended",
    }.get(assessment_state, "pending")
```

### GET endpoint 改写逻辑

1. 先解析 KG（现有逻辑已有，从 `_synthesize_kg_fallback_path` 拆出复用）
2. KG 存在时，调用 `build_node_progress_rows` 获取进度，映射状态，拓扑排序后返回
3. KG 不存在时，查历史快照返回（现有兜底逻辑不变）

### 返回格式不变

前端 `LearningPath.jsx` 已正确处理四种状态，`node.mastery` 字段名保持一致，**前端零修改**。

---

## 不修改的内容

- `GET /learning-path` 的响应结构不变
- `/learning-path/refresh` endpoint 保留但前端不调用（暂留空）
- Agent 学习路径生成逻辑不改（`agent_service/agents/learning_path.py`）
- 前端 `LearningPath.jsx` 零修改

---

## 风险与约束

| 风险 | 处置 |
|---|---|
| `build_node_progress_rows` 每次 GET 都查 DB | 查询已有索引（course_id, user_id），正常用户节点数 <50，可接受 |
| KG 节点名与 QuizQuestion.knowledge_point 不匹配 | 现有逻辑按名称精确匹配，不匹配的节点 assessment_state 为 `unstarted`，显示 `pending`，与现状一致 |
| 历史快照数据被绕过 | KG 存在时优先实时计算，KG 不存在时用快照兜底，不丢失历史数据 |
