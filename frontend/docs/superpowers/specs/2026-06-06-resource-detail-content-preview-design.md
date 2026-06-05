# ResourceDetail 资源详情正文预览契约设计

> 新增 `GET /api/v1/resources/{id}` 端点，补充 `content_preview` 字段，替换 ResourceDetail.jsx 的静态正文展示。

**日期：** 2026-06-06
**状态：** 设计稿
**依据：** `docs/superpowers/specs/2026-06-05-phase2-student-data-contract-review.md` §6 OpenAPI 更新候选

---

## 1. 目标

为 ResourceDetail 页面提供真实正文预览数据来源，使当前纯静态页面可接入正式 API。

## 2. 范围与非目标

### 在范围

- Client API 新增 `GET /api/v1/resources/{id}` 端点
- 新增 `ResourceDetailItem` schema（`ResourceItem` + `content_preview`）
- Backend 实现路由，从已有 `Resource.content` 或其他来源提供 `content_preview`
- 前端 `learningService` 新增 `getResourceDetail(id)`
- ResourceDetail.jsx 替换静态正文为 `content_preview`，删除静态阅读进度（65%）和阅读时长（12m）

### 非目标

- 阅读进度采集和展示（P2 待定）
- 阅读时长统计（P2 待定）
- 文件解析/对象存储集成（Backend 实现细节，不写入契约）
- Agent 文本生成
- 分页/全文加载
- `code` 类型正文预览

## 3. 契约定义

### 3.1 端点

```
GET /api/v1/resources/{id}
```

OpenAPI paths 声明为 `/resources/{id}`。

### 3.2 Schema：ResourceDetailItem

`ResourceDetailItem` = `ResourceItem` 全部现有字段 + `content_preview`

现有字段（来自 ResourceItem）：`id`、`title`、`type`、`description`、`tags`、`chapter`、`knowledge_point`、`view_count`、`created_at`

| 新增字段 | 类型 | 说明 |
|----------|------|------|
| `content_preview` | `string \| null` | 文字资源正文预览，通常为正文前若干字符或段落。由 Backend 提供，具体来源（SQL 列/文件解析/对象存储缓存）是 Backend 实现细节，不写入 Client API 契约 |

**适用类型：** `document`、`reading`（按现有 ResourceItem.type 枚举：`document` / `mindmap` / `reading` / `code` / `video`）。其他类型返回 `null`。`code` 本轮不纳入。

### 3.3 响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": "res_001",
    "title": "AVL树旋转详解",
    "type": "reading",
    "description": "AVL树的四种旋转操作图文说明",
    "tags": ["树结构", "平衡二叉树"],
    "chapter": "树结构",
    "knowledge_point": "AVL树",
    "view_count": 128,
    "created_at": "2026-06-05T10:30:00",
    "content_preview": "AVL树（Adelson-Velsky and Landis Tree）是一种自平衡二叉搜索树。在AVL树中，任意节点的左右子树高度差不超过1..."
  }
}
```

### 3.4 错误语义

| 状态码 | 场景 | 前端处理 |
|--------|------|---------|
| `200` | 成功 | 渲染详情 |
| `401` | 未登录 | 跳转登录页 |
| `403` | 无课程访问权限 | 展示"无权访问此资源" |
| `404` | 资源不存在或已删除 | 展示"资源不存在" |

## 4. Backend 实现说明

- 新增 `GET /resources/{id}` 路由在 `resources.py`
- 从已有 `Resource.content`（Text, nullable）取内容，截取前若干字符（建议 ~500 字符）作为 `content_preview`
- 按 `type` 判断：`document`、`reading` → 返回 `content_preview`；其他 → `null`
- 不需要 DDL 变更（`content` 列已存在）

## 5. 前端改动

### 5.1 learningService

`src/api/services/learning.js` 新增方法：

```javascript
getResourceDetail(id) {
  return apiClient.get(`/resources/${id}`);
}
```

### 5.2 ResourceDetail.jsx

- 从路由参数 `useParams()` 获取 `id`
- `useEffect` 挂载时调用 `learningService.getResourceDetail(id)`
- 用返回的 `data.content_preview` 替换当前静态正文
- 删除静态阅读进度卡片（65%、3.2k/4.8k）
- 删除静态当前阅读时长（12m）
- `content_preview` 非空 → 渲染正文预览；为 `null` → 显示"暂无正文预览"
- 保留标题、描述、关键词、章节、知识点等由详情接口支撑的字段

## 6. 验证

- `npm run lint` / `npm run build` 通过
- 手工：进入 `/resource/:id` 页面，文字资源展示正文预览，非文字资源展示"暂无正文预览"
- Backend health check 在线时验证详情端点

## 7. 非目标确认

以下不在本轮范围：
- 阅读进度采集和展示
- 阅读时长统计
- Agent 文本生成/总结
- 全文分页加载
- `code` 类型正文预览

## 自审

- 无占位符 ✅
- 类型枚举对齐现有 OpenAPI ResourceItem.type ✅
- content_preview 契约不绑定 SQL 列 ✅
- 错误语义完整（401/403/404） ✅
