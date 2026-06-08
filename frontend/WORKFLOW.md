# Frontend Workflow

`WORKFLOW.md` 只记录当前阶段状态、最近验证和下一步，不承担接口契约、完整设计规范或历史资料归档职责。
需及时修改相关内容以更新状态
## 当前判断

- 前端处于前后端联调阶段。
- 阶段一前端主链路已在真实 Backend + Agent Service + `duagent_test` 种子数据环境下完成 E2E 验收。
- 阶段一遗留契约疑点已清理；阶段二学生端数据契约审查、P0 假展示清理、ResourceDetail 正文预览链路已完成。
- 当前前端目标仍超过既有 Client API 的完整承载范围；新增能力必须先有契约审查或明确设计，再进入实现。
- 现有 `../docs/10-client-api/*` 仍是正式契约来源。已确认进入契约的新增能力包括 `GET /api/v1/resources/{id}` 与 `ResourceDetailItem.content_preview`。
- 未完成契约审查的页面能力不得继续用硬编码字段、Mock 假数据、推测响应结构或临时页面状态补齐正式能力。

## 阶段一目标

阶段一只收口现有 Client API 已能支撑的主链路，目标是让真实 Backend API 下的基础流程可运行、可验证、可回归：

- 登录、注册、验证码、`/users/me` 鉴权恢复。
- 课程列表、课程切换、课程上下文。
- 学生 Dashboard 资源列表。
- 学习路径基础展示。
- Quiz 获取题目、提交和结果页。
- AI Chat SSE 流式对话。
- 教师端学生列表和基础学情报告。
- 管理员基础用户和日志页面。

阶段一约束：

- 不新增正式 API 字段。
- 不扩展 Agent API。
- 不新增 SQL Schema。
- 后端返回空数组或空值时，展示 Empty/Unknown 状态，不回退到假数据。

说明：2026-06-05 经用户确认，为修复 E2E 种子数据与当前 ORM 不一致，Backend 画像表补充了 `knowledge_mastered`、`knowledge_weak` 两个内部 SQL 字段；该变更不新增前端可见 API 字段，不改变 Client API 或 Agent API 契约。

## 阶段一当前状态

状态：真实联调 E2E 验收通过。

已具备：

- 前端页面、API service 封装和路由已覆盖阶段一主链路。
- `e2e/specs.spec.js` 已覆盖学生登录进入资源库、课程切换、学习路径、Quiz、教师登录查看学生报告等主流程。
- 本地静态检查已通过。
- 真实 Backend `http://127.0.0.1:8001`、Agent Service `http://127.0.0.1:8002`、MySQL `duagent_test` 种子数据环境下，`npm run test:e2e` 已通过 3/3。

阶段一后续注意：

- 确认真实 API 返回空数组或空值时页面展示 Empty/Unknown，不回退到假数据。
- 前端 service 中曾存在的未声明调用已在 2026-06-05 清理；后续新增 service 方法必须先对齐 `../docs/10-client-api/Client-API.openapi.json`。

## 阶段二目标

阶段二先做契约审查，再进入实现。目标是让前端完整页面目标、Client API、Backend SQL 和必要的 Agent 数据来源重新对齐。

当前状态：

- 学生端数据契约审查已完成，审查文档见 `docs/superpowers/specs/2026-06-05-phase2-student-data-contract-review.md`。
- 已删除或降级：认知成长曲线、建议学习时长、学习动力指数、班级覆盖率、重点关注学生、排名类指标。
- 已实现：ResourceDetail 文字资源正文预览，新增 `GET /api/v1/resources/{id}`，`document`/`reading` 返回 `content_preview`，其他类型返回 `null`。
- 仍待设计或延期：累计学习时长、阅读进度、阅读时长、AIChat 活动摘要、资源偏好分布。

阶段二需要审查的能力包括：

- 资源详情正文阅读、阅读进度、累计学习时长、建议学习时长。
- 认知成长曲线、掌握度趋势、路径节点更细粒度状态。
- 班级 AI 洞察、覆盖率、排名、动力指数。
- 教师端学生深度诊断、资源偏好分布、复杂资源统计、导出报告。
- 管理员智能体日志、用户管控动作、系统运行状态。

