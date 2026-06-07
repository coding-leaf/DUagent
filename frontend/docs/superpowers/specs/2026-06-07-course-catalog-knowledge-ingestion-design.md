# CourseCatalog 资料上传与知识库真实入库设计

## 背景

Phase A 已经将平台共享课程资源库和教师教学班拆开：

- `CourseCatalog` 表示管理员维护的共享课程内容资产。
- `CourseOffering` / 教学班表示教师用于组织学生和查看学情的教学组织。
- 教师创建教学班时只能绑定 `ready` 状态的课程资源库。

Phase A 仍留下一个关键断点：课程资源库虽然已经成为开班绑定对象，但还没有真实的资料上传、解析、向量化、写入 Qdrant 和 ready 状态生产链路。

Phase B1 的目标是补齐这条链路，让 `CourseCatalog` 真正拥有可被 Agent 检索的课程知识库。

## 目标

本阶段实现 CourseCatalog 资料上传与知识库真实入库闭环：

```text
管理员上传 .txt/.md/.pdf
-> Backend 保存到服务器共享目录
-> Backend 记录 CourseCatalogMaterial 元数据
-> 管理员手动触发 ingestion
-> Agent Service 读取共享目录资料
-> Agent Service 解析 / chunk / embedding / upsert Qdrant
-> Qdrant payload.course_id = CourseCatalog.id
-> Backend 回写 material / catalog / task 状态
-> CourseCatalog 可进入 ready
```

完成后，新的课程资源库不再只是数据库记录，而是能通过产品入口准备真实课程知识库。

## 非目标

本阶段不做以下能力：

- 教师端资源生成入口恢复。
- 学生端 AIChat / LearningPath / ResourceDetail 消费 CourseCatalog 的改造。
- Quiz 生成前置 ready 校验。
- KG 生成或 KG 可视化。
- 删除、替换资料。
- 全量重建知识库按钮。
- 对象存储、MinIO、S3。
- Word / DOCX 解析。
- 前端拖拽上传。

这些能力进入后续 Phase B2 / Phase C / Phase D。

## 职责边界

### Backend

Backend 负责业务 API、权限、文件保存和状态机：

- 管理员上传 `.txt` / `.md` / `.pdf`。
- 保存原始文件到配置的共享目录。
- 记录 `CourseCatalogMaterial` 元数据。
- 管理 `CourseCatalog`、`CourseCatalogMaterial`、`AsyncTask` 状态。
- 校验权限、文件类型、文件大小和资源库状态。
- 调用 Agent ingestion API。
- 向前端提供上传、入库、状态查询接口。

Backend 不做：

- 文档解析。
- chunk。
- embedding。
- 直接写 Qdrant。
- import Agent Service 代码。
- 执行 Agent CLI 作为正式产品链路。

### Agent Service

Agent Service 负责知识库入库能力：

- 从共享目录读取受控课程资料。
- 解析 `.txt` / `.md` / `.pdf`。
- chunk。
- embedding。
- upsert Qdrant。
- 维护 course knowledge collection。
- 返回 material 级入库结果、chunk 数和错误信息。

Agent Service 不做：

- 管理员权限。
- CourseCatalog 业务状态机。
- 前端 Client API。

### CLI 定位

现有 `agent_service.tools.ingest_knowledge` CLI 保留为开发和运维入口。

正式产品链路不由 Backend 调 CLI，而是由 Backend 调 Agent Service HTTP API。CLI 和 HTTP API 复用同一 ingestion service/tool 能力。

## 文件存储

本阶段采用服务器本地共享目录。

建议 Backend 配置：

```text
COURSE_CATALOG_STORAGE_ROOT=/path/to/storage/course_catalogs
```

文件保存结构：

```text
{COURSE_CATALOG_STORAGE_ROOT}/{catalog_id}/{material_id}/{safe_filename}
```

数据库只保存相对路径：

```text
storage_type = "local"
storage_uri = "course_catalogs/{catalog_id}/{material_id}/{safe_filename}"
```

接口不返回服务器绝对路径。

安全要求：

