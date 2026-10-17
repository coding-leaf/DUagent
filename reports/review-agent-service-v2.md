## 审查

- 已核实：我逐文件检查了 `agent_service_v2/` 全部 70 个源模块和 45 个测试模块（`src/agent_service_v2/{main,team_app}.py`、`agents/`、`api/`、`runtime/`、`session/`、`tools/`、`workspaces/`、`artifacts/`、`safety/`、`observability/`、`generators/`、`schemas/`、`team/`），并与后端消费者（`backend/app/services/tutoring_stream_adapter.py`、`tutoring_artifact_service.py`）及部署脚本（`start_all.sh`、`deploy_prod.sh`）交叉核对了调用约定。
- 合并结论：**BLOCK**（P0 清单：6 项）

---

# Agent Service v2 Codebase Review Report

**审查范围**：`agent_service_v2/`（AgentScope 2.x + FastAPI + SSE，约 8.2k 行，70 个源模块 / 45 个测试模块）
**技术栈基线**：uv + Python 3.12 + `agentscope[full]>=2,<3` + FastAPI + Starlette `StreamingResponse` + Pydantic v2（`agent_service_v2/pyproject.toml:1-20`）
**审查方法**：仅以代码为事实来源；所有结论均给出可定位的文件/行号或测试证据。未执行测试（无 shell 权限），需由 supervisor 运行第 5 节附录中的命令。

---

## 1. Executive Summary & Architecture Health

### 1.1 整体判断

分层设想是清晰的，但**边界被两处“走捷径”破坏**，且**流式链路缺少故障收敛点**。整体健康度：**中等偏下（C）**——骨架正确，跑得通，但没有为“长期运行 + 并发 + 模型不确定性”付出设计成本。

| 维度 | 评级 | 依据 |
|---|---|---|
| 服务边界（与 backend MySQL 解耦） | **B** | 无任何 `mysql`/`sqlalchemy`/`pymysql` 依赖（`grep` 全仓 `agent_service_v2/` 仅命中 `redis`）；但存在**共享文件系统耦合**（见 P1-13） |
| SSE 流可靠性 | **D** | 无 keepalive / 无错误帧 / 无 `id:` 续传 / 无断连超时；team 侧存在 replay 竞态（P0-6、P1-11、P2-9） |
| 工具错误处理一致性 | **D** | 两套范式并存：**大部分工具返回信封，少数工具直接 `raise`**，且 `raise` 的工具会把整个 run 打死（P0-1、P0-2） |
| Agent 拓扑复杂度 | **C** | 工作台（单 Agent）与资源团队（挂载子 App + ASGI 回环）两套并行体系；`leader_team.py` 名称与实现严重不符（P1-7、P1-8） |
| 持久化卫生 | **D** | workspace / `events.jsonl` / `raw_assistant_chunks` 全部无上界、无 TTL、无清理（P1-4） |
| 提示词工程质量 | **C** | 单条 98 行系统提示词，含**自相矛盾条款**，且被测试按字面钉死（P1-2） |
| 测试覆盖 | **C** | 工具/适配器/工厂覆盖良好；**SSE 断连、并发、webhook、清理、team SSE 全程均无测试**（P1-15） |

### 1.2 值得肯定（Correct）

1. **run 事件总线自带缓冲，消除了“流生成器晚于事件产生”的经典丢帧竞态**：`WorkbenchRunBus.subscribe()` 从 `index=0` 重放 `state.events`（`session/run_bus.py:89-99`），而 `workbench_chat` 先 `await session.start_async(...)` 再返回 `StreamingResponse`（`api/workbench.py:36-51`）。两者顺序天然安全。
2. **客户端断连确实会取消 agent 任务**：`event_stream` 的 `finally` 调用 `session.cancel_run`（`api/workbench.py:45-49`），`cancel_run` 执行 `task.cancel()` + `await task`（`session/workbench_session.py:169-176`），`_run_agent` 在 `except asyncio.CancelledError` 中补发 `workflow_failed{reason:"cancelled"}` 并落盘 `cancelled` 状态（`session/workbench_session.py:365-369`）。这是本模块做得最正确的一处。
3. **路径穿越防护到位**：`_run_dir` 的 `is_relative_to` 校验（`workspaces/run_store.py:47-53`）、`_validate_filename`（`tools/artifact_files.py:196-206`）、`_resolve_material_path`（`api/knowledge.py:139-169`）、`resolve_workbench_artifact._safe_filename`（`workspaces/workbench_artifacts.py:34-45`）四道独立防线，且均有测试（`test_workbench_artifacts.py:45-74`、`test_knowledge_api.py:12-25`、`test_artifact_file_tool.py:41-55`）。
4. **日志脱敏有实质实现**：`SENSITIVE_KEYS` 覆盖 `reference_solution`/`hidden_inputs`/`api_key`（`observability/logging.py:12-22`），`mcp__web_search__search`、`search_memory`、`add_memory` 的入参被整体剔除而非截断（`observability/agent_log_emitter.py:88-99`）。
5. **MCP 子进程环境隔离正确**：`_build_subprocess_env` 只透传 `PATH/HOME/SYSTEMROOT`，模型密钥与 Backend Token 不会泄漏给 `npx` 子进程（`tools/web_search_mcp.py:186-196`），且启动失败会降级为 disabled 而非阻断服务（`tools/web_search_mcp.py:127-135`）。
6. **服务边界方向正确**：全部 backend 交互经 `BackendLearningClient.post_json` + `X-Internal-Agent-Token`（`tools/backend_learning_client.py:44-50`），无 ORM、无 `create_engine`、无 MySQL 驱动。

### 1.3 架构健康度关键指标

- **最长的单函数**：`WorkbenchSession._run_agent`，**191 行、6 层嵌套**（`session/workbench_session.py:183-373`）。
- **工具错误范式分裂**：19 个工具返回 `edu_tool_result(...)` 信封；**至少 5 处工具直接 `raise`**（见 P0-1）。
- **同一份 JSON 抽取逻辑被复制 4 次**：`agents/leader_team.py:74-80`、`agents/leader_team.py:299-305`、`generators/public_resources.py:264-274`、`agents/evaluation.py:26,268-271`。
- **同一组工具名被硬编码 4 次**：`agents/permissions.py:7-30`、`runtime/protocol_adapter.py:30-60`、`safety/internal_disclosure_policy.py:56-74`、各 `tools/*.py` 的 `FunctionTool(name=...)`。
- **无上界的持久化写入点**：3 处（workspace 目录、`events.jsonl`、内存 `raw_assistant_chunks`）。

---

## 2. P0 Critical Issues（运行时崩溃 / SSE 断连失效 / 工具未捕获异常）

### P0-1 · 工具抛异常会直接打死整个 agent run（范式分裂）

