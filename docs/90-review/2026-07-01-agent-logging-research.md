# Agent 日志与可观测性调研报告

生成时间：2026-07-01
范围：AIChat / AgentScope 2.x / Tool 调用 / 开发者调试日志
结论级别：用于下一步设计与实现，不是已完成实现说明

## 1. 结论摘要

当前 EDUagent 的 `debug_log` 方向是对的，但抽象层次还不够清晰。行业和框架更常见的做法不是只做一条平铺日志流，而是把 Agent 运行拆成：

- Trace：一次用户请求或一次对话 turn 的端到端执行。
- Span：Trace 内的一个有开始和结束时间的操作，例如 agent invoke、model call、tool execution、retrieval、memory read。
- Event：Span 内发生的离散事件，例如 streaming chunk、tool planned、permission required、artifact emitted。
- Log record：面向开发者的结构化摘要，可从 span/event 投影出来，用于本地 UI、grep、问题复盘。

对 EDUagent 来说，推荐落地方式是：

1. 保留前端 `debug_log` 作为开发浮窗输入，但不要把它作为唯一真实日志模型。
2. 在 Agent Service 内部建立统一 `AgentTrace` / `AgentSpan` / `AgentEvent` 结构。
3. `debug_log` 只是从统一结构投影出来的轻量开发视图。
4. 后续可接 OpenTelemetry OTLP，开发期也可以继续使用当前浮窗。

## 2. 调研来源

### 2.1 AgentScope 2.x 官方做法

AgentScope 2.0.3 官方文档明确把 middleware 定位为 agent 生命周期关键位置的拦截机制，可用于日志、追踪、输入改写和访问控制。它提供的 hook 覆盖：

- `on_reply`：一次完整 reply。
- `on_reasoning`：一轮 ReAct 推理。
- `on_model_call`：底层模型 API 调用。
- `on_acting`：一次工具调用。
- `on_compress_context`：上下文压缩。
- `on_system_prompt`：system prompt 生成。
- `list_tools`：middleware 提供工具。

官方还强调 `on_acting` 只包裹 agent 内部工具执行，通过 external execution 在 agent 外执行的工具不会被该 hook 追踪到。

AgentScope 内置 `TracingMiddleware` 会接入 OpenTelemetry，并在 `on_reply`、`on_model_call`、`on_acting` 三个位置生成层级 span。官方描述的采集字段包括：

- reply：agent 名称、session ID、reply ID、输入消息、最终输出、HITL 等待工具调用。
- model call：模型名、provider、输入/输出 token、请求与响应内容，并包装流式响应。
- tool execution：工具名、调用 ID、入参、执行结果。

来源：
https://docs.agentscope.io/versions/2.0.3/zh/building-blocks/middleware

### 2.2 OpenTelemetry GenAI 语义约定

OpenTelemetry GenAI 语义约定把 GenAI 操作定义成 spans。关键点：

- GenAI span 应覆盖从操作开始到响应完整收到，或错误/取消为止。
- model inference span 建议记录 `gen_ai.operation.name`、provider、model、conversation id、stream 标识、token 使用量等。
- 对 streaming 请求，建议记录 time to first chunk。
- 输入/输出消息、system instructions、tool definitions 都属于敏感高风险字段，语义约定中将其标为 opt-in，并提醒需要过滤或截断。
- tool execution 应该是独立 span，`gen_ai.operation.name` 应为 `execute_tool`，span name 推荐为 `execute_tool {gen_ai.tool.name}`，并记录 `gen_ai.tool.name`。
- tool 调用经常由应用代码直接执行，因此应用开发者应手工 instrument 自动工具无法覆盖的部分。

来源：
https://raw.githubusercontent.com/open-telemetry/semantic-conventions-genai/main/docs/gen-ai/gen-ai-spans.md
https://raw.githubusercontent.com/open-telemetry/semantic-conventions-genai/main/docs/gen-ai/gen-ai-agent-spans.md
https://raw.githubusercontent.com/open-telemetry/semantic-conventions-genai/main/docs/gen-ai/gen-ai-events.md
https://github.com/open-telemetry/semantic-conventions-genai

### 2.3 OpenAI Agents SDK tracing 做法

OpenAI Agents SDK 官方 tracing 将一次 workflow 表示为 trace，trace 由 spans 组成。trace 包含：

- `workflow_name`
- `trace_id`
- `group_id`，可用于把多个 traces 关联到同一 conversation/thread
- `metadata`
- `disabled`

默认 tracing 覆盖：

- 整个 `Runner.run/run_sync/run_streamed`
- 每次 agent 运行
- LLM generation
- function tool call
- guardrails
- handoff
- speech/text transcription 等多模态 span

这说明成熟 Agent SDK 的默认观测粒度不是“单条日志”，而是 workflow trace + agent/model/tool/guardrail 分层 span。

来源：
https://openai.github.io/openai-agents-python/tracing/

### 2.4 LangSmith observability 做法

LangSmith 官方概念模型：