阶段二输出应至少明确：

- 哪些字段进入 Client API 契约。
- 哪些字段需要 Backend SQL 或聚合查询支撑。
- 哪些能力需要 Agent API 或异步任务结果支撑。
- 哪些页面能力应降级、延期或删除。

## 文档定位

- `README.md`：前端模块入口、运行方式、阅读顺序。
- `AGENTS.md`：前端协作规则、修改约束、契约纪律。
- `WORKFLOW.md`：当前阶段状态、目标、下一步。
- `DESIGN.md`：视觉设计系统草案。
- `前端页面字段与布局结构数据报告.md`：页面设想和阶段二契约审查输入，不是当前实现契约。

## 最近验证

- 2026-06-08：Phase B 资源生成 / Quiz 生成前置 CourseCatalog ready 校验完成：
  - 基线与设计已重建：`docs/superpowers/specs/2026-06-08-course-catalog-ready-gate-baseline.md` 记录 CourseCatalog 三表、`knowledge_status`、ingestion 链路、生成端缺口、OpenAPI 滞后点；`docs/superpowers/specs/2026-06-08-phase-b-ready-gate-design.md` 与 `docs/superpowers/plans/2026-06-08-phase-b-ready-gate-plan.md` 明确本阶段只覆盖资源生成和 Quiz 生成，不纳入 LearningPath/KG。
  - Backend 新增共享 `course_catalog_gate.resolve_generation_catalog()`：教学班 `course_id` 必须能解析到 `CourseOffering.catalog_id`；`CourseCatalog.status=ready` 且 `knowledge_status=ready|partial`、`chunk_count>0` 才允许生成；`partial` 可用但标记 `degraded=true`；`dirty/draft/failed/ingesting` 或非 ready catalog 拒绝。
  - 错误码：未绑定或资源库缺失返回 `404 course_catalog_missing`；资料未完成入库返回 `409 course_material_missing`；知识库为空返回 `409 knowledge_base_empty`。校验在创建 `AsyncTask` 前执行，失败时不产生异步任务。
  - `/resources/generate` 和 `/quiz/generate` 共用同一套 ready gate；Backend 持久化仍使用教学班 id，发送给 Agent 的 `course_id` 改为 `CourseCatalog.id`；Quiz 个性化上下文仍按教学班 id 查询，Agent payload 额外带 `class_course_id`。
  - OpenAPI 与 `API_前端接口规范.md` 已同步 404/409 响应和 ready gate 描述；前端删除孤儿 `learningService.triggerResourceGeneration()` / `learningService.getTaskStatus()`，不新增资源生成或 Quiz 生成 UI。
  - 验证：`cd ../backend && ../.venv/bin/pytest tests/test_course_catalog_ready_gate.py tests/test_resources_async.py tests/test_agent_integration.py::TestQuizGenerateIntegration -q` 通过 20/20；`python3 -m json.tool ../docs/10-client-api/Client-API.openapi.json` 通过；`npm run lint` 通过；`npm run build` 通过，仍有既有 Vite chunk size warning。
  - 已提交：`f6b8b19 新增课程资源库生成前置校验`、`04107e4 接入资源生成资源库 ready 校验`、`1f8d765 同步生成 ready 校验契约`、`7cf6a36 接入 Quiz 生成资源库 ready 校验`。
- 2026-06-08：AIChat 历史消息对象知识点白屏修复：
  - 问题：学生端进入 AIChat 后加载历史会话，真实历史消息中的 `knowledge_points[]` 可能出现 `{name, chapter, mastery}` 对象；前端直接在 `<span>` 中渲染对象，触发 React `Objects are not valid as a React child` 白屏，同时列表使用 index key 触发 key warning。
  - 修复：`AIChat.jsx` 对历史消息、SSE `knowledge_points` 和 `suggestions` 统一做可展示文本归一化；对象优先展示 `name/title/knowledge_point/label/content/id`，避免对象直接进入 React child；建议、知识点和图解列表改用消息 ID + 内容生成稳定 key。
  - 回归：新增 Playwright 用例覆盖 `GET /tutoring/conversations/{id}` 返回对象形知识点和对象形 suggestions 时页面不白屏，并展示知识点/建议文本。
  - 验证：`npm run test:e2e -- e2e/specs.spec.js -g "AI Chat renders historical messages"` 通过 1/1；`npm run lint` 通过；`npm run build` 通过，仍有既有 Vite chunk size warning。
  - 契约状态：前端未改接口路径、方法或请求参数；OpenAPI 仍声明 `messages[].knowledge_points[]` 为 string，当前真实历史响应出现对象元素，属于后端响应与 Client API 契约存在元素类型漂移，前端仅做兼容性防白屏。