**位置**
- `tools/artifact_files.py:43-45, 76-78, 107-112, 136-159, 184-206` — `write_artifact_file` / `_persist_artifact` 直接 `raise ArtifactValidationError`（`ValueError` 子类），共 **14 处 raise**。
- `tools/personal_choice_quiz.py:38` — `PersonalChoiceQuizInput(...)` 裸构造，`ValidationError` 未捕获。
- `tools/personal_code_problem.py:37` — 同上。
- `tools/learning_progress.py:34, 46` — `LearningProgressInput` / `RecentAnswersInput` 裸构造（`limit=0` 或 `scope` 不匹配即抛）。
- `tools/learner_profile.py:59` — `DialogueProfileUpdateInput(...)` 裸构造。

**证据链**：这些 callable 经 `FunctionTool` 直接注册（`tools/workbench_toolkit.py:129-145`、`tools/learning_progress.py:103-118`），没有任何 try/except 包裹；异常沿 `agent.reply_stream` 上抛，被 `session/workbench_session.py:370-373` 捕获：

```python
except Exception as exc:
    failed_event = self._run_bus.fail(run.run_id, reason=exc.__class__.__name__)
```

结果：模型只要**一次**把 `filename` 写成 `notes.txt`（而非合法的 `.md`/`.mmd`），或把 `limit` 写成 `0`，整个 run 立刻 `workflow_failed{reason: "ArtifactValidationError"}`，用户看到的是失败而非“参数不合法，请重试”。这与同一代码库其它 19 个工具的契约完全相反（它们返回 `edu_tool_result(status="unavailable"|"rejected")`，如 `tools/oj_execution.py:52-60`、`tools/personal_practice_delivery.py:104-118`）。

**最小修复**：在 `tools/` 增加一个装饰器并在注册处统一套用：

```python
def tool_boundary(fn):
    @functools.wraps(fn)
    async def wrapper(**kwargs):
        try:
            return await fn(**kwargs)
        except Exception as exc:            # pydantic / ArtifactValidationError / 任何意外
            return edu_tool_result(status="rejected",
                                   reason=f"{type(exc).__name__}: {exc}"[:200])
    return wrapper
```
只改 `workbench_toolkit.py` / `learning_progress.py` / `learner_profile.py` / `personalized_resources.py` / `personal_*` 的 `FunctionTool(...)` 注册点（约 8 行），无需触碰各工具内部逻辑。配套回归测试：给 `write_artifact_file` 传 `bad.exe`，断言得到 `outcome="failure"` 且 run 仍以 `workflow_completed` 结束。

---

### P0-2 · `BackendLearningClient.post_json` 只捕获两种传输异常，其余全部逃逸

**位置**：`tools/backend_learning_client.py:44-65`

```python
try:
    async with httpx.AsyncClient(...) as client:
        response = await client.post(url, json=payload, headers=headers)
except httpx.TimeoutException as exc:      # 只这一种
    raise BackendLearningClientError("backend_timeout") from exc
except httpx.ConnectError as exc:          # 和这一种
    raise BackendLearningClientError("backend_unavailable") from exc

if response.status_code >= 400: ...
body = response.json()                     # ← 完全无保护
```

未覆盖的逃逸面：
- `httpx.ReadError` / `RemoteProtocolError` / `PoolTimeout` / `WriteError` / `ProxyError`（backend 重启、nginx 断连、半包）——它们是 `httpx.TransportError` 而非 `ConnectError`/`TimeoutException`。
- `response.json()`（第 64 行）在 backend 返回 `text/html` 错误页（502/网关页）时抛 `json.JSONDecodeError`。
- `_response_detail_reason`（第 68-77 行）已用 `try/except ValueError`，但主路径没有。

后果：任一情况都从工具里逃出 → 命中 P0-1 的 `except Exception` → run 变 `workflow_failed{reason:"ReadError"}`。当前 `tests/test_backend_learning_client.py:29-62` 只覆盖了 `Timeout/Connect` 与 HTTP 状态码分支，**没有任何传输层断裂或非 JSON 响应测试**。

**最小修复**（6 行）：

```python
except httpx.TransportError as exc:          # 替代 TimeoutException/ConnectError 两个分支
    reason = "backend_timeout" if isinstance(exc, httpx.TimeoutException) else "backend_unavailable"
    raise BackendLearningClientError(reason) from exc
...
try:
    body = response.json()
except ValueError:
    raise BackendLearningClientError("backend_bad_response", status_code=response.status_code)
```

---

### P0-3 · `webhook_url` 完全由调用方控制 → SSRF（可打内网与 backend 自身）

**位置**
- `api/knowledge.py:197-204`：`webhook_url: str = Field(..., description="Callback target to inject generated results")` —— 无 scheme/host/allowlist 约束。
- `api/knowledge.py:281-300`：`asyncio.create_task(run_public_resource_generation(... webhook_url=request.webhook_url))`。
- `generators/public_resource_flow.py:92-110`：

```python
async def _post_webhook(url, settings, payload):
    if not url: return
    headers = {"X-Webhook-Secret": settings.WEBHOOK_SECRET} if settings.WEBHOOK_SECRET else {}
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, json=payload, headers=headers)   # ← 任意 URL
```

Agent Service 会把 `X-Webhook-Secret` 连同生成结果 POST 到任意地址，包括 `http://127.0.0.1:8001/internal/ai-chat/...`（backend 内部接口）、`http://169.254.169.254/`、`http://qdrant:6333`。这是一个可被用作内网探测/凭据外带的原语，且失败信息会写回调用方（`public_resource_flow.py:60-76` 的 failed webhook 还会再把错误回投给同一地址）。

**最小修复**：在 `ResourceGenerationRequest` 上做 `field_validator`，要求 `webhook_url` 的 scheme ∈ {http, https} 且 netloc 属于 `BACKEND_INTERNAL_BASE_URL` 的 netloc（`agents/model_provider.py:26` 已有该配置），或直接改为**不接收 URL**，让 backend 用 `task_id` 反查回调地址。

---

### P0-4 · 每次 chat 请求在事件循环里做同步 Qdrant I/O，且客户端永不关闭

**位置**
- `api/workbench.py:25` → `async def workbench_chat`（async 上下文）
- `session/workbench_session.py:130-145` → 同步调用 `self._agent_factory.create_agent(...)`（**没有 `await`、没有 `to_thread`**）
- `agents/workbench_factory.py:196-230`：

```python
settings = AgentModelSettings()                       # 每次都重读 .env
embedding_model = build_embedding_model_from_settings(settings)
if embedding_model and settings.QDRANT_URL:
    q_client = QdrantClient(url=settings.QDRANT_URL)   # ← 同步构造，同步网络
    _ensure_memory_collection(client=q_client, ...)    # ← 同步 collection_exists + get_collection
    mem0_mw = Mem0Middleware(...)                      # ← 每次请求新建
    memory_tools = guard_memory_tools(_build_memory_tools(mem0_mw))
```

