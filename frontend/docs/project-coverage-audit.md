# EDUagent Project Coverage Audit

本文档用于证明 `docs/project-direction.md` 是否覆盖当前项目结构。它不是需求清单，也不是完成承诺；它记录当前代码和文档中能找到的证据、覆盖状态和缺口。

审计日期：2026-06-08

## 审计口径

状态定义：

- `已闭环`：Frontend、Client API、Backend、数据模型、测试或 E2E 至少形成一条可验证链路。
- `部分闭环`：主链路可用，但仍有真实联调、数据质量、契约细节或 UI 接入缺口。
- `后端/Agent 已有但前端未接`：Backend 或 Agent Service 有能力，Frontend 当前没有正式入口。
- `设计边界内暂不做`：已明确不在当前阶段实现。
- `缺口/风险`：代码、契约或测试存在明显断点，需要后续处理。

本次审计使用的证据：

- Frontend 页面：`src/pages/`
- Frontend service：`src/api/services/`
- Frontend E2E：`e2e/specs.spec.js`
- Backend route：`../backend/app/api/v1/`
- Backend service：`../backend/app/services/`
- Backend model：`../backend/app/models/`
- Backend tests：`../backend/tests/`
- Agent Service API：`../agent_service/api/v1/`
- Agent Service tests：`../agent_service/tests/`
- Client API：`../docs/10-client-api/Client-API.openapi.json`
- Agent API：`../docs/20-agent-api/Agent-Service.openapi.json`

## 实际功能链路核查

本节记录当前已经开发出来、可以从用户操作路径理解的能力。它优先于单纯文件清单。

### Admin 课程资源库导入与向量化

当前已经实现“管理员界面导入资料并向量化到课程知识库”的链路：

1. Admin 在 `AdminConsole.jsx` 打开课程资源库详情抽屉 `CourseCatalogDrawer.jsx`。
2. 抽屉通过 `adminService.getCourseCatalogMaterials()` 和 `adminService.getCourseCatalogStatus()` 展示资料列表、资料数、知识切片数、待入库资料数、失败资料数、资源库状态和知识库状态。
3. Admin 可选择本地 `txt`、`md`、`pdf` 文件上传；前端调用 `POST /admin/course-catalogs/{catalog_id}/materials/upload`。
4. Backend `catalogs.py` 将文件保存到 `COURSE_CATALOG_STORAGE_ROOT` 下，创建 `CourseCatalogMaterial`，状态为 `uploaded`。
5. Admin 点击“开始入库”；前端调用 `POST /admin/course-catalogs/{catalog_id}/ingestions`。
6. Backend 创建 `course_catalog_ingestion` 类型 `AsyncTask`，把待入库资料状态改为 `ingesting`，后台调用 Agent Service `/agent/v1/knowledge/ingestions`。
7. Agent Service 校验 `catalog_id` 和安全相对 `storage_uri`，读取 `txt/md/pdf`，切片后调用 embedding provider，再通过 `QdrantCourseKnowledgeStore.upsert_chunks()` 写入课程知识库 collection。
8. Backend 根据 Agent 返回结果回写每份资料的 `status`、`chunk_count`、`ingested_at`、`last_error`，同时回写 CourseCatalog 的 `status`、`knowledge_status`、`chunk_count`、`last_ingestion_task_id`、`last_ingestion_status`、`last_error`。
9. 前端通过 `taskService.getTaskStatus()` 轮询 `/tasks/{task_id}`；任务完成后刷新资料列表和知识库状态，界面可看到 `chunk_count` 和 ready/partial/failed 状态。

本链路的边界：

- 自动化测试已覆盖 UI 轮询、Backend 上传/入库状态回写、Agent ingestion API、embedding/upsert 调用逻辑。
- 部署级 live smoke 仍建议执行，用于确认本机或服务器上的真实 Backend、Agent Service、Qdrant、文件存储路径和 embedding provider 配置同时可用。
- “仍建议 live smoke”不是指功能未实现，而是部署环境验收。

## 能力覆盖矩阵

