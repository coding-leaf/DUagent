# Frontend Workflow

`WORKFLOW.md` 是施工日记和最近验证记录，不再承担功能主线判断职责。

阅读分工：

- 功能主线、状态和下一步：`docs/feature-ledger.md`
- 项目方向、结构和断层恢复：`docs/project-direction.md`
- 页面/API/Backend/Agent/测试证据：`docs/project-coverage-audit.md`
- 单次施工记录和最近验证：`WORKFLOW.md`

## 当前施工状态

- 当前主线以 `docs/feature-ledger.md` 为准。
- 当前最高优先级：学生 / 教师消费 CourseCatalog 入库内容的产品口径设计；LearningPath / KG ready gate 设计。
- 已确认可操作能力：Admin 课程资源库创建、资料上传、触发入库向量化、任务轮询、知识库状态展示、按资源库触发学习资源生成、生成资源列表、资料/资源软删除。
- 当前前端契约作废 / 不接入能力：资源生成 `/resources/generate`、Quiz 生成 `/quiz/generate`；教师端不提供生成资源入口，练习页不提供触发生题入口。
- 当前待设计阻塞点：LearningPath / KG ready gate。
- 当前工作区注意：`AGENTS.md` 已更新为新文档分工入口；未跟踪文件和存储产物不要混入提交。

## 最近验证

- 2026-06-10：KG-Resource 对齐探针真实盘点与校准执行：
  - 已新增只读 KG-Resource 对齐探针 service/CLI，用于盘点 catalog/course 数据、导出 KG/LearningPath 节点候选、汇总人工标注；未新增 API route，未修改前端页面，未修改 OpenAPI。
  - 当前服务状态：Backend `8001`、Agent Service `8002`、Frontend `5173` 均返回 200；MySQL、Qdrant 容器在线。探针 CLI 本身只读 MySQL，不调用 Agent Service。
  - 数据底盘盘点输出：`/tmp/kg-resource-probe/inventory.json`，共 10 个 catalog/course 组合。
  - `89f51dfbdedc4995` 盘点结果：course `59360ad8b8f445b7`，`chunk_count=1`，`kg_node_count=0`，`learning_path_node_count=0`，`resource_count=1`，`quiz_count=0`，`eligible_for_formal_probe=false`。
  - 已对 `89f51dfbdedc4995` 执行 calibration 导出：`/tmp/kg-resource-probe/89f51-calibration.csv`；导出命令成功，必需列完整，节点行数为 0。该 catalog 当前只能证明探针流程和表头可跑，不能产出命中率或 go/no-go。
  - 正式第二 catalog 选择结果：当前 inventory 中 `eligible_for_formal_probe=true` 的第二 catalog 数量为 0；因此本轮不能输出 KG-Resource 对齐 go/no-go。
  - 上线前置条件：补充或构造足量真实样本，要求 KG/LearningPath 节点可抽取 10-15 个核心节点，且资源或题目存在可匹配的 `knowledge_point` 或 `chapter` 元数据。
  - CLI 运行态修复：真实 MySQL inventory 首次暴露 `aiomysql RuntimeError: Event loop is closed` 退出噪声，已在 CLI 结束时显式 `engine.dispose()`，重跑 inventory 不再出现该警告。
  - 已运行：
    - `TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/kg_resource_probe_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_kg_resource_alignment_probe.py -q -p no:cacheprovider`：13/13 passed。
    - `../.venv/bin/python tools/probe_kg_resource_alignment.py inventory --format json --out /tmp/kg-resource-probe/inventory.json`：通过。
    - `../.venv/bin/python tools/probe_kg_resource_alignment.py probe --catalog-id 89f51dfbdedc4995 --calibration --sample-mode all --format csv --out /tmp/kg-resource-probe/89f51-calibration.csv`：通过，`wrote 0 calibration probe rows`。
    - `../.venv/bin/python` 校验 `/tmp/kg-resource-probe/89f51-calibration.csv` 必需列：`missing=[]`，`row_count=0`。
    - `../.venv/bin/python` 检查 `/tmp/kg-resource-probe/inventory.json` 正式样本候选：`eligible_count=0`。
  - Commits：`58dec7e 新增KG资源对齐探针服务`、`361b3a7 新增KG资源对齐探针命令行工具`、`988c463 修复KG探针命令连接释放`。