三处问题叠加：
1. `qdrant_client.QdrantClient` 是**同步**客户端，`collection_exists` / `get_collection` 各一次阻塞 HTTP 往返（`agents/workbench_factory.py:80-96`），在 `async def` 里直接执行 → **阻塞整个事件循环**（含所有正在进行的 SSE 流）。
2. `q_client` **从未 `.close()`**（全仓 `grep` 无 `q_client.close`），每请求泄漏一个连接池。
3. 与 `tools/rag.py:35-40` 的 `QdrantStore` + `ensure_qdrant_collection_exists`（异步版本，`tools/rag.py:43-60`）功能重复，形成两套 Qdrant 初始化路径。

后果：并发 10 个 chat 请求 → 事件循环逐请求串行阻塞，正在输出 token 的 SSE 流出现可见卡顿；长时间运行后 fd/连接耗尽。

**最小修复**（分三步，可独立落地）：
1. 把 `_ensure_memory_collection` 变成 `await asyncio.to_thread(...)`，或更优：迁到 `main.py` 的 `lifespan`（`main.py:10-24` 已有 lifespan，天然合适），进程级只做一次。
2. `q_client` 提升为模块级单例 + 在 lifespan `finally` 中 `close()`。
3. `Mem0Middleware` 的构造若必须按 `user_id` 区分，至少缓存 `MemoryConfig`/embedding model（当前每请求都 `AgentModelSettings()` + `build_embedding_model_from_settings`）。

---

### P0-5 · 未知 AgentScope 事件 = 终止 run（前向兼容性为零）

**位置**：`runtime/protocol_adapter.py:243-247`

```python
return EduEventType.WORKFLOW_FAILED, {
    "reason": "unsupported_agentscope_event",
    "event_class": event.__class__.__name__,
}
```

这是 `_map_event` 的**兜底分支**。而 `session/workbench_session.py:351-355` 会对任何 `WORKFLOW_FAILED` 置 `failed = True`，随后 `347-348` 跳过 `ReplyEndEvent`、`360-362` 把 run 状态写成 `failed`。

后果：`agentscope>=2,<3` 是**允许次版本漂移**的（`pyproject.toml:9`）。只要上游在某个 2.x 版本新增一个事件类（如 artifact 增量事件、压缩事件），**所有** chat run 立刻变成 `workflow_failed{reason:"unsupported_agentscope_event"}`，且错误信息还把内部类名暴露给学生端 SSE 流。同一个兜底还会被 `adapt_many` 双次触发（`runtime/protocol_adapter.py:117-140` 的 `_map_event` + `_build_plan_payload_for_tool_result`）。

**最小修复**（3 行）：兜底改为“忽略并记录”，把未知事件降级为 `debug_log`（`observability/logging.py:78-130` 已有该通道）：

```python
logger.warning("ignoring unknown agentscope event: %s", type(event).__name__)
return None
```

---

### P0-6 · SSE 生成器内部异常无错误帧，连接静默中断

**位置**：`api/workbench.py:34-49`

```python
async def event_stream():
    try:
        async for event in run_bus.subscribe(run.run_id):
            yield format_sse(event)
    finally:
        await session.cancel_run(run.run_id)
```

只有 `try/finally`，**没有 `except`**。触发路径：
- `run_bus.subscribe()` → `_get_run()` 抛 `KeyError("unknown run_id")`（`session/run_bus.py:104-108`）；
- `format_sse` 中 `json.dumps` 对不可序列化 payload 抛 `TypeError`（`runtime/sse.py:6-7`，而 `adapter` 会把任意 `parsed` 值塞进 payload，见 `runtime/protocol_adapter.py:186-232`）；
- `run_store.append_event`（在 agent 任务侧，`session/workbench_session.py:236`）本身抛 `OSError`（磁盘满 / 权限）。

一旦抛出，Starlette 直接中止 chunked 响应，**客户端收不到 `workflow_failed`**，只能依赖 backend 代理兜底伪造错误帧（`backend/app/services/tutoring_stream_adapter.py:336-356` 确实有兜底，但它把一切归因为 `agent_service_unavailable`，错误归因错误，且 `_persist_state` 会写入空正文）。

此外两个 SSE 结构性缺陷：
- **无 keepalive**：`ReplyStartEvent` 到首次 `ModelCallStartEvent` 之间若模型排队 >60s（`LLM_TIMEOUT=60`，`agents/model_provider.py:19`），期间无任何字节，反向代理/浏览器可能判定连接死亡。
- **无 `id:` / `retry:`**：`runtime/sse.py` 只输出 `data:` 行；`EduEvent.seq` 已是完美的事件序号（`runtime/edu_events.py:24-25`），却未用作 SSE `id:`，导致无法断线续传。

**最小修复**：给 `event_stream` 加 `except Exception` → yield 一帧 `workflow_failed{reason:"stream_error"}`；把 `format_sse` 改为 `f"id: {event.seq}\ndata: {...}\n\n"`；在 `subscribe` 的空闲等待上加 15s 心跳帧（`\n` 注释行即可保活）。

---

## 3. P1 High Tech-Debt & Spaghetti Code

### P1-1 · `_run_agent`：191 行、6 层嵌套的上帝方法，且含复制粘贴的双份 flush 逻辑

**位置**：`session/workbench_session.py:183-373`

单函数内混合了 **8 类职责**：流解析、文本脱敏门、内容安全复审、artifact 发布、plan 状态机、可观测性日志、权限确认、状态落盘。其中：

- 第 242-250 行（`ExceedMaxIters` flush）与第 279-287 行（`ReplyEnd` flush）是**逐字符相同的 9 行代码块**：

```python
if pending_filtered and pending_text_event is not None:
    buffered_event = pending_text_event.model_copy(update={"delta": pending_filtered})
    for edu_event in adapter.adapt_many(buffered_event):
        published_event = self._run_bus.publish_event(edu_event)
        run_store.append_event(run.run_id, published_event.to_dict())
```

- 第 216-263 行的 “滞后一个 chunk” 推流（`pending_filtered` / `pending_text_event`）本身就是难懂的状态机，注释为零。
- `failed` 标志分散在 5 处（`350-355`、`347`、`360`、`215`），阅读者必须同时跟踪 `last_text_event` / `pending_filtered` / `pending_text_event` / `failed` / `last_text_event=None` 四个变量。

**最小修复**：抽出 `_flush_text(pending, gate, adapter, run, run_store)` 私有方法消除重复；长期把 216-263 抽成 `TextDeltaPipeline` 类（输入 agent 事件流，输出 EduEvent 流），`_run_agent` 收敛到 ~40 行。

