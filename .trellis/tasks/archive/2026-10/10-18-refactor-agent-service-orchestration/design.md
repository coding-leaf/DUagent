# Agent Service v2 架构重构技术设计

## 1. 核心架构演进 (Before vs After)

### Before (技术债与反模式)
```
[Client] -> [Backend] -> [Agent Service :8002]
                            |
                     FastAPI 主应用
                            |
                   /team-runtime (ASGI 子 App)
                            | (HTTP 回环调用 localhost:8002)
                   LeaderAgent (150行 Prompt 假 Team)
                            | (再次 HTTP 回环调用)
                   Researcher / Workbench / DataAnalyst
```
*致命缺陷*：单次请求内嵌套 3~4 次 HTTP 本地网络往返，SSE 拆包重新打包，状态通过魔改 storage 传递，延迟极高且极脆弱。

### After (KISS 原生 ReAct 编排)
```
[Client] -> [Backend] -> [Agent Service /api/v2/chat/stream]
                            |
                  EventStreamBroadcaster (协议解耦层)
                            |
                 WorkbenchReActAgent (AgentScope 2.0.10)
                            | (纯内存调用)
                 AgentScope Toolkit (原生异常隔离)
                 ├── CourseRAGRetriever (Qdrant)
                 ├── BackendLearningClient (OJ/测验/画像)
                 └── Workspace (本地沙箱)
```

## 2. 依赖声明精简方案

在 `agent_service_v2/pyproject.toml` 中：
```toml
dependencies = [
    "agentscope[models,rag,vdb-qdrant,storage-redis,workspace]>=2.0.10",
    "fastapi>=0.138.2",
    "pydantic>=2.13.4",
    "pydantic-settings>=2.14.2",
    "sse-starlette>=3.4.5",
    "uvicorn>=0.49.0",
]
```
剔除 `extra == "tools"`（避免引入无 Windows 二进制 wheel 的 `ripgrep`），保留业务所需的全部能力。

## 3. SSE 流式广播器 (EventStreamBroadcaster) 设计

适配器接收 Agent 异步事件流，规范化为标准 SSE：
- `workflow_started`: 初始化携带 `run_id` 与 `conversation_id`。
- `thought`: 模型思考推理片段。
- `text_delta`: 正文增量片段（payload: `{"delta": "..."}`）。
- `tool_started`: 工具触发（payload: `{"tool_call_id": "...", "tool_name": "...", ...}`）。
- `tool_completed`: 工具执行完毕（payload: `{"tool_call_id": "...", "status": "completed"|"error", "output_summary": "..."}`）。
- `workflow_completed`: 携带最终 `message_id` 正常结束。
- `workflow_failed`: 捕获非预期失败，友好通知前端。

## 4. 工具异常容错策略

利用 AgentScope 2.x `Toolkit` 的原生机制：
- 工具抛出一般异常时，框架转换为 `ToolResponse(state=ToolResultState.ERROR)`。
- 大模型在下一步将其作为普通 Observation 继续推理，绝不向外冒泡破坏 ASGI 响应流。
