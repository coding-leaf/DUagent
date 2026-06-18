# Backend Catalogs 胖路由分层重构设计

## 背景

当前 Phase 2 已进入架构治理与重构阶段。前端已完成若干纵向切片样板，后端仍存在明显胖路由，其中 `backend/app/api/v1/catalogs.py` 约 1758 行，是当前最大、职责最混杂的后端文件。

按 `frontend/AGENTS.md` 的阶段二方向，本次应以当前运行代码为事实来源，优先整理目录、推行清晰分层、补测试，并且在跨模块提取前先输出专项 Spec。旧的 `backend/AGENTS.md` / `agent_service/AGENTS.md` 仅作为参考，不作为阻断规则。

本 Spec 聚焦 `catalogs.py`，不同时重构 `profile.py`、`tutoring.py`、`learning_path.py`，避免一次性扩散。

## 当前问题

`catalogs.py` 目前混合了以下职责：

1. 课程资源库 CRUD 与公开 ready catalog 列表。
2. 资料上传、删除、文件名校验、文件系统路径操作。
3. 课程资源库知识入库任务创建与后台状态流转。
4. KG host course 创建、知识图谱状态查询与生成任务创建。
5. Admin 资源列表、删除、按 KG 节点批量生成资源、父子任务聚合。
6. Admin 保底题库生成、子任务拆分、Agent 调用、skeleton 过滤、QuizQuestion 落库。
7. 响应 DTO 格式化函数与多种错误构造函数散落在路由文件内。

这导致：

- 路由层承担过多业务编排和数据访问逻辑。
- `CatalogService` 已存在但只承接了少量 CRUD，分层试点未继续推进。
- 后续修改资源生成、KG、Quiz 任一子能力时，都需要读完整胖路由。
- 测试虽然较多，但测试对象仍以 API/路由行为为主，服务层边界不清晰。

## 外部经验与工程参考

本次不引入新运行时依赖。参考方向如下：

- **FastAPI 多文件应用组织**：使用 APIRouter 和模块拆分组织大应用。这里优先保留现有 `catalogs.py` 路由入口，先把业务逻辑下沉至 services，避免路由拆分和业务拆分同时发生。
- **Service Layer**：Service 作为应用业务边界，协调 DB、Agent HTTP、文件系统和任务状态。
- **SQLAlchemy Unit of Work**：继续使用当前传入的 `AsyncSession` 作为事务边界。第一阶段不让 service 私自创建跨并发共享 session；后台任务需要独立 session 时仍使用 `async_session_factory`。
- **DTO / Presenter**：把 `_catalog_item`、`_material_item`、KG/task summary 等响应格式化从路由层抽出，集中维护。
- **State Machine 思路**：catalog `status` / `knowledge_status` 和 `AsyncTask.status` 的状态流转应逐步集中，先服务化再考虑显式状态机。
- **Command / Job Service**：入库、KG 生成、资源生成、Quiz 生成本质是“启动任务 + 后台执行/回调”的命令，应从 HTTP route 中剥离。

## 架构选型判断

### 选用：分层架构

采用 `Router -> Service -> DB/Agent/FileSystem`。

- Router 负责鉴权、依赖注入、参数接收、HTTP status 和统一响应包装。
- Service 负责业务编排、状态流转、Agent payload 构建、后台任务逻辑。
- DB 访问先保留在 Service 内，不急于抽全量 Repository。

理由：当前最大痛点是 route 文件过胖，而不是查询接口抽象不足。先做 Service Layer 能以较低风险获得最大可读性收益。

### 暂不选用：全量 Repository 模式

第一阶段不为每张表创建 Repository。

理由：现有查询多为特定业务流程服务，过早泛化会增加文件数量和跳转成本。等 Service 层稳定后，如果出现重复查询和可复用数据访问，再抽 `catalog_repository.py`、`task_repository.py` 等。

### 暂不选用：CQRS

不引入读写分离框架或专门 Query Bus。

理由：当前读写复杂度可通过 Service + Presenter 解决。Teaching / reporting 类复杂查询未来可单独评估 read model，本次不扩大。

### 暂不选用：微服务拆分

Backend 和 Agent Service 的部署边界保持不变。

理由：当前边界已经明确，问题在 Backend 内部分层，不是服务粒度。

### 选用：Command / Job Service

对入库、KG 生成、资源生成、Quiz 生成使用命令式 service 方法，例如 `start_ingestion(...)`、`start_kg_generation(...)`、`start_resource_generation(...)`。

理由：这些操作都有相同形态：校验前置状态、创建 `AsyncTask`、提交事务、启动后台任务或调用 Agent、维护任务状态。

## 目标

