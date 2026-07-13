# Agent Service v2 开发导读

## 定位

`agent_service_v2/` 是当前唯一 Agent Service。它基于 AgentScope 2.x，负责 Agent/Team、LLM、工具、RAG、Memory、Workspace 和 EDU 事件适配，不访问 MySQL。

## 阅读顺序

1. `agent_service_v2/AGENTS.md`
2. `agent_service_v2/README.md`
3. `agent_service_v2/src/agent_service_v2/main.py`
4. `agent_service_v2/src/agent_service_v2/api/`
5. `agent_service_v2/src/agent_service_v2/agents/`、`team/`、`tools/`
6. `agent_service_v2/src/agent_service_v2/runtime/`、`session/`、`workspaces/`
7. `agent_service_v2/tests/`
8. `docs/20-agent-api/`

## 运行链路

```text
Frontend -> Backend -> Agent Service v2 -> Qdrant / LLM
                      -> Backend internal API or webhook -> MySQL
```

- Workbench：`/agent/v2/workbench/*`
- 资料、KG、题目、公共资源：`/agent/v2/knowledge/*`
- 学情评估与作答诊断：`/agent/v2/evaluation/*`
- 个性化资源团队：`/agent/v2/personalized-resources/*`

学习路径和画像刷新属于 Backend 规则能力，不在 Agent Service 中生成。

## 开发约束

- AgentScope Agent 拥有推理和工具循环，不手写替代循环。
- 工具必须经 Toolkit 注册，并保留权限、超时和结构化结果边界。
- Workspace 由服务端可信的 user/course/conversation 标识派生。
- AgentScope 事件经 runtime adapter 转换为 EDU 协议，不直接暴露。
- 不新增 `/agent/v1/*` 兼容入口。

## 验证

```bash
cd agent_service_v2
./.venv/bin/pytest
./.venv/bin/python -c "from agent_service_v2.main import app; print(sorted(app.openapi()['paths']))"
```