| 能力域 | Frontend 入口 | Client API | Backend 证据 | Agent 证据 | 数据模型 | 测试证据 | 状态 | 缺口 / 风险 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Auth 登录注册验证码 | `Login.jsx`、`Register.jsx`、`AuthContext.jsx`、`authService` | `/auth/captcha`、`/auth/login`、`/auth/register`、`/users/me`、`PUT /users/me` | `auth.py`、`users.py` | 无直接 Agent 依赖 | `user.py` | `test_auth_register_contract.py`、`test_api.py`、E2E 主链路 | 已闭环 | `PUT /users/me` 已有前端入口，后续扩展用户字段必须同步 OpenAPI。 |
| 课程列表 / 加入课程 / 教师创建教学班 | `Dashboard.jsx`、`TeacherConsole.jsx`、`JoinCourseDialog.jsx`、`CreateCourseDialog.jsx`、`CourseContext.jsx`、`courseService`、`teachingService.getClasses` | `/courses`、`/courses/join`、`/course-catalogs` | `courses.py`、`catalogs.py` | 无直接 Agent 依赖 | `course.py`、`catalog.py` | `test_course_catalogs.py`、E2E 主链路 | 已闭环 | 教师创建教学班依赖 ready CourseCatalog；旧 legacy course 仍保留兼容但不适合新生成链路。 |
| CourseCatalog 管理 | `AdminConsole.jsx`、`CourseCatalogDrawer.jsx`、`adminService` | `/admin/course-catalogs`、`/admin/course-catalogs/{catalog_id}` | `catalogs.py` | 无直接 Agent 依赖 | `catalog.py` | `test_course_catalogs.py`、Admin 入库 UI E2E | 已闭环 | Admin UI 已接 catalog 管理；非 Admin 仅通过 `/course-catalogs` 选择 ready 资源库。 |
| CourseCatalog 资料上传 / 登记 | `CourseCatalogDrawer.jsx`、`adminService.uploadCourseCatalogMaterial`、`adminService.createCourseCatalogMaterial` | `/admin/course-catalogs/{catalog_id}/materials/upload`、`/admin/course-catalogs/{catalog_id}/materials`、`GET /materials` | `catalogs.py` | 无直接 Agent 依赖 | `CourseCatalogMaterial` | `test_course_catalog_ingestion.py`、Admin 入库 UI E2E | 已闭环 | 管理员界面已支持选择 `txt/md/pdf` 上传；不要提交上传文件或存储产物。 |
| CourseCatalog ingestion / 向量化 | `CourseCatalogDrawer.jsx`、`taskService.getTaskStatus` | `/admin/course-catalogs/{catalog_id}/ingestions`、`/admin/course-catalogs/{catalog_id}/knowledge-status`、`/tasks/{task_id}` | `catalogs.py`、`tasks.py`、`agent_client.py` | `api/v1/knowledge.py`、`tools/ingest_knowledge.py`、`memory/course_knowledge_ingestion.py`、`memory/course_knowledge_store.py` | `catalog.py`、`others.AsyncTask` | `test_course_catalog_ingestion.py`、Agent `test_knowledge_ingestion_api.py`、`test_ingest_knowledge.py`、`test_course_knowledge_store.py`、Admin 入库 UI E2E | 已闭环 | 功能已实现：上传资料后可触发 Agent 切片、embedding、Qdrant upsert，并回写 `chunk_count/knowledge_status`；部署级 live smoke 仍建议做。 |
| 资源列表 | `Dashboard.jsx`、`learningService.getResources` | `/resources` | `resources.py` | 无直接 Agent 依赖 | `others.Resource`、`course.py` | `test_resources_async.py`、E2E 主链路 | 已闭环 | 资源质量取决于入库和生成链路；空列表应展示空态。 |
| 资源详情 / 正文展示 | `ResourceDetail.jsx`、`learningService.getResourceDetail` | `/resources/{id}` | `resources.py` | 无直接 Agent 依赖 | `others.Resource` | `test_resource_detail.py` | 已闭环 | Mermaid mindmap 渲染为前端展示能力；资源内容本身质量不由前端保证。 |
| 资源生成 | 当前无正式前端入口；曾有 orphan service 已删除 | `/resources/generate` | `resources.py`、`course_catalog_gate.py`、`agent_client.py` | `api/v1/resources.py`、`agents/resources_workflow.py`、`agents/resources.py` | `others.AsyncTask`、`others.Resource`、`catalog.py` | `test_resources_async.py`、`test_course_catalog_ready_gate.py`、Agent `test_resources_workflow.py` | 前端不接入 / 历史接口 | 当前前端契约作废 / 不接入，教师端不提供生成资源入口；保留为后端内部能力或废弃候选背景。 |
| Quiz 获取题目 / 提交 / 结果 / 历史 | `Quiz.jsx`、`PracticeResult.jsx`、`quizService` | `/quiz/questions`、`/quiz/submit`、`/quiz/result`、`/quiz/history` | `quiz.py`、`quiz_service.py` | `/assessment/evaluate` 用于后台诊断 | `quiz.py`、`others.Evaluation` | `test_quiz_async.py`、`test_agent_integration.py`、E2E 主链路 | 已闭环 | `/assessment/evaluate` 后台失败不阻塞提交结果；诊断质量由 Agent 专项保证。 |
| Quiz 生成 | 当前无正式前端入口 | `/quiz/generate` | `quiz.py`、`quiz_service.py`、`course_catalog_gate.py` | `api/v1/assessment.py`、`agents/assessment.py`、`agents/assessment_react.py` | `quiz.py`、`others.AsyncTask`、`catalog.py` | `test_agent_integration.py::TestQuizGenerateIntegration`、`test_course_catalog_ready_gate.py`、Agent `test_assessment_agent.py` | 前端不接入 / 历史接口 | 当前前端契约作废 / 不接入，练习页不引导触发生题；保留为后端内部能力或废弃候选背景。 |
| AI Chat SSE | `AIChat.jsx`、`chatService.streamChat` | `/tutoring/chat`、`/tutoring/conversations`、`/tutoring/conversations/{id}` | `tutoring.py`、`agent_client.py` | `api/v1/tutoring.py`、`agents/tutoring*.py`、`memory/tutoring_retrieval.py` | `conversation.py` | `test_tutoring_privacy.py`、Agent `test_tutoring_api.py`、E2E AIChat 历史消息回归 | 已闭环 | 真实历史响应曾出现 `knowledge_points[]` 元素类型漂移，前端已做防白屏兼容；OpenAPI 元素类型仍需后续契约审查。 |
| LearningPath 展示 / 刷新 | `LearningPath.jsx`、`learningService.getLearningPath`、`refreshLearningPath` | `/learning-path`、`/learning-path/refresh` | `learning_path.py`、`agent_client.py` | `api/v1/learning_path.py`、`agents/learning_path.py` | `others.LearningPath`、`others.LearningPathNode` | `test_node_resources.py`、`test_refresh_async.py`、Agent `test_learning_path_api.py` | 部分闭环 | LearningPath 依赖 KG，本期未纳入 CourseCatalog ready gate；需要单独设计 KG ready 口径。 |
| LearningPath 节点资源 | `LearningPath.jsx`、`learningService.getNodeResources` | `/learning-path/nodes/{node_id}/resources` | `learning_path.py` | 无直接 Agent 调用 | `others.Resource`、`others.LearningPathNode` | `test_node_resources.py` | 已闭环 | 依赖资源与节点知识点匹配质量。 |
| 学生画像 Profile | `StudentProfile.jsx`、`profileService.getStudentProfile`、`refreshProfile` | `/profile`、`/profile/refresh`、`/profile/initialize` | `profile.py`、`agent_client.py` | `api/v1/profile.py`、`agents/profile.py` | `others.UserProfile`、`user.py` | `test_refresh_async.py`、Agent `test_profile_agent.py` | 部分闭环 | Profile 刷新链路存在，但画像质量和字段扩展需继续走契约审查。 |
| 学习效果 Evaluation | `LearningEffects.jsx`、`profileService.getLearningEffects`、`learningService.refreshEvaluation` | `/evaluation`、`/evaluation/refresh` | `evaluation.py`、`agent_client.py` | `api/v1/evaluation.py`、`agents/evaluation.py` | `others.Evaluation` | `test_refresh_async.py`、Agent `test_evaluation_agent.py` | 部分闭环 | 前端仅展示现有契约能力；累计学习时长、趋势等仍是阶段二缺口。 |
| 教师学生列表 / 班级洞察 | `TeacherConsole.jsx`、`teachingService` | `/teaching/classes/{class_id}/students`、`/teaching/classes/{class_id}/insights` | `teaching.py` | 无直接 Agent 调用 | `course.py`、`user.py`、`others.*` | `test_teacher_class_insights.py`、E2E 主链路 | 已闭环 | 复杂排名、覆盖率、动力指数等仍需契约设计，不应前端补造。 |
| 教师学生深度报告 | `TeacherStudentReport.jsx`、`teachingService.getStudentReport` | `/teaching/classes/{class_id}/students/{student_id}/learning` | `teaching.py` | 间接依赖 Profile/Evaluation/Quiz 数据 | `others.UserProfile`、`others.Evaluation`、`quiz.py` | `test_teacher_student_learning.py` | 部分闭环 | `overall_score` 真实计算口径仍待审查；前端不展示硬编码评分。 |
| Admin 用户管理 | `AdminConsole.jsx`、`adminService` | `/admin/users`、`/admin/users/{user_id}` | `admin.py` | 无直接 Agent 依赖 | `user.py` | E2E 管理员主链路、后续可补专测 | 部分闭环 | 用户停用状态跨页面持久展示需要 API 返回 `is_active/status`；当前契约未覆盖。 |
| Admin 日志 | `AdminConsole.jsx`、`adminService.getAgentLogs`、`getSystemLogs` | `/admin/logs/agent`、`/admin/logs/operations` | `admin.py` | Agent 日志为展示来源之一 | `others.OperationLog`、`others.AgentLog` | E2E 管理员主链路 | 部分闭环 | 真实日志来源和筛选维度仍较基础。 |
| AsyncTask 查询 | `CourseCatalogDrawer.jsx`、`taskService` | `/tasks/{task_id}` | `tasks.py` | 无直接 Agent 依赖 | `others.AsyncTask` | Admin 入库 UI E2E、生成相关后端测试 | 已闭环 | 前端只在已接 UI 中使用；当前用于 Admin CourseCatalog 入库轮询，不作为资源/Quiz 生成入口。 |
| Agent webhook | 无前端入口 | `/webhooks/agent` | `webhooks.py` | Agent Service 长任务回调 | `others.AsyncTask`、`others.Resource` | `test_resources_async.py`、历史生成链路 smoke 待补 | 后端内部 / 非前端主线 | Agent webhook 不再作为前端下一步验收目标，除非后续产品重新定义生成链路。 |
| Memory 压缩 | 无前端入口 | 无 Client API | 无 Backend Client route | `api/v1/memory.py`、`agents/memory.py` | Agent memory store | Agent `test_memory_agent.py`、`test_user_memory_store.py` | 后端/Agent 已有但前端未接 | 属 Agent 内部能力，不应直接进入前端契约。 |
| KG 生成 | 无前端入口 | 当前 Client API 未形成正式链路 | `test_generate_kg.py` 提示历史能力 | Agent course knowledge store / ingestion | Qdrant course knowledge | `test_generate_kg.py`、Agent knowledge tests | 缺口/风险 | LearningPath/KG ready gate 尚未设计；需要单独专项。 |

