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

## AI Chat 联网检索

Workbench 可按需接入固定版 `open-websearch@2.1.11` MCP。代码默认关闭，根目录
`./start_all.sh start` 从根目录 `.env` 读取该配置；其他启动方式可显式设置为
`false`。只向 AgentScope Toolkit 注册 `search`，不开放网页正文抓取工具。

运行配置：

- `WEB_SEARCH_ENABLED`：是否启用，默认 `false`。
- `WEB_SEARCH_PACKAGE`：NPX 包，默认 `open-websearch@2.1.11`。
- `WEB_SEARCH_DEFAULT_ENGINE`：默认 `baidu`。
- `WEB_SEARCH_ALLOWED_ENGINES`：默认 `baidu,sogou,bing,csdn,juejin`。
- `WEB_SEARCH_TIMEOUT`：单次调用超时秒数，默认 `12`。
- `WEB_SEARCH_USE_PROXY`：是否使用显式代理，默认 `false`。
- `WEB_SEARCH_PROXY_URL`：启用代理时使用的地址。

MCP 连接、工具发现或调用失败不会阻断 Agent Service；AI Chat 会继续处理稳定知识，
但必须明确说明无法联网核实当前信息。MCP 子进程不会继承模型密钥或 Backend Token。

## 验证

```bash
./.venv/bin/pytest
./.venv/bin/python -c "from agent_service_v2.main import app; print(sorted(app.openapi()['paths']))"
```

正式内部接口以 `../docs/20-agent-api/` 为准。只支持 `/agent/v2/*`；学习路径由 Backend 根据知识图谱和实时进度计算。
