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

## 能力覆盖矩阵

| 能力域 | Frontend 入口 | Client API | Backend 证据 | Agent 证据 | 数据模型 | 测试证据 | 状态 | 缺口 / 风险 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Auth 登录注册验证码 | `Login.jsx`、`Register.jsx`、`AuthContext.jsx`、`authService` | `/auth/captcha`、`/auth/login`、`/auth/register`、`/users/me`、`PUT /users/me` | `auth.py`、`users.py` | 无直接 Agent 依赖 | `user.py` | `test_auth_register_contract.py`、`test_api.py`、E2E 主链路 | 已闭环 | `PUT /users/me` 已有前端入口，后续扩展用户字段必须同步 OpenAPI。 |
| 课程列表 / 加入课程 / 教师创建教学班 | `Dashboard.jsx`、`TeacherConsole.jsx`、`JoinCourseDialog.jsx`、`CreateCourseDialog.jsx`、`CourseContext.jsx`、`courseService`、`teachingService.getClasses` | `/courses`、`/courses/join`、`/course-catalogs` | `courses.py`、`catalogs.py` | 无直接 Agent 依赖 | `course.py`、`catalog.py` | `test_course_catalogs.py`、E2E 主链路 | 已闭环 | 教师创建教学班依赖 ready CourseCatalog；旧 legacy course 仍保留兼容但不适合新生成链路。 |
| CourseCatalog 管理 | `AdminConsole.jsx`、`CourseCatalogDrawer.jsx`、`adminService` | `/admin/course-catalogs`、`/admin/course-catalogs/{catalog_id}` | `catalogs.py` | 无直接 Agent 依赖 | `catalog.py` | `test_course_catalogs.py`、Admin 入库 UI E2E | 已闭环 | Admin UI 已接 catalog 管理；非 Admin 仅通过 `/course-catalogs` 选择 ready 资源库。 |
| CourseCatalog 资料上传 / 登记 | `CourseCatalogDrawer.jsx`、`adminService.uploadCourseCatalogMaterial`、`adminService.createCourseCatalogMaterial` | `/admin/course-catalogs/{catalog_id}/materials/upload`、`/admin/course-catalogs/{catalog_id}/materials`、`GET /materials` | `catalogs.py` | 无直接 Agent 依赖 | `CourseCatalogMaterial` | `test_course_catalog_ingestion.py`、Admin 入库 UI E2E | 已闭环 | 文件存储和上传内容质量需要真实环境继续验收；不要提交上传文件或存储产物。 |
| CourseCatalog ingestion | `CourseCatalogDrawer.jsx`、`taskService.getTaskStatus` | `/admin/course-catalogs/{catalog_id}/ingestions`、`/admin/course-catalogs/{catalog_id}/knowledge-status`、`/tasks/{task_id}` | `catalogs.py`、`tasks.py`、`agent_client.py` | `api/v1/knowledge.py`、`memory/course_knowledge_ingestion.py`、`memory/course_knowledge_store.py` | `catalog.py`、`others.AsyncTask` | `test_course_catalog_ingestion.py`、Agent `test_knowledge_ingestion_api.py`、`test_ingest_knowledge.py` | 已闭环 | 真实 Qdrant / storage 环境仍需 smoke；`partial` 状态是可用但降级。 |
| 资源列表 | `Dashboard.jsx`、`learningService.getResources` | `/resources` | `resources.py` | 无直接 Agent 依赖 | `others.Resource`、`course.py` | `test_resources_async.py`、E2E 主链路 | 已闭环 | 资源质量取决于入库和生成链路；空列表应展示空态。 |
| 资源详情 / 正文展示 | `ResourceDetail.jsx`、`learningService.getResourceDetail` | `/resources/{id}` | `resources.py` | 无直接 Agent 依赖 | `others.Resource` | `test_resource_detail.py` | 已闭环 | Mermaid mindmap 渲染为前端展示能力；资源内容本身质量不由前端保证。 |
| 资源生成 | 当前无正式前端入口；曾有 orphan service 已删除 | `/resources/generate` | `resources.py`、`course_catalog_gate.py`、`agent_client.py` | `api/v1/resources.py`、`agents/resources_workflow.py`、`agents/resources.py` | `others.AsyncTask`、`others.Resource`、`catalog.py` | `test_resources_async.py`、`test_course_catalog_ready_gate.py`、Agent `test_resources_workflow.py` | 部分闭环 | Backend ready gate 已完成；还需真实 Backend + Agent webhook 联调，确认 catalog id 检索和资源落库。 |
| Quiz 获取题目 / 提交 / 结果 / 历史 | `Quiz.jsx`、`PracticeResult.jsx`、`quizService` | `/quiz/questions`、`/quiz/submit`、`/quiz/result`、`/quiz/history` | `quiz.py`、`quiz_service.py` | `/assessment/evaluate` 用于后台诊断 | `quiz.py`、`others.Evaluation` | `test_quiz_async.py`、`test_agent_integration.py`、E2E 主链路 | 已闭环 | `/assessment/evaluate` 后台失败不阻塞提交结果；诊断质量由 Agent 专项保证。 |
| Quiz 生成 | 当前无正式前端入口 | `/quiz/generate` | `quiz.py`、`quiz_service.py`、`course_catalog_gate.py` | `api/v1/assessment.py`、`agents/assessment.py`、`agents/assessment_react.py` | `quiz.py`、`others.AsyncTask`、`catalog.py` | `test_agent_integration.py::TestQuizGenerateIntegration`、`test_course_catalog_ready_gate.py`、Agent `test_assessment_agent.py` | 部分闭环 | Backend ready gate 已完成；还需真实 Agent 返回质量和题目落库 smoke。 |
| AI Chat SSE | `AIChat.jsx`、`chatService.streamChat` | `/tutoring/chat`、`/tutoring/conversations`、`/tutoring/conversations/{id}` | `tutoring.py`、`agent_client.py` | `api/v1/tutoring.py`、`agents/tutoring*.py`、`memory/tutoring_retrieval.py` | `conversation.py` | `test_tutoring_privacy.py`、Agent `test_tutoring_api.py`、E2E AIChat 历史消息回归 | 已闭环 | 真实历史响应曾出现 `knowledge_points[]` 元素类型漂移，前端已做防白屏兼容；OpenAPI 元素类型仍需后续契约审查。 |
| LearningPath 展示 / 刷新 | `LearningPath.jsx`、`learningService.getLearningPath`、`refreshLearningPath` | `/learning-path`、`/learning-path/refresh` | `learning_path.py`、`agent_client.py` | `api/v1/learning_path.py`、`agents/learning_path.py` | `others.LearningPath`、`others.LearningPathNode` | `test_node_resources.py`、`test_refresh_async.py`、Agent `test_learning_path_api.py` | 部分闭环 | LearningPath 依赖 KG，本期未纳入 CourseCatalog ready gate；需要单独设计 KG ready 口径。 |
| LearningPath 节点资源 | `LearningPath.jsx`、`learningService.getNodeResources` | `/learning-path/nodes/{node_id}/resources` | `learning_path.py` | 无直接 Agent 调用 | `others.Resource`、`others.LearningPathNode` | `test_node_resources.py` | 已闭环 | 依赖资源与节点知识点匹配质量。 |
| 学生画像 Profile | `StudentProfile.jsx`、`profileService.getStudentProfile`、`refreshProfile` | `/profile`、`/profile/refresh`、`/profile/initialize` | `profile.py`、`agent_client.py` | `api/v1/profile.py`、`agents/profile.py` | `others.UserProfile`、`user.py` | `test_refresh_async.py`、Agent `test_profile_agent.py` | 部分闭环 | Profile 刷新链路存在，但画像质量和字段扩展需继续走契约审查。 |
| 学习效果 Evaluation | `LearningEffects.jsx`、`profileService.getLearningEffects`、`learningService.refreshEvaluation` | `/evaluation`、`/evaluation/refresh` | `evaluation.py`、`agent_client.py` | `api/v1/evaluation.py`、`agents/evaluation.py` | `others.Evaluation` | `test_refresh_async.py`、Agent `test_evaluation_agent.py` | 部分闭环 | 前端仅展示现有契约能力；累计学习时长、趋势等仍是阶段二缺口。 |
| 教师学生列表 / 班级洞察 | `TeacherConsole.jsx`、`teachingService` | `/teaching/classes/{class_id}/students`、`/teaching/classes/{class_id}/insights` | `teaching.py` | 无直接 Agent 调用 | `course.py`、`user.py`、`others.*` | `test_teacher_class_insights.py`、E2E 主链路 | 已闭环 | 复杂排名、覆盖率、动力指数等仍需契约设计，不应前端补造。 |
| 教师学生深度报告 | `TeacherStudentReport.jsx`、`teachingService.getStudentReport` | `/teaching/classes/{class_id}/students/{student_id}/learning` | `teaching.py` | 间接依赖 Profile/Evaluation/Quiz 数据 | `others.UserProfile`、`others.Evaluation`、`quiz.py` | `test_teacher_student_learning.py` | 部分闭环 | `overall_score` 真实计算口径仍待审查；前端不展示硬编码评分。 |
| Admin 用户管理 | `AdminConsole.jsx`、`adminService` | `/admin/users`、`/admin/users/{user_id}` | `admin.py` | 无直接 Agent 依赖 | `user.py` | E2E 管理员主链路、后续可补专测 | 部分闭环 | 用户停用状态跨页面持久展示需要 API 返回 `is_active/status`；当前契约未覆盖。 |
| Admin 日志 | `AdminConsole.jsx`、`adminService.getAgentLogs`、`getSystemLogs` | `/admin/logs/agent`、`/admin/logs/operations` | `admin.py` | Agent 日志为展示来源之一 | `others.OperationLog`、`others.AgentLog` | E2E 管理员主链路 | 部分闭环 | 真实日志来源和筛选维度仍较基础。 |
| AsyncTask 查询 | `CourseCatalogDrawer.jsx`、`taskService` | `/tasks/{task_id}` | `tasks.py` | 无直接 Agent 依赖 | `others.AsyncTask` | Admin 入库 UI E2E、生成相关后端测试 | 已闭环 | 前端只在已接 UI 中使用；资源/Quiz 生成暂无前端 UI。 |
| Agent webhook | 无前端入口 | `/webhooks/agent` | `webhooks.py` | Agent Service 长任务回调 | `others.AsyncTask`、`others.Resource` | `test_resources_async.py`、生成链路 smoke 待补 | 部分闭环 | 资源生成真实 webhook 仍是下一步高优先级联调。 |
| Memory 压缩 | 无前端入口 | 无 Client API | 无 Backend Client route | `api/v1/memory.py`、`agents/memory.py` | Agent memory store | Agent `test_memory_agent.py`、`test_user_memory_store.py` | 后端/Agent 已有但前端未接 | 属 Agent 内部能力，不应直接进入前端契约。 |
| KG 生成 | 无前端入口 | 当前 Client API 未形成正式链路 | `test_generate_kg.py` 提示历史能力 | Agent course knowledge store / ingestion | Qdrant course knowledge | `test_generate_kg.py`、Agent knowledge tests | 缺口/风险 | LearningPath/KG ready gate 尚未设计；需要单独专项。 |

