# Tutoring ReAct 结构化输出修复设计（JSON 泄露 / 超时检索失效 / 慢）

日期：2026-06-14
状态：已批准（设计阶段，待 spec 复核 → writing-plans）
分支：当前工作分支（feat/backend-agent-integration 系列）
作者：AI + yezisama
关联前序设计：
- `2026-06-14-tutoring-fast-path-async-review-design.md`（当前快速链路：Retrieval → ReAct → 规则 Guard → 重试 → 规则兜底 → 异步审查）
- `2026-06-14-aichat-retrieval-correction-design.md`（检索降级与图谱节点注入）

---

## 1. 背景与问题

`/ai-chat`（tutoring ReAct 链路）现网暴露三个症状，均已用真实代码与真实解析器实证，非推断：

### 1.1 前端正文露出 JSON 块【严重，已实证复现】

模型返回「散文前缀 + ` ```json ` 围栏块」，且围栏内 `model_text` 字段本身又嵌了 ` ```c ` 代码块。
用真实解析器 `parse_tutoring_model_response` 跑实际泄露样例：
- `model_text` = **整段原文**（含 ` ```json ` 与字面量 `"model_text":`）→ 原样泄露到正文；
- `knowledge_points` = `[]`、`suggestion` = `None`、`diagram` = `None` → 侧栏知识点/建议/图解**全部丢失**。

根因链：
1. `agent_service/prompts/tutoring.py:9-14` 要求「只输出 JSON，不要加 markdown 代码块」，但模型（deepseek）不遵守，反而包了散文 + ` ```json `。
2. ReAct 路径**没有**强制结构化输出：`json_mode`/`response_format` 只在 `core/ai.py:54-70` 的 `AgentScopeChatProvider.complete()` 生效，而 ReAct 用的是**裸 model**（`tutoring_react_flow.py:40-44` 把 `chat_provider.model` 直接传入），绕过了它。
3. `agent_service/agents/tutoring.py:15` 的 `_MARKDOWN_JSON_PATTERN = ```(?:json)?\s*\n?(.*?)``` ` 为**非贪婪**，遇到 `model_text` 内嵌的 ` ```c ` 时，`.*?` 在第一个 ` ``` ` 即截断 → `json.loads` 失败 → `_try_parse_markdown_json_output`（`tutoring.py:93-111`）返回 None。
4. 无 `<agent_result>` 标签 → 兜底 `tutoring.py:82` 把**整段原文**当 `model_text` 返回。
5. 后端 `backend/app/api/v1/tutoring.py` 的 `event_generator` 把该 `chunk` **既转发又持久化**为 `full_content`（约 `:213` 累积、`:270` 落库）→ 实时泄露 + 历史重载仍泄露 + 脏数据进 DB。
6. 前端 `ChatMessage.jsx:167-187` 与 `AIChat.jsx:10-37,52-59` 的 `getDisplayText` 只处理「整串以 `{` 开头」的纯 JSON，对「散文 + 围栏 JSON」无能为力；工作区里 `ChatMessage.jsx:278` 未提交的调用点改动方向对但堵不住该 case。

### 1.2 检索功能失效 + APITimeoutError【严重】

- 超时保护没盖到主路径：`ed9183c` 把 `timeout=120 + asyncio.wait_for` 只加在 `AgentScopeChatProvider.complete()`（`core/ai.py:54-70`），但 ReAct 主路径用裸 `chat_provider.model`（`tutoring_react_flow.py:41`），**不经过 `complete()`**，该守卫对其完全无效。
- `core/ai.py:172-178` 的 `OpenAIChatModel(stream=False, client_kwargs={"base_url": ...})` **无显式 timeout**，用 OpenAI SDK 默认值，最终抛 `APITimeoutError`。
- 超时在 `tutoring_react.py:47-53` 被吞 → 返回 None → 降级规则兜底（RAG 不生效，通用模板答案）。
- `retrieve_course_knowledge` 报 `<system-info>The tool call has been interrupted by the user.</system-info>`：是 reasoning 超时/任务被取消时，AgentScope 把在途 tool call 标记为中断 —— 即「检索功能失效」现象。
- 附带误导日志：`tutoring_react_flow.py:46` **无条件**打 `"Tutoring ReAct succeeded"`，即使 `model_output is None`（实为失败降级），排障极具迷惑性。

