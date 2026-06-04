# AGENTS.md

该文档已过时

## Scope

- 负责 `backend/` 内的主业务后端服务。
- 负责用户、鉴权、课程、SQL 持久化、任务状态、前端 API、Agent Service 调用适配和 Webhook 落库。
- 不负责 `agent_service/` 内部的 LLM、AgentScope、Qdrant RAG、提示词、智能体编排实现。
- 不负责前端 UI 实现。
- Backend 只通过 HTTP 调用 Agent Service 的 `/agent/v1/*` 接口，不导入 `agent_service` Python 模块。
- Agent Service 不直接写 Backend 数据库；Backend 负责校验 Agent 返回结果并写入 SQL。

## Source Of Truth

开发时优先级如下：

1. `docs/10-client-api/Client-API.openapi.json`
2. `docs/10-client-api/API_前端接口规范.md`
3. `docs/20-agent-api/Agent-Service.openapi.json`
4. `docs/20-agent-api/API_Agent内部接口规范.md`
5. `docs/backend-agent-integration-reference.md`
6. 当前 `backend/` 代码
7. `backend/schema.sql`

- 前端可见接口以 `docs/10-client-api` 为准。
- Backend 调用 Agent Service 的内部契约以 `docs/20-agent-api` 为准。
- Backend-Agent 联调落地细节优先参考 `docs/backend-agent-integration-reference.md`。
- 如果文档与历史实现冲突，优先以当前非归档文档为准。
- `backend/schema.sql` 是当前数据库初始化脚本参考；若与模型或接口契约冲突，先分析影响，再决定改 SQL、模型或转换层。

## Architecture Boundaries

当前 Backend 分层职责固定为：

- `api/v1`：FastAPI 路由、鉴权依赖接入、参数接收、HTTP 状态码、统一返回包装、SSE 代理、异步任务协议适配。
- `schemas`：前端请求/响应 Pydantic 实体，以及 Backend 内部请求实体；字段应对齐 Client API 或 Agent API。
- `models`：SQLAlchemy ORM 实体，字段应与 `backend/schema.sql` 保持一致。
- `db`：数据库连接、会话、初始化。
- `core`：配置、安全、密码、JWT、跨模块基础能力。
- `services`：跨路由复用的业务编排、Agent Service HTTP client、协议转换和落库流程。若目录不存在，新增前先确认确实有复用价值。

避免把复杂业务逻辑堆进 `api` 层。API 层可以做权限校验、基础参数校验和响应包装；跨表查询、Agent 请求组装、Webhook 结果落库、任务状态流转等应优先下沉到 service/helper 层。

## Backend-Agent Boundary

- Backend 调 Agent Service 只能走 HTTP，不允许 `import agent_service...`。
- Backend 调用 Agent 前负责：
  - 从 SQL 聚合结构化上下文。
  - 创建本地 `async_tasks` 任务记录。
  - 对异步接口生成并传入 `task_id`。
  - 传入 Backend Webhook URL。
- Agent Service 返回或回调后，Backend 负责：
  - 校验 `task_id` 存在且归属正确。
  - 校验 `task_type` 与本地任务类型一致。
  - 校验结构化结果字段。
  - 幂等更新任务状态。
  - 将业务结果写入 SQL。
- Qdrant 的 `course_knowledge` 和 `user_memory` 由 Agent Service 管理；Backend 不直接读写 Qdrant。
- Backend 保存原始业务数据：用户、课程、题目、资源、对话消息、任务、画像、评估、学习路径。
- tutoring/chat 中 Backend 负责保存完整原始对话和消息 meta；Agent Service 负责生成回复和检索长期记忆/课程知识。

## Database Rules

- 修改 ORM 模型时，必须同步检查 `backend/schema.sql` 是否需要调整。
- 修改 `backend/schema.sql` 时，必须同步检查对应 `backend/app/models/` 是否一致。
- 不要让 API 返回直接依赖 ORM 对象隐式序列化，优先显式组装响应 dict 或 Pydantic schema。
- 假删字段 `is_deleted` 已存在时，查询默认过滤 `is_deleted == False`。
- 外键、唯一索引、任务幂等字段变化需要说明对现有数据的影响。
- 默认不修改生产数据初始化内容，除非任务明确要求。

## Code Change Rules

- 修改代码前需要分析并说明问题。
- 修改代码前必须先输出：
  1. 问题分析
  2. 计划修改的文件
  3. 修改方案
  4. 可能影响的功能