## Client API 覆盖概览

当前 OpenAPI path 已覆盖以下大类：

- Auth / Users：`/auth/*`、`/users/me`
- Courses / Catalogs：`/courses`、`/courses/join`、`/course-catalogs`、`/admin/course-catalogs*`
- Resources：`/resources`、`/resources/{id}`；`/resources/generate` 为前端作废 / 不接入的历史接口
- Quiz：`/quiz/questions`、`/quiz/submit`、`/quiz/result`、`/quiz/history`；`/quiz/generate` 为前端作废 / 不接入的历史接口
- Learning：`/learning-path`、`/learning-path/refresh`、`/learning-path/nodes/{node_id}/resources`
- Profile / Evaluation：`/profile*`、`/evaluation*`
- Teaching：`/teaching/classes/{class_id}/*`
- Admin：`/admin/users*`、`/admin/logs/*`
- Async / Webhook：`/tasks/{task_id}`、`/webhooks/agent`
- Tutoring：`/tutoring/chat`、`/tutoring/conversations*`

主要未被前端 UI 接入但已在 Client API 中声明的历史 / 作废入口：

- `/resources/generate`：当前前端契约作废 / 不接入，教师端不得新增生成资源入口。
- `/quiz/generate`：当前前端契约作废 / 不接入，练习页不得引导触发生题。
- `/profile/initialize`

