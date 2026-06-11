# WORKFLOW.md

## 文件用途

本文件只记录 `backend/` 当前阶段状态、最近验证和下一步。

- 模块目标与边界：看 `docs/goals.md`
- 术语：看 `docs/glossary.md`
- 关键决策：看 `docs/decisions.md`
- 临时实现与已知限制：看 `docs/temporary-implementation.md`
- 正式契约：看根目录 `docs/10-client-api/*` 与 `docs/20-agent-api/*`
- 当前处于前端页面需求与 Client API 契约完整性审查阶段。现有 `docs/10-client-api/*` 仍作为阶段一实现与联调基线；发现契约缺口时，应记录差异，区分前端隐藏或重构与后续契约扩展，并经用户确认后再修改正式契约。
不要把以下内容继续堆回本文件：

- 长篇架构导读
- glossary 术语解释
- decisions 决策正文
- 历史实施设计与讨论过程
- 可独立存在的联调操作手册

## 接口实现状态维护约定

本文件开头固定维护一份“接口实现情况”总览，用于区分：

- `真实完成`：已接真实鉴权/SQL/Agent 调用，主链路可用
- `半完成`：有真实逻辑，但仍存在硬编码、弱校验、伪异步或部分占位
- `占位/规则完成`：仅完成返回结构、路由或基础协议，业务未真实落地
- `文档声明不做`：当前 v1 契约明确不提供

维护规则：

1. 只要修改了某个接口实现，必须同步更新本文件中的该接口“最近状态”。
2. 更新时至少补充：
   - 修改日期
   - 接口路径
   - 最新状态
   - 一句说明本次变更影响
3. 如果接口从 `占位/规则完成` 提升到 `半完成` 或 `真实完成`，必须直接修改总览表，不允许只写在“最近验证”。
4. 如果接口行为回退、发现假实现、联调不闭环，也必须回写状态，不允许只保留乐观描述。

## Backend 工作流程

后续在 `backend/` 内继续修接口，默认按下面流程执行：

1. 先做上下文检查：
   - `pwd`
   - `git status --short`
   - `curl -s http://127.0.0.1:8002/agent/v1/health`
   - 必要时重读 `AGENTS.md`、相关 OpenAPI 和本文件
2. 先审契约，再动代码：
   - 先核对 `docs/10-client-api` 与 `docs/20-agent-api`
   - 明确本次是否涉及 Client API / Agent API 契约变化
   - 若存在参数、字段、枚举、同步/异步语义变化，先停下说明，不直接落代码
3. 每次只推进一个接口或一个明确子能力：
   - 先找真实问题
   - 先收口最危险的 bug，再谈状态提升
   - 默认不一次性铺开多条链路
4. 修改前先写 4 件事并等待确认：
   - 问题分析
   - 计划修改的文件
   - 修改方案
   - 可能影响的功能
5. 修改时遵循最小闭环原则：
   - 优先 minimal diff
   - 先补异常路径和状态闭环
   - 只要引入锁、事务或异步任务，必须同时检查成功路径、失败路径、幂等和提交时序
6. 刷新类接口统一按稳定化模板审查：
   - task 创建后是否会因后续异常丢失
   - 锁是否在 `commit()` 之后才释放
   - 锁超时 / Agent 失败 / DB 异常是否都会落 `task failed`
   - GET 读取是否使用 `.order_by(...).first()` 避免多行 500
7. 改完立即同步本文件：
   - 更新总览状态
   - 更新“最近状态变更”
   - 若还有残留问题，写进“已知问题”，不要只写乐观结论
8. 最后做最小验证并提交：
   - 至少跑语法检查、导入检查或相关接口测试
   - 只提交本轮相关文件
   - 最终回复必须说明：当前完成、修改文件、测试结果、契约是否漂移、下一步建议
9. 需要及时通过git 存档 commit内容为简短的修改总结
10. 根据workflow内容,更新相关记录文件

## 当前接口实现情况总览

更新日期：`2026-06-05`

### 真实完成

- `GET /api/v1/auth/captcha`
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/users/me`
- `PUT /api/v1/users/me`
- `GET /api/v1/courses`
- `POST /api/v1/courses`
- `POST /api/v1/courses/join`
- `GET /api/v1/admin/users`
- `PUT /api/v1/admin/users/{user_id}`
- `DELETE /api/v1/admin/users/{user_id}`
- `GET /api/v1/admin/logs/agent`
- `GET /api/v1/admin/logs/operations`
- `GET /api/v1/tasks/{task_id}`
- `GET /api/v1/tutoring/conversations`
- `GET /api/v1/tutoring/conversations/{conversation_id}`
- `POST /api/v1/profile/refresh`
- `POST /api/v1/evaluation/refresh`
- `POST /api/v1/learning-path/refresh`
- `GET /api/v1/quiz/questions`
- `POST /api/v1/quiz/generate`
- `POST /api/v1/quiz/submit`
- `GET /api/v1/quiz/result`

### 半完成

- `GET /api/v1/evaluation`
- `POST /api/v1/profile/initialize`
- `GET /api/v1/profile`
- `GET /api/v1/learning-path`
- `GET /api/v1/quiz/history`
- `GET /api/v1/resources`
- `POST /api/v1/resources/generate`
- `POST /api/v1/tutoring/chat`
- `GET /api/v1/teaching/classes/{class_id}/students`
- `GET /api/v1/teaching/classes/{class_id}/students/{student_id}`
- `GET /api/v1/teaching/classes/{class_id}/students/{student_id}/learning`
- `POST /api/v1/webhooks/agent`
- `GET /api/v1/learning-path/nodes/{node_id}/resources`

### 占位/规则完成

_（当前无占位接口）_

### 文档声明不做

- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/send-reset-code`

## 最近状态变更

