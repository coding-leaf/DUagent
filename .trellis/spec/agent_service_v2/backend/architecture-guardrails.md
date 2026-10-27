# Architecture Guardrails (`agent_service_v2`)

> Hard negative constraints (架构红线) plus the explicit escape hatches (显式逃生通道)
> for the AgentScope multi-agent service.

---

## Why This File Exists

The agent service is where prompts, tools, and sandboxed execution meet. Bugs here
do not throw exceptions — they produce quietly wrong curricula, unparseable
artifacts, or a sandbox that executes attacker-supplied code. The rules below are
the ones that repeatedly caused rework, so they are non-negotiable.

---

## Hard Negative Constraints (架构红线)

### ❌ 严禁生成带 `<script>` 或未受控 HTML 的文档资源 (Enforce Markdown Output Contract for Document Resources)

`personal_lesson`、`reading`、`lesson` 等讲义文档资源**必须采用标准 Markdown 格式**输出（标题、段落、Markdown 代码块、表格等），**严禁输出包含 `<script>`、`<div class="slide">`、`<style>` 或内联 DOM 事件监听的原生 HTML 幻灯片**。

**Why**:
前端渲染引擎依赖 React 与虚拟 DOM，出于 XSS 安全防御铁律不会执行内嵌 `<script>`。放任模型生成原生 HTML 幻灯片不仅会导致翻页按钮失效卡死、样式污染，还会使除首屏外的所有内容因 `display: none` 被隐性截断，严重破坏用户体验与系统安全性。在校验层（`validate_typed_resource`）必须硬性检测并阻断 `<script>` 标签。

### ❌ 严禁在 Prompt 中硬编码学科 / 技术栈 (No hardcoded subject or tech stack in prompts)

Prompts must stay **discipline-agnostic**. The curriculum planner, resource
generator, and quiz tools all receive the discipline from the caller
(`course_title`, syllabus outline, catalog chunks) and inject it at runtime.

Forbidden in prompt/f-string/template literals under `agents/` and `generators/`:

- Concrete subject nouns: `数学`, `物理`, `化学`, `Python`, `Java`, `React`, `SQL`, `C++`
- Subject-specific chapter names: `微积分`, `线性代数`, `面向对象`, `数据结构`
- "as a Python expert..." style persona lock-in

**Why**: the product serves arbitrary course catalogs. A hardcoded subject forces
a code change per discipline and leaks wrong context into unrelated courses —
a failure mode users report as "the AI thinks every course is programming".

**Standard alternative**: derive the discipline from `request.course_title` /
syllabus context and pass it into the prompt as a variable:

```python
prompt = f"""你是 {course_title} 的课程规划助手。
请基于以下大纲生成知识图谱……"""
```

### ❌ 严禁在沙箱内动态写脚本解析文件 (No dynamically written parse scripts in the sandbox)

Document parsing must go through the reviewed, in-repo tools
(`tools/rag.py` parsers, `tools/outline_extractor.py`). Generating a Python/Node
snippet at runtime and executing it via `exec`/`eval`/`subprocess` to parse a PDF
or DOCX is forbidden.

**Why**: dynamically generated code is unauditable and unbounded — it turns a
file parse into a remote code execution surface, and its output schema is not
validated by any Pydantic contract.

**Standard alternative**: extend the native parser tool, and validate the result
through the existing `FunctionTool` input/output schemas.

### ❌ 严禁绕过工具契约直接调用外部 HTTP (No ad-hoc external HTTP in agent flows)

Agent-side outbound calls go through the tool layer (`tools/backend_learning_client.py`,
`tools/web_search_mcp.py`) so logging middleware, content review, and retry policy
all apply. Scattering `httpx.get` inside an agent module bypasses
`AgentRunLoggingMiddleware` and `ContentReviewMiddleware`.

### ❌ 严禁在流式路径吞掉异常或残留会话 (Never swallow stream errors or leak sessions)

SSE/streaming handlers must terminate the stream and release the generation
session in a `finally` block. A stream that ends without an explicit terminal
event leaves the frontend state machine hanging — see the matching frontend
redline. Never `except Exception: pass` around a `yield`.

