# LearningPath 节点资源接入设计

> 在 LearningPath 页面点击节点后，底部展示该节点关联的资源入口，打通"学习路径 → 资源"链路。

**日期：** 2026-06-06
**状态：** 设计稿
**依据：** `docs/superpowers/specs/2026-06-05-phase2-student-data-contract-review.md` §6 OpenAPI 更新候选

---

## 1. 目标

让学生从学习路径节点页面直接查看和进入该节点的关联学习资源，将 LearningPath 底部的 3 张静态占位卡片替换为基于 Backend API 的真实节点资源面板。

## 2. 范围与非目标

### 在范围

- Backend：`weak_point_tutorials[]` 增加 `id`，`content` 截断为摘要
- Backend：`chapter_materials[]` 增加 `id`
- OpenAPI：`NodeResources` schema 更新 `id` 字段和 `content` 说明
- Frontend：`learningService.getNodeResources(nodeId, courseId)`
- Frontend：LearningPath.jsx 底部静态占位卡 → 真实节点资源面板
- 所有有 `id` 的节点均可点击查看资源
- 资源卡片有 `id` 时跳转 `/resource/:id`

### 非目标

- 不新增后端数据表或 Agent 调用
- 不修改 LearningPath 横向时间线结构
- 不在节点资源接口返回完整正文（正文由 `GET /resources/{id}` 负责）
- 不实现行为采集/阅读进度/阅读时长
- 不新增单独的练习详情页

## 3. 契约定义

### 3.1 端点

```
GET /api/v1/learning-path/nodes/{node_id}/resources?course_id={course_id}
```

已存在，本轮仅调整响应字段。

### 3.2 Schema 更新：NodeResources

当前 schema 见 `Client-API.openapi.json` components/schemas/NodeResources。本轮变更：

| 组件 | 变更 | 说明 |
|------|------|------|
| `weak_point_tutorials[].id` | 新增 `string` | 资源 ID，用于跳转 `/resource/:id` |
| `weak_point_tutorials[].content` | 语义收紧 | 标注为"摘要/预览，非完整正文"，Backend 截断为前 160 字符 |
| `chapter_materials[].id` | 新增 `string` | 资源 ID，用于跳转 `/resource/:id` |

其他字段（`exercises`、`full_exercise_set`）保持不变。