- 2026-06-08：CourseCatalogDrawer 入库任务轮询与状态文案修复：
  - `/tasks/{task_id}` 查询异常不再被本地改写为任务失败，不再停止入库态或写入权威终态集合；展示“任务状态查询失败，正在重试”并按原 2 秒间隔继续轮询。
  - 资源库、知识库、资料、上传队列和任务状态按设计展示中文标签；未知状态保留原值，空状态保留 UNKNOWN / `—` fallback。
  - `npm run test:e2e -- e2e/specs.spec.js -g "Admin course catalog ingestion polling"` 覆盖首次任务查询 500 后继续重试并最终完成；`npm run lint` / `npm run build` / `git diff --check -- src/components/admin/CourseCatalogDrawer.jsx e2e/specs.spec.js WORKFLOW.md` 通过。无 OpenAPI/契约漂移。
- 2026-06-05 ~ 2026-06-06（已归档，详见 git 历史）：阶段一主链路 E2E 收口（lint/build/e2e 3/3）、阶段一遗留契约疑点与多处 mock 分支清理、MS-05/MS-06/MS-08 前端入口、Tailwind v4 宽度别名修复、阶段二学生端数据契约审查、P0 假展示清理、ResourceDetail 正文/内容契约、LearningPath 节点资源接入、教师端学生 weak_points/recent_activity 聚合、阶段二文档收口。以上均已完成并通过对应 lint/build/pytest，无遗留 OpenAPI 漂移；细节见各 `docs/superpowers/specs|plans/2026-06-05-*`、`2026-06-06-*` 文档与对应 commit。
- 2026-06-07：注册登录契约扩展与隐私边界收口完成：
  - Client API：`POST /auth/register` 请求体新增可选 `real_name`、`student_id`、`major`、`grade`、`guidance_level`；`guidance_level` 限定 `L1/L2/L3`，默认 `L2`。
  - Backend：注册成功写入用户基础资料；注册码改为永久可复用码，`student` / `teacher` 为内置永久码；非法 `guidance_level` 返回 400。
  - Frontend：注册页不再提交 `gender`，提交 `real_name/student_id/major/grade/guidance_level`；登录/注册错误提示兼容 `message`、`detail.message`、`detail`。
  - AI 隐私边界：Backend 增加脱敏 `learner_context` helper，仅包含 `major`、`grade`、`guidance_level`；当前不写入实际 Agent `/tutoring/chat` payload，避免 Agent API 契约漂移；测试确认 payload 不含 `real_name/email/student_id/username`。
  - 验证：`pytest tests/test_auth_register_contract.py tests/test_tutoring_privacy.py -q` 通过 3/3（因当前工具沙箱内 `aiosqlite.connect()` 会挂住，使用已授权非沙箱 pytest 运行）；后续注册码永久化后 `pytest tests/test_auth_register_contract.py -q` 通过 3/3；`npm run lint` 通过；`npm run build` 通过，仍有既有 Vite chunk size warning；`python -m json.tool ../docs/10-client-api/Client-API.openapi.json` 通过；本轮文件 `git diff --check` 通过。
  - 契约状态：Client API 已同步更新，无 Client API 漂移；Agent API 未修改，实际 Agent 请求体未新增字段，无 Agent API 漂移。
- 2026-06-07：StudentProfile 基础资料展示补齐：
  - 学生个人画像页个人信息卡新增展示 `student_id`、`major`、`grade`、`guidance_level`，数据来自 `/users/me` 的全局用户资料。
  - 不新增接口、不修改 OpenAPI；资源库 Dashboard 保持资源页职责，不承载完整个人资料。
  - `npm run lint` / `npm run build` 通过，仍有既有 Vite chunk size warning；本轮文件 `git diff --check` 通过。