### ❌ 严禁把学科知识写进工具实现 (No subject knowledge inside tool implementations)

Tools are generic plumbing (fetch profile, query progress, execute code). Any
lookup table mapping a course topic to expected answers belongs in prompt context
or data, not in Python literals inside `tools/`.

### ❌ 严禁混用 RAG 检索 `catalog_id` 与业务归属 `course_id` (Never conflate RAG `catalog_id` with class `course_id`)

Qdrant course material chunks are indexed with `metadata.course_id = catalog_id`.
In `PersonalizedResourceGenerationRunner._produce_one`:
- Pass `rag_course_id = (request.catalog_id or request.course_id).strip()` to `writer.write(...)` so `ResourceWorkerAgent` retrieves chunks from the catalog vector collection.
- Pass `request.course_id` (the class offering ID) to `create_personalized_resource_draft`, `record_personalized_validation`, `review_personalized_resource`, and `publish_personalized_resource` so Backend persists records under the student's enrolled class.

### ❌ 严禁放行未校验的 `webhook_url` 或逃逸 `BackendLearningClient` 传输异常 (Validate webhook URLs & catch all transport/JSON errors)

1. **SSRF Guard & Origin Whitelist on Webhooks**: `ResourceGenerationRequest.webhook_url` and `public_resource_flow::_post_webhook` must validate `http/https` scheme, non-empty `netloc`, block cloud metadata hosts (`169.254.169.254`, `metadata.google.internal`), enforce exact path `/api/v1/webhooks/agent`, and require origin to match trusted whitelist (`BACKEND_INTERNAL_BASE_URL`, localhost 8000/8001, or `WEBHOOK_ALLOWED_ORIGINS`).
2. **Transport & JSON Error Convergence**: `BackendLearningClient.post_json` must catch `httpx.TransportError` (mapping timeouts to `backend_timeout` and all other transport errors to `backend_unavailable`) and `ValueError` on `response.json()` (mapping to `backend_bad_response`).

### ❌ 严禁破坏性清库式入库与混用不同模型向量空间 (No destructive overwrite in RAG ingestion; enforce model-isolated collections)

1. **教材切片与分块红线**：
   - 必须通过语法保护机制（如 `clean_text_preserving_syntax`）对代码块（````...```` / `~~~...~~~`）与数学公式（`$$...$$`、`$...$`）建立原子保护区，**严禁激进正则误伤代码缩进、注释及公式结构**；
   - 严禁对切片使用静默字符截断丢弃内容。必须采用 Token 感知递归二次分块（`TokenAwareRecursiveChunker`），当段落超限时在语义边界（双换行 -> 标点 -> 字符窗口）细分，确保所有块严格受控于模型安全 Token 窗口；
   - 提取的章节大纲路径必须作为结构化 Payload（`chapter_path`、`headings`）写入并前缀注入向量文本。
2. **Qdrant 蓝绿版本化与原子切换**：
   - **严禁“先删后写”与跨教材误删**：入库与旧版本清理必须遵循**教材级粒度隔离**（以业务真实 `material_id` 与 `course_id` 强绑定），严禁仅凭物理文件名造成同名教材数据互相覆盖，严禁跨教材清理导致同课程其他教材向量丢失；
   - **写入新版本绑定事务状态**：写入新版本切片时绑定唯一 `ingestion_version` 并置 `is_active=False`；
   - **激活强前置与失败防护**：写入后必须执行两阶段校验——激活前 `count()` 点位数强校验，以及 `set_payload` 激活后的 `is_active=True` 完整性校验；
   - **失败即刻回滚且保护旧版**：若写入不完整、激活异常或校验失败，立即回滚当前 `ingestion_version` 临时点位并阻断流程，**严禁触动与清理旧版本数据**；
   - **仅验证通过后清理旧版**：唯有在新版本激活且验证通过后，才允许淘汰同课程、同教材的历史旧版本切片。
3. **检索隔离与防未激活数据泄露**：
   - 知识库检索（`build_catalog_kg_context`、`retrieve_course_context`）严禁召回 `is_active=False` 的未激活临时切片；
   - 仅对无版本标记的 Legacy 历史切片在主检索未命中时提供透明只读回退；未完成或激活失败的版本绝对不得参与图谱生成或问答检索。