---

### P1-2 · 系统提示词自相矛盾，且被测试按字面钉死

**位置**：`agents/prompts.py`

矛盾条款（同一段内）：

- 第 61 行：“当前消息只要**明确表达或流露出**任何可长期复用的……**你必须立即、高度敏锐且单方面地**在后台调用 `update_learner_profile_from_dialogue`……**不要等待用户明确下发保存指令**”。
- 第 62 行：“**只保存用户明确陈述的稳定事实**；禁止写入推断的薄弱点”。
- `tools/workbench_toolkit.py:88-93` 的 group instructions：“Update it only when the current message **explicitly** states a stable goal”。

第 61 行教模型从“流露出”推断，第 62 行与工具 side 禁止推断 —— 这是**模型行为不确定性的直接来源**，也是 `DialogueProfileUpdateInput` 校验（`tools/input_models.py:100-110`）大量失败/重试的根因。

其它提示词工程问题：
- 第 18-20 行禁止披露工具名，但第 34、77、78 行大量直呼 `read_learning_progress`、`reset_tools(personal_choice_quiz=true)`；同一提示词自相冲突，且**工具改名即静默失效**。
- 第 70 行半角逗号笔误：“该工具仅仅是代码格式和运行分析器**,**不可替代编程题的发布”。
- **测试把提示词散文当契约**：`tests/test_workbench_factory.py:213-236, 287-320` 断言 `"不会自行在未来返回并通知"`、`"不得停在 reset_tools"`、`"先进行安全意图自检"` 等**整句中文**。任何措辞优化都会红一片测试，而真正的行为约束（工具 schema、状态机）反而没有被这样锁死。

**最小修复**：(a) 删除第 61 行的“流露出/核心职责”表述，统一为“用户显式陈述”；(b) 把对提示词散文的断言改为断言**语义锚点常量**（在 `prompts.py` 导出 `RULES = {...}`，测试引用常量）；(c) 顺手修第 70 行笔误。

---

### P1-3 · 工具名/工具元数据在 4 处硬编码，新增工具需改 4 个文件

**位置**
1. `agents/permissions.py:7-30` — `SAFE_WORKBENCH_TOOLS`（20 项，同时被用作 `StudentTextOutputGate` 的 `protected_identifiers`，`session/workbench_session.py:210-213`）
2. `runtime/protocol_adapter.py:30-60` — `_TOOL_METADATA`（工具名 → 中文标题/分类/read_only，20 项）
3. `safety/internal_disclosure_policy.py:56-74` — `_SCHEMA_FIELDS`（17 个参数名）
4. 各 `tools/*.py` 的 `FunctionTool(name="...")`

其中 (2) 里的 `read_only` 与 `FunctionTool(is_read_only=True)`（如 `tools/learning_progress.py:107,113`）是**重复真相源**，已经出现偏差风险：`runtime/protocol_adapter.py:330` 把 `create_code_sandbox_card` 列入 artifact 成功集合，而该工具根本没有注册进 `build_workbench_tool_groups`（`tools/workbench_toolkit.py:57-145` 无此工具），只在 `tests/test_artifact_file_tool.py:106` 被测试。

**最小修复**：从 `ToolGroup` 反射生成 `SAFE_WORKBENCH_TOOLS`（`Toolkit` 已有工具列表），把 `_TOOL_METADATA` 的 `read_only` 直接读 `tool.is_read_only`；保留中文标题表但**只此一处**。

---

### P1-4 · Workspace / 事件日志 / 内存缓冲全部无上界，磁盘只增不减

**位置**
- `workspaces/run_store.py:21-25`：`append_event` 对**每个**事件（含每条 `text_delta`、每条 `debug_log`）`open(..., "a")` 追加一行。
- `workspaces/workbench_workspace_manager.py:22-31`：workspace 路径 = `ai-chat/<user>/<course>/<conv>`，**永不复用、永不清理**。
- 全仓 `grep` `rmtree|unlink|cleanup|prune` 在 `agent_service_v2/src/` **零命中**（唯一 TTL 是 `team/workspaces.py:9` 的 `LocalWorkspaceManager(ttl=3600.0)`，仅覆盖 team 侧）。
- `session/workbench_session.py:208, 222`：`raw_assistant_chunks: list[str]` 累积**整段回复**（含被门过滤掉的原文），仅在 `ReplyEnd` 用于最终复审。
- `.gitignore` 已忽略 `agent_service_v2/workspaces/`，所以泄漏不可见。

量化：一次 20-iteration run，每次模型调用产生 2 条 `model_call` span + 每条 tool 2 条 + 每条 text_delta 1 条 debug/正文事件；`events.jsonl` 可达数 MB；`debug_log` 的 `attributes.available_tool_names`（`observability/agent_log_emitter.py:116`）会在**每次模型调用**重复写入最多 20 个工具名。

**最小修复**：给 `WorkbenchRunStore` 加 `max_events`（如 5000，超出丢弃 `debug_log` 保留业务事件）；在 `main.py` lifespan 启动一个 `asyncio` 周期任务，删除 `mtime > 7d` 的 run 目录；`raw_assistant_chunks` 改为有界 `deque` 或只累计到 `MAX_ARTIFACT_BYTES` 级别。

---

### P1-5 · 敏感词表在热路径上反复“读盘 + 排序”

**位置**
- `safety/local_wordlist.py:11-13`：`__init__` 每次 **`path.read_text()` + 全量排序**（`config/sensitive_words.txt` 约 330 条）。
- 调用点 `observability/logging.py:96`：

```python
def output_preview(value: Any) -> str:
    from agent_service_v2.safety.local_wordlist import LocalSensitiveWordFilter
    return _truncate(LocalSensitiveWordFilter().filter(_serialize_preview(value))[0])
```
—— 由 `tool_result_attributes`（`observability/agent_log_emitter.py:126-133`）调用，即**每次工具调用**都读一次盘。

- 调用点 `tools/artifact_files.py:135`：每次 artifact 写入再读一次。
- 调用点 `safety/workbench_guard.py:18-21`、`safety/content_review_middleware.py:19`：每请求/每 session 一次。

**最小修复**：`local_wordlist.py` 加 `@functools.lru_cache` 模块级 `_load_words`（1 行），并把 `LocalSensitiveWordFilter` 在 `observability/logging.py` 提升为模块级单例。

---

### P1-6 · `resolve_workbench_artifact` 的“最新 run”是随机的，可能返回别的 run 的产物

**位置**：`workspaces/workbench_artifacts.py:21-31`

```python
for run_dir in sorted(runs_dir.iterdir(), reverse=True):   # ← 按名字倒序
    ...
    if run_dir.name.startswith("run_") and ... and candidate.is_file():
        return candidate
```