- Project：某个应用/服务的 trace 容器。
- Trace：一次操作的步骤集合。
- Run：单个工作单元，等价于 span，例如 LLM 调用、prompt 格式化、retrieval 调用等。
- Thread：多轮对话中的一组 traces，通过 `session_id` 或 `thread_id` 关联。
- Tags / metadata：用于筛选、分组和调试。

LangSmith 同时支持自动集成和手工 instrumentation。官方文档指出，手工 instrumentation 适合不使用已支持框架，或需要更细粒度控制的场景。

来源：
https://docs.langchain.com/langsmith/observability
https://docs.langchain.com/langsmith/observability-concepts

## 3. 对当前 EDUagent 的诊断

### 3.1 当前做对的地方

- 已经使用 AgentScope middleware，而不是在业务路由里手写伪 agent loop。
- 已经把开发者日志通过 SSE 送到前端浮窗，开发时可直接在页面观察。
- 已经记录了工具名、工具参数预览、工具结果预览、模型 token、权限确认等字段。
- 已经做了参数截断和敏感 key 脱敏。

### 3.2 当前不足

当前 `debug_log` 仍然更像“事件平铺流”，缺少 trace/span 层级结构：

- 不能清楚表达父子关系：一次 chat turn 下有几轮 reasoning、几次 model call、几次 tool call。
- 不能表达 span 生命周期：start/end/error 只是靠 event 字符串约定，没有统一 span id。
- 不能计算准确耗时树：例如总耗时、模型耗时、工具耗时、等待首 token 时间。
- 前端浮窗无法按 trace、span、tool_call_id 分组。
- 没有明确区分业务事件和观测事件。
- 没有真正的落盘/导出策略，刷新页面后开发日志丢失。

### 3.3 `read_learning_state` 卡住问题的观测缺口

针对 `read_learning_state` 一直显示进行中，应该至少能看到：

- `trace_id`
- `span_id`
- `parent_span_id`
- `event_name`
- `run_id`
- `conversation_id`
- `reply_id`
- `tool_call_id`
- `tool_name`
- `tool_input_preview`
- `tool_output_preview`
- `tool_state`
- `started_at`
- `ended_at`
- `duration_ms`
- `error_type`
- `error_message`
- `model_call_before_tool`
- `model_call_after_tool`
- `last_agentscope_event_class`

如果只有 `tool_started` 而没有 `tool.call.end`，说明工具执行层卡住。
如果有 `tool.call.end` 而没有 `tool_completed`，说明 AgentScope event 到 EDU event 的适配或 SSE 转发有问题。
如果有 `tool_completed` 但 UI 仍显示进行中，说明前端 reducer 的 `tool_call_id` 匹配有问题。
如果有 `tool.call.end` 且 `tool_completed`，随后卡在 `model_call`，说明工具返回内容不足或模型继续推理卡住。

## 4. 推荐日志模型

### 4.1 内部统一模型

建议新增内部结构，不直接等同于 SSE：

```json
{
  "trace_id": "trace_xxx",
  "run_id": "run_xxx",
  "conversation_id": "conv_xxx",
  "message_id": "msg_xxx",
  "user_id": "u1",
  "course_id": "c1",
  "span_id": "span_xxx",
  "parent_span_id": "span_parent",
  "span_kind": "agent|reasoning|model|tool|permission|artifact|backend_proxy",
  "name": "execute_tool read_learning_state",
  "phase": "start|event|end|error",
  "timestamp": "2026-07-01T...",
  "duration_ms": 123.4,
  "attributes": {},
  "error": null
}
```

### 4.2 推荐 span 层级

```text
trace: tutoring.chat.turn
  span: backend.prepare_turn
  span: backend.build_agent_payload
  span: backend.proxy_sse
  span: agent.invoke edu_ai_chat_workbench
    span: reasoning.iteration 1
      span: model.call deepseek-chat
      span: tool.execute TaskCreate
    span: reasoning.iteration 2
      span: model.call deepseek-chat
      span: tool.execute read_learning_state
    span: reasoning.iteration 3
      span: model.call deepseek-chat
  span: backend.persist_assistant_message
```

### 4.3 开发者浮窗投影

前端 Dev Console 不需要显示完整 trace 后端存储模型，但应按以下分组展示：

- 当前 run / conversation。
- Timeline：按时间排序的 span/event。
- Tool panel：工具调用列表，显示 input/output/state/duration。
- Model panel：模型调用列表，显示 model、tokens、duration、first chunk。
- Error panel：只显示 error/permission/timeout。
- Raw JSON：保留展开查看。

## 5. 字段规范建议

### 5.1 必填字段

| 字段 | 说明 |
| --- | --- |
| `trace_id` | 一次用户请求/turn 的端到端 trace |
| `run_id` | Agent Service run |
| `conversation_id` | 对话 ID |
| `seq` | SSE/日志事件序号 |
| `span_id` | 当前 span |
| `parent_span_id` | 父 span |
| `name` | 低基数字符串，例如 `execute_tool read_learning_state` |
| `span_kind` | `agent/model/tool/retrieval/memory/backend_proxy` |
| `phase` | `start/end/error/event` |
| `timestamp` | ISO 时间 |
| `level` | `debug/info/warn/error` |

