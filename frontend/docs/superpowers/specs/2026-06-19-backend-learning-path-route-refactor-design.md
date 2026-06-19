# Backend Learning Path Route Refactor Design

## 背景

阶段二架构治理要求清理后端胖路由，推行 `Router -> Service -> DB` 分层。当前 `backend/app/api/v1/learning_path.py` 约 648 行，混合了 HTTP 路由、KG fallback 纯函数、实时进度合并、Agent payload 组装、后台任务 runner、学习路径写库、节点资源聚合查询等职责。

本次审查同时比较了 `profile.py` 与 `learning_path.py`。结论是先拆 `learning_path.py`，再另起 `profile.py` 专项 spec。原因是 `learning_path.py` 的职责边界更清晰，现有测试已直接覆盖多组可迁移纯函数与接口回归；`profile.py` 混合画像初始化、对话合并、规则刷新、学习目标和自定义指令，业务写入风险更高，适合在 learning path 样板稳定后处理。

## 目标

1. 将 `learning_path.py` 从胖路由收敛为只负责鉴权依赖、参数接收、service 调用、后台任务调度和响应包装。
2. 将学习路径读取、KG fallback、实时节点状态合并、Agent payload 组装、后台刷新写库、节点资源聚合迁移到 `backend/app/services/`。
3. 保持所有外部接口、响应字段、HTTP 状态码、Agent 调用路径、`AsyncTask.task_type` 和错误语义不变。
4. 以 TDD 小步迁移，每一步都能单独运行相关测试并提交。
5. 为后续 `profile.py` 拆分提供更贴近业务主链的第二个后端样板。

## 非目标

- 不修改前端调用方式。
- 不修改 Agent Service 接口。
- 不引入 Celery、RQ 或新的任务队列。
- 不引入 Repository 框架或独立 DI 容器。
- 不改变 MySQL schema。
- 不重写学习路径生成算法。
- 不把 `profile.py` 纳入本次代码实现。

## 现状拆分点

当前 `learning_path.py` 中可以按职责拆成四组：

1. 读取学习路径并合并实时进度：
   - `_map_assessment_to_status`
   - `_apply_progress_to_nodes`
   - `_build_current_position_from_nodes`
   - `_topo_sort_kg_nodes`
   - `_synthesize_kg_fallback_path`
   - `get_learning_path`
2. 学习路径刷新：
   - `_assemble_learning_path_payload`
   - `_run_learning_path_refresh_background`
   - `refresh_learning_path`
3. 节点资源聚合：
   - `get_node_resources`
   - KG node name/chapter 解析
   - latest LearningPath node name 覆盖
   - Resource / QuizQuestion 查询与响应组装
4. 通用路由 glue：
   - student enrollment 校验
   - `JSONResponse(202)` 包装
   - `asyncio.create_task(...)` 调度

## 架构与模式判断

### 选用：分层架构

采用 `Router -> Service -> DB`。Router 只处理 HTTP 边界，Service 承载业务编排和 DB 查询。该方式已在 `catalogs.py` 模块化重构中验证，适合本项目当前单体后端。

### 选用：Service Layer

新增三个服务模块：

- `app.services.learning_path_service`
- `app.services.learning_path_refresh_service`
- `app.services.node_resource_service`

请求级 service 以类形式接收 `AsyncSession`，保持和 catalog service 样板一致。

### 选用：Adapter / Presenter 思路

Agent 返回的 `nodes`、`edges`、`current_position` 由 refresh service 适配为 `LearningPath` ORM。节点资源响应也由 service 组装为面向前端的 DTO dict，避免 route 直接拼业务结构。

### 选用：Background Runner Pattern

后台 runner 保持模块级 async function，自行创建 `async_session_factory()` session，不接收 request-scoped `db` 或 ORM 实例。这延续 catalog ingestion / KG / quiz generation 的现有安全边界。

### 暂不选用：Repository Pattern

本次先不新增 repository 层。原因是当前重复查询还未大到需要额外抽象，且项目后端已有样板是 service 内封装查询。若后续 profile/evaluation/learning_path 出现共享查询膨胀，再单独设计 repository。

### 暂不选用：CQRS

`GET /learning-path` 与 `POST /learning-path/refresh` 有读写分离倾向，但本轮用 `LearningPathService` 与 `LearningPathRefreshService` 分模块即可，不引入正式 CQRS 架构。

