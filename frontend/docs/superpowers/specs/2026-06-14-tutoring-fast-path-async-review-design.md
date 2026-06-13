# Tutoring 快速链路 + 异步审查撤回 设计

日期：2026-06-14
分支：feat/backend-agent-integration
作者：AI + yezisama

## 1. 背景与问题

AIChat / tutoring 链路当前在输出第一个 chunk 之前会**串行**发起多次 LLM 调用，最坏情况约 9 次串行 LLM 往返，导致慢和超时。

当前阻塞链路（`agent_service/agents/tutoring.py:273-386`）：

1. 检索 Retrieval（embedding + Qdrant + KG 匹配）
2. `select_tutoring_strategy`（tutoring.py:321）—— 有 chat provider 时一次 LLM 调用
3. `generate_tutoring_react_response`（tutoring.py:327）—— ReAct 循环，max_iters=5，每轮一次 LLM
4. `evaluate_tutoring_response`（tutoring.py:334）—— 同步 LLM critic
5. critic 拒绝 → `generate_tutoring_model_response`（tutoring.py:345）—— 另一次完整 LLM chat fallback
6. → 再 `evaluate_tutoring_response`（tutoring.py:347）—— 又一次同步 LLM critic

最坏 = 策略(1) + ReAct(5) + critic(1) + fallback(1) + critic(1)，全部在出字之前。

个性化信息（引导级别、薄弱点、已掌握、长期记忆、会话摘要、个人检索记忆）**已经**在第 1/2/3 步注入 ReAct（`tutoring_react_flow.py:55-78`）。被砍的 4/5/6 只是"审查 + 重试"，不携带额外个性化，因此提速与个性化不冲突。

## 2. 目标

把链路改为：**Retrieval（更偏个人）→ ReAct（更用画像）→ 快速规则 Guard → 必要时重试一次 ReAct → 流式输出 → 异步规则审查 → 发现问题发撤回事件**。

三件一起做：

- **提速**：移出并删除同步 LLM critic、chat fallback、策略 LLM。
- **个性化**：检索更偏个人薄弱点/记忆；ReAct prompt 更明确按画像调讲法。
- **异步审查撤回**：正文照常流式显示；后台只跑规则审查；判定有问题时额外发一个新 SSE `review` 事件，前端把该条 AI 回答**标灰 + 提示"该回答可能不准确"**，保留原文。

## 3. 范围与授权

- 用户已授权修改契约字段，**含 `../docs/10-client-api/Client-API.openapi.json` 与 `API_前端接口规范.md`**（新增 `review` SSE 事件）。
- 数据库仅 MySQL（本设计不涉及 schema 变更）。
- 不引入 mock/假数据。

## 4. 新链路设计

```
学生发消息
  │
  ├─【1】检索 Retrieval（增强：个人薄弱点/记忆加权）
  │       build_tutoring_retrieval_context_with_ai
  │
  ├─【2】选教法 Strategy：快速链路只用规则 _select_rule_strategy（不打策略 LLM）
  │
  ├─【3】ReAct 主生成（增强 prompt：明确按引导级别/薄弱点调讲法和深浅）
  │       generate_tutoring_react_response（max_iters 不变）
  │
  ├─【4】快速规则 Guard（同步、瞬时，复用 _evaluate_by_rule）
  │       通过 → 直接进入【5】流式输出
  │       不通过 → 重试一次 ReAct（带收紧指令）
  │                 仍不通过 → 规则兜底答案（build_tutoring_generation_result 的 used_rule_fallback 路径）
  │
  ├─【5】流式输出：chunk / diagram / knowledge_points / suggestion / done（顺序不变）
  │
  └─【6】异步规则审查（不阻塞，在 done 之后）
          复用 _evaluate_by_rule（不打 LLM）
          accepted=False → 发 review 事件 {status:"flagged", reason}
          accepted=True  → 不发 review 事件（沉默通过）
```

### 4.1 Guard 判什么（复用现有规则）

`_evaluate_by_rule`（`tutoring_response_critic.py:47-60`）已有规则：非空、`clarifying_question` 策略须含问句、与知识点/消息相关。Guard 与异步审查复用同一套规则函数，避免两套口径。

### 4.2 重试一次 ReAct

Guard 拒绝时，再调用一次 `generate_tutoring_react_response`，在 user_message 末尾追加一条收紧指令（例如"上一轮回答未围绕该学生的薄弱点/当前问题，请直接针对 {focus_points} 给出可用回答"）。仍失败则走规则兜底，不再额外打任何 LLM chat。

### 4.3 异步审查的执行时机

正文与 done 全部 yield 完后，在同一个 async generator 末尾**再跑一次** `_evaluate_by_rule`（纯规则、无网络），若 `accepted=False` 则 yield 一个 `review` 事件。由于规则审查是本地纯函数，几乎不增加尾部延迟，但语义上明确"输出已不被它阻塞"。

> 设计取舍：因为 Guard 已在输出前用同一规则把过门，异步审查命中"flagged"的概率低；它的价值是兜住"Guard 通过但仍轻微跑题"的边缘情况，并为将来升级为异步 LLM 审查保留事件通道。

## 5. 契约变更（SSE `review` 事件）

### 5.1 Agent schema（`agent_service/schemas/tutoring.py`）

新增：

```python
class ReviewEvent(BaseModel):
    type: Literal["review"] = "review"
    status: Literal["flagged"] = Field(..., description="审查结论；flagged 表示该回答可能不准确")
    reason: str = Field(..., description="审查判定原因，如 off_topic / empty_response")
```

