# Architecture Guardrails (`backend`)

> Hard negative constraints (架构红线) plus the explicit escape hatches (显式逃生通道)
> that keep the FastAPI backend architecturally honest.

---

## Why This File Exists

Linters catch syntax. They cannot catch *architectural* drift — a service reaching
for `httpx` to call an LLM directly, a route importing a model's private helper,
a background task swallowing exceptions. The rules below encode the decisions we
already paid for once. Violating them is a review blocker, not a style nit.

---

## Hard Negative Constraints (架构红线)

### ❌ 严禁在 `backend` 内直接调用大模型 (No direct LLM calls)

`backend` is a **business orchestrator**. Every AI capability lives behind
`agent_service_v2` and is reached through `app/services/agent_client.py`
(`agent_client.post_json(...)` / `agent_client.stream_sse(...)`).

Forbidden in `backend/app/`:

- `import openai` / `import anthropic` / `import agentscope` / `import ollama` / `import litellm`
- Hardcoded provider URLs (`api.openai.com`, `dashscope.aliyuncs.com`, ...)
- Prompt string construction destined for an LLM
- API keys for model providers in `app/core/config.py`

**Why**: the agent service owns prompt engineering, tool policy, content safety,
and provider failover. A second caller silently duplicates that policy surface and
splits observability. `backend` must stay free of provider SDKs so the agent layer
can be deployed, scaled, and swapped independently.

**Standard alternative**: add or extend a typed method on
`app/services/agent_client.py`, and let the service layer call that.

### ❌ 严禁跨层直接访问模型私有内部 (No cross-layer shortcuts)

- API routes (`app/api/v1/`) must not import from another API module to reuse logic — extract into `app/services/`.
- `app/schemas/` must not import `app/models/` (schemas are transport contracts; models are persistence).
- `app/models/` must not import `app/services/` or `app/api/`.
- Business logic in routes beyond request validation + service delegation is forbidden; put it in `app/services/`.

### ❌ 严禁在业务层散写裸 SQL / 同步阻塞调用 (No raw SQL in services, no blocking I/O in async code)

- Use SQLAlchemy 2.0 constructs (`select()`, `update()`, `delete()`). Raw `text()` belongs to `app/infrastructure/` only.
- Inside `async def`, never call `time.sleep`, `requests.*`, or synchronous file reads. Use `asyncio.sleep`, `httpx.AsyncClient`, `anyio.to_thread`.

### ❌ 严禁吞掉异常 (No silent exception swallowing)

`except Exception: pass` and `except Exception: return None` without a
`logger.warning(...)`/`logger.error(...)` are forbidden. Background tasks must
always terminate in an explicit state (`completed` / `failed` on `AsyncTask`) so
`_recover_orphaned_background_tasks()` and clients can reconcile.

### ❌ 严禁 ORM 布尔列改写为 Python 真值判断 (Keep SQL boolean comparisons in SQL)

Write `Model.is_deleted == False`, **never** `not Model.is_deleted`. The latter
evaluates Python truthiness on the instrumented attribute instead of emitting
`WHERE is_deleted = 0`, silently breaking the filter. `E712` is globally ignored
in `ruff.toml` precisely to protect this pattern.

---

## Escape Hatches (显式逃生通道)

Sometimes a redline genuinely must be crossed — a legacy vendor SDK, a
special-case migration, a bootstrap script. Cross it **explicitly**, never
silently.

### Rule

1. **Converge, don't scatter.** The exception lives in `app/infrastructure/`
   (or `app/db/`), never in `app/services/` or `app/api/`.
2. **Declare it inline.** Add an annotation on the offending line or the line
   above it:

   ```python
   # arch-allow: llm-call-override (reason: legacy vendor SDK has no agent-service path; tracked in #1234)
   resp = legacy_sdk.complete(prompt)
   ```

3. **Use a known tag.** Unknown tags fail review:

   | Tag | Meaning |
   | :-- | :-- |
   | `llm-call-override` | Direct model provider call |
   | `raw-sql` | Hand-written SQL instead of SQLAlchemy constructs |
   | `sync-io` | Intentionally blocking call inside an async function |
   | `cross-layer-import` | Deliberate schema↔model or api↔api import |

4. **Keep a reason.** `(reason: ...)` is mandatory. An unannotated crossing is a
   review blocker even if the tag is otherwise valid.
5. **Re-audit.** Every `# arch-allow:` is expected to shrink over time. Audit
   with `grep -rn "arch-allow:" backend/app/` during review.

### Example: allowed vs. forbidden

```python
# ✅ Allowed — converged, tagged, reasoned
# app/infrastructure/legacy_llm.py
# arch-allow: llm-call-override (reason: finance report summarizer predates agent_service_v2)
async def summarize(text: str) -> str:
    return await legacy_client.complete(text)


# ❌ Forbidden — business service calling a provider directly, no tag
# app/services/quiz_service.py
async def make_hint(q):
    return await openai_client.chat(...)
```

---

## Static Enforcement

```bash
# Both Python packages, one shared config (repo-root ruff.toml)
uv tool run ruff==0.13.0 check backend/app/ agent_service_v2/src/agent_service_v2/

# Escape-hatch audit
grep -rn "arch-allow:" backend/app/
```

`ruff.toml` selects `E`, `F`, `W`, `I` (pycodestyle, pyflakes, import sorting) and
ignores `E712` (SQLAlchemy boolean comparisons) and `E501` (formatter owns line
length). The full repo gate is `python check_all.py`.
