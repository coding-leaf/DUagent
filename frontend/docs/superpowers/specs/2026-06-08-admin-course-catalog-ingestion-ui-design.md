# Admin CourseCatalog 入库 UI 设计

## 背景

Phase B1 已完成 Backend-Agent 课程资源库知识入库编排：

- Backend 支持课程资源库真实资料上传。
- Backend 支持触发 `course_catalog_ingestion` 异步任务。
- Backend 后台任务调用 Agent Service 入库，并回写 `CourseCatalog`、`CourseCatalogMaterial` 和 `AsyncTask` 状态。
- 前端已有 AdminConsole 课程资源库列表和创建入口，但还没有真实上传、入库触发、任务轮询和资料级状态展示。

本设计定义 Phase B2 的前端接入范围：在 AdminConsole 中补齐管理员可操作的课程资源库入库管理 UI。

## 目标

本轮实现管理员端资源库入库闭环：

```text
管理员进入 AdminConsole
-> 打开课程资源库 tab
-> 创建或选择资源库
-> 右侧详情抽屉展示资源库状态、资料列表和入库任务
-> 多选 .txt/.md/.pdf 文件
-> 前端逐个调用单文件上传接口
-> 管理员手动点击开始入库
-> 前端轮询 /tasks/{task_id}
-> 入库完成或失败后刷新资源库、资料和知识库状态
```

完成后，管理员可以不借助 curl 或数据库查询完成 B1 前端验收。

## 非目标

本轮不做：

- 修改 Backend 多文件上传接口。
- 修改 OpenAPI 契约。
- 直连 Agent Service。
- 使用 mock 数据补齐正式能力。
- 删除资料、替换资料。
- 拖拽上传。
- 上传完成后自动入库。
- 独立资源库详情路由。
- 完整任务历史列表。
- Qdrant 内容浏览或 chunk 预览。

这些能力后续单独设计。

## 推荐方案

采用现有 AdminConsole 内的右侧详情抽屉方案：

- 资源库列表保留在主内容区。
- 点击资源库行后打开右侧详情抽屉。
- 抽屉承载资料上传、资料状态、入库按钮和最近任务状态。
- 多文件选择在前端拆成多个单文件上传请求，契约仍使用当前 `multipart/form-data` 的单 `file` 字段。
- 入库由管理员手动触发，不自动触发。

不采用行内展开面板，原因是资料列表、错误原因和任务状态会让表格高度失控。

不采用独立页面，原因是本轮目标是接通 B1 能力，不需要扩大到新路由和完整管理模块。

## 前端结构

计划修改或新增以下前端文件：

- `src/api/services/admin.js`
- `src/api/services/task.js`
- `src/pages/AdminConsole.jsx`
- `src/components/admin/CourseCatalogDrawer.jsx`
- `WORKFLOW.md`

`AdminConsole` 保留页面级职责：

- 拉取资源库列表。
- 创建资源库。
- 管理当前选中的 `selectedCatalog`。
- 打开和关闭详情抽屉。
- 在抽屉内资料或入库状态变化后刷新资源库列表。

`CourseCatalogDrawer` 承担资源库详情职责：

- 根据 `catalog.id` 拉取资料列表。
- 根据 `catalog.id` 拉取知识库状态。
- 管理多文件上传队列。
- 触发入库。
- 轮询任务状态。
- 展示资料级状态和失败原因。
- 切换资源库、关闭抽屉或组件卸载时清理轮询。

`taskService` 承担通用异步任务查询职责：

```js
getTaskStatus(taskId)
```

`learningService.getTaskStatus()` 目前可用，但 task 查询是通用能力，不属于 learning 专属。新增 `taskService` 后，后续可逐步让 TeacherConsole 等调用迁移到同一封装。本轮可以只让新抽屉使用 `taskService`，不强制重构 TeacherConsole。

## 使用的 Client API

本轮只消费已进入 `../docs/10-client-api/Client-API.openapi.json` 的端点。

资源库列表：

```text
GET /api/v1/admin/course-catalogs
```