### 3.3 响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "node_id": "node_001",
    "node_name": "AVL树旋转",
    "weak_point_tutorials": [
      {
        "id": "res_001",
        "title": "AVL树旋转详解",
        "content": "AVL树（Adelson-Velsky and Landis Tree）是一种自平衡二叉搜索树..."
      }
    ],
    "exercises": [
      { "id": "q_001", "type": "single_choice", "content": "AVL树的平衡因子取值范围是？" }
    ],
    "chapter_materials": [
      { "id": "res_002", "title": "树结构补充阅读", "type": "reading", "url": "" }
    ],
    "full_exercise_set": [
      { "id": "q_003", "type": "multi_choice", "content": "以下哪些是自平衡树？" }
    ]
  }
}
```

### 3.4 错误语义

| 状态码 | 场景 | 前端处理 |
|--------|------|---------|
| `200` | 成功（含空数组） | 渲染资源面板，空数组展示"该节点暂无推荐资源" |
| `401` | 未登录 | 跳转登录页 |
| `403` | 未加入该课程 | 展示"无权访问" |

## 4. Backend 实现说明

`backend/app/api/v1/learning_path.py` — `get_node_resources` 函数（第 305-448 行）：

**weak_point_tutorials（第 370-383 行）：**
```python
weak_point_tutorials.append({
    "id": r.id,                              # 新增
    "title": r.title,
    "content": (r.content or "")[:160],      # 截断为摘要
})
```

**chapter_materials（第 403-418 行）：**
```python
chapter_materials.append({
    "id": r.id,                              # 新增
    "title": r.title,
    "type": r.type,
    "url": r.url or "",
})
```

其他逻辑（课程权限校验、节点名称解析、知识点/章节匹配）不变。

## 5. 前端改动

### 5.1 learningService

`src/api/services/learning.js` 新增方法：

```javascript
getNodeResources(nodeId, courseId) {
  return apiClient.get(`/learning-path/nodes/${nodeId}/resources`, {
    params: { course_id: courseId }
  });
}
```

### 5.2 LearningPath.jsx

**状态管理：**
- 新增 `selectedNodeId` state
- 新增 `nodeResources` state
- 新增 `resourcesLoading` state

**默认选中节点（优先从可点击节点中选择）：**
1. `learningPath.current_position.node_id`
2. 第一个 `status === 'in_progress'` 的节点
3. 第一个 `status === 'recommended'` 的节点
4. 第一个节点（`nodes[0]`，仅当非 `pending` 时）

**节点点击：**
- `completed`、`in_progress`、`recommended` 节点可点击
- `pending` 节点不可点击（保持现有锁样式）
- 点击后 `setSelectedNodeId(node.id)`，触发 `fetchNodeResources`
- 当前选中节点高亮（如边框色变化）

**底部面板（替换原 3 张静态占位卡）：**

展示 4 个 section：

1. **薄弱点讲解**（`weak_point_tutorials`）
   - 资源卡片：标题 + 摘要（`content` 前 80 字符）
   - 有 `id` → `Link to /resource/:id`
   - 空态："该节点暂无薄弱点讲解"

2. **节点练习**（`exercises`）
   - 题目摘要卡片：类型图标 + `content` 摘要
   - 暂不跳详情，展示"进入练习"按钮 → `/quiz`
   - 空态："该节点暂无练习"

3. **章节资料**（`chapter_materials`）
   - 资源卡片：类型图标 + 标题
   - 有 `id` → `Link to /resource/:id`
   - 空态："该节点暂无章节资料"

4. **全部练习集**（`full_exercise_set`）
   - 默认折叠，首屏只显示数量（如"共 12 题"）+ "展开"按钮
   - 展开后最多展示前 10 条，每项展示类型 + 摘要
   - 超过 10 条时底部显示"查看更多请进入练习"
   - 本轮不做分页
   - 空态：不展示此 section

**删除：**
- 原底部 3 张静态占位卡片（知识导图推荐、课件讲义推荐、混合练习集推荐）
- `completed` 节点卡片内资源/习题占位文案（"知识点推荐将在..."、"配套习题将在..."）
- `in_progress` 节点卡片内资源/习题占位文案（"配套习题将在节点资源接入后展示"）

**保留：**
- `in_progress` 节点卡片内的 Agent 提示文案（"智能体提示将在路径 Agent 输出接入后展示"）——本轮只消费已落库资源，Agent 提示不在本轮范围

### 5.3 节点卡片微调

- `completed` 和 `in_progress` 节点卡片内删除资源/习题相关静态占位文案
- `locked` 节点保持现有样式（不可点击）

## 6. 验证

- `npm run lint` / `npm run build` 通过
- Backend pytest：确认 `weak_point_tutorials[]` 含 `id`，`content` 截断为 160 字符
- Backend pytest：确认 `chapter_materials[]` 含 `id`
- 手工：LearningPath 页面默认选中当前节点，底部展示真实资源
- 手工：点击不同节点，资源面板切换
- 手工：有 id 的资源可跳转 `/resource/:id`

## 7. 非目标确认

以下不在本轮范围：
- 新增数据表或 SQL 迁移
- Agent 调用
- 阅读进度/阅读时长采集
- 节点详情独立页
- 练习单题详情页
- `full_exercise_set` 分页

## 自审

- 无占位符 ✅
- 边界清楚：NodeResources 提供入口，ResourceDetail 提供正文 ✅
- `content` 截断在 Backend 侧完成（前 160 字符），不需要前端额外处理 ✅
- 所有节点可点击，默认选中逻辑明确 ✅
- full_exercise_set 默认折叠 ✅