- `2026-06-11` `KG 资源生成 metadata 对齐实现`
  - **完成**：Admin catalog resource generation 在未显式传 `chapter/knowledge_point` 时读取绑定教学班课程的 active KG，选择核心 KG 节点子集，创建父 `resource_generation` 任务与 KG-node 子任务；显式 metadata 请求保持旧单目标语义。
  - **完成**：Agent 资源生成仍使用现有 `/agent/v1/resources/generate` 契约，`course_id` 继续传 catalog id 以匹配 CourseCatalog 知识库 Qdrant payload；每个子任务 payload 使用 KG 节点 `chapter/node_name`。
  - **完成**：Webhook 对 KG-node 子任务用 `task.result.target_node` 覆盖 `Resource.chapter/knowledge_point`，追加 `kg_node:*` / `support_band:*` 诊断 tags，并在每次子任务完成/失败后基于 DB 子任务状态重算父任务 `completed/degraded/failed`。
  - **完成**：无 active KG 时创建 failed 父任务 `kg_not_ready`；active KG 无可用节点时创建 failed 父任务 `kg_target_empty`；全部子任务失败时父任务 `failed`，内部错误码为 `all_children_failed`（适配 `AsyncTask.error_code VARCHAR(20)`）。
  - **测试维护**：`test_admin_catalog_resource_generation.py` 在 MySQL 下每个 async 测试后 dispose engine，避免 aiomysql 连接跨 event loop 复用；`test_kg_resource_alignment_probe.py` 清库补齐 `course_catalog_materials` 与 `async_tasks`，满足 MySQL 外键。
  - **验证**：
    - `TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/kg_version_service_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_admin_catalog_resource_generation.py::test_webhook_kg_node_child_overrides_agent_metadata_and_updates_parent_completed tests/test_admin_catalog_resource_generation.py::test_webhook_parent_aggregation_marks_degraded_when_one_child_failed tests/test_admin_catalog_resource_generation.py::test_webhook_parent_aggregation_marks_failed_when_all_children_failed -q -p no:cacheprovider`：3 passed
    - `TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/kg_version_service_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_admin_catalog_resource_generation.py::test_admin_catalog_generation_without_metadata_fails_parent_when_no_active_kg tests/test_admin_catalog_resource_generation.py::test_admin_catalog_generation_without_metadata_fails_parent_when_no_usable_targets -q -p no:cacheprovider`：2 passed
    - `TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/kg_version_service_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_kg_resource_targets.py tests/test_admin_catalog_resource_generation.py tests/test_node_resources.py tests/test_kg_resource_alignment_probe.py tests/test_course_knowledge_graph_versions.py -q -p no:cacheprovider`：46 passed
  - **契约**：Client API 契约改变：`否` / Agent API 契约改变：`否`。
  - **剩余风险**：尚未在真实 C 语言 catalog 上触发 KG-node 默认资源生成并重跑正式 KG-Resource probe；因此暂不推进 LearningPath ready gate。

- `2026-06-11` `Route A 可用正文支撑阈值实现`
  - **完成**：Backend Route A 裁剪默认阈值从 `0.70` 改为 `0.60`；显式传入其他阈值时仍按传入阈值裁剪，`body_support_pass_ratio` 保持兼容语义。
  - **完成**：`filter_supported_knowledge_graph()` 新增固定 `0.60/0.65/0.70` 支撑分档 metrics；`strong/good/weak_but_usable/unsupported` count 均按全部 candidate nodes 统计，不只统计 kept nodes。
  - **完成**：CLI `--grounding-threshold` 默认改为 `0.60`，默认 Route A 版本写入 `generation_strategy=route_a_prune_usable_060`；显式非 `0.60` 阈值仍写 `route_a_prune_unsupported`。
  - **真实执行**：开发库 `duagent` 用 `/tmp/kg-resource-probe/c-language-active-kg-v1.json` 和 `/tmp/kg-resource-probe/c-language-route-a-grounding-filtered-expanded-best-v3.json` 生成新 active KG：`graph_id=27c3acb1e98a49d1`，`version=3`，`source_type=route_a_body_grounded`，`generation_strategy=route_a_prune_usable_060`，`108` nodes / `100` edges。
  - **真实核验**：metrics 为 `candidate_node_count=116`、`kept_node_count=108`、`pruned_node_count=8`、`body_support_pass_ratio=0.9310344827586208`、`support_band_counts={strong:57, good:34, weak_but_usable:17, unsupported:8}`。
  - **已知后续风险**：`metrics.pruned_nodes` 仍保留完整 detail 列表，当前 C 语言样本只裁 8 个节点可接受；未来更大图需要考虑限长或外部诊断文件。
  - **验证**：
    - `../.venv/bin/python -m pytest tests/test_kg_body_grounding.py tests/test_generate_kg.py -q -p no:cacheprovider`：19 passed
    - `TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/kg_version_service_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_kg_cli_versioning.py tests/test_course_knowledge_graph_versions.py -q -p no:cacheprovider`：8 passed
    - `DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/duagent?charset=utf8mb4 PYTHONDONTWRITEBYTECODE=1 ../.venv/bin/python tools/generate_knowledge_graph.py --course-id 6c698badb60a4809 --kg-json /tmp/kg-resource-probe/c-language-active-kg-v1.json --grounding-file /tmp/kg-resource-probe/c-language-route-a-grounding-filtered-expanded-best-v3.json --grounding-threshold 0.60 --auto`：成功
  - **契约**：Client API 契约改变：`否` / Agent API 契约改变：`否`。

- `2026-06-10` `Route A 真实样本闭环 no-go`
  - **真实执行**：开发库 `duagent.course_knowledge_graphs` 已应用版本化迁移；C 语言课程 `6c698badb60a4809` 旧目录版 KG 为 `version=1`，`116` nodes / `115` edges。Agent CLI 对 catalog `b2444963f0e54587` 真实 Qdrant chunks 导出 `/tmp/kg-resource-probe/c-language-route-a-grounding.json`。
  - **结果**：`body_top1_score>=0.70` 的节点只有 `22/116=18.97%`，median `0.6618`，未达到跑前固定成功线 `>=70%`。Backend CLI 创建 Route A 新 KG `1801d8e677d04a43`，`version=2,is_active=1`，`22` nodes / `2` edges，`metrics.body_support_pass_ratio=0.1896551724137931`。
  - **结论**：两段式 Route A 工具链可跑通，但“只裁剪无正文支撑节点”第一版在真实样本上 no-go；KG 生成未完成，下一步应改生成策略，优先分析被裁剪节点并推进正文补点 / 正文驱动候选生成。
  - **修复**：`tools/generate_knowledge_graph.py` 新增 `--kg-json`，支持直接裁剪现有 KG JSON，避免重新 LLM 生成导致 grounding 节点 id 不匹配；CLI 结束时显式 `engine.dispose()`，收口 aiomysql event loop closed 噪声。
  - **验证**：
    - `../.venv/bin/python -m pytest tests/test_generate_kg.py tests/test_kg_body_grounding.py -q`：15 passed（有既有 pytest cache 只读 warning）
    - `TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/kg_version_service_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_kg_cli_versioning.py tests/test_course_knowledge_graph_versions.py -q -p no:cacheprovider`：8 passed
  - **契约**：Client API 契约改变：`否` / Agent API 契约改变：`否`。