### 暂不选用：Middleware / Chain of Responsibility

权限校验仍保留在 FastAPI dependency 与 route glue 中。学生选课校验可在本次保持局部函数或 route 内逻辑，不扩展成全局权限框架。

### 暂不选用：外部组件库或新依赖

这是后端结构重构，不需要前端组件库，也不需要新 Python 依赖。

## 目标文件结构

### `backend/app/services/learning_path_service.py`

职责：

- 暴露 `LearningPathService(db)`。
- 提供 `get_learning_path(user_id, course_id)`。
- 保留并迁移纯函数：
  - `topo_sort_kg_nodes`
  - `map_assessment_to_status`
  - `apply_progress_to_nodes`
  - `build_current_position_from_nodes`
- 提供 KG fallback 合成逻辑。
- 返回完整 `data` dict，不包含外层 `{code, message}`。

### `backend/app/services/learning_path_refresh_service.py`

职责：

- 暴露 `LearningPathRefreshService(db)`。
- 提供 `assemble_payload(user_id, course_id)`。
- 提供 `create_refresh_task(user_id, course_id)`，创建并 flush/refresh `AsyncTask`，commit 仍由 route 控制，保持当前“任务持久化后再调度后台协程”的时序。
- 提供模块级 `run_learning_path_refresh_background(task_id, user_id, course_id, payload)`。
- 后台 runner 内部调用 Agent `/agent/v1/learning-path/generate`，写入 `LearningPath`，更新 `AsyncTask`。
- 保持 `task_type="learning_path_refresh"`、`error_code="lock_timeout" | "internal_error" | agent_code` 不变。

### `backend/app/services/node_resource_service.py`

职责：

- 暴露 `NodeResourceService(db)`。
- 提供 `get_node_resources(user, course_id, node_id)`。
- 复用 `ensure_course_resource_access`、`resolve_course_resource_scope`、`resource_scope_clause`。
- 解析 KG node name/chapter，并用 latest LearningPath node name 覆盖 KG name。
- 返回现有字段：
  - `node_id`
  - `node_name`
  - `weak_point_tutorials`
  - `exercises`
  - `chapter_materials`
  - `full_exercise_set`

### `backend/app/api/v1/learning_path.py`

职责：

- 保留 `router = APIRouter(...)`。
- `GET ""` 调用 `LearningPathService(db).get_learning_path(...)`。
- `POST "/refresh"` 保留学生选课权限校验，调用 refresh service 组装 payload 和创建 task，然后 `asyncio.create_task(...)`。
- `GET "/nodes/{node_id}/resources"` 调用 `NodeResourceService(db).get_node_resources(...)`。
- 不再包含 KG 排序、payload 组装、后台写库和资源聚合查询细节。

## 接口兼容性

本次不允许接口漂移：

- `GET /api/v1/learning-path`
  - 保留 `code/message/data` 外层结构。
  - 保留 `data.course_id/nodes/edges/current_position/source/generated_at`。
  - 保留 `source` 当前语义：`realtime_merged`、`kg_realtime`、`kg_fallback`。
- `POST /api/v1/learning-path/refresh`
  - 成功仍返回 HTTP 202。
  - body 仍为 `{code: 202, message: "accepted", data: {task_id}}`。
  - `task_type` 仍为 `learning_path_refresh`。
  - Agent 路径仍为 `/agent/v1/learning-path/generate`。
- `GET /api/v1/learning-path/nodes/{node_id}/resources`
  - 保留现有响应字段和分组 key。
  - 不改变 resource 和 quiz 查询匹配语义。

## 测试策略

### RED/GREEN 单元测试迁移

先新增 service 测试并让它们从新模块 import 失败，再迁移实现：

- `backend/tests/test_learning_path_service.py`
  - 覆盖 topo sort。
  - 覆盖 assessment state 到 UI status 的映射。
  - 覆盖 progress merge 保留原字段。
  - 覆盖 current position 选择。
  - 覆盖 KG fallback 返回节点。
- `backend/tests/test_learning_path_refresh_service.py`
  - 覆盖 `assemble_payload` 使用 active KG。
  - 覆盖后台 runner Agent 失败时 task failed。
  - 覆盖 lock timeout 仍写 `error_code="lock_timeout"`。