- 用户确认后，才允许修改代码文件。
- 文档类文件可在用户明确要求时直接修改，但仍需说明修改范围。
- 保持命名风格和当前项目结构。
- 只能小范围重构，以 minimal diff 为准则。
- 不要一次性修改超过 5 个文件；若有需要，先提出申请。
- 不要过度工程化；除非能简化调用、减少真实重复或隔离明确边界，否则不要引入复杂抽象。
- 新增对外承接函数、Agent 协议转换函数、Webhook 落库函数时，需要添加简短注释，说明作用、主要输入和输出。
- 简单私有辅助函数不强制添加长注释，优先用清晰命名表达意图。
- 注释应与 `docs/10-client-api` 和 `docs/20-agent-api` 的语义保持一致，不要编造协议字段。

## Incremental Development

- 默认一次只推进一个接口或一个明确子能力。
- 推荐流程：
  1. 写或补测试。
  2. 运行测试确认失败。
  3. 最小实现。
  4. 运行相关测试。
  5. 若涉及文档或 schema，补充同步说明。
- 除非用户明确要求，不要一次性实现多个接口的业务逻辑。
- Backend-Agent 联调优先按接口逐个闭环，不要一次性改完整 AI 功能链路。
- 非必要功能可最小实现，优先满足主要功能和契约正确性。

## Documentation Boundary

- `docs/10-client-api` 是前端与 Backend 的接口契约来源。
- `docs/20-agent-api` 是 Backend 与 Agent Service 的接口契约来源。
- 默认不修改 `docs/` 下任何文件。
- 如果代码与 `docs/` 冲突，默认修改代码或测试以贴合当前非归档文档。
- 只有用户明确要求时，才允许修改 `docs/`。

## Agent Service Integration Rules

- 新增 Agent 调用时，优先建立或复用统一 HTTP client，例如 `backend/app/services/agent_client.py`。
- Agent Service 地址从 `settings.AGENT_SERVICE_URL` 读取，不要在业务代码中硬编码端口。
- 同步 Agent 接口返回 `{code,message,data}` 时，Backend 应校验 `code` 和 `data` 后再落库。
- 异步 Agent 接口必须遵守 `task_id` 原样传递和 Webhook 回调约定。
- Webhook completed 回调必须幂等，重复 completed 不得重复插入业务数据。
- Webhook failed 回调应写入 `async_tasks.error_message`，必要时写入 `error_code`。
- Agent 超时、不可用或返回结构异常时，Backend 应给前端稳定错误响应或保持任务为 failed，不要暴露内部 traceback。

## Progress Tracking

- 当前仓库根目录没有专门的 Backend `WORKFLOW.md` 时，不要为了记录流水新建进度文件。
- 如用户要求维护进度文档，应先确认文件位置和格式。
- 每次完成开发任务后，最终回复至少说明：
  - 当前完成
  - 修改文件
  - 测试结果
  - Client API / Agent API 契约是否漂移
  - 下一步建议

## Context Handoff

每次开始 `backend` 开发前，先执行非修改型检查：

```bash
pwd
git status --short
sed -n '1,220p' AGENTS.md
```

跨窗口继续开发时，以 `AGENTS.md`、`git status --short`、相关文档和最近测试结果为主要上下文。

## Git

- 避免在 `master` / `main` / `dev` 等主分支直接开发。
- 默认在用户当前分支开发；如需新分支，先说明原因。
- 修改前如工作区已有未提交内容，必须先识别哪些是用户改动，不能回滚或覆盖无关改动。
- 如需使用 `git stash`，必须先告知用户。
- 每次文件修改后需要总结修改内容并 git commit（并非 git push）。
- 提交时只纳入本次任务相关文件，不要顺手提交用户已有改动。

## Testing

- 修改 Python 代码后，优先运行相关测试。
- 修改 `api/` 或 `schemas/` 后，优先运行对应接口测试；如存在 OpenAPI 对齐测试，也必须运行。
- 修改 `models/`、`db/` 或 `schema.sql` 后，至少运行模型导入检查或应用启动检查。
- 修改 Agent 联调逻辑后，至少覆盖：
  - Agent 请求 payload 组装。
  - Agent 返回/回调结构校验。
  - SQL 落库或任务状态更新。
- 如无现有测试，至少运行基本导入检查或启动检查。
- 推荐使用 `pytest`。
- 不为了测试而大规模重构项目。

## Commands

`backend/` 使用 `requirements.txt` 管理 Python 依赖，根目录不是 Backend 运行目录。

当前常用命令在 `backend/` 目录下执行：

```bash
python -m pytest
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
python -m app.main
```

如使用虚拟环境，请优先使用项目已有环境；不要在仓库根目录直接安装依赖或运行服务。

## Completion Summary

每次完成开发任务后，最终回复需要包含：

- 当前完成
- 修改文件
- 测试结果
- Client API / Agent API 契约是否漂移
- 下一步建议