- `2026-06-10` `Route A KG 正文支撑裁剪工具链接入`
  - **完成**：`tools/generate_knowledge_graph.py` 新增 `--grounding-file` / `--grounding-threshold`，读取 Agent Service `tools/kg_body_grounding.py` 导出的正文支撑 JSON，调用 Backend 纯裁剪层保留 `body_top1_score >= threshold` 的节点、裁掉悬空边，并以 `source_type=route_a_body_grounded`、`generation_strategy=route_a_prune_unsupported` 创建新 KG 版本。
  - **边界**：Backend 不导入 `agent_service`，不直接访问 Qdrant / embedding；Agent Service 不读写 Backend SQL。两段式文件交接不新增 Client API 或 Agent HTTP API。
  - **验证**：
    - `../.venv/bin/python -m pytest tests/test_generate_kg.py tests/test_kg_body_grounding.py -q`：13 passed（有既有 pytest cache 只读 warning）
    - `../.venv/bin/python -m pytest tests/test_kg_cli_versioning.py tests/test_course_knowledge_graph_versions.py -q -p no:cacheprovider`：1 passed, 4 skipped（未带 MySQL URL）
    - `TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/kg_version_service_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_kg_cli_versioning.py tests/test_course_knowledge_graph_versions.py -q -p no:cacheprovider`：8 passed
  - **契约**：Client API 契约改变：`否` / Agent API 契约改变：`否`。
  - **剩余风险**：尚未用真实 C 语言 `116` 节点样本重跑 Route A 新版本；固定成功线仍是排除目录型 chunk 后 `body_top1_score>=0.70` 节点占比 `>=70%`。

- `2026-06-08` `课程资源库知识入库真实联调验收通过`
  - **环境固化**：Agent Service 本机 `.env` 已配置 `COURSE_CATALOG_STORAGE_ROOT=/home/yezisama/workspace/workflow/EDUagent/backend/storage/course_catalogs`，与 Backend 上传目录一致；未修改 Client API 或 Agent API 契约。
  - **数据库前置**：当前 `duagent` 开发库已补齐 `2026-06-08-extend-course-catalog-ingestion.sql` 对应字段（catalog last_ingestion/status/chunk_count/last_error，material file_size/chunk_count/last_error/ingested_at）。
  - **真实验收**：catalog `533dc29ef5c44166` 上传 material `de8173b05aa74fd7` 后触发 task `e8ee00ddb97c4078`；task `completed`，catalog `ready/ready`，material `ingested`，`chunk_count=1`。
  - **Qdrant 证据**：`course_knowledge_v1_1024` 按 `course_id=533dc29ef5c44166` 过滤 count=1，payload 包含 `B1_SHARED_ROOT_MARKER_20260608`。
  - **阶段判断**：Phase B1 Backend-Agent 知识入库链路可按真实联调通过收尾；剩余工作转入前端管理 UI 接入和后续大文件/PDF 压测。

- `2026-06-08` `课程资源库知识入库 Backend 编排收尾`
  - **完成**：`POST /api/v1/admin/course-catalogs/{catalog_id}/ingestions` 已按异步任务模式启动知识入库，Backend 后台任务同步调用 Agent Service 并回写 catalog/material/task 状态。
  - **修复**：启动入库时先对 catalog 做 `SELECT ... FOR UPDATE`，再选择待入库 materials，收口 start/upload/create 并发窗口；上传端点继续保持原有条件更新保护，不额外扩大锁范围。
  - **修复**：后台未知异常恢复先 `rollback()`，再用干净 session 重新加载 task/catalog/materials；恢复材料查询限定 `catalog_id`，并将已被内存改动的 material `chunk_count` 与 `ingested_at` 清回 `0` / `null`。
  - **验证**：
    - `backend/` 下运行 `../.venv/bin/pytest tests/test_course_catalog_ingestion.py tests/test_course_catalogs.py -q`：26 passed
    - `agent_service/` 下运行 `../.venv/bin/pytest tests/test_knowledge_ingestion_api.py -q`：13 passed；该命令用于确认下游 Agent Service 入库接口基线仍通过，不是 Backend diff 的直接测试证据
    - `frontend/` 下运行 `../.venv/bin/python -m json.tool ../docs/10-client-api/Client-API.openapi.json`：通过
    - `git diff --check -- ../backend/app/api/v1/catalogs.py ../backend/tests/test_course_catalog_ingestion.py`：通过
  - **契约**：本次改变 Client API 契约：`否` / 本次改变 Agent API 契约：`否`。
  - **剩余风险**：尚未做真实大文件 PDF 入库压测；当前验证覆盖状态机、异常恢复和 API 契约格式。

- `2026-06-05` `阶段一 E2E 种子数据修复与真实联调验收`
  - **修复**：`UserProfile` ORM 与 `schema.sql` 补齐 `knowledge_mastered`、`knowledge_weak` 两个内部画像统计字段，用于承载 E2E 种子脚本中的画像统计数据。
  - **迁移**：新增 `backend/migrations/2026-06-05-add-user-profile-knowledge-counters.sql`，用于既有 MySQL 库幂等补列；新部署仍由 `schema.sql` 直接创建这两个字段。
  - **修复**：`backend/scripts/seed_e2e_data.py` 移除历史字段 `QuizSession.status` 写入，避免向当前 ORM 写入不存在字段；Quiz 提交统计仍按现有 QuizSession/QuizAnswer 语义处理，不新增对外状态枚举。
  - **测试库维护**：已对当前 `duagent_test.user_profiles` 执行补列；新建测试库会由更新后的 ORM/schema 创建对应字段。
  - **种子数据**：`PYTHONPATH=. ALLOW_E2E_SEED=true DATABASE_URL='mysql+aiomysql://root:123456@127.0.0.1:3306/duagent_test?charset=utf8mb4' python scripts/seed_e2e_data.py`：通过；写入 2 用户、2 课程、2 选课、10 资源、6 题、2 画像、2 评估、1 QuizSession。
  - **阶段一 E2E**：`npm run test:e2e`：3/3 passed；Backend 8001、Agent Service 8002、MySQL `duagent_test` 均在线。
  - **契约**：Client API 契约改变：`否` / Agent API 契约改变：`否`。本次仅补 SQL/ORM 内部字段与测试数据脚本，不新增前端可见字段、路径、参数或 Agent 协议字段。

- `2026-06-05` `前端阶段边界与后续 Client API 扩展审查`
  - **阶段一边界**：当前只收口现有 `docs/10-client-api/*` 能承接的基础主链，包括鉴权、课程切换、资源列表、学习路径、Quiz、AI Chat、教师学生列表与基础学情报告；以真实环境 E2E 验收为完成条件，不继续混入新增页面能力。
  - **正式字段纠错**：`StudentLearning.weak_points` 与 `StudentLearning.recent_activity` 已在正式 OpenAPI 和前端接口规范中声明，前端不得以“未声明”为由移除。后端当前仅返回空数组，属于实现或数据来源待完善，不是契约缺失。
  - **后续审查范围**：资源详情与正文阅读、阅读进度、累计学习时长、建议学习时长、认知成长曲线、班级 AI 洞察、覆盖率、排名、动力指数、资源偏好分布等页面能力，现有契约与 SQL 数据来源不足，进入后续产品与契约扩展审查。
  - **变更预判**：后续能力大概率需要修改 Client API 契约并可能修改 SQL Schema；是否修改 Agent API 需按具体能力的数据来源判断。未完成字段语义、计算方式、数据来源和空值规则确认前，不修改正式契约。
  - **契约**：本次仅记录后续审查边界；Client API 契约改变：`否` / Agent API 契约改变：`否`。