4. **Token 预算大纲前缀与完整文本双重兜底**：
   - 章节大纲路径作为结构化 Payload（`chapter_path`、`headings`）写入并前缀注入向量文本；
   - 大纲前缀过长时必须动态折叠高层目录（`[... > 当前节]`）或截断；拼接完整文本后必须进行最终 Token 校验，超标时强制二次递归拆分，硬性保障全部输出 Chunk 严格 `<= safe_threshold`。
5. **向量空间物理隔离与历史集合严格模型身份校验**：
   - 严禁不同 Embedding 模型或不同输出维度的向量混存在同一个 Qdrant Collection。集合名称必须动态绑定模型标识与维度（如 `course_knowledge_{model_slug}_{dim}`），保障向量空间纯净度；
   - 严禁仅因“向量维度相同”而静默回退历史集合。历史集合只读回退必须通过模型身份校验（集合名含模型标识、配置显式白名单或 DUagent 历史基准模型 `BAAI/bge-large-zh-v1.5` 严格一致），未知或模型不匹配时保守拒绝回退。

### ❌ 严禁手写过程式循环替代多智能体编排与任务悬挂 (Enforce AgentScope native pipelines & failover closure)

1. **拥抱 AgentScope 原生管道**：多智能体协作与多资源分派必须依赖 AgentScope 官方原生编排管道（如 `TeamPipeline`、`TeamMember`、`Toolkit`），禁止手写过程式单线程 `for` 循环串行调用，充分利用框架原生的 Leader-Member 并发任务调度与工具异常自愈机制；
2. **任务生命周期状态闭环**：后台多智能体异步生成若遇未捕获异常或执行失败，必须显式调用 Backend 专用的任务失败闭环端点（如 `POST /internal/personalized-resources/tasks/{task_id}/fail`）通知后端更新 `AsyncTask` 状态，严禁任务静默崩溃并悬挂在 `processing`，彻底杜绝前端无休止转圈死锁。

---

## Escape Hatches (显式逃生通道)

The agent service occasionally needs a controlled exception — an experimental
model provider, a one-off migration, a provider that genuinely has no tool
wrapper yet.

### Rule

1. **Converge.** Put the exception in `agents/model_provider.py`,
   `tools/`, or `infrastructure/`-equivalent modules — never inline in a route
   handler or an agent's `reply()` loop.
2. **Declare it inline** with a tagged, reasoned annotation:

   ```python
   # arch-allow: subject-hardcode (reason: benchmark fixture pins the discipline; see tests/test_curriculum_planner.py)
   BENCHMARK_SUBJECT = "数学"
   ```

3. **Use a known tag.** Unknown tags fail review:

   | Tag | Meaning |
   | :-- | :-- |
   | `subject-hardcode` | A discipline name that must be literal |
   | `sandbox-script` | Runtime-generated parse/exec code |
   | `direct-http` | Outbound call bypassing the tool layer |
   | `stream-error-swallow` | Intentionally non-fatal stream exception |

4. **Keep a reason.** `(reason: ...)` is mandatory.

5. **Re-audit.** Audit with `grep -rn "arch-allow:" agent_service_v2/src/`.

### Example: allowed vs. forbidden

```python
# ✅ Allowed — converged in the model provider, tagged, reasoned
# agents/model_provider.py
# arch-allow: direct-http (reason: provider SDK lacks async streaming; tracked in #204)
async def _raw_stream(settings):
    async with httpx.AsyncClient() as c:
        ...


# ❌ Forbidden — hardcoded discipline inside a generic prompt builder
# agents/curriculum_planner.py
prompt = "你是 Python 编程课程的规划专家，请生成……"
```

---

## Static Enforcement

```bash
# Both Python packages, one shared config (repo-root ruff.toml)
uv tool run ruff==0.13.0 check agent_service_v2/src/agent_service_v2/

# Unit tests (tool contracts, middleware, streaming)
uv run --project agent_service_v2 pytest agent_service_v2/tests/ -q

# Escape-hatch audit
grep -rn "arch-allow:" agent_service_v2/src/
```

The full repo gate is `python check_all.py`.