1. 将 `catalogs.py` 从胖路由压缩为薄路由，目标最终低于 400 行。
2. 不改变 Client API 路径、参数、响应字段、状态码语义。
3. 不改变 Agent API 契约，不修改 Agent Service。
4. 不修改 `.env`、密钥、volume、上传文件或构建产物。
5. 按阶段拆分，每阶段不超过 5 个核心代码文件，便于测试和回滚。
6. 每阶段补或调整测试，优先覆盖抽出的纯函数、service 行为和现有 API 回归。

## 非目标

- 不重写课程资源库业务流程。
- 不替换当前 `AsyncTask + BackgroundTasks + Webhook` 架构。
- 不引入 Celery、Redis Queue、DI 容器或新的 ORM 抽象库。
- 不把 Agent 内部对象引入 Backend。
- 不修复无关功能 bug，除非重构测试暴露出直接相关问题。
- 不更新已过时的 `docs/feature-ledger.md`。

## 拆分边界

### 阶段 1：Presenter 与 Catalog / Material 基础服务

目标：先切低风险、同步逻辑，把 DTO 和资料管理从路由层剥离。

建议文件：

- 新增 `backend/app/services/catalog_presenters.py`
  - `catalog_item(catalog)`
  - `material_item(material, include_storage_uri=False)`
  - `knowledge_graph_summary(graph)`
  - `knowledge_graph_task_summary(task)`
  - 其他纯响应格式化函数
- 扩展 `backend/app/services/catalog_service.py`
  - catalog 详情、列表、创建已有逻辑保留并补齐方法命名。
  - ready catalog 公开列表迁入 service。
- 新增 `backend/app/services/catalog_material_service.py`
  - 文件名校验。
  - material 创建、删除、状态更新。
  - 文件系统目录删除包装。
- 修改 `backend/app/api/v1/catalogs.py`
  - 对应 route 只调用 service / presenter。

测试：

- 新增或扩展 `backend/tests/test_catalog_service.py`。
- 新增 `backend/tests/test_catalog_material_service.py`，覆盖非法文件名、状态流转、material item 格式。
- 运行现有 `test_course_catalogs.py`、`test_course_catalog_ingestion.py` 相关回归。

### 阶段 2：Catalog Ingestion Service

目标：入库启动和后台入库状态流转从路由层移出。

建议文件：

- 新增 `backend/app/services/catalog_ingestion_service.py`
  - `start_catalog_ingestion(...)`
  - `run_catalog_ingestion_background(...)`
  - 入库 task 创建、catalog/material 状态初始化、异常恢复。
- 修改 `catalogs.py`
  - `POST /admin/course-catalogs/{catalog_id}/ingestions` 仅做参数/鉴权和 background task 注册。

测试：

- 迁移或复用 `backend/tests/test_course_catalog_ingestion.py`。
- 覆盖：
  - 无待入库资料时拒绝。
  - 启动后创建 task 并置 processing。
  - Agent 失败后 task/catalog/material 状态落 failed。
  - 成功后 catalog/material/chunk_count 状态正确。

### 阶段 3：Catalog KG Service

目标：KG host course、知识状态、KG 生成任务收口。

建议文件：

- 新增 `backend/app/services/catalog_kg_service.py`
  - `get_catalog_knowledge_status(...)`
  - `get_catalog_knowledge_graph_status(...)`
  - `start_catalog_kg_generation(...)`
  - `_get_or_create_catalog_kg_host_course(...)` 迁入 service。
- 保留现有 `kg_generation.py`、`course_knowledge_graphs.py` 的底层能力，不搬动其内部算法。
- 修改 `catalogs.py`
  - KG 相关 route 只调用 service。

测试：

- 复用 `test_admin_catalog_kg_generation.py`、`test_course_knowledge_graph_versions.py`。
- 补 service 单测覆盖 duplicate processing task、knowledge base not ready、kg host course 并发/唯一性兜底。

### 阶段 4：Catalog Resource Generation Service

目标：资源生成父子任务、KG-node 目标选择、Agent payload 构建下沉。

建议文件：

- 新增 `backend/app/services/catalog_resource_generation_service.py`
  - `list_catalog_resources(...)`
  - `delete_catalog_resource(...)`
  - `start_catalog_resource_generation(...)`
  - 显式 metadata 单目标路径。
  - KG-node 默认批量路径。
  - 父子 task 创建与 Agent payload 构建。
- 保留 `kg_resource_targets.py`、`resource_scope.py` 作为底层工具。

测试：

- 复用 `test_admin_catalog_resource_generation.py`、`test_kg_resource_targets.py`、`test_node_resources.py`。
- 补 service 测试覆盖：
  - 无 active KG 时 failed 父任务。
  - 无 usable target 时 failed 父任务。
  - 显式 metadata 仍走旧单目标语义。
  - KG-node 子任务 result 包含 target_node。

### 阶段 5：Catalog Quiz Generation Service

目标：保底题库生成和子任务落库逻辑从路由层移出。

建议文件：