而 run 目录名来自 `run_id = f"run_{uuid4().hex}"`（`session/run_bus.py:36`）—— **UUID4 的字典序与时间无关**。

后果：同一 conversation 下多次 run 都产生 `lesson.md` 时，`GET /agent/v2/workbench/artifacts?filename=lesson.md` 有约 50% 概率返回**上一轮**的旧内容。测试 `tests/test_workbench_artifacts.py:19-43` 用 `run_001`/`run_002` 这种递增名，因此**掩盖了该缺陷**。

**最小修复**：按 `state.json` 的 mtime 或 `run_dir.stat().st_mtime` 排序，并在测试中改用 `run_<uuid4>` 生成的名字。

---

### P1-7 · 两套并行 Agent 拓扑：挂载子 App + ASGI 回环 + 手工改写 storage 会话来注入权限

**位置**
- `team_app.py:30-70` 构建独立的 AgentScope `create_app`；`team_app.py:76` 在**模块导入时**执行（`team_runtime_app = build_team_app()` → 立即 `build_team_storage()` 连 Redis，`team/storage.py:8-15`）。
- `main.py:31` 把它 `mount` 成 `/agent/v2/team-runtime`。
- `api/personalized_resources.py:22-48` 却**不直接调用**，而是用 `httpx.ASGITransport(app=team_runtime_app)` 对自己进程发 HTTP（`team/runtime_client.py:28-95`）：`POST /credential/` → `POST /agent/` → `POST /sessions/` → `POST /chat/`，**4 次回环**。
- 权限注入靠 `grant_permissions` **读出 session、`model_copy` 改 state、再整条 upsert 回去**（`api/personalized_resources.py:27-39`）。

这是全模块最绕的一段：一次“启动资源生成”要走 4 次进程内 HTTP + 一次 storage 读改写 + 一次 Redis registry 写。`tests/test_resource_agent_team.py:22-60` 用 mock transport 把它固化了。

**最小修复（渐进）**：短期把 `grant_permissions` 的改写成一次 `storage.upsert_session` + 明确 `permission_context` 初始值，消除“先创建再改”的两阶段；中期直接 `await team_runtime_app.state.<handler>` 调用，去掉 4 次 ASGI 回环；长期评估是否只需 workbench 一套拓扑。

---

### P1-8 · `agents/leader_team.py`：名为 “team” 实为两个裸 LLM 调用 + 150 行内联 f-string 提示词

**位置**
- `CoursePlannerAgent`（第 40-95 行）：单次 `model([UserMsg(...)])`，无 Agent、无 Toolkit、无验证。
- `ResourceWorkerAgent`（第 101-328 行）：`generate_asset` 是一个 **227 行**函数，内含 4 个巨型 f-string 提示词（quiz / document / mindmap / reading），quiz 分支里又内嵌 personalization 字符串拼接（第 160-186 行）与 JSON 示例（第 191-245 行）。
- 第 74-80 行与第 299-305 行：**同一段 markdown fence 剥离逻辑写了两遍**，且与 `generators/public_resources.py:264-274`、`agents/evaluation.py:26` 共 4 份。
- 第 308 行 `data = json.loads(content)` **无 try/except**（对比 `CoursePlannerAgent` 第 82-88 行有），解析失败直接 500。
- 类名与实现不符：没有 AgentScope `SubAgentTemplate`、没有 leader/worker 通信，与 `team_app.py` 的真团队完全无关，二者却共享“team/leader/worker”命名。

**最小修复**：把 4 份 fence 剥离统一为 `agent_service_v2/utils/json_extract.py::extract_json(text)`；把 `generate_asset` 拆成 `_build_quiz_prompt` / `_build_document_prompt` / `_build_mindmap_prompt` / `_build_reading_prompt`；第 308 行加 try/except 返回结构化错误；把类重命名为 `SyllabusKgExtractor` / `QuizAssetGenerator`。

---

### P1-9 · 后台任务 fire-and-forget，无引用、无错误出口

**位置**：`api/knowledge.py:289-299`

```python
asyncio.create_task(
    run_public_resource_generation(settings=settings, task_id=..., webhook_url=...)
)
return {"code": 202, ...}
```

`asyncio.create_task` 的返回值被丢弃。事件循环只持有**弱引用**（`asyncio.tasks._all_tasks` 是 `WeakSet`），任务在 await 点之间可能被 GC；同时该端点返回 202 却**没有任何查询状态的接口**，失败唯一去向是 webhook（而 webhook 无 SSRF 防护，见 P0-3）。

`generators/public_resource_flow.py:18` 的模块级 `_generation_semaphore`（并发 2）是**每进程**的，`deploy_prod.sh:263-264` 单 worker 部署下成立，但一旦扩 worker 即失效。

**最小修复**：模块级 `_BACKGROUND_TASKS: set[asyncio.Task]` 持有强引用 + `task.add_done_callback(_BACKGROUND_TASKS.discard)`；并用 `asyncio.Semaphore` 之外的显式队列或 Redis 计数替换进程内并发限制。

---

### P1-10 · 语义安全复审被本地词表“短路”，词表即事实上限

**位置**：`safety/content_review_middleware.py:24-46`

```python
count = self._local.matches(content)
if count == 0:
    return self._local_allow_review()      # ← 直接 allow，语义模型完全不调用
if self._client is None:
    return self.local_block_review(count)
try:
    review = await asyncio.wait_for(self._client.review(content), timeout=3.0)
```

语义分类器（`safety/content_review_client.py:60-92`，提示词在第 39-50 行）**只在本地词表命中时才会被调用**。词表是 330 条**精确子串**（`config/sensitive_words.txt`），对改写、拼音、英文同义、跨句拆分完全无效。也就是说：系统提示词第 17 行承诺的“安全意图自检 + 语义分类”在实际代码里退化为一张固定短语表。

同时 `workbench_session.py:288-296` 的**终审复审在正文已经推给用户之后**才执行，只补发一个 `content_safety_reviewed{action:"block"}` 事件；撤回依赖 backend 端清空 `state.chunks`（`backend/app/services/tutoring_stream_adapter.py:190-196`），但**浏览器已渲染**。

**最小修复**：对“命中词表 OR 命中 probe 模式 OR 长度 > N”之外，增加抽样语义复审（如每 run 一次终审必跑），把当前 3.0s 超时改成可配置；终审 block 时在 SSE 尾部补发 `text_delta{delta: REFUSAL_TEXT}` 明确覆盖。

---

### P1-11 · team 事件流：`log_read` 与 `subscribe` 之间的 replay 窗口会丢事件

**位置**：`api/personalized_resources.py:88-102`