- 2026-06-07：AdminConsole 既有 Client API 契约对齐补齐：
  - 用户表“最后登录”改为展示 `created_at` 创建时间；新增当前管理员自保护的“停用”按钮，调用既有 `DELETE /admin/users/{user_id}` 并成功后刷新用户列表。
  - 日志页同时消费 `GET /admin/logs/agent` 与 `GET /admin/logs/operations`，新增 Agent 日志 / 系统日志切换；两类日志为空时展示空态，不回退 mock 数据。
  - `adminService.removeUser` 注释同步为软删除/停用语义；请求路径和方法未变。
  - `npm run lint` 通过；`npm run build` 通过，仍有既有 Vite chunk size warning。
  - 本轮文件 `git diff --check -- src/pages/AdminConsole.jsx src/api/services/admin.js WORKFLOW.md` 通过；全量 `git diff --check` 仍受既有未触碰的 `../.gitignore:73` 末尾空行影响失败。
  - 契约状态：未修改 OpenAPI；未新增 Client API 或 Agent API；无 OpenAPI / Agent API 漂移。
- 2026-06-07：本地管理员账号与登录跳转修复：
  - 当前 MySQL `duagent.users` / `duagent_test.users` 缺少 `admin@admin.com`，已补入本地管理员账号并确认 `role=admin`、`is_active=1`、`is_deleted=0`。
  - 修正登录成功后的角色分流：`admin` 跳转 `/admin`，`teacher` 跳转 `/teacher`，学生跳转 `/dashboard`。
  - 旧 `schema.sql` 中的示例 bcrypt hash 经当前后端 `verify_password` 校验不匹配 `Admin123456`；本地账号使用当前后端 `hash_password("Admin123456")` 生成的可验证 hash。
  - `POST /api/v1/auth/login` 管理员登录 smoke 通过：`admin@admin.com` / `Admin123456` 返回 `role=admin`。
  - `npm run lint` 通过；`npm run build` 通过，仍有既有 Vite chunk size warning；本轮文件 `git diff --check -- src/pages/Login.jsx WORKFLOW.md` 通过。
  - 契约状态：未修改 OpenAPI；未新增接口；无 OpenAPI / Agent API 漂移。
- 2026-06-07：管理员路由兜底修复：
  - 修正 `ProtectedRoute` 无权限兜底：`admin` 访问非授权页面时回到 `/admin`，不再被重定向到 `/teacher`。
  - AdminConsole 顶部“返回前台”改为“管理首页”，目标 `/admin`，避免管理员点击后进入学生 `/dashboard` 再被守卫兜底。
  - `npm run lint` 通过；`npm run build` 通过，仍有既有 Vite chunk size warning；本轮文件 `git diff --check -- src/components/ProtectedRoute.jsx src/pages/AdminConsole.jsx WORKFLOW.md` 通过。
  - 契约状态：前端路由修复，不涉及 OpenAPI / Agent API。
- 2026-06-07：AdminConsole 停用按钮状态修复：
  - 当前管理员自保护从单一 `id` 比较增强为 `id/email` 双重判断，避免登录态与列表字段不一致时仍显示可停用。
  - 停用用户成功后在当前页面记录已停用用户 ID，刷新列表后按钮显示“已停用”并禁用。
  - 说明：现有 `GET /admin/users` 契约未返回 `is_active/status`，跨页面刷新后的持久状态展示需要后续契约扩展；本轮不修改 OpenAPI。
  - `npm run lint` 通过；`npm run build` 通过，仍有既有 Vite chunk size warning；本轮文件 `git diff --check -- src/pages/AdminConsole.jsx WORKFLOW.md` 通过。
  - 契约状态：未修改 OpenAPI；无 OpenAPI / Agent API 漂移。
