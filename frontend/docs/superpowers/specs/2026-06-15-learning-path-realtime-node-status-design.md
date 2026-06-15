# 学习路径节点状态实时计算设计

**日期**：2026-06-15  
**状态**：已审核（v2，修订自代码审查意见）  
**范围**：Backend `GET /learning-path` 实时叠加节点状态

---

## 问题背景

当前 `GET /learning-path` 返回的节点状态全部为 `pending`，原因：

1. **历史快照路径**：有 LearningPath 记录时直接返回快照，节点 `status` 由上次 Agent 生成时写入，不随后续行为更新。
2. **kg_fallback 路径**：无快照时从 KG 合成，全部节点硬编码 `status="recommended"`，不反映任何行为。
3. **手动刷新入口已移除**：`/learning-path/refresh` 路由不再被前端使用，用户无法触发 Agent 重规划。

结果：无论学生做了多少题、浏览了多少资源，节点状态始终不变，学习进度无法在闯关节点规划中体现。

---

## 设计目标

每次前端打开 `/learning-path` 页面时，节点状态实时反映做题正确率（QuizAnswer）和学习活动记录（LearningActivity），同时保留 Agent 快照中的个性化字段（reason、order、edges、current_position）。

---

## 核心策略：实时状态叠加快照（Merge）

不绕过快照，而是以快照为基础，用实时计算结果覆盖 `status` 和 `mastery` 两个字段，其余字段从快照继承。

---

## 数据流架构

```
GET /learning-path?course_id=xxx
  ↓
1. build_node_progress_rows(user_id, course_id, db)
   → 得到 progress_by_id: {node_id: {assessment_state, mastery_score}}
   
2. 查询 LearningPath 快照（现有逻辑）

   [快照存在] → Merge 模式
     遍历快照 nodes：
       - status  = _map_assessment_to_status(progress_by_id[node.id].assessment_state)
                   若 node_id 在 progress_by_id 中，否则保留快照原值
       - mastery = progress_by_id[node.id].mastery_score（同上，否则保留原值）
       - reason, order, edges, current_position 全部保留快照原值
     source = "realtime_merged"

   [快照不存在，KG 存在] → KG 构建模式（现有 _synthesize_kg_fallback_path 逻辑）
     - 节点 status 来自实时映射（替换原来的全部 "recommended"）
     - current_position 取第一个非 pending 节点
     - source = "kg_realtime"

   [快照不存在，KG 不存在] → 返回空节点列表（不变）
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

`mastery_score`（0-100）映射到前端 `mastery` 字段（进度条）。

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

```
原流程：
  有快照 → 直接返回快照
  无快照 → KG fallback（全部 recommended）

新流程：
  Step 1. 调用 build_node_progress_rows → progress_by_id
  Step 2. 有快照 → Merge：覆盖 status/mastery，保留其余字段
  Step 3. 无快照，KG 存在 → KG 构建 + 实时状态映射
  Step 4. 均无 → 返回空
```

### 字段对齐

`build_node_progress_rows` 返回的行以 `node_id` 为 key 索引，快照 `nodes` 中每个节点有 `id` 字段，两者通过 `id == node_id` 对齐。未命中（节点在快照中存在但无做题记录）时保留快照原值。

### 返回格式不变

响应结构（nodes/edges/current_position/source）不变，前端 `LearningPath.jsx` 零修改。

---

## 不修改的内容

- `GET /learning-path` 的响应结构
- `/learning-path/refresh` endpoint（保留，暂不使用）
- Agent 学习路径生成逻辑（`agent_service/agents/learning_path.py`）
- 前端 `LearningPath.jsx`

---

## 风险与约束

| 风险 | 处置 |
|---|---|
| `build_node_progress_rows` 每次 GET 同步查多张表 | 当前用户规模可接受；后续可加 Redis TTL=30s 缓存，但不在本次范围 |
| KG 节点 id 与快照 node.id 不对齐 | 未命中时保留快照原 status，降级行为与现状一致 |
| KG 节点名与 QuizQuestion.knowledge_point 不匹配 | 不匹配节点 assessment_state 为 `unstarted`，显示 `pending`，与现状一致 |
| 未来重开 Agent 刷新入口 | Merge 模式天然兼容：新快照写入后，下次 GET 自动以新快照为基础叠加实时状态 |

---

## v1 → v2 变更说明

v1 设计在 KG 存在时完全绕过快照，导致：

1. Agent 生成的 `reason`、`order` 丢失
2. `current_position` 和 `edges` 未处理
3. 快照永久失效（未来 Agent 刷新失去意义）

v2 改为 Merge 策略，只覆盖 `status` 和 `mastery` 两个字段，其余从快照继承，上述问题全部消除。