## Client API 覆盖概览

当前 OpenAPI path 已覆盖以下大类：

- Auth / Users：`/auth/*`、`/users/me`
- Courses / Catalogs：`/courses`、`/courses/join`、`/course-catalogs`、`/admin/course-catalogs*`
- Resources：`/resources`、`/resources/{id}`、`/resources/generate`
- Quiz：`/quiz/questions`、`/quiz/submit`、`/quiz/result`、`/quiz/history`、`/quiz/generate`
- Learning：`/learning-path`、`/learning-path/refresh`、`/learning-path/nodes/{node_id}/resources`
- Profile / Evaluation：`/profile*`、`/evaluation*`
- Teaching：`/teaching/classes/{class_id}/*`
- Admin：`/admin/users*`、`/admin/logs/*`
- Async / Webhook：`/tasks/{task_id}`、`/webhooks/agent`
- Tutoring：`/tutoring/chat`、`/tutoring/conversations*`

主要未被前端 UI 接入但已在 Client API 中声明的生成入口：

- `/resources/generate`
- `/quiz/generate`
- `/profile/initialize`

这些入口当前不应靠临时 UI 硬接；必须先完成真实联调或明确产品交互设计。

## Backend 到 Agent Service 调用点

| Backend 调用点 | Agent API | 当前用途 | 主要风险 |
| --- | --- | --- | --- |
| `catalogs.py` | `/agent/v1/knowledge/ingestions` | CourseCatalog 资料入库 | 真实存储/Qdrant 环境、partial 状态处理 |
| `resources.py` | `/agent/v1/resources/generate` | 资源生成 | webhook 回调和资源质量需要真实联调 |
| `quiz.py` | `/agent/v1/assessment/generate-questions` | Quiz 生成 | 题目质量、catalog id 检索、教学班 id 落库 |
| `quiz_service.py` | `/agent/v1/assessment/evaluate` | Quiz 提交后的诊断 | 后台失败不阻塞提交，诊断质量需专项 |
| `tutoring.py` | `/agent/v1/tutoring/chat` | AI Chat SSE | SSE 事件契约和历史消息类型漂移 |
| `learning_path.py` | `/agent/v1/learning-path/generate` | 学习路径刷新 | KG ready 口径未收口 |
| `evaluation.py` | `/agent/v1/evaluation/generate` | 学习效果刷新 | 指标口径和趋势类字段仍需设计 |
| `profile.py` | `/agent/v1/profile/generate` | 学生画像刷新 | 字段扩展需同步契约 |