- `backend/tests/test_node_resource_service.py`
  - 覆盖节点资源按 KG chapter 返回 `chapter_materials`。
  - 覆盖 latest LearningPath 中 node name 优先于 KG name。

### 现有测试 import 路径调整

迁移后调整现有测试 import：

- `test_learning_path_realtime.py`
  - 从 `app.services.learning_path_service` import 纯函数。
- `test_learning_path_fallback.py`
  - 从 `app.services.learning_path_service` import topo sort。
- `test_node_resources.py`
  - 从 `app.services.learning_path_refresh_service` import payload 组装函数或通过 service 类调用。
- `test_lock_async.py` / `test_refresh_async.py`
  - Agent mock patch 路径从 `app.api.v1.learning_path.agent_client.post_json` 改为 `app.services.learning_path_refresh_service.agent_client.post_json`。

### 回归命令

后端局部回归：

```bash
cd ../backend
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/learning_path_refactor_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_learning_path_service.py tests/test_learning_path_refresh_service.py tests/test_node_resource_service.py tests/test_learning_path_realtime.py tests/test_learning_path_fallback.py tests/test_node_resources.py -q -p no:cacheprovider
```

刷新链路回归：

```bash
cd ../backend
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/learning_path_refactor_refresh_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_refresh_async.py tests/test_lock_async.py -q -p no:cacheprovider
```

语法检查：

```bash
cd ../backend
PYTHONPYCACHEPREFIX=/tmp/eduagent_pycache ../.venv/bin/python -m py_compile app/api/v1/learning_path.py app/services/learning_path_service.py app/services/learning_path_refresh_service.py app/services/node_resource_service.py
```

前端无需改动；如实际实现中触碰前端 service，则必须补跑：

```bash
npm run lint
npm run build
```

## 实施顺序

1. 新建 `learning_path_service.py`，先迁移纯函数和 KG fallback，更新纯函数测试 import。
2. 将 `GET /learning-path` 委托给 `LearningPathService`，跑 fallback/realtime/node resources 相关回归。
3. 新建 `learning_path_refresh_service.py`，迁移 payload 组装和后台 runner，更新 mock patch 路径。
4. 将 `POST /learning-path/refresh` 委托给 refresh service，跑 refresh/lock 回归。
5. 新建 `node_resource_service.py`，迁移节点资源聚合查询，补 service 测试。
6. 将 `GET /learning-path/nodes/{node_id}/resources` 委托给 node resource service，跑 node resources 回归。
7. 清理 `learning_path.py` 残留 helper 和未使用 import，确保路由文件只保留 HTTP glue。
8. 更新 `WORKFLOW.md` 与 `docs/requirements-coverage.md`，记录无接口漂移。

## 风险与控制

- **风险：测试 mock 路径失效。** 控制：每迁移一个 Agent 调用或后台 runner，同步更新 patch 路径并跑对应测试。
- **风险：后台 runner 误用 request-scoped db。** 控制：runner 只接收标量和 payload，内部创建独立 session。
- **风险：节点资源 chapter fallback 退化。** 控制：保留 KG host course 优先、current course fallback 的现有查询顺序，并用 `test_node_resources.py` 回归。
- **风险：响应 source 字段变化。** 控制：service 返回现有 `source` 值，测试中断言 `kg_fallback`、`kg_realtime`、`realtime_merged`。
- **风险：一次改动过大。** 控制：按三组 service 分批提交，任何一批失败都能定位。

## 验收标准

1. `learning_path.py` 不再包含 KG 排序、实时进度合并、payload 组装、后台写库、节点资源聚合查询的具体实现。
2. 新 service 模块均有聚焦测试或被现有接口测试覆盖。
3. `GET /learning-path`、`POST /learning-path/refresh`、`GET /learning-path/nodes/{node_id}/resources` 响应结构不变。
4. 后台任务仍使用独立 DB session，`AsyncTask` 完成/失败状态语义不变。
5. 所有局部回归和 py_compile 通过。
6. `WORKFLOW.md` 记录改动、测试结果和“无接口漂移”。

## 后续

本 spec 完成后，再单独编写 `profile.py` 专项重构 spec。profile 拆分应优先复用本次经验，但需要更谨慎处理画像写入、对话合并和用户指导级别的业务真值。