- 文件名必须清洗或拒绝路径穿越。
- `storage_uri` 必须是相对路径。
- Agent API 不接受任意绝对路径。
- Agent Service 解析路径时必须确认最终路径仍在共享根目录内。

## 资料类型

本阶段支持：

- `.txt`
- `.md`
- `.pdf`

不支持：

- `.docx`
- `.pptx`
- 压缩包
- 图片 OCR
- 视频 / 音频

不支持类型上传时返回 400。

## ID 与 Qdrant 隔离规则

Qdrant 中的课程知识库隔离 ID 使用 `CourseCatalog.id`。

```text
Qdrant payload.course_id = CourseCatalog.id
```

不使用旧 `Course.id` 或教学班 ID 作为知识库 ID。

原因：

- 多个教学班共享同一份课程资源库。
- 课程资料只需入库一次。
- 后续 Agent 消费链路应通过教学班找到 `catalog_id`，再用 `catalog_id` 检索 Qdrant。

## 状态机

状态分为两层：

- `CourseCatalog.status` 表示资源库是否可绑定开班。
- `CourseCatalog.knowledge_status` 表示知识库是否与资料同步。

### CourseCatalog.status

| 状态 | 含义 | 是否可绑定 |
| --- | --- | --- |
| `draft` | 从未成功入库 | 否 |
| `ingesting` | 首次入库中 | 否 |
| `ready` | 至少成功入库过 | 是 |
| `failed` | 首次入库失败 | 否 |

教师开班只判断：

```text
CourseCatalog.status == "ready"
```

### CourseCatalog.knowledge_status

| 状态 | 含义 |
| --- | --- |
| `draft` | 没有可用知识库 |
| `pending_ingest` | 有资料待入库 |
| `ingesting` | 正在入库 |
| `ready` | 知识库已同步到当前资料 |
| `dirty` | 已有可用知识库，但存在新增资料未入库 |
| `failed` | 最近一次入库失败 |

### CourseCatalogMaterial.status

| 状态 | 含义 |
| --- | --- |
| `uploaded` | 文件已保存 |
| `pending_ingest` | 等待入库 |
| `ingesting` | 正在处理 |
| `ingested` | 已写入 Qdrant |
| `failed` | 本资料入库失败 |

### 状态转换

首次上传资料：

```text
catalog.status = draft
catalog.knowledge_status = pending_ingest
material.status = pending_ingest
```

首次开始入库：

```text
catalog.status = ingesting
catalog.knowledge_status = ingesting
material.status = ingesting
```

首次入库成功：

```text
catalog.status = ready
catalog.knowledge_status = ready
material.status = ingested
```

首次入库失败：

```text
catalog.status = failed
catalog.knowledge_status = failed
material.status = failed
```

ready 后新增资料：

```text
catalog.status = ready
catalog.knowledge_status = dirty
material.status = pending_ingest
```

ready 后增量入库中：

```text
catalog.status = ready
catalog.knowledge_status = ingesting
pending material.status = ingesting
```

ready 后增量入库成功：

```text
catalog.status = ready
catalog.knowledge_status = ready
processed material.status = ingested
```

ready 后增量入库失败：

```text
catalog.status = ready
catalog.knowledge_status = failed
failed material.status = failed
```

此时旧知识库仍可用，教师仍可开班绑定。

## 增量入库规则

管理员手动触发 ingestion。

每次触发只处理：

- `pending_ingest` 资料。
- 允许重试的 `failed` 资料。

不处理：

- 已 `ingested` 资料。
- 删除或替换资料。

如果没有待处理资料，Backend 返回 409。

现有 Agent ingestion 已按 `source_file` 支持幂等跳过。本阶段需要保证 Backend 传给 Agent 的 `storage_uri` 与 Qdrant payload 中的 `source_file` 可稳定对应。

同名文件内容替换不在本阶段支持范围内。

## Backend Client API

### 上传资料

```text
POST /api/v1/admin/course-catalogs/{catalog_id}/materials/upload
Content-Type: multipart/form-data
```

请求字段：

```text
file
```

