---
name: agentscope-v2-development
description: Use when developing, refactoring, or reviewing agents, tools, workflows, memory, workspaces, or deployment components in the agent_service_v2 package.
---

# AgentScope v2.0.3 智能体开发规范

## Overview
在 `agent_service_v2` 中开发智能体必须完全使用 AgentScope v2.0.3 的原生抽象（如 `Agent`、`Msg`、`reply_stream`、`append_event`、`tasks_context`），**严禁自建 LLM 交互循环与手写防御性 JSON 解析**。

---

## When to Use

### 适用场景
*   在 `agent_service_v2` 中新建或重构智能体（Agent）。
*   为智能体编写、配置或挂载外部工具（Tools）与服务。
*   编写多智能体协作、规划（Planning）或微服务化部署（AaaS）逻辑。

### 不适用场景
*   纯粹的前端 UI 渲染（使用 React 相关的 SWR / MVVM 规范）。
*   与 AI 逻辑完全解耦的普通后台 HTTP 路由或单纯数据库 CRUD。

---

## Core Pattern

### 1. 消息重构与事件流 (Message Reconstruction)
*   **Before (❌ 脏代码 - 正则配平与手写 JSON 截取)**：
    ```python
    # 绕过框架直接获取 LLM 文本，并手写复杂的正则和花括号配平
    raw_output = await chat_provider.complete([ChatMessage(...)])
    match = re.search(r"<agent_result>(.*?)</agent_result>", raw_output)
    payload = json.loads(match.group(1)) # 极易因多行转义或未配平崩溃
    ```
*   **After (✅ 规范代码 - append_event 自还原与 API 结构化提取)**：
    ```python
    from agentscope.message import AssistantMsg
    from agentscope.event import ReplyStartEvent

    msg = None
    # 1. 订阅标准流式事件
    async for event in agent.reply_stream(user_message):
        if isinstance(event, ReplyStartEvent):
            # 2. 用 ReplyStartEvent 初始化 Msg
            msg = AssistantMsg(name=event.name, content=[], id=event.reply_id)
        else:
            # 3. 依靠框架将事件增量还原到 msg 中
            if msg is not None:
                msg.append_event(event)

    # 4. 从还原后的结构化消息中，直接获取解析好的工具块
    tool_calls = msg.get_content_blocks("tool_call")
    ```

### 2. 规划与任务驱动 (Planning & Plan Mode)
*   **Before (❌ 脏代码 - 手写 while/if/else 控制任务流)**：
    ```python
    # 用复杂的硬编码逻辑和状态字段来判断下一步做什么
    if task == "fetch":
        run_fetch()
    elif task == "draft":
        run_draft()
    ```
*   **After (✅ 规范代码 - 使用官方 Planning 工具及 tasks_context 驱动)**：
    ```python
    from agentscope.agent import Agent
    from agentscope.tool import Toolkit, TaskCreate, TaskGet, TaskList, TaskUpdate

    # 1. 装备官方的 Planning 状态注入工具
    toolkit = Toolkit(
        tools=[TaskCreate(), TaskGet(), TaskList(), TaskUpdate()]
    )
    agent = Agent(
        name="planner",
        system_prompt="...",
        model=model,
        toolkit=toolkit,
    )
    # 2. 或是预先向 tasks_context 注入任务图（双向依赖 blocks 与 blocked_by）
    agent.state.tasks_context.tasks.extend([
        Task(id="1", subject="第一步", description="..."),
        Task(id="2", subject="第二步", description="...", blocked_by=["1"])
    ])
    agent.state.tasks_context.tasks[0].blocks.append("2")
    ```

---

## Quick Reference

| 模块名称 | 框架核心类 / 接口 | 核心作用与使用规范 |
| :--- | :--- | :--- |
| **消息 block** | `TextBlock`, `ThinkingBlock`, `ToolCallBlock`, `ToolResultBlock` | `msg.role=="assistant"` 可装载所有类型 blocks。 |
| **消息提取** | `msg.get_text_content()`, `msg.get_content_blocks("tool_call")` | 用于从还原的 Msg 中直接提取结构化段落，**禁止正则切割**。 |
| **上下文 offload** | `Agent(offloader=workspace)`, `ContextConfig` | 超过 `tool_result_limit` 的结果将自动 offload 到 workspace 中。 |
| **高危工具权限** | `PermissionContext`, `PermissionRule`, `RequireUserConfirmEvent` | 阻断敏感行为（如修改配置），抛出 ASK 事件等待 user_confirm 总线。 |
| **可观测追踪** | `MiddlewareBase`, `AgentRunLoggingMiddleware` | 中间件钩子记录 Model/Tool call 周期，生成 traces 分发给 Studio。 |
| **团队协同** | `TeamCreate`, `AgentCreate`, `TeamSay` | 沟通通过 `MessageBus` 异步推入 inbox 并通过 wakeup 信号解耦并发。 |

---

## Common Mistakes

### 1. 越权调用 Model
*   **错误做法**：直接调用 `model.complete([...])` 或 `chat_provider.complete(...)`。
*   **后果**：绕过了 Agent 挂载的 Memory，Observability 完全缺失，无法产生事件流。
*   **纠正**：必须在定义好的 `Agent` 上执行 `agent(msg)` 或 `agent.reply_stream(msg)`。

### 2. 手写多轮嵌套协同 (Nested Coroutines)
*   **错误做法**：在 Leader Agent 内部直接 `await worker_agent.reply()` 来串行同步获取返回。
*   **后果**：高并发多租户环境下协程堵塞崩溃。
*   **纠正**：多智能体交互一律在 MessageBus 底座上，使用 `TeamSay` 投递 `HintBlock` (带有 `<team-message from="...">` 标识)，以 inbox 消息驱动 Worker 进程。

---

## Red Flags (审查禁区 - 触发即回滚)

*   [ ] 导入了底层的 LLM Client（如 `from openai import ...` 或 `httpx.post` 到模型接口）。
*   [ ] 出现了针对模型输出进行 XML 解析、正则提取 JSON、括号计数配平的手写函数。
*   [ ] 在 `Agent` 类外部手写 Python `while` 循环做智能体推理。
*   [ ] 绕过 `Workspace` 对象直接使用 `open("host/absolute/path", "w")` 写入生成资产。

> **提示**：违反上述任何一项，均视作违背框架规范开发，必须立即回滚并重构。