```python
async def events():
    key = MessageBusKeys.session_events(session_id)
    for _entry_id, raw in await message_bus.log_read(key, max_count=...):   # ① 读历史
        ...
    async for raw in message_bus.subscribe(key):                            # ② 订阅新事件
        ...
```

① 与 ② 之间发布的事件既不在历史里（尚未写入 log_read 快照）也不在订阅里（订阅尚未建立）—— 典型 replay gap，且无法去重（未使用 `_entry_id`）。同一函数还把 `json.loads(raw_run)` 裸调（第 82 行），registry 里一条脏数据即 500。

**最小修复**：先用 `subscribe` 建立后续管道并缓冲，再 `log_read` 回放并按 `entry_id` 去重（或直接用 message bus 的 `subscribe(from="0")` 语义）。

---

### P1-12 · `/agent/v2/*` 全部无鉴权，artifact 端点可跨用户读取

**位置**：`api/workbench.py:56-70`

```python
async def download_workbench_artifact(
    user_id: str = Query(...), conversation_id: str = Query(...),
    filename: str = Query(...), course_id: str | None = Query(None),
):
    artifact = resolve_workbench_artifact(manager=..., user_id=user_id, course_id=..., ...)
```

`user_id` 完全由查询参数决定，无 token 校验、无调用方身份绑定。全仓 `grep` `Depends|HTTPBearer|Authorization` 在 `agent_service_v2/src/` **零命中**。`start_all.sh:150-151` 与 `deploy_prod.sh:263-264` 绑定 `127.0.0.1`（外部不可达），因此风险取决于是否存在其他访问路径；但 backend 代理（`backend/app/services/tutoring_artifact_service.py:44-50`）会在其鉴权后传入 `user_id`，一旦 Agent 服务被同机任意进程或误配反向代理暴露，即为 IDOR。

**最小修复**：为 `/workbench/*` 与 `/knowledge/*` 增加共享密钥头校验（复用已有的 `X-Internal-Agent-Token` 语义，`tools/backend_learning_client.py:48`），或让 backend 传签名的 `user_id`。

---

### P1-13 · 服务边界被共享文件系统破坏

**位置**
- `agents/model_provider.py:38`：`COURSE_CATALOG_STORAGE_ROOT: str = "../backend/storage/course_catalogs"` —— 默认值直接指向 **backend 的磁盘目录**。
- `api/knowledge.py:65`：`storage_root = Path(settings.COURSE_CATALOG_STORAGE_ROOT).resolve()`，随后以**相对路径直接 `read_text`/`PDFParser.parse`** 读取 backend 拥有的文件。
- 与任务声明“agent_service_v2 与 backend MySQL 解耦、仅经 API/SSE 通信”**部分矛盾**：无 SQL 耦合（好），但有**文件系统耦合**（坏）—— 换机部署、多机横向扩展、backend 用对象存储时全部失效。

**最小修复**：让 backend 通过 multipart 上传或预签名 URL 传文件，Agent 侧只接收流；短期至少把 `COURSE_CATALOG_STORAGE_ROOT` 改为必填、无默认值，避免静默依赖相对路径。

---

### P1-14 · 会话历史无 token 上界；单 run 无墙钟上限

**位置**
- `session/workbench_input.py:13-19`：把 backend 传来的 `recent_messages`（最多 20 条，见 `backend/app/services/tutoring_payload_builder.py:165-173`）**全量**转成 `Msg`，无长度/条数裁剪。
- `agents/workbench_factory.py:263`：`ContextConfig(tool_result_limit=20000)` 只限工具结果，不限历史。
- `agents/workbench_factory.py:264`：`ReActConfig(max_iters=20)` × `LLM_TIMEOUT=60s`（`agents/model_provider.py:19`）= **单 run 最长 20 分钟**，无整体超时、无 per-run registry 可在进程外取消。

后果：长对话 + 20 轮 ReAct 可轻易超模型上下文，触发 400 后 run 直接失败（又走 P0-1/2 的异常路径）。

**最小修复**：在 `build_workbench_agent_input` 前按字符预算裁剪历史（保留最近 N 字符 + 摘要），并把 `max_iters` 与总时长做成可配置并在 `_run_agent` 上套 `asyncio.timeout(...)`。

---

### P1-15 · 关键路径零测试：SSE 断连、并发、清理、webhook、team SSE

**证据（45 个测试文件中缺失的断言）**
- **无** `client.disconnect` / `is_disconnected` / 生成器取消测试。`tests/test_workbench_api.py:29-95` 只覆盖“模型未配置”和“正常推流”两条路径。
- **无** `run_bus.subscribe` 被取消后 `state.waiters` 是否残留的测试（`session/run_bus.py:96-99` 的 `waiter` 在消费者取消时不会被移除）。
- **无** webhook 测试（`generators/public_resource_flow.py:92-110` 只被 `tests/test_public_resource_generation.py:167-190` patch 掉）。
- **无** workspace 清理/增长测试（根本无清理代码）。
- **无** `GET /personalized-resources/generations/{id}/events` 的真实流测试（`tests/test_resource_agent_team.py:95` 只断言 `event_path` 字符串）。
- **无** 未知 AgentScope 事件（P0-5）的测试 —— `grep "unsupported_agentscope_event"` 在 `tests/` 零命中。

**最小修复**：补 5 个测试：断连取消、（waiter 泄漏）、SSRF 拒绝、replay gap 去重、未知事件不终止 run。

---

## 4. P2 KISS Simplification Opportunities