行为：

- 仅 admin 可调用。
- 校验 `catalog_id` 存在。
- 校验当前资源库不处于 `ingesting`。
- 校验扩展名为 `.txt` / `.md` / `.pdf`。
- 校验文件大小不超过配置上限。
- 保存文件到共享目录。
- 创建 `CourseCatalogMaterial`。
- 首次上传时 `knowledge_status=pending_ingest`。
- ready 资源库新增资料时 `status` 保持 `ready`，`knowledge_status=dirty`。

响应示例：

```json
{
  "code": 201,
  "message": "created",
  "data": {
    "id": "mat_xxx",
    "catalog_id": "catalog_xxx",
    "filename": "chapter1.md",
    "source_type": "file",
    "storage_type": "local",
    "file_size": 12345,
    "status": "pending_ingest",
    "created_at": "2026-06-07T10:00:00"
  }
}
```

### 资料列表

```text
GET /api/v1/admin/course-catalogs/{catalog_id}/materials
```

响应补充字段：

- `storage_type`
- `file_size`
- `status`
- `last_error`
- `ingested_at`

### 触发入库

```text
POST /api/v1/admin/course-catalogs/{catalog_id}/ingestions
```

行为：

- 仅 admin 可调用。
- 无待入库资料返回 409。
- 资源库正在入库返回 409。
- 创建 `AsyncTask`。
- 更新 catalog/material 到入库中状态。
- 调用 Agent ingestion API。
- 根据 Agent 结果回写状态。

响应示例：

```json
{
  "code": 202,
  "message": "accepted",
  "data": {
    "task_id": "task_xxx",
    "catalog_id": "catalog_xxx",
    "status": "processing"
  }
}
```

### 知识库状态

```text
GET /api/v1/admin/course-catalogs/{catalog_id}/knowledge-status
```

响应补充字段：

- `last_ingestion_task_id`
- `last_ingestion_status`
- `chunk_count`
- `pending_material_count`
- `failed_material_count`
- `last_error`

## Agent API

### 触发知识入库

```text
POST /agent/v1/knowledge/ingestions
```

请求体：

```json
{
  "catalog_id": "catalog_xxx",
  "materials": [
    {
      "material_id": "mat_xxx",
      "storage_uri": "course_catalogs/catalog_xxx/mat_xxx/chapter1.md",
      "filename": "chapter1.md"
    }
  ]
}
```

行为：

- 校验 `catalog_id` 非空。
- 校验 materials 非空。
- 校验 `storage_uri` 是共享根目录内的相对路径。
- 读取 `.txt` / `.md` / `.pdf`。
- chunk、embedding、upsert Qdrant。
- 写入 Qdrant 时 `course_id = catalog_id`。
- 返回 material 级结果。

响应体：

```json
{
  "catalog_id": "catalog_xxx",
  "chunk_count": 42,
  "materials": [
    {
      "material_id": "mat_xxx",
      "status": "ingested",
      "chunk_count": 42,
      "error": null
    }
  ],
  "duration_seconds": 3.2
}
```

Agent API 不暴露给前端。

## 前端交互

在 `AdminConsole` 的“课程资源库”页补齐：

1. 资源库列表。
2. 当前资源库资料列表。
3. 上传资料。
4. 开始入库。
5. 入库状态展示。

建议交互：

- 管理员创建 CourseCatalog。
- 点击资源库的“管理资料”。
- 上传 `.txt` / `.md` / `.pdf`。
- 上传成功后刷新资料列表和资源库状态。
- 点击“开始入库”。
- 入库中禁用上传和再次入库按钮。
- 轮询 `GET /tasks/{task_id}` 或 `knowledge-status`。
- 成功后显示“已就绪，可绑定”。
- 失败后显示失败原因。

状态文案：

| 状态组合 | 文案 |
| --- | --- |
| `draft` + `pending_ingest` | 待入库，教师暂不可绑定 |
| `ready` + `dirty` | 可绑定，有新资料待入库 |
| `ingesting` + `ingesting` | 正在入库 |
| `ready` + `ready` | 已就绪，可绑定 |
| `failed` + `failed` | 首次入库失败，暂不可绑定 |
| `ready` + `failed` | 可绑定，最近入库失败 |

