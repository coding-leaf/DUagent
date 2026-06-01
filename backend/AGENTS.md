# AGENTS.md

## Scope

- 负责 `backend/` 内的主业务后端服务。
- 负责用户、鉴权、课程、SQL 持久化、任务状态、前端 API、Agent Service HTTP 调用适配和 Webhook 落库。
- 不负责 `agent_service/` 内部的 LLM、AgentScope、Qdrant RAG、提示词、智能体编排实现。
- Backend 只通过 HTTP 调用 Agent Service，使用统一的 `app/services/agent_client.py`，不导入 `agent_service` Python 模块。
- Agent Service 不直接写 Backend SQL；Backend 负责校验 Agent 返回结果并写入 SQL。

## Source Of Truth

开发时优先级如下：

1. `../docs/20-agent-api/Agent-Service.openapi.json` — Agent Service 接口契约
2. `../docs/20-agent-api/API_Agent内部接口规范.md` — 字段语义和错误码规范
3. `../docs/backend-agent-integration-reference.md` — 联调接入参考
4. 当前 `app/` 代码
5. `backend/schema.sql` — 数据库 schema 参考

- 如果文档与历史实现冲突，优先以当前非归档文档为准。
- `WORKFLOW.md` 是联调进度和跨窗口恢复上下文的主状态文件，不是接口契约来源。

## Contract Discipline

- 不允许隐式扩展 API 契约。
- 不允许新增、删除、重命名任何对外 API 字段、路径参数、query 参数、response 字段、状态枚举，除非用户明确确认。
- 不允许新增未在 OpenAPI 或接口规范中声明的 `task_type`、`status`、`error_code` 语义。
- 只要字段会通过前端可见接口返回，就视为对外契约；不得以“内部实现”为理由新增后再暴露。
- 任何同步/异步行为变化也视为契约变化，必须先确认。包括但不限于：
  - 原本由前端轮询结果，改为请求内直接等待外部调用完成
  - 原本快速返回，改为响应时间依赖新增的 Agent / 外部服务调用
  - 原本同步返回结果，改为返回 `task_id` 轮询
- 若实现发现现有契约不足，必须先停止修改，并向用户明确说明：
  1. 当前契约限制
  2. 为什么无法按现有契约正确实现
  3. 建议的契约变更
  4. 受影响的文档和代码文件
- 未获确认前，不允许先改代码再补文档。

修改 API 接口前，必须先核对：
- `../docs/10-client-api/Client-API.openapi.json`
- `../docs/10-client-api/API_前端接口规范.md`
- `../docs/20-agent-api/Agent-Service.openapi.json`
- `../docs/20-agent-api/API_Agent内部接口规范.md`

并在修改说明中显式写出：
- 本次是否改变 Client API 契约：`是` / `否`
- 本次是否改变 Agent API 契约：`是` / `否`

修改 API 接口后，必须再次核对以下项目是否与 OpenAPI 和接口规范一致：
- 路径参数
- query 参数
- response 字段
- `task_type` / `status` / 其他枚举值
- 字段是否允许为 `null`

若任一项发生变化，必须判定为“契约漂移”，先说明并等待用户确认，不允许直接提交实现。
## Architecture Boundaries

### Backend 分层职责

- `api/v1`：FastAPI 路由、鉴权依赖、参数校验、统一返回包装 `{code, message, data}`、SSE 代理、异步任务协议适配。
- `schemas`：前端请求/响应 Pydantic 实体，以及 Webhook 请求实体。
- `models`：SQLAlchemy ORM 实体，对齐 `backend/schema.sql`。
- `db`：数据库连接、会话初始化。
- `core`：配置（`AGENT_SERVICE_URL` 等）、安全、JWT。
- `services`：跨路由复用的业务编排，核心是 `agent_client.py` 统一 Agent HTTP 客户端。

避免把复杂业务逻辑堆进 `api` 层。API 层做鉴权、参数校验、响应包装；Agent 请求组装、Webhook 结果落库、任务状态流转下沉到 service。

### Backend 负责
- 用户鉴权和课程权限校验
- SQL 查询和写入（UserProfile、Resource、QuizQuestion、Evaluation、LearningPath、Conversation、AsyncTask 等）
- AsyncTask 创建和状态维护
- 前端 API 响应格式（`{code, message, data}`）
- Webhook 接收和业务数据落库
- 原始对话消息保存
- SSE 代理：接收 Agent SSE 流，转发给前端

### Agent Service 负责
- LLM 调用和 AgentScope 编排
- RAG 检索（Qdrant course knowledge / user memory）
- 结构化 AI 结果生成
- Tutoring SSE 内容生成
- Resources 异步生成 + 回调 Backend Webhook

### 禁止
- Backend 直接访问 Qdrant
- Backend 导入 `agent_service` Python 模块
- Agent Service 直接写 Backend SQL
- Agent Service 自行生成 `task_id`（必须由 Backend 传入）
- 修改 `../docs/` 下已有文档，除非用户明确要求

## Code Change Rules

- 修改代码前需要分析并说明问题。
- 修改代码前必须先输出：
  1. 问题分析
  2. 计划修改的文件
  3. 修改方案
  4. 可能影响的功能
- 用户确认后，才允许修改文件。
- 保持命名风格和当前项目结构。
- 以接口或明确子能力为修改边界，不要过度影响其他功能。
- 一次不超过 5 个文件。
- 不要过度工程化。
- 新增跨层函数时添加简短注释说明作用、输入和输出。
- 注释与 `API_Agent内部接口规范.md` 语义一致，不编造协议字段。

## Incremental Development

- 默认一次只推进一个接口或一个明确子能力。
- 推荐流程：
  1. 写或补测试
  2. 运行测试确认失败
  3. 最小实现
  4. 运行相关测试
  5. 更新 `WORKFLOW.md`

## Progress Tracking

每次完成一个小阶段后更新 `WORKFLOW.md`，至少同步：

- 对应接口的联调状态
- 当前上下文
- 下一步建议
- 已运行的测试命令和结果

临时进度、当前任务、下一步队列写入 `WORKFLOW.md`，不写入 `AGENTS.md`。

## Testing

- 修改代码后优先运行相关测试。
- 修改 Agent 联调逻辑后覆盖：
  - Agent 请求 payload 正确性
  - Agent 不可用时降级（task failed，不崩服务）
  - Agent 超时处理
  - SQL 落库正确性
- 修改 `models/`/`db`/`schema.sql` 后运行导入检查。

## Context Handoff

每次开始 Backend 联调前，先执行：

```bash
pwd
git status --short
curl -s http://127.0.0.1:8002/agent/v1/health
```

跨窗口继续时，以 `AGENTS.md`、`WORKFLOW.md`、`git status --short`、最近测试结果为主要上下文。

## Git

- 避免在 `main` / `dev` 直接开发。
- 默认在 `feat/backend-agent-integration` 分支。
- 修改前识别已有未提交内容，不回滚无关改动。
- 使用 `git stash` 前告知用户。
- 每次修改后 git commit（不 push）。
- 提交只纳入本轮文件。

## Completion Summary

每次完成任务后回复包含：

- 当前完成
- 修改文件
- 测试结果
- Agent API 契约是否漂移
- 下一步建议
