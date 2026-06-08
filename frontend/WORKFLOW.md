# Frontend Workflow

`WORKFLOW.md` 是施工日记和最近验证记录，不再承担功能主线判断职责。

阅读分工：

- 功能主线、状态和下一步：`docs/feature-ledger.md`
- 项目方向、结构和断层恢复：`docs/project-direction.md`
- 页面/API/Backend/Agent/测试证据：`docs/project-coverage-audit.md`
- 单次施工记录和最近验证：`WORKFLOW.md`

## 当前施工状态

- 当前主线以 `docs/feature-ledger.md` 为准。
- 当前最高优先级：资源生成 `/resources/generate` 真实 Backend + Agent Service webhook 联调。
- 已确认可操作能力：Admin 课程资源库创建、资料上传、触发入库向量化、任务轮询、知识库状态展示。
- 已确认后端闭环但前端无入口能力：资源生成 `/resources/generate`、Quiz 生成 `/quiz/generate`。
- 当前待设计阻塞点：LearningPath / KG ready gate。
- 当前工作区注意：`AGENTS.md` 已更新为新文档分工入口；未跟踪文件和存储产物不要混入提交。

## 最近验证

- 2026-06-09：重建功能进度主线看板：
  - 新增 `docs/feature-ledger.md`，按“用户实际能操作什么”重建开发进度账本。
  - 逐页核查真实前端调用，区分 `已可操作`、`后端闭环`、`联调待验收`、`前端无入口`、`待设计`、`暂缓`。
  - 确认资源生成和 Quiz 生成当前没有前端正式入口；Admin 资料上传和向量化已可操作。
  - 验证：占位符扫描无匹配；`git diff --check -- docs/feature-ledger.md` 通过。
  - Commit：`e7f1104 重建功能进度主线看板`。
- 2026-06-09：修正项目覆盖审计实际功能：
  - 修正 `docs/project-coverage-audit.md`，明确 Admin 界面已支持上传 `txt/md/pdf` 资料并触发 Agent 切片、embedding、Qdrant upsert，Backend 回写 `chunk_count/knowledge_status`，前端轮询刷新状态。
  - 验证：`cd ../backend && ../.venv/bin/pytest tests/test_course_catalog_ingestion.py -q` 通过 22/22；`cd ../agent_service && ../.venv/bin/pytest tests/test_knowledge_ingestion_api.py -q` 通过 13/13；`cd ../agent_service && ../.venv/bin/pytest tests/test_ingest_knowledge.py tests/test_course_knowledge_store.py -q` 通过 11/11；`npm run test:e2e -- e2e/specs.spec.js -g "Admin course catalog ingestion polling"` 通过 1/1。
  - Commit：`4c6ccf7 修正项目覆盖审计实际功能`。
- 2026-06-08：Phase B 资源生成 / Quiz 生成前置 CourseCatalog ready gate 完成：
  - Backend 新增共享 ready gate：教学班 `course_id` 解析到 `CourseOffering.catalog_id`，`CourseCatalog.status=ready` 且 `knowledge_status=ready|partial` 且 `chunk_count>0` 才允许生成。
  - `/resources/generate` 和 `/quiz/generate` 共用同一套校验；Agent payload 使用 `CourseCatalog.id`，Backend 持久化仍使用教学班 id。
  - OpenAPI、接口规范和前端 orphan service 清理已同步。
  - 验证：`cd ../backend && ../.venv/bin/pytest tests/test_course_catalog_ready_gate.py tests/test_resources_async.py tests/test_agent_integration.py::TestQuizGenerateIntegration -q` 通过 20/20；`python3 -m json.tool ../docs/10-client-api/Client-API.openapi.json` 通过；`npm run lint` 通过；`npm run build` 通过，仍有既有 Vite chunk size warning。
  - Commits：`f6b8b19`、`04107e4`、`1f8d765`、`7cf6a36`、`9778020`。
- 2026-06-08：AIChat 历史消息对象知识点白屏修复：
  - `AIChat.jsx` 对历史消息、SSE `knowledge_points` 和 `suggestions` 做可展示文本归一化，避免对象直接进入 React child。
  - 验证：`npm run test:e2e -- e2e/specs.spec.js -g "AI Chat renders historical messages"` 通过 1/1；`npm run lint` 通过；`npm run build` 通过。
  - 契约注意：OpenAPI 仍声明 `messages[].knowledge_points[]` 为 string，真实历史响应出现对象元素；前端当前只做兼容防白屏。
- 2026-06-08：CourseCatalogDrawer 入库任务轮询与状态文案修复：
  - `/tasks/{task_id}` 查询异常不再被本地改写为任务失败，继续轮询并展示“任务状态查询失败，正在重试”。
  - 资源库、知识库、资料、上传队列和任务状态按设计展示中文标签。
  - 验证：`npm run test:e2e -- e2e/specs.spec.js -g "Admin course catalog ingestion polling"` 通过；`npm run lint` 通过；`npm run build` 通过。
- 2026-06-08：AdminConsole 课程资源库入库 UI 接入完成：
  - 新增资源库详情抽屉，支持资料列表、知识库状态、批量选择文件逐个上传、手动触发入库和 `GET /tasks/{task_id}` 轮询。
  - 上传请求使用 `FormData`，不直连 Agent Service，不使用 mock 数据补字段。
  - 验证：`npm run lint` 通过；`npm run build` 通过。
- 2026-06-08：Phase B1 CourseCatalog 资料入库后端编排完成：
  - Backend 新增 `POST /admin/course-catalogs/{catalog_id}/ingestions`，创建 `course_catalog_ingestion` AsyncTask，后台调用 Agent `/agent/v1/knowledge/ingestions`，并回写资料和资源库状态。
  - 验证：Agent `test_knowledge_ingestion_api.py` 通过 13/13；Backend `test_course_catalog_ingestion.py test_course_catalogs.py` 通过 23/23；OpenAPI JSON 校验通过。

## 历史摘要

- 阶段一真实 Backend 主链路已完成 E2E 验收：登录、注册、课程、资源列表、学习路径基础展示、Quiz、AI Chat、教师基础学情、管理员基础页面。
- 阶段二已完成多项契约收口：学生端数据契约审查、P0 假展示清理、ResourceDetail 内容、LearningPath 节点资源、教师端学生聚合、AdminConsole 既有契约对齐。
- CourseCatalog 主线已完成：三表、教学班绑定、Admin 创建资源库、Admin 上传资料、Agent 入库向量化、知识库状态展示、资源/Quiz 生成前 ready gate。
- TeacherConsole 曾短暂接入资源生成 UI；CourseCatalog 主线调整后已移除。当前资源生成和 Quiz 生成都没有前端正式入口。
- 详细历史请回看 git 提交、`docs/superpowers/specs/`、`docs/superpowers/plans/` 和 `docs/project-coverage-audit.md`。

## 本地联调注意事项

- 浏览器前端如果使用真实 Backend，请优先使用 `http://localhost:5173`，避免 `127.0.0.1` 与 Backend CORS origin 不一致。
- 推荐启动方式：`VITE_USE_MOCK=false VITE_API_BASE_URL=http://localhost:8001/api/v1 npm run dev`。
- 资源生成真实联调需要 Backend、Agent Service、MySQL、Qdrant/storage、embedding provider 配置同时可用。

## 下一步指针

下一步队列不在本文件维护，统一查看 `docs/feature-ledger.md` 的“当前下一步队列”。