前端 service 增加：

```text
uploadCourseCatalogMaterial(catalogId, file)
getCourseCatalogMaterials(catalogId)
startCourseCatalogIngestion(catalogId)
getCourseCatalogStatus(catalogId)
```

## OpenAPI 与契约

需要同步：

- `../docs/10-client-api/Client-API.openapi.json`
- 如有维护，更新前端接口规范文档。
- Agent API 文档或 Agent Service OpenAPI。

Backend 错误响应继续沿用当前格式：

```json
{
  "detail": {
    "code": 40912,
    "message": "课程资源库正在入库中",
    "data": null
  }
}
```

## 测试计划

### Backend

上传资料：

- 非 admin 403。
- 不存在 catalog 404。
- 不支持扩展名 400。
- ingesting 状态上传 409。
- `.txt` / `.md` / `.pdf` 上传成功。
- 文件保存到受控目录。
- DB material 状态为 `pending_ingest`。
- ready 资源库上传后 `status` 仍为 `ready`，`knowledge_status` 变为 `dirty`。

开始入库：

- 无待入库资料 409。
- 首次入库中 `status=ingesting`。
- ready 增量入库中 `status=ready`，`knowledge_status=ingesting`。
- Agent 成功后 material `ingested`，catalog `ready`。
- Agent 失败后首次入库 catalog `failed`。
- Agent 失败后增量入库 catalog 仍 `ready`，`knowledge_status=failed`。
- 并发入库 409。

安全：

- `storage_uri` 只保存相对路径。
- 路径穿越文件名被清洗或拒绝。
- 上传接口不返回服务器绝对路径。

### Agent Service

ingestion API：

- 只允许共享根目录下 `storage_uri`。
- 拒绝 `../` 路径穿越。
- 拒绝不存在文件。
- `.txt` / `.md` / `.pdf` 可解析。
- Qdrant payload `course_id = catalog_id`。
- 返回 material 级结果。

增量入库：

- 已 ingested source_file 不重复 upsert。
- 新 material 会追加写入同一 `catalog_id` 知识库。

### Frontend

- `npm run lint`
- `npm run build`
- 管理端上传资料 smoke。
- 管理端开始入库 smoke。
- 入库中按钮禁用。
- ready + dirty / ready + failed 状态文案正确。

## 手工验收

建议验收链路：

```text
1. 管理员创建 CourseCatalog。
2. 上传 .md。
3. 点击开始入库。
4. 观察状态 ingesting -> ready。
5. 教师创建教学班时能选择该资源库。
6. 管理员继续上传 .txt。
7. 资源库仍可被教师选择，但显示有待入库更新。
8. 再次入库，只处理新增资料。
9. Agent / Qdrant 中以 catalog_id 检索能找到新增资料内容。
```

## 剩余风险

- 真实 embedding provider 或 Qdrant 不可用时，必须把错误清楚落到 `last_error`，不能静默 ready。
- PDF 解析质量可能不稳定，本阶段只保证可解析和入库，不保证内容质量完美。
- 现有 Agent 增量跳过逻辑按 `source_file` 判断；如果同名文件内容变化，本阶段暂不支持替换。
- Backend 与 Agent Service 共享目录要求部署在同机或共享 volume；后续分布式部署时需要改为对象存储或内部下载 URL。
- 本阶段不解决 KG，同步知识图谱进入 Phase C。

## 后续阶段

Phase B2：

- 资源生成 / Quiz 生成前置 ready 校验。
- 生成结果记录 source refs。
- 无课程资料时拒绝泛化生成。

Phase C：

- KG 与 CourseCatalog ingestion 同源化。
- LearningPath 使用 catalog KG。
- NodeResources 使用稳定知识点标识。

Phase D：

- 学生资源访问事件。
- 学习时长和完成状态。
- AIChat 活动摘要。
- Evaluation / Profile / TeacherReport 消费行为数据。