创建资源库：

```text
POST /api/v1/admin/course-catalogs
```

资料列表：

```text
GET /api/v1/admin/course-catalogs/{catalog_id}/materials
```

单文件上传：

```text
POST /api/v1/admin/course-catalogs/{catalog_id}/materials/upload
Content-Type: multipart/form-data
field: file
```

触发入库：

```text
POST /api/v1/admin/course-catalogs/{catalog_id}/ingestions
```

知识库状态：

```text
GET /api/v1/admin/course-catalogs/{catalog_id}/knowledge-status
```

任务轮询：

```text
GET /api/v1/tasks/{task_id}
```

## 数据展示

资源库列表展示：

- `title`
- `description`
- `status`
- `knowledge_status`
- `material_count`
- `chunk_count`
- `last_ingestion_status`
- `last_error`
- `created_at`

抽屉摘要展示：

- `status`
- `knowledge_status`
- `material_count`
- `chunk_count`
- `pending_material_count`
- `failed_material_count`
- `last_ingestion_task_id`
- `last_ingestion_status`
- `last_error`

资料列表展示：

- `filename`
- `source_type`
- `file_size`
- `status`
- `chunk_count`
- `last_error`
- `ingested_at`
- `created_at`

上传队列展示：

- 本地文件名。
- 本地上传状态：`queued`、`uploading`、`uploaded`、`failed`。
- 失败错误信息。

上传队列状态是前端本地 UI 状态，不写入 Backend。

## 状态文案

资源库状态：

| 状态 | 展示文案 | 说明 |
| --- | --- | --- |
| `draft` | 未入库 | 从未成功入库，不可绑定教学班 |
| `ingesting` | 入库中 | 首次入库中，不可绑定 |
| `ready` | 可绑定 | 至少成功入库过，可绑定教学班 |
| `failed` | 入库失败 | 首次全失败，不可绑定 |

知识库状态：

| 状态 | 展示文案 | 说明 |
| --- | --- | --- |
| `draft` | 未入库 | 没有可用知识库 |
| `ingesting` | 入库中 | 正在入库 |
| `ready` | 已同步 | 知识库已同步 |
| `dirty` | 待更新 | 已有知识库，但有新增资料未入库 |
| `partial` | 部分失败 | 有可用知识库，但部分资料失败 |
| `failed` | 入库失败 | 最近入库失败 |

资料状态：

| 状态 | 展示文案 |
| --- | --- |
| `uploaded` | 已上传 |
| `ingesting` | 入库中 |
| `ingested` | 已入库 |
| `failed` | 入库失败 |

未知状态按原值展示，避免前端静默吞掉后端新增状态。

## 交互规则

### 打开抽屉

点击资源库表格行或“管理资料”按钮打开详情抽屉。

打开后并行拉取：

- 资料列表。
- 知识库状态。

如果资料列表加载失败，抽屉保留打开并显示错误提示。

如果知识库状态加载失败，抽屉保留打开并显示错误提示。

### 多文件上传

文件选择支持多选 `.txt`、`.md`、`.pdf`。

前端对每个文件逐个调用当前单文件上传端点：

```text
POST /admin/course-catalogs/{catalog_id}/materials/upload
```

单个文件失败不阻断后续文件上传。

上传全部结束后刷新：

- 资料列表。
- 知识库状态。
- 资源库列表。

### 开始入库

管理员手动点击“开始入库”触发：

```text
POST /admin/course-catalogs/{catalog_id}/ingestions
```

按钮禁用条件：

- 资源库 `status === "ingesting"`。
- 知识库 `knowledge_status === "ingesting"`。
- 前端正在上传文件。
- 资料列表中没有 `status` 为 `uploaded` 或 `failed` 的资料。
- 当前已有入库任务正在轮询。

使用资料列表中的 `uploaded/failed` 判断是否可触发入库，因为它能直接覆盖新增资料和 partial 重试场景。

### 任务轮询

触发入库返回 `202` 后：

- 保存 `task_id`。
- 显示最近任务状态。
- 每 2 秒调用 `GET /tasks/{task_id}`。