### 1.3 回答时间过长【高】

- `core/ai.py:176` `stream=False`：后端须等整段补全才往下走；ReAct 还要多轮（`max_iters=5`）串行整段补全。
- `agent_service/agents/tutoring.py:332-333`：最终 `chunk_text` 一次性整段 yield，无 token 级流式。虽接口是 SSE，用户实际只在最后一刻见到答案，感知延迟 = 整个生成时长。

---

## 2. 关键决策（已与用户确认）

1. **AI 部分优先使用 AgentScope 框架。**
2. **输出方式：结构化 + 实时状态（不做逐字流式）。** 用 AgentScope `structured_model`，最终答案作为已校验对象一次性返回，配合检索/推理阶段的 `status` 与工具卡片实时反馈让等待「可感知」。延迟改善来自「有界超时 + 快速失败 + status 反馈」，而非逐字流式。
3. **历史脏数据：仅前端防御，不动 MySQL 数据。** 靠 `getDisplayText` 加固在展示时剥离围栏 JSON，旧会话重载不再泄露；不写一次性迁移脚本。

AgentScope 1.0.20 能力已核实：
- `ReActAgent.reply(structured_model=Type[BaseModel])`（`_react_agent.py:379`）注册 `generate_response` 收口工具，按 schema 用 `model_validate(kwargs).model_dump()` 校验（`:844`），结果存入返回 `Msg.metadata`（`:701` `return chunk.metadata.get("structured_output")`，`:463` `metadata=structured_output`）。
- `OpenAIChatModel`（`_openai_model.py:74-117`）：`stream` 默认 `True`（当前代码强制 `False`）；`client_kwargs` 透传给 AsyncOpenAI，可含 `timeout`；`generate_kwargs` 透传到补全调用；`stream_tool_parsing=True` 内建流式工具 JSON 解析。

---

## 3. 架构与数据流（修复后）

```
ReActAgent(structured_model=TutoringStructuredOutput)
  → generate_response 工具校验 → result.metadata = {model_text, knowledge_points, suggestion, diagram}
  → TutoringModelResponse（直接由 metadata 构建，不再正则解析自由文本）
  → 规则 Guard（作用于干净 model_text）
  → SSE: status(实时) + chunk(干净 model_text) + diagram + knowledge_points + suggestion + done
  → 后端持久化干净 full_content
  → 前端渲染（getDisplayText 防御层兜旧脏数据/偶发不合规）
```

核心思想：把「模型吐什么、我们再解析」换成「AgentScope 用 `generate_response` 工具强制产出已校验结构化对象」。从源头消灭围栏 JSON，正则解析降为防御性兜底。降级链（重试一次 → 规则兜底 → 异步审查）保持不变。

---

## 4. 组件级改动（最小化，按子能力切边界）

| # | 文件 | 改动 | 解决 |
|---|------|------|------|
| 1 | `agent_service/schemas/tutoring.py` | 新增 Pydantic `TutoringStructuredOutput`：`model_text: str` / `knowledge_points: list[str]`（1–3） / `suggestion: str` / `diagram: str \| None`，每字段带 description 引导 `generate_response` schema | 1.1 |
| 2 | `agent_service/agents/tutoring_react.py` | `generate()` 传 `structured_model=TutoringStructuredOutput`；返回类型改为 `dict \| str \| None`：metadata 非空返回 dict；metadata 为空但有文本返回 `get_text_content()`（str，交由上游兜底解析）；异常/空返回 None | 1.1 |
| 3 | `agent_service/agents/tutoring_react_flow.py` | 按类型分支：`isinstance(result, dict)` → 直接构建 `TutoringModelResponse`；`isinstance(result, str)` → 走 `parse_tutoring_model_response`；None → 返回 None（进降级链）。**修复误导日志**——仅在产出非 None 时记 "succeeded"，降级单独记 warning | 1.1 + 误导日志 |
| 4 | `agent_service/core/ai.py` | `OpenAIChatModel(stream=settings.LLM_STREAM, client_kwargs={"base_url": ..., "timeout": settings.LLM_TIMEOUT})`；`complete()` 路径行为不变 | 1.2 + 1.3 |
| 5 | `agent_service/core/config.py` + `agent_service/.env` | 新增 `LLM_TIMEOUT: float = 60`、`LLM_STREAM: bool = True`（`.env` 仅在需覆盖时写入，不存密钥变更） | 1.2 + 1.3 |
| 6 | `agent_service/prompts/tutoring.py` | 删除「请以 JSON 格式输出…只输出 JSON，不要加 markdown 代码块」整段（已被 `generate_response` 工具取代，且正是它诱导模型输出 ` ```json `）；保留贴合画像 / 围绕图谱节点 / diagram 用 Mermaid 的教学指引 | 1.1 |
| 7 | `frontend/src/components/chat/ChatMessage.jsx` + `frontend/src/pages/AIChat.jsx` | 加固 `getDisplayText`：用**括号配平**而非非贪婪正则，剥离「散文 + ` ```json{…}``` `」围栏并提取 `model_text`（正确处理嵌套 ` ```c `）；保留 `ChatMessage.jsx:278` 已存在的调用点改动 | 1.1（防御 + 旧脏数据） |