- 新增 `backend/app/services/catalog_quiz_generation_service.py`
  - `start_catalog_quiz_generation(...)`
  - `run_quiz_generation_background(...)`
  - `_generate_quiz_for_child(...)`
  - baseline payload 构建。
  - skeleton 过滤、答案格式化、QuizQuestion 落库。
- 修改 `catalogs.py`
  - Quiz generation route 只调用 service。

测试：

- 复用 `test_admin_catalog_resource_generation.py` 中 quiz 相关用例，必要时拆出 `test_admin_catalog_quiz_generation.py`。
- 覆盖：
  - 父子 task 创建。
  - 批量生成全 skeleton 后拆 single/multi 小批次。
  - 多选答案格式仍为逗号分隔。
  - 子任务失败不拖垮其他子任务，父任务聚合正确。

## 数据流

### 同步查询类

1. Router 接收 query/path 参数与鉴权用户。
2. Router 创建 service 实例或调用 service 函数，传入 `AsyncSession`。
3. Service 执行查询和业务过滤。
4. Presenter 将 ORM / task / graph 转为现有响应 dict。
5. Router 返回现有 `{code, message, data}` 包装。

### 异步任务类

1. Router 接收请求并完成鉴权。
2. Service 校验 catalog/material/offering/KG 前置状态。
3. Service 创建 `AsyncTask`，初始化 catalog/material 状态。
4. Router 或 service 注册 `BackgroundTasks`，传递 task id / catalog id / user id 等标量，不传活跃 session。
5. 后台函数使用独立 `async_session_factory()`。
6. 成功/失败路径都显式更新 task 状态和相关业务表状态。

## 错误处理

- 第一阶段不改变现有错误 envelope 和 HTTP status。
- 现有 `HTTPException(detail={"code": ..., "message": ..., "data": ...})` 语义保持。
- 可将重复错误构造函数迁入 service 或 `catalog_errors.py`，但不引入新错误码。
- Agent 调用失败继续使用现有 `AgentServiceError` 语义。
- 文件系统删除失败不应导致 DB 状态回滚，除非当前代码已有此语义；重构保持现状。

## 测试策略

每个阶段遵循 TDD：

1. 先补 service 或 presenter 单测，验证当前 route 内逻辑的目标行为。
2. 跑测试确认红灯，或在纯迁移场景下确认新测试能捕获缺失模块/函数。
3. 最小迁移逻辑，让测试通过。
4. 跑相关 API 回归测试，确认响应不漂移。
5. 跑 Python 语法检查。
6. 更新 `WORKFLOW.md`，说明本阶段改动与契约漂移情况。

推荐测试命令按阶段选择：

```bash
cd backend
../.venv/bin/python -m py_compile app/api/v1/catalogs.py app/services/catalog_service.py
../.venv/bin/python -m pytest tests/test_catalog_service.py tests/test_course_catalogs.py -q -p no:cacheprovider
```

涉及具体阶段时追加对应测试：

```bash
../.venv/bin/python -m pytest tests/test_course_catalog_ingestion.py -q -p no:cacheprovider
../.venv/bin/python -m pytest tests/test_admin_catalog_kg_generation.py -q -p no:cacheprovider
../.venv/bin/python -m pytest tests/test_admin_catalog_resource_generation.py -q -p no:cacheprovider
```

## 风险与约束

- `catalogs.py` 涉及文件系统、DB、Agent、后台任务，不能一次性全拆。
- 现有测试依赖 MySQL/SQLite 混合，执行时需要按当前项目习惯显式设置测试 DB。
- 后台任务不要复用请求内 `AsyncSession`。
- 父子任务聚合、锁、commit 时序是高风险点，迁移时必须保持原有提交顺序。
- 不要用全局正则搬代码。每阶段迁移一个明确子能力。

## 推荐实施顺序

1. 阶段 1：Presenter + Catalog/Material 基础服务。
2. 阶段 2：Ingestion service。
3. 阶段 3：KG service。
4. 阶段 4：Resource generation service。
5. 阶段 5：Quiz generation service。

阶段 1 完成后即可评估 `catalogs.py` 行数下降和测试稳定性，再决定是否继续阶段 2。

## 自审

### Placeholder 扫描

通过。本文没有未填内容、空章节或“后续再说”式模糊要求。每个阶段都有明确目标、文件和测试方向。

### 内部一致性

通过。文档统一采用 `Router -> Service -> DB/Agent/FileSystem` 分层，不同时引入 Repository、CQRS 或微服务拆分，和“先低风险服务化”的目标一致。

### 范围检查

通过。本 Spec 只覆盖 `backend/app/api/v1/catalogs.py` 及其直接服务化，不同时处理 `profile.py`、`tutoring.py`、`learning_path.py` 或 Agent Service 内部重构。范围适合拆成多个实施计划。

### 歧义检查

通过。明确了第一阶段优先级、非目标、契约不漂移、后台任务 session 约束，以及每阶段的建议文件边界。实现时若发现接口字段或状态码需要变化，必须视为契约漂移并停止确认。