| # | 位置 | 问题 | 最小简化 |
|---|---|---|---|
| P2-1 | `tools/contracts.py:44-55` | `{"outcome": ..., "status": ..., "data": payload, **payload}` —— `**payload` 在最后，**后端返回的 `status`/`outcome`/`reason` 会覆盖信封字段**（`normalize_tool_result` 路径已过滤，但直接 `edu_tool_result(data=...)` 的 5 处未过滤） | 把 `**payload` 移到 `"data"` 之前，或彻底删除扁平展开（下游 `protocol_adapter` 已同时读嵌套与扁平，删扁平需同步改） |
| P2-2 | `tools/memory_guard.py:106-113` | `_chunk(payload, error=False)` 成功时返回 `ToolResultState.RUNNING`（应为 `SUCCESS`） | 改成 `SUCCESS if not error else ERROR`，一行 |
| P2-3 | `runtime/team_event_adapter.py:46-61` | `TOOL_RESULT_END` 无条件映射为 `TOOL_COMPLETED`，即使 `state=="error"`；未知事件静默 `return None`（对比 `protocol_adapter` 至少会失败） | 加 `state == "error" → TOOL_FAILED` 分支 |
| P2-4 | `tools/workbench_placeholders.py:1-26` | 三个函数**只返回 `{"status":"placeholder"}`**，仅被测试引用 | 直接删除；同时清理 `tests/test_workbench_factory.py:97` 的 `assert "draft_study_artifact" not in allow_rules` |
| P2-5 | `tools/artifact_files.py:62-95, 98-129` | `build_create_code_sandbox_card` / `build_create_quiz_practice_card` **未接入** `build_workbench_tool_groups`，但 `runtime/protocol_adapter.py:330` 仍把它们列为 artifact 成功工具 | 删除两个 builder 与 protocol_adapter 对应集合项，或真正接入（二选一，别悬空） |
| P2-6 | `tools/learning_progress.py:15-27` | `_bounded_recent_limit` / `_bounded_node_limit` **定义后从未调用**（实际裁剪由 pydantic `ge/le` 完成） | 删除这两个函数 |
| P2-7 | `agent_service_v2/__init__.py:1-2` + `pyproject.toml:17-18` | 声明的 CLI 入口 `agent-service-v2 = "agent_service_v2:main"` 实际只 `print("Hello from agent-service-v2!")` | 改为 `uvicorn.run("agent_service_v2.main:app", ...)`，或删除 `[project.scripts]` |
| P2-8 | `api/knowledge.py:174-177, 221-222` | 路由定义之后**再次 `import asyncio` / `from pydantic import BaseModel, Field`**，且 `KGGenerationRequest` 等模型定义在 178-215 行（两个路由之间） | 全部移到文件顶部；把第 174 行之后到文件尾部的“V3 Multi-Agent”段拆成 `api/course_assets.py` |
| P2-9 | `runtime/sse.py:6-7` | 无 `id:` / `retry:`；`EduEvent.seq` 已有天然序号未利用 | 见 P0-6 |
| P2-10 | `agents/leader_team.py:14-22`、`agents/evaluation.py:27-43`、`generators/public_resources.py:258-274` | 三份 `_text_from_chat_response` / `_response_text`，仅其中一份处理流式 `AsyncIterator` | 收敛为 `utils/model_text.py` 一份，支持 `ChatResponse`/`AsyncIterator`/`str` |
| P2-11 | `runtime/protocol_adapter.py:130, 250, 300, 320` | `getattr(event.state, "value", event.state)` 同一兼容 shim 复制 4 次 | 抽 `_state_value(event)` 一行函数 |
| P2-12 | `tools/web_search_mcp.py:122-124` | 启动期要求 `tool_names != {WEB_SEARCH_INTERNAL_TOOL_NAME}` **完全相等**才启用；上游包加一个工具即静默 disabled | 改为 `WEB_SEARCH_INTERNAL_TOOL_NAME in tool_names` |
| P2-13 | `api/workbench.py:76-77`、`safety/local_wordlist.py:7` | `parents[3]` / `parents[4]` 硬编码目录层级（`agent_service_v2/workspaces`、`<repo>/config/sensitive_words.txt`）。若按 wheel 安装或独立部署，`_load_words` 在构造时抛 `FileNotFoundError` → 每个 chat 500 | 改为可配置路径 + 启动期校验（lifespan 中 fail fast） |
| P2-14 | `agents/model_provider.py:100-140` | `OpenAICompatibleRerankerProvider.score` 按 `index` 排序返回，**不回填缺失 index**；调用侧 `tools/rag.py:166-172` 用 `zip(..., strict=True)` → 部分响应必抛 → 每次都走 fallback 分支 | 按 `len(documents)` 构造全 0 默认分再覆盖 |
| P2-15 | `generators/public_resources.py:264-274`、`agents/leader_team.py:74-80` | 4 份 JSON fence 剥离 | 见 P1-8 |
| P2-16 | `session/workbench_input.py:12` | 把 `<untrusted_context>` 塞进 `UserMsg(name="system_context")` —— 用 user 角色承载伪系统块 | 若 AgentScope 2.x 支持 system 角色注入，改用它；否则至少在 payload 前加显式分隔标记 |
| P2-17 | `workspaces/run_store.py:21-24` | 每个事件一次 `open()` | 用长驻 `aiofiles`/`with` 复用或批量 flush |
| P2-18 | `artifacts/manifest.py:22-70` | 每次 `ReplyEnd` 与每次成功 artifact 工具结果都**全目录扫描 + 全量 manifest 重写**（`protocol_adapter.py:121-127`、`_build_artifact_events`）；`published_seq` 与 bus 的 `seq` 是两套编号且可能不一致 | `publish_new` 接受增量文件名集合而非全扫；`published_seq` 改由 `run_bus.publish_event` 回填 |
| P2-19 | `schemas/workbench.py:1-15` | `WorkbenchChatRequest` 无长度/枚举约束（`message: str`、`scope: str = "course"`、`context: dict` 任意） | `message: str = Field(min_length=1, max_length=8000)`、`scope: Literal["course","global"]` |

---

## 5. Actionable Agent Service Refactoring Roadmap

> 原则：先止血（P0，每项 ≤1 天、≤50 行 diff），再降复杂度。每步都可独立上线、可回滚。

### 阶段 0 — 立刻合并（P0，阻断发布）

| 步骤 | 动作 | 触及文件 | 验收 |
|---|---|---|---|
| 0.1 | 加 `tool_boundary` 装饰器并套到全部 `FunctionTool` 注册点 | `tools/workbench_toolkit.py`、`tools/learning_progress.py:103-118`、`tools/learner_profile.py:112-129`、`tools/personalized_resources.py:96-99`、`tools/personal_code_problem.py:60-68`、`tools/personal_choice_quiz.py:55-63` | 新测试：`write_artifact_file(filename="x.exe")` → `outcome="failure"` 且 run 以 `workflow_completed` 结束 |
| 0.2 | `post_json` 改捕 `httpx.TransportError` + JSON 解码兜底 | `tools/backend_learning_client.py:44-65` | 新测试：`MockTransport` 返回 `text/html` → `BackendLearningClientError("backend_bad_response")`；`RemoteProtocolError` → `backend_unavailable` |
| 0.3 | `webhook_url` 加 validator（netloc allowlist 或直接移除字段） | `api/knowledge.py:197-204`、`generators/public_resource_flow.py:92-110` | 新测试：`webhook_url="http://127.0.0.1:8001/x"` → 422 |
| 0.4 | 未知 AgentScope 事件 → `return None` + `logger.warning` | `runtime/protocol_adapter.py:243-247` | 新测试：构造假事件类 → `adapt()` 返回 `None`，run 不被标记 failed |
| 0.5 | 记忆/Qdrant 初始化迁到 lifespan + `to_thread` + `close()` | `agents/workbench_factory.py:196-230`、`main.py:10-24` | 手工：并发 10 个 chat，事件循环无 >100ms 阻塞（py-spy 抽样） |
| 0.6 | SSE：`event_stream` 加 `except` → 补 `workflow_failed`；`format_sse` 加 `id:`；订阅空闲 15s 心跳 | `api/workbench.py:34-51`、`runtime/sse.py:6-7`、`session/run_bus.py:89-99` | 新测试：让 `format_sse` 抛 `TypeError` → 客户端仍收到一帧 `workflow_failed` |