- 2026-06-09：CourseCatalog 资源消费闭环前端落地完成：
  - 学生端 `Dashboard.jsx` 仅把“有课程但无资源”空态文案改为“课程资源正在准备中 / 请稍后查看”，`data-testid="resources-empty"` 保留不变，无课程空态仍是“暂无课程 / 请先加入一门课程”。
  - 教师端 `TeacherConsole.jsx` 新增只读“本班学习资源”区，按当前教学班 `course_id` 调 `GET /resources?course_id=...&page=1&page_size=50`，展示绑定资源库状态、资源卡片，并可跳转现有 `/resource/:id` 详情。
  - 教师端未恢复生成 / 上传 / 删除入口，仍不调用 deprecated `/resources/generate`。
  - E2E 回归通过：`npm run test:e2e -- e2e/specs.spec.js -g "Student dashboard shows preparation copy|Teacher console shows catalog-bound class resources|Teacher console shows no-resource fallback|Teacher console does not expose"` 通过 4/4。
  - 前端检查通过：`npm run lint` 通过；`npm run build` 通过，仍有既有 Vite chunk size warning。
  - 契约检查：未修改 Backend / OpenAPI / `../docs/`，继续按班存、按班读，不引入 catalog-level resource API。
  - Commit：`998b29d 调整学生资源准备空态`、`e6421d9 新增教师只读资源面板`。
  - 剩余风险：`ResourceDetail.jsx` 仍无显式 404/403 错误态；教师资源区 E2E 存在重复路由设置，后续测试扩展时可再抽 helper。
- 2026-06-09：Admin CourseCatalog 入库 / 资源生成 / 教师绑定 / 学生消费真实多服务冒烟验收通过：
  - 真实服务：Backend `8001`、Agent Service `8002`、MySQL、Qdrant 均在线；Agent health 返回 `qdrant_connected=true`、`model_loaded=true`。
  - 首次 live smoke 暴露运行态配置问题：Agent Service 未带共享上传目录，入库 task `b09513e51aef4431` 失败，错误为 `material does not exist`。根因是 Backend 文件在 `../backend/storage/course_catalogs`，Agent 默认从自身 `storage/course_catalogs` 解析。重启 Agent 时显式设置 `COURSE_CATALOG_STORAGE_ROOT=/home/yezisama/workspace/workflow/EDUagent/backend/storage/course_catalogs` 后通过。
  - 通过正式 Client API 创建 Admin/Teacher/Student，创建资源库 `89f51dfbdedc4995`，上传真实 md 资料 `2ff62f2a34134655`，触发入库 task `d0b234d74df94822`，任务 `completed`，资源库 `status=ready`、`knowledge_status=ready`、`chunk_count=1`。
  - 教师可见 ready CourseCatalog，并绑定创建教学班 `59360ad8b8f445b7`，确认 `CourseOffering.id == Course.id`。
  - Admin 触发资源库级资源生成 task `39dfbd5feb9a4cb7`，任务 `completed`，fan-out 到课程 `59360ad8b8f445b7`，生成资源 `c9faf2f4ce304d3d`（document）和 `2ca8a6af636f4b20`（mindmap）。
  - 学生加入教学班后，`GET /resources` 可见生成资源，`GET /resources/{id}` 可打开真实内容；软删除 `2ca8a6af636f4b20` 后 Admin/Student 列表均隐藏，数据库只读核验该资源 `is_deleted=1`，未软删 document 仍保留。
  - Qdrant 只读核验：按 `course_id=89f51dfbdedc4995` 过滤 `course_knowledge_v1_1024` count 为 1。
  - 回归验证：`../.venv/bin/pytest tests/test_admin_catalog_resource_generation.py tests/test_course_catalog_ingestion.py tests/test_resources_async.py tests/test_course_catalog_ready_gate.py -q` 通过 54/54；`npm run test:e2e -- e2e/specs.spec.js -g "Admin course catalog resource generation|Teacher console does not expose"` 通过 2/2；`npm run lint` 通过；`npm run build` 通过，仍有既有 Vite chunk size warning；`python3 -m json.tool ../docs/10-client-api/Client-API.openapi.json` 通过。