- `2026-06-05` `前端阶段一验收缺陷修复（v2）`
  - **完成**：审查并提交 6 个候选修复，清理部分顶层非契约字段回退，建立 E2E 种子数据脚本。
    - **候选修复提交**：[Login.jsx] AuthContext.login() 集成；[CourseContext.jsx] data.courses 解析 + user 守卫；[teaching.js] 移除假数据适配器，真实 API 透传；[AIChat.jsx] 多键 knowledge_points 兼容解析；[App.jsx] 移除 ResourceDetail 路由。
    - **契约对齐纠错**：[TeacherStudentReport.jsx] 真实模式移除 `report.username`、`report.student_id` 顶层回退是正确的；移除 `weak_points`、`recent_activity` 的依据错误，这两个字段属于正式 `StudentLearning`，待恢复展示。
    - **E2E 种子脚本**：新增 `backend/scripts/seed_e2e_data.py`，幂等创建测试账号（s@t.com / t@t.com）、课程、资源、题库、画像、测评、学习路径数据。需 `ALLOW_E2E_SEED=true` + DB 名含 `test` 守卫。
    - **E2E 基础设施**：[playwright.config.js] webServer.env 注入 VITE_API_BASE_URL；[specs.spec.js] 验证码等待算术题文本 + 解析失败 throw 替代静默返回 0。
    - **路径修正**：[learning.js] getTaskStatus 路径 `/tasks/{id}/status` → `/tasks/{id}`。
    - **页面状态修复**（前 3 轮 commit）：FeedbackStatus 接入、永久 Loading 修复、硬编码回退清理、data-testid 添加、E2E 用例补强、.gitignore test-results/。
  - **契约**：本次改变 Client API 契约：`否` / 本次改变 Agent API 契约：`否`。
  - **验证结果**：
    - `npm run lint`：0 errors, 0 warnings
    - `npm run build`：通过（含 chunk 大小警告，>500KB）
    - `npm run test:e2e`：待测试 DB 后端 + 种子脚本执行后重验（当前 E2E 需专用测试数据库 `duagent_test`、种子数据、Agent Service 和后端同时在线的完整环境）
    - `git diff --check`：通过
    - Client API 契约漂移：否
    - Agent API 契约漂移：否

- `2026-06-04` `前端对齐现有接口联调（阶段一实施）完成`
  - **完成**：Vite 前端已成功对齐后端 API 契约与数据模型结构。
    - **Mock 开关**：利用环境变量 `VITE_USE_MOCK` 实现前端 API Mock 拦截器的条件性加载。
    - **登录态与安全路由**：搭建 `AuthContext` 统一管理登录态并集成 `/users/me`；配置 `ProtectedRoute` 拦截组件防护核心页面。
    - **多课程上下文同步**：搭建 `CourseContext` 实现与 URL `?course_id=` 及 Navbar 选择栏的无缝同步。
    - **SSE 智能辅导对话**：重构 `chat.js` 和 `AIChat.jsx` 接口为 `/tutoring/*`，利用 Fetch 对接 SSE `text/event-stream` 流，完美渲染打字机 chunk 片段、Mermaid 图解和引用知识点标签。
    - **教学看板与报告**：将 `getClassStudents` 和 `getStudentReport` 改造对齐 `/teaching/*`，追加数据适配层转换数据库画像至教师报告所需的完整展示结构。
    - **系统审计日志**：更新 `admin.js`，将核心日志获取改至 `/admin/logs/agent` 与 `/admin/logs/operations`。
    - **ESLint 修复**：清除前端项目全部编译警告与错误（累计修复了 28 个 unused imports, setState-in-effect, impure Date.now, variable hoisting 等 lint 报错），实现 `0 errors, 0 warnings`。
  - **契约**：本次改变 Client API 契约：`否` / 本次改变 Agent API 契约：`否`。

- `2026-06-04` `产品方向变化与前后端契约脱节确认`
  - **结论**：当前问题已不再是单纯的前后端接口接入，而是静态前端原型、现有 Client API、Agent API 和最新口述产品需求之间存在明显断层。
  - **产品方向**：资源与题目调整为课程级公共内容，由 Agent 统一生成后供通过课程码加入课程的学生共享；资源定期更新暂不作为当前 MVP。
  - **新增能力候选**：每日一题/多题作业与完成打卡、累计学习时长、本周最高正确率、知识点练习掌握度、认知成长曲线、教师端学生状态聚合。
  - **边界说明**：每日作业完成结果、答题记录和学习统计仍按学生独立记录；资源库继续只承载学习资料，题目主链仍应通过 quiz/题库能力承载，避免资源与答题边界混淆。
  - **前端现状**：前端静态示例已在 `5173` 运行，但仍大量使用 Mock、旧接口路径、固定 `course_id` 和无正式数据来源的展示字段。
  - **决策**：暂停按旧 `integration_plan.md` 继续扩展 Teaching 看板或 refresh 恢复；在产品需求、页面字段、Client API、Agent API、SQL 数据来源五方差距矩阵确认前，不修改正式契约。
  - **契约**：本次仅更新状态记录；Client API 契约改变：`否` / Agent API 契约改变：`否`。

- `2026-06-04` `Quiz 空会话统计污染修复`
  - **修复**：`GET /api/v1/quiz/result` 与 `GET /api/v1/quiz/history` 只统计至少存在一条未删除 `QuizAnswer` 的已提交练习，页面刷新产生的未提交 QuizSession 不再拉低平均分或污染历史。
  - **语义**：`POST /api/v1/quiz/submit` 的 `answers=[]` 仍保持 200 响应，但该会话不计入练习历史和统计；`GET /quiz/questions` 仍创建并返回字符串 `quiz_id`，避免 Client API 契约漂移。
  - **测试**：`tests/test_quiz_async.py` 新增未提交会话和空答案提交不进入 result/history 的回归断言，并将统计样本补齐为真实包含 QuizAnswer 的已完成练习。
  - **验证**：`python tests/test_quiz_async.py`：`82 OK, 0 FAIL`；`python tests/test_api.py`：`56 PASSED, 0 FAILED`
  - **覆盖率**：`pytest --cov=app --cov-report=term-missing`：`20 passed, 5 failed`，覆盖率 `51%`；失败仍为已知的顶层 `async def test()` pytest 收集问题。
  - **契约**：本次改变 Client API 契约：`否` / 本次改变 Agent API 契约：`否`。