### 5.2 Tool 字段

| 字段 | 说明 |
| --- | --- |
| `tool_call_id` | AgentScope tool call id |
| `tool_name` | 工具名 |
| `tool_input_preview` | 脱敏截断后的输入 |
| `tool_output_preview` | 脱敏截断后的输出 |
| `tool_state` | `success/error/denied/interrupted/running` |
| `duration_ms` | 工具执行耗时 |

### 5.3 Model 字段

| 字段 | 说明 |
| --- | --- |
| `model` | 模型名 |
| `provider` | provider，例如 `deepseek` |
| `input_tokens` | 输入 token |
| `output_tokens` | 输出 token |
| `time_to_first_chunk_ms` | 流式首 chunk 耗时 |
| `finish_reason` | 模型停止原因 |

### 5.4 安全策略

- 默认不记录完整 prompt、完整 user message、完整 tool output。
- preview 默认截断到 2KB。
- 对 key 名包含 `api_key`、`authorization`、`password`、`secret`、`token`、`cookie` 的字段脱敏。
- 高风险字段必须 opt-in 才能进入持久日志。
- 前端 Dev Console 可显示 preview，不应显示完整敏感上下文。

## 6. 推荐落地步骤

### Step 1：建立统一 trace/span id

在 Agent Service 创建 run 时生成：

- `trace_id`
- root `span_id`

并贯穿：

- Backend SSE payload
- Agent middleware
- protocol adapter
- Dev Console

### Step 2：把现有 `debug_log` 改成统一结构投影

保留 `debug_log` 事件类型，但 payload 从自由字段改为稳定结构：

```json
{
  "trace_id": "trace_xxx",
  "span_id": "span_xxx",
  "parent_span_id": "span_root",
  "span_kind": "tool",
  "name": "execute_tool read_learning_state",
  "phase": "end",
  "level": "info",
  "message": "tool read_learning_state success",
  "attributes": {
    "tool_call_id": "tool-1",
    "tool_name": "read_learning_state",
    "tool_state": "success",
    "tool_output_preview": "{...}"
  }
}
```

### Step 3：补 Backend proxy spans

Backend 目前只代理 Agent SSE，但排查时需要看到：

- prepare turn 是否成功
- payload build 是否成功
- Agent Service HTTP 是否连接成功
- SSE 是否中断
- assistant message 是否持久化成功

这些属于 Backend span，不应该只靠 Agent Service 的日志。

### Step 4：修复 `read_learning_state` 前先用日志锁定位置

下一步排障命令应该是：

1. 触发“补弱计划”。
2. Dev Console 搜索 `read_learning_state`。
3. 对照是否出现：
   - `tool_started`
   - `tool.call.start`
   - `tool.call.end`
   - `tool_completed`
   - 后续 `model_call.end`
4. 由缺失位置决定修复点。

### Step 5：再实现真实学习状态工具

日志修到位后，再把 `read_learning_state` 从 placeholder 升级为真实工具，返回 Backend 已构造的：

- `knowledge_weak`
- `knowledge_mastered`
- `guidance_level`
- `modal_preference`
- `active_kg_nodes`
- `recent_messages` 摘要

否则即使日志显示闭环，Agent 仍然只能基于空数据生成低质量补弱计划。

## 7. 对 EDUagent 的最终建议

短期：

- 不建议马上接 LangSmith 或完整 OTLP collector。
- 先把当前本地 Dev Console 的 `debug_log` 规范化为 trace/span/event 结构。
- 补 Backend 侧 proxy/persist span。
- 用这套日志定位 `read_learning_state` 到底卡在工具执行、事件适配、SSE 转发还是前端 reducer。

中期：

- 增加可选 OTLP exporter。
- 使用 AgentScope `TracingMiddleware` 作为 OpenTelemetry 主路径。
- 自定义业务 span 继续保留，例如 `backend.build_agent_payload`、`artifact.emit`。

长期：

- 用统一 trace 连接：
  - 前端 turn
  - Backend tutoring API
  - Agent Service run
  - AgentScope model/tool events
  - MySQL 持久化
  - Qdrant/RAG 检索
- 让每个用户反馈、失败、重新生成都能回放完整执行路径。

## 8. 推荐下一步实施项

优先级从高到低：

1. 统一 `debug_log` payload 为 trace/span/event 格式。
2. 增加 `trace_id/span_id/parent_span_id`。
3. Dev Console 改为 timeline + tool/model/error 分区。
4. Backend `TutoringStreamAdapter` 增加 proxy/persist 调试事件。
5. 用日志复现并定位 `read_learning_state` 进行中问题。
6. 修复真实 `read_learning_state` 工具注入上下文。
7. 后续考虑 AgentScope `TracingMiddleware` + OTLP。
