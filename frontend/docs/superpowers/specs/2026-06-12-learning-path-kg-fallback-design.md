# LearningPath KG Fallback Design

## 问题

`learning_paths` 表自建表以来 0 行数据，`GET /learning-path?course_id=x` 永远返回 `{nodes:[], edges:[], current_position:null}`，导致 LearningPath 页面始终空白。

## 根因

个性化路径生成依赖 Agent `/learning-path/generate`，前置条件（evaluation + profile + agent 调通）未满足，始终未触发。

## 方案

**KG 骨架 fallback + 全 recommended 初始态。** 有真实 LP 返回真实路径，无 LP 时用 active KG 合成路径，染色逻辑后置。

---

## 改动范围

- **单文件**：`backend/app/api/v1/learning_path.py`
- **函数**：`get_learning_path()` + 新增 `_synthesize_kg_fallback_path()`
- **前端不动**

---

## 逻辑

```
GET /api/v1/learning-path?course_id=x
  │
  ├── 查 LearningPath (user_id + course_id)
  │     ├── 有 → 原样返回 (不变)
  │     └── 无 → 进入 fallback
  │
  └── Fallback (_synthesize_kg_fallback_path):
        1. 查 CourseOffering (id=course_id) → catalog_id
        2. 查 CourseCatalog (id=catalog_id) → kg_host_course_id
        3. 查 active KG (course_knowledge_graphs WHERE course_id=kg_host_course_id AND is_active=1 AND is_deleted=0)
        4. 拓扑排序 KG nodes（按 edges，Kahn 算法）
        5. 组装响应
```

---

## 拓扑排序规则

- 算法：Kahn（基于入度）
- 入度为 0 的节点优先输出
- 同层多节点按 KG 数组原始顺序
- 如果 KG 没有 edges，直接按原始数组顺序
- 如果 KG 不存在，返回空数组（行为与现在一致）

---

## 节点字段

| 字段 | 来源 | 值 |
|------|------|----|
| `id` | KG node.id | 字符串 |
| `name` | KG node.name | 字符串 |
| `chapter` | KG node.chapter | 字符串 |
| `order` | 拓扑序 | 从 1 开始递增 |
| `status` | 固定 | `"recommended"` |
| `mastery` | 固定 | `0` |

---

## 响应格式

有 LP 记录时（不变）：

```json
{
  "code": 200,
  "data": {
    "course_id": "xxx",
    "nodes": [...],
    "edges": [...],
    "current_position": {"node_id": "...", "node_name": "..."},
    "source": "learning_path",
    "generated_at": "2026-06-12T12:54:23"
  }
}
```

无 LP 记录时（新增 fallback）：

```json
{
  "code": 200,
  "data": {
    "course_id": "xxx",
    "nodes": [
      {"id": "basic_types", "name": "基本数据类型", "chapter": "第2章 数据类型、运算符与表达式", "order": 1, "status": "recommended", "mastery": 0}
    ],
    "edges": [
      {"from": "basic_types", "to": "constants"}
    ],
    "current_position": {"node_id": "basic_types", "node_name": "基本数据类型"},
    "source": "kg_fallback",
    "generated_at": "2026-06-12T12:54:23"
  }
}
```

关键字段：

- `source`：`"learning_path"` 或 `"kg_fallback"`，区分真路径 vs 合成路径
- `generated_at`：KG 的 `create_time`，不返回 null
- `current_position`：拓扑序第一个节点（仅 fallback 时）

---

## 待定（后置）

- **mastery 染色**：等 `evaluations.mastery_table` 结构稳定为 `{node_id: score}` 后，在 fallback 分支里补一层状态映射
- **complete_threshold**：默认 70，届时再定
- **pending 状态**：留给未来真正的路径编排策略

---

## 错误处理

| 场景 | 行为 |
|------|------|
| CourseOffering 不存在 | 返回空 `{nodes:[], edges:[]}` |
| CourseCatalog 不存在 | 返回空 |
| kg_host_course_id 为空 | 返回空 |
| active KG 不存在 | 返回空 |
| KG nodes 为空 | 返回空 |
| KG edges 为空 | 按原始数组顺序赋 order |

---

## 前端影响

零改动。`src/pages/LearningPath.jsx` 现有逻辑：

- 优先选 `current_position.node_id`
- 其次选 `in_progress`
- 再选 `recommended`

全 recommended + 第一个节点高亮，页面行为完全通。
