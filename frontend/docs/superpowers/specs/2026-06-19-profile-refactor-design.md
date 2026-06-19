# Backend Profile Route Refactor Design

## 背景

在阶段二架构治理中，核心任务是清理后端胖路由，推行 `Router -> Service -> DB` 分层架构。当前 `backend/app/api/v1/profile.py` 约为 **718行**，是整个接口路由层中体量最大的“胖路由”文件。

该模块混杂了以下多重职责：
1. **接口生命周期控制与权限校验**（学生选课校验、响应体封装）。
2. **并发锁逻辑**（MySQL Named Lock 的获取与释放）。
3. **数据存取 (CRUD) 与初始化**（画像 `/initialize` 路由的写库事务、学习目标和自定义指令读写）。
4. **对话画像解析与合并规则引擎**（调用 Agent 对话分析、数据类型规范化、多版本规则合并）。
5. **异步刷新计算**（创建后台刷新任务、调用 `app/services/profile_rules.py` 的 `compute_profile_fields` 并刷新画像）。
6. **展现层数据转化 (Presenter/DTO)**（为前端卡片及雷达图组装字段）。

为了保证系统架构可读性、高内聚性以及在测试时可完全隔离数据库对核心“画像规则合并”进行纯逻辑单测，本 Spec 制定了将该模块进行彻底重构的分层设计方案。

---

## 目标

1. 将 `backend/app/api/v1/profile.py` 缩减为纯路由控制器（100行以内），仅负责路由声明、权限校验、Service 调用与后台任务派发。
2. 剥离 MySQL Named Lock 并下沉至新建的独立基础设施层 `backend/app/infrastructure/locks.py`，保持非 Web 依赖。
3. 创建画像基本服务 `ProfileService`、对话合并服务 `ProfileDialogueService`、后台刷新服务 `ProfileRefreshService` 与呈现器 `profile_presenters.py`。
4. 保持 `backend/app/services/profile_rules.py`（画像数据刷新计算规则）职责纯粹，重构范围不侵入该模块逻辑，由服务层直接调用。
5. 保持所有外部接口契约、Pydantic Schema、API 路由路径、HTTP 状态码、任务类型（`profile_refresh`）和错误语义完全不变。
6. 编写或调整测试覆盖纯逻辑归一化与合并规则函数，确保重构不发生功能退化。

## 非目标

* 不修改前端 API 调用方式。
* 不改变 MySQL 数据表 Schema。
* 不改变 Agent Service 端点与契约。
* 不在基础设施层引入任何 FastAPI 依赖（不抛 HTTPException）。
* 不做多数据库类型（如 SQLite）的抽象妥协（锁定 MySQL 生产环境）。
* 不修改 `backend/app/services/profile_rules.py` 内部计算逻辑。

---

## 目标文件结构

### 1. `backend/app/infrastructure/locks.py` (新建)

* **职责**：提供独立的并发控制设施，不依赖 FastAPI 或 Web 框架。
* **主要内容**：
  * 自定义异常类 `LockAcquisitionTimeout(Exception)`。
  * 异步上下文管理器 `profile_lock(db: AsyncSession, user_id: str, course_id: str)`。
  * 硬编码执行 MySQL Named Lock 获取 `GET_LOCK(key, 10)`，若失败抛出 `LockAcquisitionTimeout`。
  * `finally` 块中强制执行 `RELEASE_LOCK`，确保异常安全释放锁。

### 2. `backend/app/services/profile_presenters.py` (新建)

* **职责**：无状态数据转换层（DTO），负责组装面向前端的响应结构，并集中定义画像基础常量。
* **主要内容**：
  * 定义全局画像缺省常量 `_default_profile = { ... }`（供 presenters, service 和 dialogue_service 导入使用）。
  * `_resource_preference_summary(modal_preference: dict) -> str`
  * `_profile_dimensions(profile: dict) -> list[dict]`
  * `profile_data(pf: UserProfile | None, course_id: str, user: User | None = None) -> dict`

### 3. `backend/app/services/profile_service.py` (新建)

* **职责**：画像基本生命周期 CRUD 与事务封装。
* **方法定义**：
  * `ProfileService(db: AsyncSession)` 类。
  * `get_or_create_profile(user_id: str, course_id: str) -> UserProfile`
  * `initialize_profile(user_id: str, course_id: str, answers: dict) -> UserProfile`：封装 `/initialize` 路由的初始化业务，使用 `profile_lock` 上锁，执行首选项、目标与默认指标计算并写入。
  * `update_learning_goal(user_id: str, course_id: str, goal: str)`
  * `update_custom_instruction(user_id: str, course_id: str, instruction: str)`

### 4. `backend/app/services/profile_dialogue_service.py` (新建)

* **职责**：同步对话画像提取与深度规则合并。
* **方法与模块级纯函数**：
  * `ProfileDialogueService(db: AsyncSession)` 类，暴露 `update_from_dialogue(user_id: str, course_id: str, extracted_data: dict) -> UserProfile`，使用 `profile_lock` 上锁更新。
  * 模块级纯函数 `_normalize_fields(extracted: dict) -> dict`：包含原有 `_classify_learning_goal` 与 `_classify_resource_preferences` 的匹配算法。
  * 模块级纯函数 `_merge_profile(pf: UserProfile, normalized: dict) -> dict`：执行规则决策（盲区追加、偏好分提升、指导等级修改、JSONB 的 flag_modified 标记）。