- 2026-06-07：开发重心调整：
  - 管理员页已完成当前既有 Client API 能承载的基础对接；停用状态跨页面持久展示、管理员初始化 SQL 固化、AdminConsole 文案/细节交互等暂列后续收尾，不继续阻塞当前主线。
  - 当前优先级调整为继续对接其余功能，优先推进“资源生成异步任务链路接入”等仍未闭环的主能力。
  - 若后续要完整展示用户停用状态，需要先扩展 Admin 用户列表契约，返回 `is_active` 或状态字段，再同步后端、前端和 OpenAPI。
  - 本条为进度与优先级记录，无代码变更；未运行测试。
- 2026-06-07：TeacherConsole 资源生成异步任务前端接入：
  - 教师端新增“课程资源生成”面板，使用当前选中课程 `activeClass` 作为 `course_id`，支持填写 `chapter`、`knowledge_point`，选择 `document` / `mindmap` / `reading` / `code` 资源类型。
  - 接入既有 `learningService.triggerResourceGeneration()` 与 `learningService.getTaskStatus()`，完成 `POST /resources/generate` -> `GET /tasks/{task_id}` 轮询闭环。
  - 页面展示 `processing` / `completed` / `failed` 任务状态、`task_id`、进度和失败 `error_message`；切换课程或卸载页面时清理轮询定时器。
  - 当前课程资源列表按 `activeClass` 调用 `GET /resources?course_id=...` 拉取，面板展示课程名与课程 ID，任务完成后自动刷新资源列表。
  - 教师端资源卡片可点击进入 `/resource/{id}`；`/resource/:id` 前端路由放开 `teacher` 角色。后端详情接口已有课程教师权限校验，非所属课程仍由后端 403 拦截。
  - 不新增 Client API，不直连 Agent Service，不新增 mock 数据；真实资源入库仍依赖 Backend -> Agent -> Webhook 配置。
  - `npm run lint` 通过；`npm run build` 通过，仍有既有 Vite chunk size warning；`git diff --check -- src/App.jsx src/pages/TeacherConsole.jsx WORKFLOW.md` 通过。
  - 契约状态：未修改 OpenAPI；无 Client API / Agent API 漂移。
- 2026-06-07：ResourceDetail 资源内容展示补齐：
  - `GET /resources/{id}` 后端响应新增 `content`，保留 `content_preview` 作为文字资源预览字段；`code` / `mindmap` 等类型不再只能得到空预览。
  - ResourceDetail 按资源类型渲染：`code` 使用代码块，`mindmap` 使用内容面板，`document` / `reading` 使用正文段落；无内容时展示类型化空态。
  - Backend 测试 `test_resource_detail.py` 补充 `content` 字段和 code 内容断言。
  - Client API OpenAPI 与接口说明已同步补充 `ResourceDetailItem.content`；本轮按真实资源详情能力扩展契约，不修改 Agent API。
