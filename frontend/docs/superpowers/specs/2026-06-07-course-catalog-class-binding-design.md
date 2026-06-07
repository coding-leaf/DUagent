# CourseCatalog 与教学班绑定设计

## 目标

Phase A 的目标是修正当前“教师创建课程、资源生成、课程资料、Qdrant 知识库”混在一起导致的产品链路脱节问题。

新的产品模型将“共享课程内容资产”和“教师教学组织”拆开：

- `CourseCatalog`：平台共享课程资源库，由管理员维护。
- `Class` / `CourseOffering`：教师开的教学班，只负责学生组织、邀请码、班级状态和报告。

Phase A 只要求完成管理员资源库闭环和教师开班绑定，不要求立即改造所有学生端 Agent 消费链路。

## 当前问题

当前项目中，教师端已经可以触发资源生成任务，但生成链路与真实课程资料没有稳定关系：

```text
TeacherConsole -> POST /resources/generate -> Backend task -> Agent -> Qdrant by course_id -> resources
```

这个链路的问题是：

- 教师创建课程不等于准备了课程资料。
- 后端 `resources` 表不等于原始课程资料。
- Qdrant 课程知识库不一定来自当前课程真实资料。
- `course_knowledge_graphs` 多依赖开发/运维预置，不是教师开班自然产生的结果。
- 教师端资源生成会让“教学班”和“共享课程内容资产”混在一起。

因此 Phase A 不继续扩展教师端资源生成，而是先拆清领域模型。

## 领域模型

### CourseCatalog

`CourseCatalog` 表示平台共享课程资源库，例如：

- 数据结构
- Python 程序设计
- 线性代数
- 计算机网络

它承载课程内容资产：

- 原始资料：PDF、Markdown、TXT、DOCX 等。
- ingestion 状态。
- Qdrant 课程知识库。
- 课程知识图谱 KG。
- 管理员审核后发布的学生可见学习资源。

`CourseCatalog` 由管理员维护，教师不可直接创建或修改。

### Class / CourseOffering

`Class` 或 `CourseOffering` 表示教师开的教学班，例如：

- 2026 春季 数据结构 1 班
- 王老师 数据结构强化班

它承载教学组织：

- 教师 ID。
- 绑定的 `catalog_id`。
- 班级名称。
- 邀请码。
- 学生加入关系。
- 班级报告和学生状态。

教师创建教学班时必须选择一个 `ready` 状态的 `CourseCatalog`。绑定后不可更换，避免学生学习路径、测验、画像和报告跨资源库混乱。

## 状态模型

`CourseCatalog` 至少需要以下状态：

| 状态 | 含义 | 是否可绑定开班 |
|------|------|----------------|
| `draft` | 已创建资源库，但资料未准备完成 | 否 |
| `ingesting` | 原始资料正在解析、切片、embedding、写入 Qdrant | 否 |
| `ready` | 知识库和必要 KG 已准备完成 | 是 |
| `failed` | ingestion 失败，需要管理员处理 | 否 |

后续若引入资源审核，可增加资源级状态：

| 状态 | 含义 |
|------|------|
| `candidate` | Agent 生成的候选学习资源 |
| `published` | 管理员审核后发布给学生 |
| `rejected` | 管理员拒绝发布 |

Phase A 的开班只依赖 `CourseCatalog.status == ready`。

## 管理员闭环

管理员负责共享课程资源库的完整内容准备链路：

```text
创建 CourseCatalog
-> 上传原始资料
-> Backend 保存资料元数据
-> 触发 ingestion 异步任务
-> 文档解析 / chunk / embedding
-> 写入 Qdrant
-> 生成或更新 KG
-> CourseCatalog ready
```

如果后续引入自动生成学生可见资源，则继续：

```text
CourseCatalog ready
-> Agent 生成候选学习资源
-> 管理员审核 / 编辑
-> 发布到共享资源库
```

Phase A 中，管理员资源库维护是唯一允许进入课程知识库准备链路的产品入口。

## 教师闭环

教师不再生成资源。教师只创建教学班：

```text
教师打开创建教学班
-> 选择 ready 的 CourseCatalog
-> 填写班级名称
-> 创建 Class/CourseOffering
-> 获得邀请码
-> 学生加入
-> 教师查看学生状态和报告
```

教师端应移除“课程资源生成”入口。若后续需要教师提出资源补充需求，应单独设计“资源补充申请”流程，不在 Phase A 实现。

## 学生与 Agent 定位规则

学生加入的是教学班，但所有课程内容和 Agent 知识来源都应通过教学班绑定的资源库定位：

```text
student_id
-> class_id
-> catalog_id
-> CourseCatalog
-> Qdrant / KG / published resources
```

后续能力应按这个规则消费数据：

- AIChat：通过 `class_id` 或当前课程上下文找到 `catalog_id`，检索 CourseCatalog 对应 Qdrant。
- Quiz 生成：使用 CourseCatalog 对应 Qdrant。
- LearningPath：使用 CourseCatalog 对应 KG。
- ResourceDetail：展示 CourseCatalog 下已发布资源。
- Evaluation/Profile/TeacherReport：后续结合学生行为数据聚合。

Phase A 只建立模型和绑定关系；这些消费链路可放入 Phase B/C。

## API 设计方向

Phase A 设计层面建议新增或调整以下 Client API。实际路径可在实施计划中按 OpenAPI 细化。