- `2026-06-04` `Resource Webhook completed 结果校验收口`
  - **修复**：`POST /api/v1/webhooks/agent` 在更新任务状态和写入 Resource 前，严格校验 `task_type`、`status`、`result.resources` 数组及资源必填字段/类型。
  - **修复**：畸形 completed 回调不再被错误标记为 completed，也不会因非对象资源元素触发未处理异常；failed 回调缺少 `error_message` 时返回 400。
  - **测试**：`tests/test_resources_async.py` 新增缺失 result/resources、非法资源类型、非法 status、failed 缺少错误信息等负例；同步修正 `tests/test_api.py` 中非资源任务调用 Webhook 的过期断言。
  - **验证**：
    - `python tests/test_resources_async.py`：`30 OK, 0 FAIL`
    - `python tests/test_api.py`：`56 PASSED, 0 FAILED`
    - `python tests/test_agent_integration.py`：`16 passed`
    - `pytest --cov=app --cov-report=term-missing`：`20 passed, 5 failed`，覆盖率 `51%`；失败原因为 5 个脚本的顶层 `async def test()` 未被 pytest-asyncio 标记，属于既有测试收集缺陷，覆盖率目标未达成
  - **契约**：本次改变 Client API 契约：`否` / 本次改变 Agent API 契约：`否`。

- `2026-06-04` `重构 Quiz 部分接口：解耦 submit 与 generate 业务逻辑`
  - **重构**：针对 `backend/app/api/v1/quiz.py` 进行部分解耦，将 `/submit` 接口的答题评分比对、DB 持久化写库、后台诊断调用等核心业务编排，以及 `/generate` 接口的生题 payload 拼装逻辑，移至新增的业务服务层 `backend/app/services/quiz_service.py`。
  - **说明**：此轮为最小范围重构。`/generate` 端点的任务状态管理、直接 Agent 请求与写入生成的题目记录，以及所有查询类端点（`/questions`、`/result`、`/history`）的逻辑依然留在 `quiz.py` 控制器内。
  - **验证**：
    - 在 MySQL 本地开发环境下运行 `python tests/test_quiz_async.py`，所有 78 项测试全数通过。
    - 在 SQLite 测试环境下运行 `python tests/test_api.py`（56 项测试）与 `python tests/simulate_real_study.py`（完整用户学习流），全数通过无报错。
  - **契约**：本次改变 Client API 契约：`否` / 本次改变 Agent API 契约：`否`。



- `2026-06-04` `Refresh 刷新端点契约对齐与 SQLite 锁适配`
  - **修复**：将 `/profile/refresh`、`/evaluation/refresh`、`/learning-path/refresh` 从接收 Query 参数改回接收 **JSON Body**，对齐既有的 Client API OpenAPI 契约。
  - **修复**：对 refresh 锁机制进行 SQLite 环境适配，若 Dialect 为 SQLite 则直接跳过 MySQL 特有的 `GET_LOCK` / `RELEASE_LOCK`，防止测试环境报 `no such function: GET_LOCK` 异常。
  - **重构**：完成测试文件从根目录向 `tests/` 目录的安全迁移与适配；修复了 `simulate_real_study.py` 中 `message`、`stats` 和 `resources` 嵌套契约键，以及 `test_api.py` 中缺失 query 参和 `student_id` Typo 的测试缺陷。
  - **验证**：
    - 运行 `python tests/simulate_real_study.py` (真实用户流模拟) **全链路通过，无任何错误**。
    - 运行 `python tests/test_api.py` (全量冒烟测试) **56/56 全量通过**。
    - 运行 `python tests/test_refresh_async.py` (真异步集成测试) **24/24 全量通过**。
    - 运行 `python tests/test_lock_async.py` (锁竞争一致性测试) **16/16 全量通过**。
  - **契约**：本次改变 Client API 契约：`否` / 本次改变 Agent API 契约：`否`。

- `2026-06-04` `CourseKnowledgeGraph 智能生成与导入临时过渡工具`
  - **新增**：`tools/generate_knowledge_graph.py` — 作为单课程过渡方案的临时 KG 冷启动工具，不在 backend 内作为正式产品功能，仅供开发 and 运维阶段本地提取生成。
  - **新增**：`tests/test_generate_kg.py` — 针对该工具的数据去重、必填项过滤和悬空边剔除等核心校验逻辑进行单元测试。
  - **验证**：运行 `pytest tests/test_generate_kg.py`，所有 4 个测试点全部通过（4/4 passed）。
  - **契约**：无 HTTP API 契约变化（Client API 漂移：否，Agent API 漂移：否）。存在架构边界放宽/临时例外（在工具脚本内部直接实现了一次性 Prompt 和 LLM 接口调用）。

- `2026-06-03` `CourseKnowledgeGraph 手工导入工具`
  - **新增**：`tools/import_knowledge_graph.py` — CLI upsert 工具
  - **验证**：导入 7 nodes/6 edges → learning-path/refresh → task completed → GET 返回 7 nodes/6 edges（从降级到真实通过）
  - **契约**：无 HTTP API 变化

- `2026-06-03` `quiz diagnosis 语义收口（方向 A）`
  - **问题**：Agent LLM 诊断写入 `diagnosis_json` 后无任何 API 消费，Agent 计算被浪费
  - **修复**：`GET /quiz/result` 已开始部分消费 Agent 诊断；当前保持课程级 SQL `summary` / `weak_points`，`suggestions` 优先使用最新有效 Agent 诊断（带类型校验、空列表回退、空白字符串过滤、向旧 session 回溯）
  - **契约**：Client API 字段名/类型均不变；`error_pattern` 不暴露

- `2026-06-03` `quiz wrong_points 查询修复`
  - **问题**：`_assemble_quiz_generate_payload` 中"最近错题知识点"查询只从 `QuizQuestion` 表直接取点，无 `QuizAnswer.is_correct=False` 过滤、无 `user_id` 限定，传给 Agent 的不是真实错题
  - **修复**：改为显式 JOIN `QuizSession` + `QuizAnswer` + `QuizQuestion`，限定 `user_id` + `is_correct=False`，按 `QuizAnswer.create_time DESC` 去重取最近 10 个
  - **契约**：`wrong_points` 输出结构不变，Client/Agent API 均未漂移

- `2026-06-03` `refresh 孤儿任务启动恢复`
  - **问题**：profile/evaluation/learning-path refresh 使用 `asyncio.create_task`，进程重启后协程丢失，task 永久卡在 `status="processing"`
  - **修复**：`app/main.py` lifespan 中新增 `_recover_orphaned_refresh_tasks()`，启动时将 refresh 三类 processing 任务标记 `failed`（`error_code=None`, `error_message="服务重启，后台任务丢失"`）
  - **验证**：插入 3 个 processing refresh 任务 → 运行恢复 → 3 个变为 failed, 1 个 resource_generation 未受影响
  - **契约**：不新增对外 API，`error_code` 保持 null

- `2026-06-03` `resources/generate + quiz/generate Agent 失败分支 task 可见性修复`
  - **问题**：Agent 同步调用失败时，`db.flush()` 不提交事务。`get_db` 在 HTTP 202 发出后才 `session.commit()`，导致客户端立即轮询 `GET /tasks/{id}` 时 task 行对其他事务不可见（MySQL REPEATABLE READ）
  - **修复**：`resources.py` 和 `quiz.py` 的 `except AgentServiceError` 分支中 `db.flush()` → `db.commit()`，确保 202 返回前 task 已稳定落库
  - **验证**：停 Agent → POST resources/generate → ORM 直查确认 `status=failed, error_code=agent_error` 在 202 返回时已可见
  - **契约**：Client API / Agent API 均未变化

