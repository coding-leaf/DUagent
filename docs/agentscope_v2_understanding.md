# AgentScope 2.0.3 全模块深度理解与 v2 重构设计规范

本规范完全基于 AgentScope 2.0.3 官方 `llms.txt` 引用的核心设计与部署文档，为 `agent_service_v2` 在核心积木、沙箱工作区、权限及智能体服务化（AaaS）等全部板块下的开发和迁移确立强约束红线，彻底杜绝手写框架的隐患。

---

## 一、 核心构建模块规范 (Building Blocks)

### 1. 消息与事件 (Message & Event)
*   **官方设计**：
    *   `Msg` 包含 Ordered blocks：`TextBlock`、`DataBlock` (通过 Base64/URL 表达多模态)、`ThinkingBlock` (思维链)、`ToolCallBlock`、`ToolResultBlock`、`HintBlock` (用于系统提示、定时提醒或团队消息)。
    *   `Event`（继承自 `EventBase`）是 streaming 传输单元。运行 `agent.reply_stream()` 会产生 `TextBlockDeltaEvent`、`ToolCallDeltaEvent`、`RequireUserConfirmEvent` 等。
    *   **核心机制**：框架内置 `msg.append_event(event)` 可增量还原 `Msg` 的状态，前端可使用官方 `@agentscope-ai/agentscope` 的 `appendEvent` 在端侧异步还原气泡消息。
*   **v1 痛点**：手动编写复杂的正则提取工具入参，并手写括号配平 `_scan_balanced_object_end` 等极其脆弱的防御解析代码。
*   **v2 规范**：
    *   **强红线**：禁止在智能体内部手写 JSON 提取与正则截取。
    *   必须使用流式调用 `agent.reply_stream()` 配合 `msg.append_event()` 累加还原 `Msg`，再直接通过 `msg.get_content_blocks("tool_call")` 提取结构化参数。

### 2. 智能体 (Agent) 与模型 (Model)
*   **官方设计**：
    *   2.x 统一以基类 `Agent` 为核心，移除独立 `ReActAgent` 子类。ReAct 能力通过 `react_config=ReActConfig()` 配置化注入，上下文溢出限制通过 `context_config=ContextConfig()` 管理。
*   **v1 痛点**：直接提取 `chat_provider` 并手写 `chat_provider.complete(...)` 越级调用，彻底破坏了框架的 Memory 链路与 Observability 中间件。
*   **v2 规范**：
    *   **强红线**：禁止绕过 `Agent` 实例手写 LLM API。一切大模型调用必须实例化 `Agent`，并经由 `model_provider.py` 注册的官方 Model。

### 3. 上下文管理 (Context) 与长期记忆 (Long-Term Memory)
*   **官方设计**：
    *   大尺寸的 tool result 或压缩过的历史 message 会通过 `workspace.offload_context()` / `offload_tool_result()` 自动 offload 到本地的 `sessions/<session_id>/` 目录下，在 message 中仅留下引用 Path（符合 `Offloader` 协议）。
*   **v1 痛点**：手写防御性的 `while` 循环截断 message 列表，且没有处理离线数据隔离。
*   **v2 规范**：
    *   必须将 Workspace 传入 `Agent` 作为 `offloader`，依靠框架内置的 `ContextConfig(tool_result_limit=...)` 进行上下文自动截断与离线存储。

### 4. 计划模式 (Plan)
*   **官方设计**：
    *   四大状态注入工具：`TaskCreate`、`TaskGet`、`TaskList`、`TaskUpdate`。
    *   计划的 TODO List、所有者（owner）以及 blocks/blocked_by 依赖图 scoped 在 `agent.state.tasks_context` 中。
*   **v1 痛点**：在路由层或智能体内部写一大堆 `if/else` 硬编码来实现复杂的拆步路由控制。
*   **v2 规范**：
    *   凡是 3 步以上且存在依赖的任务，必须通过在 `agent.state.tasks_context` 中注入 `Task` 图结构，并装备上述四大工具，由 ReAct 自主更新和 claim 任务，严禁手写控制流状态机。

### 5. 工具 (Tool) 与权限系统 (Permission System)
*   **官方设计**：
    *   全局支持 5 种 Permission Mode：`DEFAULT`、`ACCEPT_EDITS`、`EXPLORE` (只读)、`BYPASS`、`DONT_ASK`。
    *   通过 `PermissionContext` 注册 `PermissionRule(tool_name, rule_content, behavior, source)`。
    *   敏感操作通过 `bypass_immune=True` 实现不可绕过的安全 ASK，而 Bash 的 read-only 指令（如 `ls`、`cat`、`pip show`等）则是原生自动 ALLOW。
