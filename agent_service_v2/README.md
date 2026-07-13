# EDUagent Agent Service v2

当前唯一 Agent Service 运行时，基于 AgentScope 2.x 和 FastAPI。

## 目录

- `src/agent_service_v2/api/`：v2 HTTP/SSE 接口
- `src/agent_service_v2/agents/`、`team/`：Agent 与团队
- `src/agent_service_v2/tools/`：AgentScope 工具
- `src/agent_service_v2/runtime/`：事件总线与 EDU 协议适配
- `src/agent_service_v2/session/`、`workspaces/`：会话与工作区隔离
- `tests/`：真实入口、Agent 生命周期和工具测试

## 启动

```bash
./.venv/bin/uvicorn agent_service_v2.main:app --host 127.0.0.1 --port 8002
```

根目录 `./start_all.sh` 会使用同一入口启动服务。

## 验证

```bash
./.venv/bin/pytest
```

正式内部接口以 `../docs/20-agent-api/` 为准。只支持 `/agent/v2/*`；学习路径由 Backend 根据知识图谱和实时进度计算。