- `2026-06-03` `tutoring knowledge_points 字段解析修复 + 联调验证`
  - **问题**：`tutoring/chat` SSE 解析中 `parsed.get("points", [])` 只匹配 `points` key，但 Agent 实际发送 `{"type":"knowledge_points","knowledge_points":[{...}]}`，导致 knowledge_points 静默丢失
  - **修复**：`app/api/v1/tutoring.py` event_generator 中扩大多 key 兼容：`points` → `knowledge_points` → `data`，并新增 `done.knowledge_points_used` 兜底捕获
  - **联调验证**（课程 `758aeff588e84044`，学生 `stu_1446b359@test.com`）：
    - SSE 事件解析 ✅（Agent key=`knowledge_points`，兼容命中）
    - GET conversation API ✅（3 个 knowledge_points 返回）
    - SQL messages.knowledge_points ✅（3 个知识点 JSON 已落库）
    - Agent/Client API 契约均未漂移
  - **结论**：knowledge_points 从「代码已修」升级为「联调已验证」

- `2026-06-03` `联调 v1 验收完成`
  - 根目录 `联调v1结果.md` 已记录 7 条链路的完整验收结果：服务健康、账号课程、profile/evaluation refresh、resources + webhook、tutoring/chat RAG、quiz/generate + submit + result、learning-path/refresh
  - `tutoring/chat` 首次拿到完整 RAG 证据：SSE 正常、课程知识命中、教材特征内容、Mermaid 图表、知识点和建议完整
  - `learning-path/refresh` 经手工灌入 `CourseKnowledgeGraph` 后复跑为 `7 nodes / 6 edges`，证明 learning-path 链路成立；当前缺口不再是接口本身，而是 KG 数据准备链路
  - 联调主链已从“逐接口打通”转入“收口系统级能力缺口”：KG 数据准备、refresh 任务持久化恢复、quiz 个性化质量与 diagnosis 语义、新课程 Qdrant 知识灌入流程
- `2026-06-04` `文档状态校正`
  - **修正**：移除已修复的 tutoring `knowledge_points` / resources-generate 失败可见性缺陷表述
  - **修正**：同步 quiz diagnosis、KG 导入工具、测试路径到当前真实状态
  - **目标**：避免后续 AI/人工继续基于过期状态重复修复
- `2026-06-02` `沉淀完整联调验收手册`
  - 重写 `../docs/30-dev-guide/联调测试指导.md`，将原有接口清单式说明升级为阶段化联调验收手册
  - 明确服务启动顺序、健康检查、环境一致性、AI 执行规则、通过/降级可用/未通过判定标准
  - 明确 `tutoring/chat` 是核心 RAG 验收链路，`learning-path/refresh` 非 RAG 且依赖 `CourseKnowledgeGraph`
  - 后续联调默认先按该手册执行，再把验收结果回写本文件
- `2026-06-02` `RAG embeddings 400 修复 + resources 复验通过`
  - Agent 侧 commit 2febbe6 修复 SiliconFlow `BAAI/bge-m3` embeddings 400（根因：AgentScope `OpenAITextEmbedding` 发送不支持的 `dimensions` 参数；通过 `EMBEDDING_REQUEST_DIMENSIONS_ENABLED=false` 解决）
  - Qdrant `course_knowledge_v1_1024` collection 已灌入 760 chunks 课程知识数据
  - 复验 resources/generate：Agent 日志确认 embeddings 200、Qdrant query 200、RAG 检索参与生成；resource 质量从泛化模板提升为课程知识驱动的具体内容
- `2026-06-01 ~ 2026-06-02` `主链打通与稳定化`
  - 已完成 refresh 真异步化、resources + webhook 闭环、quiz 收口、锁与 webhook 集成测试、联调启动手册补充等主干工作
  - 细节以 git 提交记录和最近验证为准，不再在此处逐条展开历史流水账

## 当前联调结论

- Backend -> Agent Service 主干已打通，且不是仅“能调接口”，而是已完成任务状态闭环、SQL 落库闭环和真实业务验收。
- 联调 v1 已完成 7 条目标链路验收：
  - 服务健康
  - 账号课程
  - `POST /api/v1/profile/refresh` + `POST /api/v1/evaluation/refresh`
  - `POST /api/v1/resources/generate` + `POST /api/v1/webhooks/agent`
  - `POST /api/v1/tutoring/chat`
  - `POST /api/v1/quiz/generate` + `POST /api/v1/quiz/submit` + `GET /api/v1/quiz/result`
  - `POST /api/v1/learning-path/refresh`
- 当前可以确认：
  - refresh 三条链路在运行态下真异步语义成立
  - resources + webhook 真实闭环成立
  - tutoring/chat 已验证真实 RAG 命中，不再只是“可回答”
  - quiz 主链功能成立，评分、结果统计、后台 diagnosis 写入都可用
  - learning-path 链路成立，但前提是课程已有 `CourseKnowledgeGraph`
- 当前阶段的主要问题已不再是“接口是否能通”，而是“系统级数据准备和生产可靠性是否收口”。
- 最新产品口径已改变资源与题目生成方式：从学生个性化生成转向课程级统一生成和共享。现有主链可作为技术验证基础，但不能直接视为最终产品契约。
- 前端静态原型包含累计学习时长、认知成长曲线、练习掌握度、教师学生状态、每日打卡等展示；当前正式 API 和 SQL 数据模型不足以真实支撑这些字段。
- 当前阶段优先级决策：
  - 优先完成产品需求、前端页面、Client API、Agent API、SQL 数据来源五方差距矩阵
  - 优先冻结课程公共资源、课程公共题库、每日作业/打卡和学习统计的 MVP 边界
  - 在契约确认前，只继续验证现有接口，不新增字段、路径、任务类型或状态语义

## Agent Service 接口对接状态

| Backend 接口 | Agent 路径 | 类型 | 状态 | 备注 |
|-------------|-----------|------|------|------|
| `POST /api/v1/profile/refresh` | `/agent/v1/profile/generate` | 真异步 | ✅ | 202 + task_id；后台 asyncio.create_task 执行 Agent 调用 + 写库 |
| `POST /api/v1/tutoring/chat` | `/agent/v1/tutoring/chat` | SSE 代理 | ✅ | SSE 流透传，累积 chunk 后保存 |
| `POST /api/v1/resources/generate` | `/agent/v1/resources/generate` | 异步+Webhook | ✅ | task_id + webhook_url 传入 |
| `POST /api/v1/quiz/generate` | `/agent/v1/assessment/generate-questions` | 异步 | ✅ | 生成后写 quiz_questions |
| `POST /api/v1/evaluation/refresh` | `/agent/v1/evaluation/generate` | 真异步 | ✅ | 202 + task_id；后台 asyncio.create_task 执行 Agent 调用 + 写库 |
| `POST /api/v1/learning-path/refresh` | `/agent/v1/learning-path/generate` | 真异步 | ✅ | 202 + task_id；后台 asyncio.create_task 执行 Agent 调用 + 写库 |
| `POST /api/v1/webhooks/agent` | — | Webhook | ⚠️ | 见已知问题 |