### 5. `backend/app/services/profile_refresh_service.py` (新建)

* **职责**：画像后台计算与刷新触发。
* **内容定义**：
  * `ProfileRefreshService(db: AsyncSession)` 类，暴露 `create_refresh_task(user_id: str, course_id: str) -> AsyncTask`，在当前请求事务中创建并持久化任务记录。
  * 模块级后台 Runner `run_profile_refresh_background(task_id: int, user_id: str, course_id: str)`：供 `asyncio.create_task` 在后台线程中调度。使用独立 session 工厂，并在内部通过 `profile_lock` 对更新操作加锁。内部直接调用外部的 `backend/app/services/profile_rules.py` 进行数据统计更新。

### 6. `backend/app/api/v1/profile.py` (精简)

* **职责**：仅包含 API 依赖项、权限拦截器声明、HTTP 错误包装翻译。
* **主要变动**：
  * 路由函数内只调用对应的 Service 方法。
  * 捕获 `LockAcquisitionTimeout` 异常并统一翻译为 `HTTPException(status_code=503, ...)`。
  * `/dialogue-update` 路由在**锁区间外**请求 Agent（硬约束），获得提取结果后再转入 `ProfileDialogueService` 锁区间写库，避免网络超时导致长时间霸占 DB 锁。
  * `/initialize` 路由调用 `ProfileService(db).initialize_profile(...)`，不包含业务写入逻辑。

---

## 架构与模式选型声明

| 架构/模式 | 选择状态 | 理由 |
| :--- | :--- | :--- |
| **分层架构** | **选用** | `Router -> Service -> DB` 三层架构已在 `catalogs` 和 `learning_path` 重构中验证，高度契合本项目单体后端现状。 |
| **Service Layer** | **选用** | 新增三个服务模块（`profile_service`, `profile_dialogue_service`, `profile_refresh_service`）将复杂的 CRUD、初始化、规则合并和异步刷新彻底解耦。 |
| **Presenter / DTO** | **选用** | 新增 `profile_presenters.py` 将数据库 ORM 字典在输出层统一清洗转换，隔离底层数据库字段变更对前端的直接冲击。 |
| **基础设施解耦** | **选用** | 锁管理器挪入新建的 `backend/app/infrastructure` 目录，采用 `LockAcquisitionTimeout` 领域异常，切断底层组件对 FastAPI 的反向依赖。 |
| **数据库降级适配** | **弃用** | 坚持“数据库只用 MySQL”的绝对环境边界，基础设施层不做 SQLite/Dialect 动态降级，测试环境统一用 mock 代理或在 MySQL 库中覆盖锁断言。 |

---

## 异常处理与错误翻译契约

1. **Named Lock 获取超时**：
   * `locks.py` 抛出 `LockAcquisitionTimeout`。
   * Router 捕获后返回：
     * `HTTP_503_SERVICE_UNAVAILABLE`
     * Payload: `{"code": 50300, "message": "服务繁忙，请稍后重试", "data": None}`
2. **外部 Agent 交互异常**：
   * 捕获 `AgentServiceError`。
   * 接口层返回 `HTTP_502_BAD_GATEWAY`，Payload: `{"code": 50200, "message": "画像解析结果格式错误", "data": None}`。

---

## 核心合并逻辑纯度与技术债记录

* 在 `profile_dialogue_service.py` 中，`_normalize_fields` 与 `_merge_profile` 保持为 **纯函数 (Pure Function)**，其内部除了改变实体对象（`UserProfile`）的属性外，**严禁引入任何 `db.execute` 数据库访问与 `agent_client` 网络访问**。
* **锁安全关键约束**：在 MySQL Named Lock 保护区间内禁止任何外部 I/O 交互（如外部 API、文件读写等），以防止长事务导致锁无法释放，所有外部数据准备（如 Agent API 请求）必须在锁范围之外完成。
* **盲区去重幂等性技术债**：
  * 当前 `_dedupe_limit` 去重判定逻辑依赖完全文本匹配（`exact string match`）。
  * 若 Agent 同一概念不同措辞（例如“C语言指针”与“指针内存指向”），系统会视其为两个盲区写入。
  * 本次重构保持现有完全文本匹配行为，并在 Spec 中显式登记该技术债，待后续升级为语义相似度匹配（LLM / Embedding）时再重写此纯函数，不改变 Service 外层结构。

---

## 测试覆盖计划

* **逻辑单测更新**：
  * 将 `tests/test_profile_dialogue_rules.py` 的导入替换为 `app.services.profile_dialogue_service._normalize_fields`。
  * 补齐画像合并用例 `test_merge_profile_blindspots`（验证 `_merge_profile` 去重 10 条上限与偏好权重阈值 max(x, 70) 逻辑）。
* **Presenter 单测新建**：
  * 创建 `tests/test_profile_presenters.py`，验证 `profile_data` 组装返回给前端的数据结构一致性。
* **回归保障**：
  * 运行 `tests/test_profile_rules.py` 与 `tests/test_lock_async.py` 确保回归全绿。
