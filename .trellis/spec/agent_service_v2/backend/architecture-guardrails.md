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

1. **SSRF Guard on Webhooks**: `ResourceGenerationRequest.webhook_url` must validate `http/https` scheme, non-empty `netloc`, and block cloud metadata hosts (`169.254.169.254`, `metadata.google.internal`).
2. **Transport & JSON Error Convergence**: `BackendLearningClient.post_json` must catch `httpx.TransportError` (mapping timeouts to `backend_timeout` and all other transport errors to `backend_unavailable`) and `ValueError` on `response.json()` (mapping to `backend_bad_response`).

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