### Admin CourseCatalog

```text
GET    /admin/course-catalogs
POST   /admin/course-catalogs
GET    /admin/course-catalogs/{catalog_id}
PATCH  /admin/course-catalogs/{catalog_id}
```

用途：

- 管理员维护共享课程资源库。
- 列表支持按状态筛选。
- `ready` 状态资源库可被教师绑定。

### Admin Course Materials

```text
POST   /admin/course-catalogs/{catalog_id}/materials
GET    /admin/course-catalogs/{catalog_id}/materials
```

用途：

- 上传或登记原始资料。
- 文件解析和存储细节由 Backend 管理。

### Admin Knowledge Ingestion

```text
POST   /admin/course-catalogs/{catalog_id}/ingestions
GET    /admin/course-catalogs/{catalog_id}/knowledge-status
GET    /tasks/{task_id}
```

用途：

- 触发 ingestion 异步任务。
- 查询知识库和 KG 准备状态。
- 继续复用现有 `AsyncTask` 轮询模式。

### Teacher Class / CourseOffering

```text
GET    /course-catalogs?status=ready
POST   /classes
GET    /classes
GET    /classes/{class_id}
```

用途：

- 教师创建教学班时读取可绑定资源库。
- 创建教学班时必须传 `catalog_id`。
- Backend 校验 `catalog_id` 对应资源库为 `ready`。

## 错误处理

建议错误码：

| 错误码 | 场景 |
|--------|------|
| `catalog_not_ready` | 教师尝试绑定非 ready 资源库 |
| `catalog_not_found` | 资源库不存在或无权访问 |
| `material_required` | 触发 ingestion 时没有可处理资料 |
| `ingestion_failed` | 文档解析、embedding、Qdrant 写入或 KG 生成失败 |
| `catalog_binding_locked` | 尝试更换已绑定资源库 |

错误响应继续遵循现有 `{code, message, data}` 包装格式。

## 前端设计方向

### AdminConsole

新增“课程资源库”管理区域：

- 列表展示 CourseCatalog 名称、状态、资料数量、最近 ingestion 时间。
- 支持创建资源库。
- 支持进入详情页上传资料。
- 支持触发 ingestion。
- 显示 `draft / ingesting / ready / failed` 状态。

### TeacherConsole

调整为“教学班管理”：

- 创建教学班时选择已有 ready CourseCatalog。
- 展示班级绑定的资源库名称和状态。
- 移除“课程资源生成”面板。
- 若没有 ready CourseCatalog，展示“暂无可绑定课程资源库，请联系管理员”。

### Student 页面

Phase A 不强制改造学生页面。后续通过学生所在教学班定位 CourseCatalog。

## 数据兼容策略

用户选择 v1 不做旧数据全量迁移。

策略：

- 旧 `courses` 和相关资源暂保留。
- 新数据走 `CourseCatalog + Class/CourseOffering`。
- 实施时需要兼容旧 API 或提供临时适配层，避免阶段一已通过链路立即断裂。
- 旧数据迁移作为后续独立任务。

## 测试策略

Phase A 至少需要覆盖：

1. 管理员创建 CourseCatalog。
2. 管理员上传资料或登记资料。
3. ingestion 任务状态从 `ingesting` 到 `ready` 或 `failed`。
4. 教师创建教学班只能选择 `ready` CourseCatalog。
5. 教师不能绑定 `draft / ingesting / failed` CourseCatalog。
6. 教学班创建后不允许更换 `catalog_id`。
7. 教师端资源生成入口已移除。
8. 旧课程数据不因新模型引入而立即不可用。

## Phase A 成功标准

Phase A 完成时应满足：

- 管理员可以创建共享课程资源库。
- 管理员可以上传原始资料并触发 ingestion。
- 系统可以展示知识库状态。
- `ready` 的 CourseCatalog 可以被教师绑定开班。
- 非 ready 的 CourseCatalog 不能被绑定。
- 教师端不能直接生成资源。
- 新数据走 CourseCatalog + Class/CourseOffering。
- 旧 `courses` 数据暂时兼容保留。

## 非目标

Phase A 不做：

- 旧数据全量迁移。
- 教师资源生成。
- 教师编辑共享资源。
- 教师资源补充申请。
- 学生行为统计闭环。
- AIChat / Quiz / LearningPath 的完整新链路改造。
- 资源候选审核发布的完整 UI，如实现压力过大可放到后续 Phase。

## 后续阶段

### Phase B

让资源生成和 Quiz 生成强绑定 CourseCatalog 知识库：

- 无 ready 知识库时拒绝生成。
- 生成结果记录 source refs。
- Agent 日志暴露 retrieval hit count。

### Phase C

让 LearningPath 和 KG 同源化：

- KG 来自 CourseCatalog 原始资料。
- 节点资源匹配使用稳定知识点标识。

### Phase D

建立学生行为闭环：

- 资源访问。
- 阅读完成。
- 学习时长。
- AIChat 活动摘要。
- 行为进入 Evaluation/Profile/TeacherReport。

## 实施计划门禁

进入实施计划前，需要先给出 2-3 个实施方案供用户选择，不直接进入代码修改。

候选方向包括：

- 数据模型优先。
- Admin 管理优先。
- 最小兼容切换优先。

用户确认实施方案后，才能进入 writing-plans 阶段。