并把 `ReviewEvent` 加入 `TutoringSSEEvent` union（schemas/tutoring.py:83）。

### 5.2 OpenAPI（`../docs/10-client-api/Client-API.openapi.json`）

更新 `/tutoring/chat` 200 响应 description（行 2123）：

```
事件类型: chunk / diagram / knowledge_points / suggestion / done / review
```

并在描述中补充 review 事件语义（在 done 之后异步发出，status=flagged 表示回答可能不准确，前端应标灰提示）。同步更新 `API_前端接口规范.md` 中 tutoring SSE 事件列表。

### 5.3 不破坏现有契约

不删除/改名任何现有事件字段；review 为**新增可选事件**，旧前端忽略它仍能正常工作。

## 6. 前端改动

### 6.1 `src/api/services/chat.js`

在 SSE 解析分支（chat.js:114-127）显式识别 `review` 事件，通过 `onMessage(parsed)` 透传（当前 generic fallback 已能透传，但显式分支更清晰、便于维护）。

### 6.2 `src/pages/AIChat.jsx`

**关键时序问题**：`done` 事件已把 placeholder 的 id 改为 `message_id`（AIChat.jsx:199）。`review` 在 done 之后到达，此时 placeholder 已不存在。因此：

- 在 done 回调里把最终 `message_id` 记到一个 ref（如 `lastMessageIdRef`）。
- `review` 事件到达时，按 `lastMessageIdRef`（或回退到最后一条 assistant 消息）定位并打上 `{ reviewFlagged: true, reviewReason }`。
- 消息渲染时，`reviewFlagged` 为真则整条 AI 回答**标灰**并在顶部加一行提示"该回答可能不准确"，原文保留可读。

### 6.3 `src/components/chat/ChatMessage.jsx`

接收 `reviewFlagged` / `reviewReason`，渲染标灰样式 + 提示条。不替换正文。

### 6.4 Mock 分支

`chat.js` mock 分支与 `chatMock.js` 不需要伪造 review（保持沉默通过即可），避免引入假数据。

## 7. 删除清单（移出阻塞链路并删除死代码）

确认无其它调用方后删除：

- `agent_service/agents/tutoring.py`：`generate_tutoring_model_response`、`_try_structured_output`、`_TutoringStructuredOutput`、`build_tutoring_model_response`（chat fallback 相关），以及编排里第 5/6 步调用。
- `agent_service/agents/tutoring_response_critic.py`：删除 `evaluate_tutoring_response` 的 LLM 分支（critic LLM）与 `_parse_llm_critic_result`、`build_response_critic_messages` 调用；**保留** `_evaluate_by_rule` 及相关 helper，重命名导出为规则 Guard 用途（如 `evaluate_tutoring_response_by_rule`）。
- `agent_service/agents/tutoring_strategy.py`：删除 `select_tutoring_strategy` 的 LLM 分支与 `_parse_llm_strategy`、`build_strategy_selection_messages` 调用；**保留** `_select_rule_strategy`，对外暴露为快速链路策略入口。
- `agent_service/prompts/tutoring.py`：删除仅被上述 LLM 分支使用的 `build_response_critic_messages`、`build_strategy_selection_messages`（需先 grep 确认无其它引用）。

> 删除前对每个符号做全仓 grep，确认无测试/工具/其它模块引用；有引用的同步处理。

## 8. 测试计划

### Agent Service（TDD）

- 新增 `test_tutoring_fast_path`：
  - 给定 mock chat（ReAct 返回有效答案）→ 不调用 strategy LLM、不调用 critic LLM、不调用 chat fallback；断言串行 LLM 调用次数 = ReAct 次数。
  - ReAct 返回跑题答案 → Guard 拒绝 → 触发一次 ReAct 重试。
  - 重试仍失败 → 走规则兜底，`used_rule_fallback=True`。
  - 异步审查命中 flagged → SSE 流末尾出现 `review` 事件，且在 `done` 之后。
  - 异步审查通过 → 不出现 `review` 事件。
- 回归现有 `agent_service/tests/test_aichat_hybrid_retrieval.py`、tutoring 相关测试全绿。
- 命令：`cd agent_service && uv run pytest tests/ -q`（按项目实际命令）。

### 前端

- `npm run lint`
- `npm run build`
- review 事件标灰渲染：尽量加单测或 Playwright；若环境导航不稳则降级为手动验证并在 WORKFLOW 注明。

### 契约

- OpenAPI JSON 语法检查通过。

## 9. 风险

- **时序竞态**：review 必须在 done 之后定位到已 finalize 的消息；用 `lastMessageIdRef` 兜底，避免落到 placeholder。
- **删除连带**：critic/strategy/fallback 的 prompt builder 可能被工具或测试引用；删除前必须 grep。
- **个性化增强的检索加权**：调权重可能影响命中分布；以现有 C 语言样本探针回归，避免回归 grounding。
- **沉默通过的可观测性**：异步审查通过不发事件，需保留 `agent_trace` 日志记录审查结论，便于排查。

## 10. 验收口径

- 正常一轮对话：出字前只有"检索 + ReAct（+ 最多一次重试）"，无策略/critic/fallback 的 LLM 往返。
- 个性化：ReAct prompt 中按引导级别/薄弱点明确调讲法；检索更偏个人记忆/薄弱点。
- 撤回：审查 flagged 时前端整条标灰 + "该回答可能不准确"，原文保留。
- 契约：OpenAPI / 接口规范已含 review 事件；旧前端忽略 review 仍可用。