- 2026-06-09：Admin 课程资源库资源生成和软删除前端接入完成：
  - `CourseCatalogDrawer.jsx` 新增 Admin-only 生成学习资源表单、生成任务独立轮询、生成资源列表、资料软删除和生成资源软删除。
  - 前端只调用已写入 Client API 的 Admin 端点：`GET /admin/course-catalogs/{catalog_id}/resources`、`POST /admin/course-catalogs/{catalog_id}/resources/generations`、`DELETE /admin/resources/{resource_id}`、`DELETE /admin/course-catalogs/{catalog_id}/materials/{material_id}`。
  - 教师端保持无生成资源入口，不调用 deprecated `/resources/generate`。
  - 验证：`npm run test:e2e -- e2e/specs.spec.js -g "Admin course catalog resource generation|Teacher console does not expose"` 通过 2/2；`npm run lint` 通过；`npm run build` 通过，仍有既有 Vite chunk size warning。
- 2026-06-09：纠正生成接口前端契约主线：
  - 将 `/resources/generate`、`/quiz/generate` 标记为当前前端契约作废 / 不接入，保留历史后端能力背景但不再作为教师端 UI 或下一步联调主线。
  - 当前主线回到 Admin 资源库创建、资料上传、触发入库 / 向量化、教师绑定 ready CourseCatalog 创建教学班，以及学生 / 教师如何消费入库后的资源和知识库内容。
  - 同步修正 `docs/feature-ledger.md`、`docs/project-direction.md`、`docs/project-coverage-audit.md`、Client API Markdown 与 OpenAPI 描述。
  - 验证：文档语义扫描、OpenAPI JSON 格式检查、`git diff --check`。
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
- CourseCatalog 主线已完成：三表、教学班绑定、Admin 创建资源库、Admin 上传资料、Agent 入库向量化、知识库状态展示、Admin 资源库资源生成、资料/资源软删除、历史资源/Quiz 生成前 ready gate。
- TeacherConsole 曾短暂接入资源生成 UI；CourseCatalog 主线调整后已移除。当前教师资源生成和 Quiz 生成在前端契约中作废 / 不接入，不是当前主线。
- 详细历史请回看 git 提交、`docs/superpowers/specs/`、`docs/superpowers/plans/` 和 `docs/project-coverage-audit.md`。

## 本地联调注意事项

- 浏览器前端如果使用真实 Backend，请优先使用 `http://localhost:5173`，避免 `127.0.0.1` 与 Backend CORS origin 不一致。
- 推荐启动方式：`VITE_USE_MOCK=false VITE_API_BASE_URL=http://localhost:8001/api/v1 npm run dev`。
- Admin CourseCatalog 入库和资源生成真实验收需要 Backend、Agent Service、MySQL、Qdrant/storage、embedding provider 配置同时可用。
- Agent Service 必须带共享上传目录运行：`COURSE_CATALOG_STORAGE_ROOT=/home/yezisama/workspace/workflow/EDUagent/backend/storage/course_catalogs`。缺失时入库会失败为 `material does not exist`。

## 下一步指针

下一步队列不在本文件维护，统一查看 `docs/feature-ledger.md` 的“当前下一步队列”。