- 2026-06-07：ResourceDetail 思维导图 Mermaid 渲染接入：
  - 新增前端依赖 `mermaid`，`mindmap` 类型资源详情会将 `content` 作为 Mermaid 源渲染为 SVG。
  - 支持去除常见 ```mermaid 代码围栏；渲染失败时保留原始内容并展示失败提示，页面不崩溃。
  - Mermaid 使用 `securityLevel: strict`，仅前端展示层变化；Backend、Client API、Agent API 均未新增字段。
- 2026-06-07：Phase A CourseCatalog + 教学班绑定实施完成：
  - Backend 新增 `CourseCatalog` / `CourseCatalogMaterial` / `CourseOffering`，并补充 MySQL migration `backend/migrations/2026-06-07-add-course-catalogs.sql`。
  - Admin 可创建/查看课程资源库、登记资料并查看知识库状态；Phase A 暂不实现真实文件上传、Qdrant ingestion 或 KG 生成。
  - 教师创建教学班时绑定 `ready` CourseCatalog；非 `ready` 不可绑定；旧 `courses` 路径保留兼容。
  - TeacherConsole 移除教师端资源生成入口；创建教学班时选择共享课程资源库。
  - AdminConsole 新增课程资源库管理入口。
  - OpenAPI 已同步新增 CourseCatalog 端点并扩展 `catalog` 字段。
  - 验证：`cd ../backend && pytest tests/test_course_catalogs.py -q` 通过 4/4；`cd ../backend && pytest tests/test_resources_async.py tests/test_teacher_class_insights.py tests/test_teacher_student_learning.py -q` 失败于 collection 阶段，关键错误为 `RuntimeError: ... Future ... attached to a different loop`，发生在 `tests/test_teacher_student_learning.py` 调用 `init_db()` 的 MySQL/aiomysql 初始化过程；`npm run lint` 通过；`npm run build` 通过，仍有既有 Vite chunk size warning；`python -m json.tool ../docs/10-client-api/Client-API.openapi.json >/tmp/client-api-openapi-check.json` 通过。
  - 契约状态：Client API 已同步，无 Agent API 变更；真实 ingestion 和 Agent 消费链路进入 Phase B/C。
- 2026-06-08：Phase B1 CourseCatalog 资料入库后端编排完成：
  - Agent Service 加固 `POST /agent/v1/knowledge/ingestions` 参数校验，拒绝空白 `catalog_id`。
  - Backend 新增 `POST /admin/course-catalogs/{catalog_id}/ingestions`，创建 `course_catalog_ingestion` AsyncTask，后台调用 Agent `/agent/v1/knowledge/ingestions`，并按 `storage_uri` 回写 `CourseCatalogMaterial` 状态、`chunk_count`、`ingested_at`、`last_error`。
  - 知识库状态接口补齐 `chunk_count`、待入库资料数、失败资料数、最近任务 ID/状态和错误信息；管理员可通过 `GET /tasks/{task_id}` 轮询课程资源库入库任务。
  - 状态策略：首次全成功为 `ready/ready`；首次部分成功为 `ready/partial`；首次全失败为 `failed/failed`；ready 资源库增量失败保持 `status=ready` 且 `knowledge_status=partial`，避免误断开教师开班绑定。
  - OpenAPI 已同步新增上传、入库触发和扩展状态字段；本轮不新增 Agent API 字段，不引入 `storage_type`，不扩展前端 Admin UI。
  - 验证：`cd ../agent_service && pytest tests/test_knowledge_ingestion_api.py -q` 通过 13/13；`cd ../backend && pytest tests/test_course_catalog_ingestion.py::test_start_catalog_ingestion_success tests/test_course_catalog_ingestion.py::test_start_catalog_ingestion_without_uploaded_materials_returns_409 tests/test_course_catalog_ingestion.py::test_incremental_ingestion_partial_failure_keeps_catalog_ready tests/test_course_catalog_ingestion.py::test_first_ingestion_partial_success_marks_catalog_ready_partial -q` 通过 4/4；`cd ../backend && pytest tests/test_course_catalog_ingestion.py tests/test_course_catalogs.py -q` 通过 23/23；`python -m json.tool ../docs/10-client-api/Client-API.openapi.json >/tmp/client-api-openapi-check.json` 通过。
- 2026-06-08：AdminConsole 课程资源库入库 UI 接入完成：
  - 新增资源库详情右侧抽屉，支持资料列表、知识库状态、批量选择文件并逐个上传、手动触发入库和 `GET /tasks/{task_id}` 轮询。
  - 新增 `taskService` 和共享 `getErrorMessage` 工具；上传请求使用 `FormData`、既有单文件上传接口、60s timeout。
  - 抽屉对资源库切换、关闭、任务轮询异常和后端状态短暂滞后做了异步保护；`partial` 按可用但不完整状态展示。
  - 不修改 OpenAPI，不直连 Agent Service，不使用 mock 数据补字段。
  - `npm run lint` 通过；`npm run build` 通过，仍有既有 Vite chunk size warning。

## 本地联调注意事项

- 2026-06-05：验证码接口 `GET /auth/captcha` 使用 `curl` 正常，但浏览器前端报 `net::ERR_FAILED 200 (OK)` / Axios `Network Error` 时，优先检查 CORS origin。Backend 当前 CORS 默认允许 `http://localhost:5173`，不包含 `http://127.0.0.1:5173`；本地验证前端需统一使用 `http://localhost:5173`，并以 `VITE_USE_MOCK=false VITE_API_BASE_URL=http://localhost:8001/api/v1 npm run dev` 启动。长期可考虑在 Backend CORS 配置中补充 `http://127.0.0.1:5173`。

## 阶段二当前结论