*   **v1 痛点**：智能体函数内部无鉴权地直接请求外部接口。
*   **v2 规范**：
    *   所有外部操作一律包装为 `FunctionTool` / `ToolBase`；涉及修改或 Shell 执行的高危工具必须通过 `PermissionRule` 拦截，在 `DEFAULT` 模式下统一触发 `RequireUserConfirmEvent` 并交由平台总线提示用户授权。

### 6. 中间件 (Middleware)
*   **官方设计**：
    *   智能体级别中间件继承自 `MiddlewareBase`。框架默认强制安装：
        *   `InboxMiddleware`：只负责接收 hint 信息（如定时事件、团队消息）。
        *   `ToolOffloadMiddleware`：处理后台异步超时工具并将结果以 hint + wakeup 推回总线。
        *   `StateChangeMiddleware`：当 `tasks_context` 变化时生成 `CustomEvent` 广播。
*   **v1 痛点**：零星手写 `logger.info()` 埋点，造成追踪 Trace 丢失。
*   **v2 规范**：
    *   可观测性追踪必须使用 `MiddlewareBase`（例如 `AgentRunLoggingMiddleware`），在 reply/reasoning/tool 周期自动生成 traces 和 model span。

---

## 二、 工作区规范 (Workspace)

*   **官方设计**：
    *   提供 `LocalWorkspace` (宿主文件系统)、`DockerWorkspace` 和 `E2BWorkspace` (云端沙箱)。
    *   对于隔离的 Docker/E2B，通过在沙箱内部署 **MCP Gateway** 暴露 FastAPI 服务，Host 端使用 `GatewayMCPClient` 和 `GatewayMCPTool` 通过 Bearer Token 与网关通信以穿越 stdio 物理边界。
*   **v1 痛点**：没有规范的工作目录，导致智能体运行生成的文件凌乱，甚至冲突覆盖。
*   **v2 规范**：
    *   **强红线**：智能体运行时产生的文件（如代码运行、artifact 产生）必须被隔离在 `workspace.workdir` 下。
    *   多租户并发时由 `LocalWorkspaceManager` 等依据 `agent_id`/`session_id` 自动缓存和创建隔离的工作区目录，严禁硬编码绝对宿主机路径。

---

## 三、 智能体即服务规范 (Agent as a Service, AaaS)

### 1. 微服务部署 (Architecture)
*   **官方设计**：
    *   AaaS 基于 FastAPI，配合 `StorageBase`（内置 `RedisStorage`，可自定义 `PostgresStorage`）和 `MessageBus` 实现多租户多会话微服务。
    *   通过 `MessageBus` 解耦请求触发与 SSE 流推送，以便在 Serverless/K8s 集群中水平扩展。
*   **v1 痛点**：在智能体端直接做 HTTP 推送或自建消息轮询。
*   **v2 规范**：
    *   智能体不能感知外部的网络 API 状态，所有的响应必须通过 `reply_stream()` 产生原生事件，由 Protocol Adapter 转化为 SSE 形式向 `MessageBus` 推送，实现解耦。

### 2. 智能体团队协作 (Agent Team)
*   **官方设计**：
    *   多智能体协作不依靠另外的框架，完全被抽象为四个内置的 Team Tools：`TeamCreate`、`AgentCreate` (派生子智能体)、`TeamSay` (点对点/广播沟通)、`TeamDelete` (解散团队)。
    *   **并发解耦**：Leader 与 Worker 是独立的 Session 实体，各拥有其 event stream。Leader 通过 `TeamSay` 投递 `HintBlock`（带 `<team-message from="...">` 标记）并发出 wakeup 信号唤醒空闲的 Worker，实现在不同进程/节点上的异步并发。
*   **v1 痛点**：在 Python 内部手写嵌套的协同循环（Nested Coroutine），导致多租户请求堵塞。
*   **v2 规范**：
    *   **强红线**：多智能体交互严禁手写循环，必须注册官方的 Team Tools，通过 `MessageBus` 发出 `inbox + wakeup` 信号来驱动 Worker 并行运作。
    *   利用 `SubAgentTemplate` 注册不同岗位模版（如 explorer/coder），并分别注入对应的 Permission Mode（只读 vs 读写）。