**阶段 0 出口条件**：`uv run --project agent_service_v2 pytest` 全绿；手工验证 3 场景（正常对话 / 客户端中途断开 / backend 重启中的工具调用）。

---

### 阶段 1 — 一周内（P1 止血，降低运维风险）

| 步骤 | 动作 | 触及文件 |
|---|---|---|
| 1.1 | 修 `resolve_workbench_artifact` 排序依据为 mtime，并把测试改用真实 `run_<uuid>` 目录 | `workspaces/workbench_artifacts.py:21-31`、`tests/test_workbench_artifacts.py:19-43` |
| 1.2 | `LocalSensitiveWordFilter` 词表 `lru_cache` + 日志侧单例 | `safety/local_wordlist.py:11-13,48-53`、`observability/logging.py:96` |
| 1.3 | 后台任务强引用 + `add_done_callback`；`_BACKGROUND_TASKS` 集合 | `api/knowledge.py:289-299` |
| 1.4 | `subscribe` 取消时清理 `state.waiters`（`try/finally` 中 `state.waiters.remove(waiter)`） | `session/run_bus.py:96-99` |
| 1.5 | 修正提示词矛盾：删 `prompts.py:61` 的“流露出/核心职责”，统一为显式陈述；修 70 行笔误 | `agents/prompts.py:61-62,70` |
| 1.6 | `/agent/v2/*` 增加共享密钥头校验（含 `workbench/artifacts`） | `main.py`（`middleware`）、`api/workbench.py:56-70` |
| 1.7 | 给 workspace + `events.jsonl` 加上界与 TTL 清理任务 | `workspaces/run_store.py:21-25`、`main.py` lifespan |
| 1.8 | history token 预算裁剪 + run 级 `asyncio.timeout` | `session/workbench_input.py:13-19`、`session/workbench_session.py:183` |
| 1.9 | 补 5 个关键缺失测试（断连、waiter 泄漏、SSRF、replay gap、未知事件） | `tests/` |

---

### 阶段 2 — 两周内（结构性降复杂度）

| 步骤 | 动作 | 触及文件 |
|---|---|---|
| 2.1 | 抽出 `_flush_text` 消除双份 flush；随后把 216-263 行提炼为 `TextDeltaPipeline` | `session/workbench_session.py:216-296` |
| 2.2 | 工具名/元数据单一真相源：从 `Toolkit` 反射生成 `SAFE_WORKBENCH_TOOLS`，`read_only` 读 `tool.is_read_only` | `agents/permissions.py:7-30`、`runtime/protocol_adapter.py:30-60` |
| 2.3 | 统一 JSON 抽取为 `utils/json_extract.py::extract_json`（4 处调用点） | `agents/leader_team.py`、`generators/public_resources.py`、`agents/evaluation.py` |
| 2.4 | 拆 `ResourceWorkerAgent.generate_asset`（227 行）为 4 个 prompt builder；补第 308 行异常处理；类重命名 | `agents/leader_team.py:101-328` |
| 2.5 | 拆 `api/knowledge.py`：课程资产生成路由 → `api/course_assets.py`，消除中段 import | `api/knowledge.py:174-330` |
| 2.6 | 修 `team_event_adapter` 的 `TOOL_FAILED` 映射；team SSE 用 `entry_id` 去重 | `runtime/team_event_adapter.py:46-61`、`api/personalized_resources.py:88-102` |
| 2.7 | 语义安全复审改为“终审必跑”，终审 block 时补发拒答文本 | `safety/content_review_middleware.py:24-46`、`session/workbench_session.py:288-296` |
| 2.8 | 死代码清理：`workbench_placeholders.py`、`_bounded_*_limit`、悬空的 `create_*_card` builders、`[project.scripts]` stub | 见 P2-4/5/6/7 |

---

### 阶段 3 — 一个月内（架构收敛，需 PRD 评审）

1. **收敛双拓扑**：评估 `team_app` 是否可退化为 workbench 内的一个 ToolGroup；若保留，去掉 4 次 ASGI 回环与两阶段权限改写（P1-7）。
2. **服务边界正规化**：教材入库改为 backend 主动上传（去掉 `COURSE_CATALOG_STORAGE_ROOT` 共享盘依赖，P1-13）；`webhook_url` 从契约中移除，改由 backend 按 `task_id` 回调到白名单地址。
3. **运行时可观测性**：把 `EduEvent.seq` 作为端到端 trace 主轴；把 `debug_log` 与业务事件分流到不同 SSE 通道（或独立 `/logs` 端点），避免学生端带宽与泄漏面（P1-4、P2-18）。
4. **提示词工程化**：把 98 行系统提示词按“安全 / 事实 / 工具路由 / 教学风格”拆成可独立测试的片段，测试断言片段常量而非散文（P1-2）。
5. **压测基线**：以“20 并发 × 20 轮 ReAct”为基线，量化事件循环阻塞、内存增长、workspace 增长速率，作为阶段 4 的输入。

---

### 附录 A · 需由 supervisor 执行的验证命令

```bash
# 全量测试（本审查未执行，无 shell 权限）
cd agent_service_v2 && uv run --project . pytest -q

# 关键回归（阶段 0 之后应新增并通过）
cd agent_service_v2 && uv run --project . pytest -q \
  tests/test_artifact_file_tool.py tests/test_backend_learning_client.py \
  tests/test_protocol_adapter.py tests/test_workbench_api.py \
  tests/test_workbench_session.py tests/test_run_bus.py

# 路由清单与文档一致性
cd agent_service_v2 && uv run python -c \
  "from agent_service_v2.main import app; print(sorted(app.openapi()['paths']))"
```

### 附录 B · 本报告未覆盖的内容（供后续审查补充）

- AgentScope 2.x 内部对 `FunctionTool` 调用异常的包装行为（`agentscope` 未安装在本仓库树内，无法确认是否已在框架层兜底；P0-1 的结论基于“工具层契约分裂”这一可验证事实，若框架已兜底则应降级为 P1）。
- `team_app` 挂载 App 在 `uvicorn --reload`（`start_all.sh:151`）下的 lifespan 双执行行为。
- Redis 不可用时的 `team_runtime_app` 导入期失败路径（`team_app.py:76` 模块级构建）。
- 前端对 `debug_log` 的消费量与 `useRunLogs` 的 300 条上限（`frontend/src/hooks/__tests__/useRunLogs.test.js:8-14`）与后端无上界写入之间的容量错配。