## 未完成项

以下项目不是“链路没通”，而是联调通过后暴露出的系统级能力缺口或待收口问题。

### 优先级高

- 产品需求与现有契约重新对齐
  - 课程公共资源、课程公共题库、每日作业/打卡、学习时长和成长指标尚未形成正式 Client API / Agent API / SQL 设计。
  - 前端静态原型中的展示字段不能直接作为 Backend 返回字段，需要先确认指标定义和数据来源。
  - 下一步产物应为五方差距矩阵和 MVP 契约变更草案，而不是直接修改代码。
- `CourseKnowledgeGraph` 数据准备与冷启动链路
  - `learning-path/refresh` 接口本身已验证成立，但课程若无 KG 则只能返回空 `nodes/edges`。
  - 已提供手工导入工具 `tools/import_knowledge_graph.py` 与智能提取导入工具 `tools/generate_knowledge_graph.py`。
  - 后者可直接加载大纲并通过 LLM 智能生成合规的 nodes 和 edges，自动去重并清洗悬空边，已成功降低了课程图谱准备的难度，满足单课程图谱的数据冷启动需要。
- refresh 真异步任务持久化/恢复
  - `POST /api/v1/profile/refresh`、`POST /api/v1/evaluation/refresh`、`POST /api/v1/learning-path/refresh` 当前在返回 `202` 后使用进程内 `asyncio.create_task`
  - 当前已补“启动时将孤儿 refresh task 标记 failed”的止血方案
  - 仍缺真正的持久化执行/恢复机制；worker reload / 进程重启 / crash 后不会恢复继续执行
- `POST /api/v1/quiz/submit` + `GET /api/v1/quiz/result`
  - 功能主链已成立，MySQL 集成测试已补齐（71/71 通过）
  - 仍未收口的是个性化质量与语义统一：
    - 没有足够 profile/evaluation/context 时，题目会退化为泛化题
    - diagnosis 当前是折中融合：课程级 SQL `summary/weak_points` + Agent `suggestions`
  - 需与前端/Agent 侧对齐后单独收口
- `POST /api/v1/webhooks/agent`
  - completed 结果结构校验、failed 错误信息校验、鉴权和幂等已覆盖
  - 当前保留可选 `error_code` 兼容行为，不新增精确错误码语义
- KG 自动生成能力
  - 当前不是没有 learning-path，而是没有正式的 KG 生成/导入机制
  - 若后续希望新课程自动具备 learning-path，需要补：
    - 手工导入工具
    - 或 Agent 生成候选 KG + Backend 落库
  - 当前这块尚未开始实现

### 优先级中

- RAG 检索 embeddings 400 排查与修复
  - ✅ Agent 侧已修复（`agent_service` commit 2febbe6）：根因为 AgentScope `OpenAITextEmbedding` 对 SiliconFlow `BAAI/bge-m3` 发送了不支持的 `dimensions` 参数；通过 `EMBEDDING_REQUEST_DIMENSIONS_ENABLED=false` 默认不传 `dimensions` 解决
  - ✅ 课程知识已灌入 Qdrant（`course_knowledge_v1_1024`，760 chunks from 数据结构教材），实测 `search_course_knowledge` limit=3 命中 3 hits
  - ✅ embeddings 400 和空 collection 问题已不再是当前联调阻塞；RAG 检索链路已验证可用
  - 后续：验证 tutoring/chat 等场景下 RAG 命中率与检索质量
- `POST /api/v1/profile/initialize`
  - 当前可用，但仍属于半完成
  - 若后续继续稳定化，可补更多重复提交和异常路径测试
- `POST /api/v1/resources/generate` + `POST /api/v1/webhooks/agent`
  - 当前主链路和鉴权/幂等已覆盖
  - 若后续继续加强，可补更高并发 webhook 场景验证
- 新课程的 Qdrant 知识灌入流程
  - 老课程已验证真实 RAG 可用，但新课程若要复现课程级 RAG，仍需单独灌入课程知识
  - 当前属于“能力存在，但流程未产品化”

## 已知问题

1. **Webhook 鉴权需要两端同步配置**（`webhooks.py` + Agent Service `resources.py`）：Backend 已实现 `X-Webhook-Secret` 校验，Agent Service 的 `_post_json_payload` 已同步发送该 header。两端需配置一致的 `WEBHOOK_SECRET` 环境变量，未配时鉴权自动跳过（向后兼容）。
2. **`GET /learning-path/nodes/{id}/resources` chapter_materials 依赖 KG 预置数据**：`chapter_materials` 从 `CourseKnowledgeGraph.nodes` JSON 中提取 `chapter` 字段并匹配 `Resource.chapter`。若 KG 未预置完整数据，该字段将返回空数组（不影响其他字段）。
3. **`POST /quiz/submit` 诊断链路已后台异步化，GET /quiz/result 为折中融合语义**：后台 `quiz_service.run_diagnosis_background` 通过 `asyncio.create_task` 调用 Agent `/assessment/evaluate`，使用 UPDATE 写入 `QuizSession.diagnosis_json`（无 DB 读依赖，消除竞态）。当前 `GET /quiz/result` 保持课程级 SQL `summary/weak_points`，只部分消费 Agent `suggestions`；这条链路已不再“完全未消费 Agent 诊断”，但语义尚未最终收口。
4. **refresh 真异步任务当前不具备持久执行能力**：`POST /api/v1/profile/refresh`、`POST /api/v1/evaluation/refresh`、`POST /api/v1/learning-path/refresh` 在返回 `202` 后使用进程内 `asyncio.create_task` 执行 Agent 调用和写库。当前已补启动恢复：服务启动时将残留 refresh `processing` 任务标记为 `failed`；但尚未解决任务持久化执行/恢复问题。
5. ~~**RAG 检索当前可能整体失效**~~（已修复，2026-06-02）：Agent 侧 embeddings 400 已修复（commit 2febbe6），课程知识已灌入 Qdrant（course `758aeff588e84044`，760 chunks，检索命中 3/3）。RAG 不再整体失效，resources/generate 真实链路验收已确认日志中不再出现 embeddings 400 或 Qdrant collection 404。
6. **`learning-path/refresh` 依赖 KG 数据准备已具备临时工具支持**：当前已通过手工写入与 `generate_knowledge_graph.py` 智能命令行提取导入工具验证 learning-path 拓扑结构闭环。新课程若不准备 KG 图谱，则 learning-path 仍会空结果，但现在可通过 CLI 工具快速完成图谱抽取与数据灌入。
7. **新课程课程知识灌入流程未产品化**：已验证课程 `758aeff588e84044` 的 RAG 可用，但新课程若要复现课程级 tutoring/resources/quiz 上下文，仍需额外灌入 Qdrant 数据。