切边界说明：1–6 属 agent_service，按「结构化输出 / 模型配置 / 提示词」三个子能力分文件改；7 属 frontend 防御层。不动后端 `backend/` 与契约字段。

---

## 5. 错误处理与降级链

- 超时现在有界（`client_kwargs.timeout`）→ 快速失败 → 现有「重试一次 → 规则兜底」链不变。
- 结构化 metadata 缺失（模型未调用 `generate_response`）→ `generate()` 回退返回文本 → `tutoring_react_flow` 走 `parse_tutoring_model_response` 兜底 → 仍失败则规则兜底。
- 规则 Guard（`evaluate_tutoring_response_by_rule`）仍作用于干净 `model_text`。
- `max_iters` 仍防 ReAct 死循环。
- 前端防御层：`getDisplayText` 对「纯 JSON」「散文+围栏 JSON」「对象」三类输入都能提取 `model_text`，提取失败时回退展示原文（不抛错）。

---

## 6. 测试

agent_service（`uv run pytest`）：
- metadata dict → `TutoringModelResponse` 映射单测（含 knowledge_points 截断到 3、diagram 透传）。
- `generate()` 在 metadata 缺失时回退文本的单测（用 fake agent，避免联网）。
- 保留并加固 `parse_tutoring_model_response` 兜底测试：新增「散文 + 嵌套 ` ```c ` 围栏」回归用例，断言兜底路径**不再把围栏 JSON 当正文**、且能提取 knowledge_points/suggestion/diagram。
- `tutoring_react_flow` 降级日志单测：metadata 为 None 时不记 "succeeded"。

frontend（`npm run lint && npm run build`）：
- `getDisplayText` 对实际泄露样例（散文 + 嵌套 ` ```c ` 的围栏 JSON）剥离逻辑：若有单测设施补单测，否则手动回归 + lint/build。

不做联网集成测试（真实 LLM 的 structured 行为属集成层）；用 fake metadata / fake agent 验证映射与降级。

---

## 7. 契约影响

- SSE 事件格式（`status` / `chunk` / `diagram` / `knowledge_points` / `suggestion` / `done` / `review`）与 `../docs/10-client-api/Client-API.openapi.json` 字段**不变**，仅内部生成方式变化。
- 不修改 `../docs/` 下任何契约文件。
- 数据库仅 MySQL，本设计**不涉及 schema 变更，也不做数据迁移**。

---

## 8. 已知风险

- **模型须支持 function/tool calling**（`generate_response` 是注册工具）。deepseek 支持；若某次未调用该工具，靠文本兜底 + 规则兜底兜住。
- `stream=True` + 工具调用：AgentScope `stream_tool_parsing=True` 已内建流式工具 JSON 解析。
- `LLM_TIMEOUT` 设太低会误杀长回答 → 设为可配置，默认 60s，可经 `.env` 覆盖。
- 本方案优先正确性/健壮性；不做逐字流式（已确认）。

---

## 9. 不在本次范围

- 逐字（token 级）流式输出正文。
- 历史 DB 脏数据的一次性清洗脚本。
- 后端 `backend/` 路由/契约改动。
- 检索召回质量本身（见 `project_resource_quality_issue` 记忆与 Route A 相关设计）。