这些入口当前不应靠临时 UI 硬接；如需恢复，必须先重新完成产品契约审查。

## Backend 到 Agent Service 调用点

| Backend 调用点 | Agent API | 当前用途 | 主要风险 |
| --- | --- | --- | --- |
| `catalogs.py` | `/agent/v1/knowledge/ingestions` | CourseCatalog 资料入库 | 真实存储/Qdrant 环境、partial 状态处理 |
| `resources.py` | `/agent/v1/resources/generate` | 历史资源生成 / 后端内部能力候选 | 当前不作为前端下一步验收目标；如需恢复需重新定义生成产品链路 |
| `quiz.py` | `/agent/v1/assessment/generate-questions` | 历史 Quiz 生成 / 后端内部能力候选 | 当前不作为前端下一步验收目标；题目质量和落库链路需等产品重新定义后再验收 |
| `quiz_service.py` | `/agent/v1/assessment/evaluate` | Quiz 提交后的诊断 | 后台失败不阻塞提交，诊断质量需专项 |
| `tutoring.py` | `/agent/v1/tutoring/chat` | AI Chat SSE | SSE 事件契约和历史消息类型漂移 |
| `learning_path.py` | `/agent/v1/learning-path/generate` | 学习路径刷新 | KG ready 口径未收口 |
| `evaluation.py` | `/agent/v1/evaluation/generate` | 学习效果刷新 | 指标口径和趋势类字段仍需设计 |
| `profile.py` | `/agent/v1/profile/generate` | 学生画像刷新 | 字段扩展需同步契约 |