## 测试覆盖概览

Backend 当前测试证据：

- Auth：`test_auth_register_contract.py`、`test_api.py`
- CourseCatalog：`test_course_catalogs.py`
- Ingestion：`test_course_catalog_ingestion.py`
- Ready gate：`test_course_catalog_ready_gate.py`
- Resources：`test_resources_async.py`、`test_resource_detail.py`
- Quiz：`test_quiz_async.py`、`test_agent_integration.py`
- LearningPath：`test_node_resources.py`、`test_refresh_async.py`
- Teaching：`test_teacher_class_insights.py`、`test_teacher_student_learning.py`
- AI Chat privacy：`test_tutoring_privacy.py`

Frontend 当前 E2E：

- `e2e/specs.spec.js` 覆盖阶段一主链路和若干回归场景。

Agent Service 当前测试证据：

- Knowledge ingestion：`test_knowledge_ingestion_api.py`、`test_ingest_knowledge.py`、`test_course_knowledge_ingestion.py`
- Resources：`test_resources_workflow.py`、`test_resources_agent.py`、`test_resources_critic.py`
- Assessment：`test_assessment_agent.py`、`test_assessment_quality.py`、`test_assessment_knowledge_guard.py`
- Tutoring：`test_tutoring_api.py`、`test_tutoring_retrieval.py`、`test_tutoring_react*.py`
- LearningPath：`test_learning_path_api.py`、`test_learning_path_agent.py`
- Profile / Evaluation：`test_profile_agent.py`、`test_evaluation_agent.py`
- Readiness / health / schema：`test_readiness.py`、`test_health.py`、`test_schema_contracts.py`、`test_openapi_alignment.py`