当任务状态为：

- `processing`：继续轮询。
- `completed`：停止轮询，刷新资料列表、知识库状态、资源库列表。
- `failed`：停止轮询，显示错误信息，刷新资料列表、知识库状态、资源库列表。

轮询期间切换资源库、关闭抽屉或组件卸载时必须清理定时器。

## 错误处理

错误提示复用现有 `getErrorMessage()` 风格，兼容：

- `detail` 为字符串。
- `detail.message`。
- `message`。
- Axios `error.message`。

上传错误处理：

- `400`：显示文件名、类型或内容非法。
- `409`：显示资源库正在入库中。
- `413`：显示资料文件过大。
- 网络错误：显示网络错误或默认上传失败。

入库错误处理：

- `409` 正在入库或没有待入库资料：显示为操作提示，不关闭抽屉。
- 其他错误：显示默认入库触发失败。

状态语义：

- `partial` 不是前端错误态，而是“可用但不完整”。
- catalog `failed` 表示首次全失败，不可绑定。
- material `failed` 表示单份资料失败，可通过再次入库重试。

## 视觉与布局

抽屉采用右侧面板：

- 桌面端宽度约 `420px` 到 `520px`，不遮挡主列表核心信息。
- 小屏幕改为全宽覆盖面板。
- 抽屉包含四块：
  - 顶部摘要：标题、ID、`status`、`knowledge_status`。
  - 统计摘要：资料数、chunk 数、待入库数、失败数。
  - 上传资料：多文件选择和逐项上传结果。
  - 资料与任务：资料状态列表、开始入库按钮、最近任务状态。

状态颜色：

- ready / ingested：绿色。
- dirty / partial / processing：黄色或琥珀色。
- failed：红色。
- draft / uploaded：灰色或蓝灰色。
- ingesting：青色或琥珀色。

保持当前 AdminConsole 的管理台风格，不引入营销式视觉、不添加大型 hero 或装饰背景。

## 测试与验收

计划运行：

```bash
npm run lint
npm run build
```

如果新增前端单元测试基础设施成本过高，本轮不临时引入新测试依赖，使用现有构建检查和真实手工验收覆盖 UI 流程。

手工验收路径：

1. 使用管理员账号登录。
2. 进入 `/admin`。
3. 打开“课程资源库”。
4. 创建一个新资源库。
5. 点击资源库打开右侧抽屉。
6. 多选 `.md`、`.txt`、`.pdf` 上传。
7. 确认上传队列逐项显示成功或失败。
8. 确认资料列表出现已上传资料。
9. 点击“开始入库”。
10. 确认显示 `task_id` 和 processing 状态。
11. 等待轮询完成。
12. 确认资源库状态刷新为 `ready/ready` 或 `ready/partial`。
13. 确认资料状态刷新为 `ingested` 或 `failed`。
14. 若存在失败资料，再次点击“开始入库”可触发重试。

本轮前端验收不直接检查 Qdrant 内容；Qdrant 写入已由 B1 Backend-Agent E2E 验证覆盖。

## 契约纪律

本轮不修改 `../docs/10-client-api/Client-API.openapi.json`。

不得新增未声明字段。

不得为了 UI 展示硬编码 mock 资料、mock chunk、mock task 或 mock 错误。

不得直连 Agent Service。

不得把多文件上传实现成新的 Backend API 形态。前端多选必须拆成多个既有单文件上传请求。

## 剩余风险

- `AdminConsole.jsx` 已经偏大，新增抽屉必须拆组件，避免继续堆叠页面 JSX。
- 上传多个大文件时，前端逐个上传总耗时较长，但比并发上传更容易控制后端压力和错误提示。
- 如果 Backend 和 Agent Service 运行时没有共享 `COURSE_CATALOG_STORAGE_ROOT`，前端会看到入库失败；这属于部署配置问题，不在前端规避。
- 若后续需要展示任务历史，需要扩展或复用更多 AsyncTask 查询能力，本轮只展示最近触发的任务。