## 测试覆盖概览

Backend 当前测试证据：

- Auth：`test_auth_register_contract.py`、`test_api.py`
- CourseCatalog：`test_course_catalogs.py`
- Ingestion：`test_course_catalog_ingestion.py`，本轮验证 22/22 通过
- Ready gate：`test_course_catalog_ready_gate.py`
- Resources：`test_resources_async.py`、`test_resource_detail.py`
- Quiz：`test_quiz_async.py`、`test_agent_integration.py`
- LearningPath：`test_node_resources.py`、`test_refresh_async.py`
- Teaching：`test_teacher_class_insights.py`、`test_teacher_student_learning.py`
- AI Chat privacy：`test_tutoring_privacy.py`

Frontend 当前 E2E：

- `e2e/specs.spec.js` 覆盖阶段一主链路和若干回归场景。

Agent Service 当前测试证据：

- Knowledge ingestion：`test_knowledge_ingestion_api.py`、`test_ingest_knowledge.py`、`test_course_knowledge_store.py`、`test_course_knowledge_ingestion.py`；本轮 `test_knowledge_ingestion_api.py` 13/13 通过，`test_ingest_knowledge.py test_course_knowledge_store.py` 11/11 通过
- Resources：`test_resources_workflow.py`、`test_resources_agent.py`、`test_resources_critic.py`
- Assessment：`test_assessment_agent.py`、`test_assessment_quality.py`、`test_assessment_knowledge_guard.py`
- Tutoring：`test_tutoring_api.py`、`test_tutoring_retrieval.py`、`test_tutoring_react*.py`
- LearningPath：`test_learning_path_api.py`、`test_learning_path_agent.py`
- Profile / Evaluation：`test_profile_agent.py`、`test_evaluation_agent.py`
- Readiness / health / schema：`test_readiness.py`、`test_health.py`、`test_schema_contracts.py`、`test_openapi_alignment.py`

本轮额外核查命令：

- `cd ../backend && ../.venv/bin/pytest tests/test_course_catalog_ingestion.py -q`：22/22 通过。
- `cd ../agent_service && ../.venv/bin/pytest tests/test_knowledge_ingestion_api.py -q`：13/13 通过。
- `cd ../agent_service && ../.venv/bin/pytest tests/test_ingest_knowledge.py tests/test_course_knowledge_store.py -q`：11/11 通过。
- `npm run test:e2e -- e2e/specs.spec.js -g "Admin course catalog ingestion polling"`：1/1 通过。

## 覆盖结论

`docs/project-direction.md` 覆盖了当前项目的主结构和方向，但不能替代本审计表。按当前证据，项目覆盖状态如下：

- 主链路已闭环：Auth、课程、CourseCatalog 管理、管理员资料上传、CourseCatalog 资料入库和向量化、资源列表/详情、基础 Quiz、AI Chat、教师基础学情、AsyncTask 查询。
- 生成链路已降级为前端不接入 / 历史接口：资源生成和 Quiz 生成虽已有 ready gate、契约和后端测试背景，但不再作为当前前端主线。
- Agent 依赖链路部分闭环：Profile、Evaluation、LearningPath 有 Backend/Agent 调用和测试，但部分页面指标和 KG ready 口径尚未收口。
- 阶段二页面能力仍有缺口：学习时长、阅读进度、AIChat 活动摘要、资源偏好分布、复杂教师/Admin 指标不应直接实现。
- 高风险下一步：Admin CourseCatalog 入库部署级验收、教师绑定 ready CourseCatalog 创建教学班验收、学生 / 教师消费入库内容的产品口径、LearningPath/KG ready gate 设计。

## 下一轮审计动作

1. 做 Admin CourseCatalog 上传 / 入库部署级验收，记录真实 Backend、Agent Service、MySQL、Qdrant/storage/provider 配置下的任务和知识库状态证据。
2. 做教师绑定 ready CourseCatalog 创建教学班验收，确认学生加入、资源列表、基础练习和教师端课程上下文正常。
3. 设计学生 / 教师如何消费 CourseCatalog 入库后的资源与知识库内容，避免用历史生成接口补 UI。
4. 设计并审计 LearningPath/KG ready gate，避免资料缺失时泛化生成学习路径。
5. 为 Admin 用户停用状态补契约审查，决定是否扩展 `GET /admin/users`。