- 阶段二 P0 已完成，不再存在 TeacherConsole Insights 的当前阻塞项。
- TeacherConsole 班级 Insights 最小 SQL 聚合已完成，OpenAPI / Backend / Frontend 三层已对齐。
- `students` / `insights` 独立错误处理已闭环，真实模式下不再依赖旧 mock 守卫。
- AI Chat SSE 真实流已验证通过（2026-06-05），不作为当前阻塞。
- `docs/superpowers/specs/2026-06-05-phase2-gap-analysis.md` 继续作为剩余事项台账来源，但其中已关闭的 P0 项不再视为当前状态。

## 下一步建议

- 已完成（已归档，详见 git 历史）：阶段一契约疑点清理；mock 分支清理与 MS-05/MS-06/MS-08 前端入口；ResourceDetail 正文/内容、LearningPath 节点资源、StudentProfile 字段重接与切课竞态修复、教师端学生个体聚合、TeacherConsole 班级 Insights 最小 SQL 聚合（三层对齐、useMock 守卫已移除、students/insights 独立错误处理闭环）。均已轻量手工验收。
- TeacherStudentReport 深度诊断字段扩展收口（2026-06-07）：
  - `StudentLearning` 已补 `summary_text`、`knowledge_coordinates`、`mastery_breakdown` 三个真实字段；`useMock` 布局分叉已删除。
  - 本轮补齐报告切换状态重置与过期响应丢弃，避免同一路由切换学生/课程时展示旧报告。
  - `profile_summary` 已按 `UserProfile` 存在返回，`knowledge_coordinates=[]` 时仍保留 `modal_preference`；已补集成回归测试。
  - `overall_score` 真实计算口径仍待独立契约审查；前端综合评分卡显示“待定”，不再展示后端当前硬编码数值。
  - OpenAPI 无新增漂移；本轮未新增字段、未改 Agent。
- 第二轮 P1 剩余：资源生成异步任务真实联调验收；教师端已补完成后资源列表刷新和详情跳转。AdminConsole 既有契约对齐已完成，剩余停用状态持久展示和初始化账号固化等细节暂缓，不作为当前阻塞。后续执行流程见 `docs/superpowers/plans/2026-06-07-next-agent-field-integration-flow.md`。
- 第二轮 P2：累计学习时长、阅读进度/阅读时长、AIChat 活动摘要、资源偏好分布、学生学习状态流转；这些需要行为采集口径和可能的 activity 表设计，暂不直接实现。
- 资源内容质量偏低暂不作为本轮阻塞，后续应归入资源生成/资源入库质量专项。
- 资源生成 / Quiz 生成前置 CourseCatalog ready 校验已完成；下一步若继续生成链路，应优先做真实 Backend + Agent Service 联调，确认资源生成 webhook、Quiz Agent 返回和 `partial` 降级提示在真实环境下稳定。
- LearningPath 生成依赖 KG，本期明确未纳入 Phase B ready gate；后续需要单独设计 KG ready 口径和错误码，不应复用本轮 chunk-only 判定直接放行。
- 阶段二接口差距分析材料见 `docs/superpowers/specs/2026-06-05-phase2-gap-analysis.md`（19 条差距台账）。
- 轻量手工体验反馈见 `docs/superpowers/specs/2026-06-05-manual-smoke-feedback.md`，包含学生端个人信息/加入课程入口/资源预期和教师端身份展示/数据丰富度问题。
- 新增契约能力必须先走设计/审查；禁止用前端静态字段补齐未确认业务能力。
- **AGENTS.md 约束检查（2026-06-06）：** 本轮 StudentProfile 连续改动中，代码修改前审查步骤（问题分析→修改方案→用户确认→动手）和增量开发第 2 步（写/补测试）被跳过。后续每次修改代码前必须先通过审查步骤，禁止直接动手；涉及接口变更时必须补集成/E2E 测试。
- **下一步建议：** 按 AGENTS.md 增量开发流程推进 P1 剩余项，优先用真实 Backend + Agent Service 验收资源生成异步任务是否稳定从 `processing` 到 `completed`；`overall_score` 真实计算口径、AdminConsole 停用状态持久展示和管理员初始化固化均单独作为后续契约/收尾项。
