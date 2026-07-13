# AGENTS.md

## Scope

本文件补充根目录 `AGENTS.md`，适用于 `agent_service_v2/`。

- 负责 AgentScope 2.x Agent、团队、工具、RAG、Workspace、Middleware、运行事件和 FastAPI 协议适配。
- 不写 MySQL；业务事实通过 Backend 内部 API 或 webhook 持久化。
- 不暴露 AgentScope 原始事件，统一适配为 EDU 协议。
- Backend 传入的 `task_id`、用户、课程和会话标识必须原样使用；不得自行生成业务任务标识。

## Source Of Truth

1. `src/agent_service_v2/` 当前运行代码
2. `tests/` 对真实入口和框架生命周期的验证
3. `../docs/20-agent-api/` 当前 v2 契约
4. `../WorkLine.md`

文档与代码冲突时，以实际入口和测试为准，并在 `WorkLine.md` 记录差异。

## Architecture

- `api/`：FastAPI 路由与协议边界
- `agents/`、`team/`：AgentScope Agent 与团队编排
- `tools/`：注册到 AgentScope Toolkit 的原子能力
- `runtime/`：运行总线、事件适配和生命周期
- `session/`、`workspaces/`：可信标识派生的隔离边界
- `generators/`：非 Agent 的结构化生成能力
- `safety/`：权限与安全限制

主推理/工具循环必须由 AgentScope Agent 驱动。不得重新引入手写 LLM/tool 循环，不得恢复 `/agent/v1/*`。

## Verification

```bash
./.venv/bin/pytest
./.venv/bin/python -c "from agent_service_v2.main import app; print(sorted(app.openapi()['paths']))"
```

修改接口、运行时、工具、Workspace 或事件适配后，必须运行对应测试及全量测试，并更新根目录 `WorkLine.md`。
