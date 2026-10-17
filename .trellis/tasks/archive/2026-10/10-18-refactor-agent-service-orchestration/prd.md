# 重构 Agent Service 编排与流式引擎架构

## Goal

将 `agent_service_v2` 升级至 AgentScope 2.0.10，拔除内部 `/team-runtime` ASGI 回环与虚假 Team 串行，收敛为原生内存流转的 ReAct 工作台，统一强类型 SSE 事件广播契约，并消除 Windows 环境下的 C++ 编译阻碍。

## Requirements

1. **依赖与环境瘦身**：
   - 将 `agent_service_v2/pyproject.toml` 中的 `agentscope[full]>=2,<3` 替换为精准依赖：`agentscope[models,rag,vdb-qdrant,storage-redis,workspace]>=2.0.10`。
   - 彻底摆脱 `ripgrep` 的 Rust/MSVC 编译阻碍，确保在 Windows 与 Linux 环境下 `uv sync` 一键秒级构建。

2. **协议抽离层（EventStreamBroadcaster）**：
   - 编写独立的事件广播适配器，解耦 AgentScope 内部事件与外层 HTTP SSE 协议。
   - 输出符合前端 `chatStreamEvents.js` 预期的结构化事件：`workflow_started`、`thought`、`text_delta`、`tool_started`、`tool_completed`、`workflow_completed`、`workflow_failed`。

3. **拔除伪 Team，重构 ReAct 工作台**：
   - 废除 `team_app.py` 中基于 ASGI 子 App 的 HTTP 回环与内联 Prompt 拼接的 `leader_team.py`。
   - 实现高内聚的 `WorkbenchReActAgent`，直接使用 AgentScope 原生 `Toolkit` 挂载业务工具（知识库检索、OJ 评测、题库抽取等）。
   - 保留 AgentScope 原生异常机制（框架在工具抛出异常时自动转换为 `ToolResultState.ERROR`），严禁未捕获异常破坏 SSE 流。

4. **无状态计算与课程上下文注入**：
   - 保持 Agent Service 计算层无状态，以 Backend 为持久化权威，按请求传入历史记录。
   - 知识库检索（RAG）自动绑定请求中的 `course_id`，并提供空库降级处理。

## Acceptance Criteria

- [x] `agent_service_v2` 使用 `uv sync` 干净成功构建虚拟环境，无任何编译报错。
- [x] `/team-runtime` 路由及伪 Team 内部 HTTP 回环彻底移除，代码无废弃死路径。
- [x] 对话交互通过统一 `WorkbenchReActAgent` 正常运行，工具调用与思考链完整工作。
- [x] SSE 流式输出稳定规范，前端能正常接收增量文本并渲染工具卡片。
- [x] 工具发生异常时自动降级容错，SSE 连接不中断。
