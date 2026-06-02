# WORKFLOW.md

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

## 当前接口实现情况总览

更新日期：`2026-06-02`

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

### 半完成

- `GET /api/v1/evaluation`
- `POST /api/v1/profile/initialize`
- `GET /api/v1/profile`
- `GET /api/v1/learning-path`
- `GET /api/v1/quiz/questions`
- `POST /api/v1/quiz/generate`
- `GET /api/v1/quiz/history`
- `GET /api/v1/resources`
- `POST /api/v1/resources/generate`
- `POST /api/v1/tutoring/chat`
- `GET /api/v1/teaching/classes/{class_id}/students`
- `GET /api/v1/teaching/classes/{class_id}/students/{student_id}`
- `GET /api/v1/teaching/classes/{class_id}/students/{student_id}/learning`
- `POST /api/v1/webhooks/agent`
- `GET /api/v1/learning-path/nodes/{node_id}/resources`
- `POST /api/v1/quiz/submit`
- `GET /api/v1/quiz/result`

### 占位/规则完成

_（当前无占位接口）_

### 文档声明不做

- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/send-reset-code`

## 最近状态变更

- `2026-06-01` `接口盘点初始化`
  - 新增接口实现情况总览
  - 明确后续每次改接口时必须同步更新最近状态
- `2026-06-01` `修复 webhook task.status 闭环 + 实现两个占位接口`
  - `POST /api/v1/webhooks/agent`：补充 task.status 设置（completed/failed），幂等保护生效，接口保持「半完成」
  - `GET /api/v1/learning-path/nodes/{node_id}/resources`：新增 `course_id` 查询参数，从 `LearningPath` + `Resource` + `QuizQuestion` 表真实查询，状态提升至「半完成」。同步更新 `docs/10-client-api/Client-API.openapi.json` 补充 `course_id` 参数；已添加课程权限校验（学生需已加入课程）
  - `GET /api/v1/quiz/result`：替换硬编码诊断为基于 `QuizAnswer` JOIN `QuizQuestion` 的数据驱动聚合计算，状态提升至「半完成」。无答题记录时 `diagnosis` 返回 `null`（符合 API 前端接口规范）
- `2026-06-01` `webhook error_code 落库 + 鉴权`
  - `POST /api/v1/webhooks/agent`：failed 分支补充 `task.error_code` 落库；Agent Service `build_resource_generation_failed_payload` 同步发送 `error_code: "agent_error"`
  - 新增 `X-Webhook-Secret` 鉴权（两端都配同一个 secret 时生效；仅一端配置时，Agent 配 Backend 未配→header 被忽略，Backend 配 Agent 未配→401；两端都不配→跳过鉴权）
- `2026-06-02` `实现 quiz/submit 后台异步 LLM 诊断（修正）`
  - `POST /api/v1/quiz/submit`：评分完成后通过 `asyncio.create_task` 后台异步调用 `agent_client.post_json("/agent/v1/assessment/evaluate")`，LLM 诊断存入 `QuizSession.diagnosis_json`。后台任务使用独立 DB session，不创建 AsyncTask（避免新增未声明 task_type），失败时记录结构化日志。接口保持「半完成」— 诊断链路已打通但依赖后台异步完成
  - `GET /api/v1/quiz/result`：诊断保持纯课程级数据驱动聚合（summary/weak_points/suggestions 全部基于 QuizAnswer JOIN QuizQuestion 计算），不混合 diagnosis_json。接口保持「半完成」— 数据驱动诊断可用，LLM 诊断数据存于 diagnosis_json 供未来 per-session 端点使用
- `2026-06-02` `profile 刷新链路稳定化`
  - `POST /api/v1/profile/refresh`：MySQL `GET_LOCK`/`RELEASE_LOCK` 序列化同用户+课程并发写入；软删旧行 → 插新行；显式 `commit()` 后再释放锁；异常兜底覆盖完整路径；GET `/profile` 改为 `.order_by(desc).first()`
  - `POST /api/v1/profile/initialize`：同锁策略 + 显式 `commit()` 后释放锁；重复提交 = 覆盖；锁超时返回 `503`
- `2026-06-02` `profile/refresh 真异步化`
  - `POST /api/v1/profile/refresh`：请求内只做权限校验 + payload 组装 + task 创建/提交 + 返回 202；后台 `_run_profile_refresh_background` 通过 `asyncio.create_task` 执行 Agent 调用 → 锁 → 写库 → task 完成/失败，使用独立 DB session + `UPDATE AsyncTask` 写任务终态。接口从「半完成」提升至「真实完成」— Agent 调用不阻塞请求响应，task 状态真实反映后台进度
- `2026-06-02` `evaluation + learning-path 真异步化（复制 profile 模板）`
  - `POST /api/v1/evaluation/refresh`：同 profile 模式 — 请求内只做权限校验 + payload 组装 + task 创建/提交 + 返回 202；后台 `_run_evaluation_refresh_background` 执行 Agent 调用 + 锁 + 写库 + task 完成/失败。接口从「半完成」提升至「真实完成」
  - `POST /api/v1/learning-path/refresh`：同 evaluation 模式。接口从「半完成」提升至「真实完成」
- `2026-06-02` `evaluation + learning-path 刷新链路稳定化（复制 profile 模板）`
  - `POST /api/v1/evaluation/refresh`：MySQL `GET_LOCK` 序列化写入；task 创建后显式 `commit()`；try 覆盖 Agent 调用 + DB 写入完整路径；成功路径 `commit → release lock`；AgentServiceError、锁超时和通用 Exception 分支都会先 `rollback()` 再落 `task failed`，不再残留 `processing`
  - `POST /api/v1/learning-path/refresh`：同 evaluation 模式；额外修复 GET `/learning-path` 的 `scalar_one_or_none()` → `.order_by(desc).first()`（修复多次 refresh 后 GET 500 崩溃）；`_assemble_learning_path_payload` 中 UserProfile / CourseKnowledgeGraph 读取同改 `.first()`；`get_node_resources` 中 CourseKnowledgeGraph 同改 `.first()`；锁超时同样会落 `task failed`
- `2026-06-02` `补充 backend 实际工作流程`
  - 新增"Backend 工作流程"章节，固定约束：先审契约、一次只推进一个接口、修改前先给 4 项分析、优先收口异常路径和任务状态闭环、改完立即同步 `WORKFLOW.md`
- `2026-06-02` `resources/generate + webhooks/agent 集成测试`
  - 新增 `test_resources_async.py`（7 条用例）：generate 202 + task_type、webhook completed 落库、failed 落 error_code、幂等（不重复插 resources）、X-Webhook-Secret 鉴权通过+拒绝、task_type mismatch 400。全部使用 MySQL + AsyncMock
- `2026-06-02` `refresh 锁相关集成测试补齐`
  - 新增 `test_lock_async.py`：真实 MySQL `GET_LOCK` 超时路径集成测试，覆盖 `POST /api/v1/profile/refresh`、`POST /api/v1/evaluation/refresh`、`POST /api/v1/learning-path/refresh` 三条链路。验证锁被占用时仍返回 `202 + task_id`，后台 task 最终 `failed`，且 `error_code = "lock_timeout"`
  - 补充 `profile/refresh` 锁竞争测试：并发两个 refresh 请求，两个 task 都进入终态，最终仅保留一条 `is_deleted = false` 的活跃记录，验证锁 + 软删 + 插入 + commit 后释放锁的写入一致性

## 文件用途

本文件记录 Backend 联调的开发进度和跨窗口恢复上下文。
接口契约以 `../docs/20-agent-api/Agent-Service.openapi.json` 和 `../docs/20-agent-api/API_Agent内部接口规范.md` 为准，本文件不是接口契约来源。

## 当前项目结构

### Backend 负责范围

- `app/api/v1`
  - 前端 API 路由
  - 鉴权、权限校验、HTTP 状态码、统一返回包装
  - AsyncTask 协议适配
  - Webhook 接收
- `app/services/agent_client.py`
  - Backend -> Agent Service 的统一 HTTP client
- `app/models`
  - SQLAlchemy ORM，保存用户、课程、题目、任务、画像、评估、学习路径、资源、对话等业务数据
- `app/db`
  - 数据库连接、session、启动初始化
- `app/schemas`
  - 前端请求/响应实体、Webhook 请求实体
- `WORKFLOW.md`
  - 当前联调状态、已改/未改能力、最近验证和下一步任务

### Agent Service 负责范围

- 只通过 `/agent/v1/*` HTTP 接口被 Backend 调用
- 负责 LLM、AgentScope 编排、RAG、结构化 AI 结果生成、SSE 内容生成
- 不直接写 Backend SQL

## 当前联调结论

- Backend -> Agent Service 主干已打通，且不是仅“能调接口”，而是已有任务状态闭环和 SQL 落库闭环。
- 目前最稳定的联调能力是 3 条 refresh 链路：
  - `POST /api/v1/profile/refresh`
  - `POST /api/v1/evaluation/refresh`
  - `POST /api/v1/learning-path/refresh`
- 三条链路当前都满足：
  - 请求内快速返回 `202 + task_id`
  - 立即轮询 `GET /api/v1/tasks/{task_id}` 可见 `processing`
  - 后台协程独立调用 Agent Service
  - 成功时 `AsyncTask -> completed`
  - 失败时 `AsyncTask -> failed`
  - `error_code` / `error_message` 正确落库
  - 成功时对应业务表写入新记录
- 资源生成链路已接近完整闭环，但仍需补更扎实的集成测试。
- quiz 链路已从明显占位提升到半完成，但仍不建议继续扩功能，应先保持当前语义稳定。

## 当前方向

- Backend 已具备对接 Agent Service 的基础：统一的 `AgentClient`、AsyncTask 管理、Webhook 接收落库。
- 6 个 Agent 接口全部完成对接，所有调用统一走 `agent_client` 单例。
- 后续进入联调验证：逐接口启动两个服务，验证完整链路（请求 → Agent 返回 → Backend 落库）。
- 发现的问题优先修 bug，再补 stub。

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

## 已改内容

### 已完成并验证通过

- `POST /api/v1/profile/refresh`
  - 从请求内同步调用 Agent 改为后台异步执行
  - 请求内只做 payload 组装、创建任务、返回 `202 + task_id`
  - 后台独立 session 调 Agent、加锁、软删旧行、插新行、更新 task
- `POST /api/v1/evaluation/refresh`
  - 复制 profile 真异步模板
  - 成功/失败路径都落稳定 task 终态
- `POST /api/v1/learning-path/refresh`
  - 复制 profile 真异步模板
  - 额外修复历史多行读取导致的 GET 500 风险
- `POST /api/v1/webhooks/agent`
  - task.status completed/failed 闭环
  - failed 分支 `error_code` 落库
  - `X-Webhook-Secret` 鉴权
- `GET /api/v1/learning-path/nodes/{node_id}/resources`
  - 从占位实现改为真实 DB 查询
  - 新增 `course_id` 查询参数并已同步前端契约
  - 补课程权限校验
- `GET /api/v1/quiz/result`
  - 替换硬编码诊断为课程级数据驱动聚合
  - 无数据时 `diagnosis: null`
- `POST /api/v1/quiz/submit`
  - 后台异步保存 Agent 诊断到 `QuizSession.diagnosis_json`
  - 不新增未声明 `task_type`

### 已完成的验证

- `test_refresh_async.py`
  - 当前 `24/24` 通过
  - 覆盖三条 refresh 链路：
    - `202 + task_id`
    - immediate poll 仍为 `processing`
    - 最终 `completed`
    - SQL 写入成功
    - Agent error -> `failed + error_code`

## 暂不修改 / 不必要修改

- 暂不为 `profile/evaluation/learning-path` 引入 Celery、RQ、消息队列或持久化 worker
  - 当前阶段以前端可见异步语义和任务状态闭环为完成标准
- 暂不再投入 SQLite 兼容测试
  - 当前真实运行环境是 MySQL
  - 联调测试以 MySQL 为准
- 暂不大规模抽象三条 refresh 的公共 service 层
  - 当前虽有重复模式，但仍以 minimal diff 为主
- 暂不扩展 quiz 的 per-session 新接口
  - 先保持当前课程级结果语义稳定

## 等待修改 / 待办项

### 优先级高

- `POST /api/v1/quiz/submit` + `GET /api/v1/quiz/result`
  - 继续保持课程级语义单一
  - 补更扎实的 MySQL 集成测试，验证后台诊断写入与前端读取行为一致
- `POST /api/v1/webhooks/agent`
  - failed 回调当前已验证 `error_code present`
  - 若继续收口，可补精确 `error_code` 值校验与更多异常负例

### 优先级中

- `POST /api/v1/profile/initialize`
  - 当前可用，但仍属于半完成
  - 若后续继续稳定化，可补更多重复提交和异常路径测试
- `POST /api/v1/resources/generate` + `POST /api/v1/webhooks/agent`
  - 当前主链路和鉴权/幂等已覆盖
  - 若后续继续加强，可补更高并发 webhook 场景验证

### 等待更后续再考虑

- 异步任务持久化恢复能力
  - 当前使用 `asyncio.create_task`
  - 进程重启后后台任务不会自动续跑
  - 这属于后续生产级可靠性增强，不是当前联调主阻塞
- 锁等待秒数配置化
  - 对锁超时测试和运维有帮助
  - 但不是当前第一优先级

## 已知问题

1. **Webhook 鉴权需要两端同步配置**（`webhooks.py` + Agent Service `resources.py`）：Backend 已实现 `X-Webhook-Secret` 校验，Agent Service 的 `_post_json_payload` 已同步发送该 header。两端需配置一致的 `WEBHOOK_SECRET` 环境变量，未配时鉴权自动跳过（向后兼容）。
2. **`GET /learning-path/nodes/{id}/resources` chapter_materials 依赖 KG 预置数据**：`chapter_materials` 从 `CourseKnowledgeGraph.nodes` JSON 中提取 `chapter` 字段并匹配 `Resource.chapter`。若 KG 未预置完整数据，该字段将返回空数组（不影响其他字段）。
3. **`POST /quiz/submit` 诊断链路已后台异步化，GET /quiz/result 保持纯课程级**：后台 `_run_diagnosis_background` 通过 `asyncio.create_task` 调用 Agent `/assessment/evaluate`，使用 UPDATE 写入 `QuizSession.diagnosis_json`（无 DB 读依赖，消除竞态）。`GET /quiz/result` 的 summary/weak_points/suggestions 全部基于课程级聚合计算，不混合 `diagnosis_json`（该字段保留供未来 per-session 诊断端点使用）。
4. **当前「真实完成」的异步链路以前端可见语义和任务状态闭环为准**：`asyncio.create_task` 后台协程满足 202 + task_id 轮询的契约，但进程重启后未完成的后台任务不会自动续跑（无持久化队列/外部 worker）。这不影响单次请求-轮询链路正确性，但长期来看若需生产级可靠性，可考虑引入独立 worker 或持久化任务队列。

## 联调命令

```bash
# Agent Service（agent_service/ 目录，终端 1）
./.venv/bin/uvicorn agent_service.main:app --host 127.0.0.1 --port 8002

# Backend（backend/ 目录，终端 2）
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload

# 验证 Agent Service 健康
curl http://127.0.0.1:8002/agent/v1/health

# Backend 联调测试
python test_agent_integration.py

# Backend 冒烟测试
python test_api.py

# Agent Service 全量回归
cd agent_service && ./.venv/bin/pytest -q
```

## 测试文件

| 文件 | 用途 | 覆盖范围 |
|------|------|---------|
| `test_agent_integration.py` | Agent 联调集成测试 | 6 个 Agent 接口 + Webhook + 权限 + 降级 |
| `test_api.py` | 全量冒烟测试 | 所有端点的基础可用性 |
| `test_refresh_async.py` | refresh 真异步链路集成测试 | profile / evaluation / learning-path 的 202、processing、completed、DB 写入、Agent error |
| `test_resources_async.py` | resources 异步链路集成测试 | generate 202 + task_type、webhook completed/failed、幂等、鉴权、task_type mismatch |
| `test_lock_async.py` | refresh 锁相关集成测试 | 三条 refresh 的 lock_timeout + profile/refresh 锁竞争一致性 |

## 最近验证

- `2026-06-02`
  - `python test_refresh_async.py`
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
  - `python test_resources_async.py`
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
  - `python test_lock_async.py`
  - 结果：`16/16` 通过
  - 覆盖：
    - `POST /api/v1/profile/refresh`
    - `POST /api/v1/evaluation/refresh`
    - `POST /api/v1/learning-path/refresh`
  - 断言：
    - 真实 MySQL `GET_LOCK` 超时路径 -> `task failed + error_code=lock_timeout`
    - `profile/refresh` 并发两个请求 -> 两个 task 都终态，且只保留一条 `is_deleted = false` 活跃记录

## 下一步建议

1. 先集中收口 `POST /api/v1/quiz/submit` + `GET /api/v1/quiz/result`，补 MySQL 集成测试，验证课程级语义、后台诊断写入和前端读取行为一致。
2. 若继续加强 resources/webhook 链路，优先补 `failed` 分支精确 `error_code` 校验和更高并发 webhook 场景测试。
3. 暂不继续扩展新的 Agent 能力或持久化队列，先把现有已接通链路的测试和语义完全收口。