## 覆盖结论

`docs/project-direction.md` 覆盖了当前项目的主结构和方向，但不能替代本审计表。按当前证据，项目覆盖状态如下：

- 主链路已闭环：Auth、课程、CourseCatalog 管理、资料入库、资源列表/详情、基础 Quiz、AI Chat、教师基础学情、AsyncTask 查询。
- 生成链路部分闭环：资源生成和 Quiz 生成已有 ready gate、契约和后端测试，但缺真实 Backend + Agent Service 联调证据。
- Agent 依赖链路部分闭环：Profile、Evaluation、LearningPath 有 Backend/Agent 调用和测试，但部分页面指标和 KG ready 口径尚未收口。
- 阶段二页面能力仍有缺口：学习时长、阅读进度、AIChat 活动摘要、资源偏好分布、复杂教师/Admin 指标不应直接实现。
- 高风险下一步：资源生成 webhook 真实闭环、Quiz 生成真实闭环、LearningPath/KG ready gate 设计。

## 下一轮审计动作

1. 给 `/resources/generate` 做真实环境 smoke，记录 task、webhook、resources 落库和前端展示证据。
2. 给 `/quiz/generate` 做真实环境 smoke，记录 Agent payload、题目落库和 `/tasks/{task_id}` 结果。
3. 设计并审计 LearningPath/KG ready gate，避免资料缺失时泛化生成学习路径。
4. 为 Admin 用户停用状态补契约审查，决定是否扩展 `GET /admin/users`。
5. 若新增页面指标，先在本表追加一行，再进入 spec 和 plan。