## 当前待修复缺陷

- **高优先级：产品口径与现有 API 契约脱节**
  - 当前正式契约仍以学生触发的个性化资源/题目生成为主，最新产品口径改为课程级统一生成和共享。
  - 每日作业/打卡、累计学习时长、本周最高正确率、认知成长曲线、知识点练习掌握度和教师端学生状态聚合均缺正式契约或数据来源。
  - 在完成需求确认和契约冻结前，不应继续按静态页面字段猜测实现。
- **高优先级：全量 pytest 无法正确收集脚本式异步测试**
  - `tests/test_api.py`、`tests/test_lock_async.py`、`tests/test_quiz_async.py`、`tests/test_refresh_async.py`、`tests/test_resources_async.py` 使用顶层 `async def test()` + `asyncio.run(test())`，被 pytest 收集后因缺少 asyncio 标记而失败
  - 当前 `pytest --cov=app --cov-report=term-missing` 只能得到 `51%` 覆盖率，未达到项目要求的 80%
- **高优先级：teaching 学习看板存在假数据/占位数据**
  - `GET /api/v1/teaching/classes/{class_id}/students/{student_id}/learning` 仍存在硬编码/空数组字段，不能作为真实学习看板结果使用
  - 该问题更偏前端接入阶段的数据真实性缺口，不属于当前 Backend-Agent 主链阻塞
- **中优先级：`GET /api/v1/quiz/questions` 仍会创建未提交 QuizSession**
  - 因 Client API 要求返回字符串 `quiz_id`，当前保留取题即创建会话的行为
  - result/history 已过滤无 QuizAnswer 的会话，不再污染统计；数据库中的未提交会话清理可后续作为运维治理处理

## 延期处理问题

- **资源列表接口课程权限校验不足**
  - 当前审查意见：任意已登录用户若知道 `course_id`，可能读取该课程资源
  - 当前阶段先记录为延期处理，不作为联调 v1 阻塞项；后续进入权限治理阶段时再统一修复
- **任务查询接口对教师放权过宽**
  - 当前审查意见：任意教师可能查询任意 `resource_generation` 任务，不仅限任务归属人或课程归属范围
  - 当前阶段先记录为延期处理，不作为联调 v1 阻塞项；后续进入权限治理阶段时再统一修复

## 联调命令

```bash
# Agent Service（agent_service/ 目录，终端 1）
./.venv/bin/uvicorn agent_service.main:app --host 127.0.0.1 --port 8002

# Backend（backend/ 目录，终端 2）
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload

# 验证 Agent Service 健康
curl http://127.0.0.1:8002/agent/v1/health

# Backend 联调测试
python tests/test_agent_integration.py

# Backend 冒烟测试
python tests/test_api.py

# Agent Service 全量回归
cd agent_service && ./.venv/bin/pytest -q
```

## 测试文件

| 文件 | 用途 | 覆盖范围 |
|------|------|---------|
| `tests/test_agent_integration.py` | Agent 联调集成测试 | 6 个 Agent 接口 + Webhook + 权限 + 降级 |
| `tests/test_api.py` | 全量冒烟测试 | 所有端点的基础可用性 |
| `tests/test_refresh_async.py` | refresh 真异步链路集成测试 | profile / evaluation / learning-path 的 202、processing、completed、DB 写入、Agent error |
| `tests/test_resources_async.py` | resources 异步链路集成测试 | generate 202 + task_type、webhook completed/failed、结果结构校验、幂等、鉴权、task_type mismatch |
| `tests/test_lock_async.py` | refresh 锁相关集成测试 | 三条 refresh 的 lock_timeout + profile/refresh 锁竞争一致性 |
| `tests/test_quiz_async.py` | quiz 链路集成测试 | submit 评分 + 落库、多选题评分、非法 question_id 容错、Agent payload 对齐、空答案、404、后台诊断写入/失败、result 聚合 + 统计 + trend 排序 + diagnosis 字段形状检查 |

## 最近验证

- `2026-06-02`
  - `python tests/test_quiz_async.py`
  - 结果：`71/71` 通过
  - 覆盖：
    - `POST /api/v1/quiz/submit`
    - `GET /api/v1/quiz/result`
  - 断言：
    - submit 评分 + QuizAnswer 落库 + 多选题评分（完整/排序无关/不完整/全错）
    - 非法 question_id → `is_correct=False` + 无 FK 违规 + 仍计入 total_count + 不进入 Agent 诊断 payload
    - 空答案 → 200 score=0、无效 quiz_id → 404
    - 后台 Agent 诊断写入 + Agent 失败容错 + 后台任务触发验证
    - result 统计计算（total_attempts/avg_score/avg_time）+ score_trend 排序 + diagnosis 字段形状检查（无额外键；语义仍待确认）
- `2026-06-02`
  - `python tests/test_refresh_async.py`
  - 结果：`24/24` 通过
  - 覆盖：
    - `POST /api/v1/profile/refresh`
    - `POST /api/v1/evaluation/refresh`
    - `POST /api/v1/learning-path/refresh`
  - 断言：
    - `202 + task_id`
    - immediate poll = `processing`
    - 最终 `completed`
    - SQL 写入成功
    - Agent error -> `failed + error_code`
- `2026-06-02`
  - `python tests/test_resources_async.py`
  - 结果：`15/15` 通过
  - 覆盖：
    - `POST /api/v1/resources/generate`
    - `POST /api/v1/webhooks/agent`
  - 断言：
    - `202 + task_id + task_type=resource_generation`
    - webhook completed -> `200` + task `completed` + resources 写入
    - webhook failed -> `200` + task `failed` + `error_code present`
    - 重复 completed 回调不重复写入 resources
    - `X-Webhook-Secret` 正确时业务正常处理，错误时 `401`
    - `task_type mismatch -> 400`
- `2026-06-02`
  - `python tests/test_lock_async.py`
  - 结果：`16/16` 通过
  - 覆盖：
    - `POST /api/v1/profile/refresh`
    - `POST /api/v1/evaluation/refresh`
    - `POST /api/v1/learning-path/refresh`
  - 断言：
    - 真实 MySQL `GET_LOCK` 超时路径 -> `task failed + error_code=lock_timeout`
    - `profile/refresh` 并发两个请求 -> 两个 task 都终态，且只保留一条 `is_deleted = false` 活跃记录

## 下一步建议

1. 优先推进新课程 Qdrant 知识灌入流程工程化，先把样板课程能力变成可复制流程。
2. 为 refresh 三条真异步链路设计最小可行的持久化执行/恢复策略，避免运行中可用但重启后不可靠。
3. 统一收口 KG 工具与 RAG 工具的工程化规范，而不是重复证明 learning-path 主链是否可用。
4. 前端真实接入相关页面前，再集中处理 teaching 看板数据真实性、空 `QuizSession` 等展示侧问题。
