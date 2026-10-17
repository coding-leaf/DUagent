# System Integration & Architecture Governance Review Report

**Scope:** cross-service contracts (frontend ↔ backend ↔ agent_service_v2), configuration/ports/CORS/tokens, deployment scripts, monorepo boundaries.
**Baseline:** working tree at `449ceec` (no uncommitted source change; `watchdog_diff --stat` shows only `.gitignore`, `.trellis/workflows/`, `reports/`). All findings are properties of the current committed code, not of a pending diff.
**Method:** read-only. Every claim below cites the file/line or the grep result that establishes it. Nothing was executed; the test commands a supervisor must run are listed in §5.

> Note on credential-looking tokens: this review's tool output redacts emails/passwords (e.g. `{{EMAIL_*}}`, `{{PASSWORD_*}}`, `{{SECRET_*}}`). Where such a token appears in a cited file, treat it as **redacted, not literal**. One action item in §4 asks a human to confirm with `grep -Rn '{{' --include='*' backend deploy README.md`.

---

## 1. Executive Summary & Cross-Service Consistency

### 1.1 Topology as implemented (verified against code, not docs)

| Hop | Transport | Declared surface | Auth |
|---|---|---|---|
| Frontend → Backend | HTTP/SSE, base `VITE_API_BASE_URL` (`frontend/src/api/client.js:5`) | `/api/v1/*` | `Bearer` JWT from `localStorage` (`client.js:14-17`) |
| Backend → Agent | HTTP/SSE via `AgentClient` (`backend/app/services/agent_client.py:41`) | `/agent/v2/*` | **none** |
| Agent → Backend | HTTP via `BackendLearningClient` (`agent_service_v2/.../tools/backend_learning_client.py:45-50`) | `/internal/ai-chat/*`, `/internal/personalized-resources/*` | `X-Internal-Agent-Token` |
| Agent → Backend | webhook POST (`agent_service_v2/.../generators/public_resource_flow.py:104-114`) | `/api/v1/webhooks/agent` | `X-Webhook-Secret` |
| Backend → Agent artifacts | GET (`backend/app/services/agent_client.py:80`) | `/agent/v2/workbench/artifacts` | **none** |

The layering claim in `docs/00-overview/README.md` ("Frontend 不直连 Agent Service", "Backend 负责鉴权…Agent Service 不访问 MySQL") **holds**: no frontend file references `8002`/`/agent/v2`; no agent_service_v2 module imports a MySQL driver.

### 1.2 What is already consistent (do not "fix" these)

- **Ports** are coherent everywhere: Backend 8001, Agent 8002, Qdrant 6333/6334, Redis 6379, Judge0 2358 — `start_all.sh:7-11`, `deploy_prod.sh:16-17`, `vite.config.js:8-10`, `deploy/env.production.example:7-46`, `docs/00-overview/README.md`.
- **Response envelope** `{code, message, data}` is applied uniformly by all backend routers (`app/api/v1/*.py`) and by `AgentClient.post_json` which rejects anything but 200/201/202 (`agent_client.py:76`).
- **Shared secrets** are single-sourced in `.env` and injected on both sides (`deploy_prod.sh:259-266`); Judge0 passwords are written to a `600` env-file and consumed via `env_file`, never bind-mounted (`deploy/judge0/docker-compose.yml:12`, guarded by `backend/tests/test_deploy_prod.py:44-47`).
- **Internal endpoints fail closed** on missing token (`internal_ai_chat.py:66-74`, `internal_personalized_resources.py:29-35`).
- **Agent surface guard**: `backend/app/static_site.py:9` reserves `api/internal/agent/…` so the SPA catch-all cannot shadow service routes.
- **Degradation paths** are real: web-search MCP failure disables only that tool (`tools/web_search_mcp.py:100-140`), OJ outage returns `status="degraded"` (`api/v1/sandbox.py:38-50`).

### 1.3 The governance problem in one sentence

The code is internally coherent, but **the three "contract" documents are all stale or incomplete**, and **two cross-service contracts are only enforced by convention** (`INTERNAL_AGENT_TOKEN` shape, `catalog_id`-vs-`course_id` meaning), so drift is currently undetectable by any test.

| Contract | Doc exists | Matches code |
|---|---|---|
| Frontend ↔ Backend | `docs/10-client-api/Client-API.openapi.json` | **No** — ≥9 live routes absent (§3.1) |
| Backend ↔ Agent (`/agent/v2/*`) | `docs/20-agent-api/Agent-Service.openapi.json` | **Partially** — status codes and one mount missing (§3.2) |
| Agent → Backend (`/internal/*`) | **none** | n/a — 15 endpoints undocumented (§3.3) |

---

## 2. P0 Critical Issues

### P0-1 — Dev environment silently disables *every* AI-Chat tool: `INTERNAL_AGENT_TOKEN` vs `BACKEND_INTERNAL_AGENT_TOKEN`
**Location:** `start_all.sh:147-151` vs `deploy_prod.sh:259`; consumer `agent_service_v2/src/agent_service_v2/tools/backend_learning_client.py:82-90`; `agent_service_v2/src/agent_service_v2/agents/model_provider.py:19`

**Evidence.** The agent reads the token as `BACKEND_INTERNAL_AGENT_TOKEN`:

```python
# model_provider.py:19
BACKEND_INTERNAL_AGENT_TOKEN: str | None = None
# backend_learning_client.py:84
if not settings.BACKEND_INTERNAL_BASE_URL or not settings.BACKEND_INTERNAL_AGENT_TOKEN:
    return None
```

Production maps the name correctly (`deploy_prod.sh:259`:
`env BACKEND_INTERNAL_AGENT_TOKEN="$(env_value "$INFRA_ENV" INTERNAL_AGENT_TOKEN)"`).
`start_all.sh:147-151` does **not** map it — it only passes `QDRANT_URL`, `AGENTSCOPE_REDIS_PORT`, `COURSE_CATALOG_STORAGE_ROOT` and relies on `--env-file "$ROOT_DIR/.env"`, whose key is `INTERNAL_AGENT_TOKEN` (`deploy/env.production.example:33`). The names never meet.

**Impact.** `build_backend_learning_client_from_settings()` returns `None`, so `WorkbenchAgentFactory.create_agent` wires in *no* internal tools: learning progress, learner profile read/update, OJ execution, personalized-resource recommend/generate, choice-quiz and code-problem delivery all return `unavailable / course_context_missing` (`tools/learning_progress.py:44-46`, `tools/learner_profile.py:30-32`, `tools/oj_execution.py:28-36`). Dev AI-Chat looks "broken but alive" — exactly the failure mode that wastes hours.

**Smallest fix.** Add one line to the agent launch in `start_all.sh`:
```bash
env BACKEND_INTERNAL_AGENT_TOKEN="$(env_value INTERNAL_AGENT_TOKEN)" \
```
(keep `INTERNAL_AGENT_TOKEN` as the single canonical key), and add a startup assertion in `agent_service_v2.main` lifespan that logs `WARNING: BACKEND_INTERNAL_AGENT_TOKEN unset — internal tools disabled`.

---

### P0-2 — Webhook auth is fail-open, and preflight cannot detect a blank secret
**Location:** `backend/app/api/deps.py:124-135`; `backend/app/core/config.py:53-55`; `deploy_prod.sh:66-73`

**Evidence.**
```python
# deps.py:124-129
async def verify_webhook_secret(x_webhook_secret: str = Header(None, alias="X-Webhook-Secret")) -> None:
    if not settings.WEBHOOK_SECRET:
        return                      # <-- allow
```
`WEBHOOK_SECRET: str = ""` and `INTERNAL_AGENT_TOKEN: str = ""` are both optional with empty defaults (`config.py:53-55`). The only prod guard is `validate_env_placeholders()` (`deploy_prod.sh:66-73`), which greps for `replace-with-`/`your-` prefixes only — a *blank* `WEBHOOK_SECRET=` line passes preflight cleanly.

**Impact.** With a blank secret, `POST /api/v1/webhooks/agent` (`app/api/v1/webhooks.py:169`) accepts calls that can mark any `resource_generation` task completed/failed and insert `resources` rows (`webhooks.py:222-280`). Task IDs are 16-hex `uuid4` slices but are exposed to students via `/api/v1/tasks/{id}` (`app/api/v1/tasks.py:12`) and `personalized_resources.py` list payloads — so this is a write primitive, not a secret.

**Smallest fix.** Invert the default: make `verify_webhook_secret` raise `503` when `settings.WEBHOOK_SECRET` is empty *unless* `settings.DEBUG`, and extend `validate_env_placeholders` with a required-key list (`WEBHOOK_SECRET`, `INTERNAL_AGENT_TOKEN`, `JWT_SECRET_KEY`, `DB_PASSWORD`) that fails on empty values.

---

### P0-3 — JWT exfiltration through URLs (artifact download)
**Location:** `frontend/src/components/common/MarkdownViewer.jsx:202-203`; `frontend/src/components/workspace/plugins/MarkdownViewer.jsx:102-103`; accepted by `backend/app/api/deps.py:48-53`

**Evidence.**
```js
// MarkdownViewer.jsx:202-203
const token = localStorage.getItem('access_token');
const downloadUrl = `${apiBaseUrl}/tutoring/conversations/${activeSession}/files/${encodeURIComponent(filename)}${token ? `?token=${encodeURIComponent(token)}` : ''}`;
```
and the backend deliberately supports it:
```python
# deps.py:48-52
async def get_download_user(token: str | None = Query(None), credentials = Depends(security_scheme), ...):
    resolved_token = credentials.credentials if credentials else token
```

**Impact.** A 7-day JWT (`config.py:28-29`, `ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080`) lands in: browser history (`<a href>` produced by React Markdown renderer), `Referer` for same-origin navigations, uvicorn access logs, and any reverse proxy/CDN log. There is no revocation path (`backend/app/core/security.py` issues stateless HS256). Combined with `localStorage` storage (`api/client.js:14`), one XSS or one log archive yields a 7-day impersonation token.

**Smallest fix (two lines, no UX change).** Replace the query-token links with a same-origin fetch: `apiClient.get(url, { responseType: 'blob' })` then `URL.createObjectURL(...)` + programmatic `<a download>`; delete the `token: str | None = Query(None)` parameter from `get_download_user` so the shortcut can never come back. Also see P1-9 for the duplicated viewer.

---

### P0-4 — Dev CORS breakage: `start_all.sh` pins one origin, Vite is allowed to drift to another
**Location:** `start_all.sh:157`; `frontend/vite.config.js:8-10`; `deploy/env.production.example:22`

**Evidence.**
```bash
# start_all.sh:157
env CORS_ORIGINS='["http://localhost:5173","http://127.0.0.1:5173"]' \
```
`vite.config.js` sets `port: 5173` **without `strictPort: true`**, so if 5173 is occupied Vite picks 5174 — while `start_all.sh` only pre-checks 8001/8002 (`ensure_port_free` at `start_all.sh:44-49,138-139`). `detect_frontend_url` even *tolerates* this by scrape-regexing the log for any port (`start_all.sh:80-88`), so the script happily prints a working 5174 URL whose API calls are then blocked by CORS. Backend `allow_credentials=True` (`app/main.py:76`) makes browser rejection certain.

Production side of the same knob: the template ships `CORS_ORIGINS='["http://localhost:8001"]'` (`env.production.example:22`) while the documented access URL is `http://服务器IP:8001` (`README.md` §7). Same-origin means this is currently harmless, but it is a landmine the moment anyone adds a second origin (e.g. a mobile web build).

**Smallest fix.** Set `strictPort: true` in `vite.config.js`, add 5173 to `ensure_port_free`, and derive dev CORS from the detected frontend URL rather than a hardcoded pair.

---

### P0-5 — Personalized-resource grounding is keyed to the wrong ID (`course_id` passed where `catalog_id` is required)
**Location:** `backend/app/api/v1/personalized_resources.py:338-341`; `backend/app/services/ai_chat_resource_service.py:182-196`; consumer `agent_service_v2/.../agents/resource_team_leader.py:35-52` + `agent_service_v2/.../team_app.py:33-38` + `agent_service_v2/.../tools/rag.py` (`get_course_knowledge_base`).

**Evidence.** Qdrant vectors are keyed by **catalog id**: ingestion is called as `ingest_course_material(..., course_id=request.catalog_id, ...)` and stores `metadata={"course_id": catalog_id}` (`agent_service_v2/src/agent_service_v2/api/knowledge.py`, `ingest_course_material` body; filter in `build_catalog_kg_context` scrolls `key="chunk.metadata.course_id", match=MatchValue(value=catalog_id)`).

Backend then sends the *class* course id on the team path:
```python
# personalized_resources.py:338-341
agent_path = ("/agent/v2/personalized-resources/generations" if is_goal_generation
              else "/agent/v2/knowledge/resources/generations")
```
```python
# personalized_resources.py:325  (payload built just above)
"course_id": req.course_id if is_goal_generation else catalog_context.catalog_id,
```
```python
# ai_chat_resource_service.py:185-194
await agent_client.post_json("/agent/v2/personalized-resources/generations", {
    "task_id": task_id, "user_id": user_id,
    "course_id": course_id,          # <-- class course id
    ...
})
```
The team runtime forwards that value straight into retrieval:
```python
# team_app.py:33-38
async def retrieve_course_context_tool(query: str, course_id: str, limit: int = 4):
    return await retrieve_course_context(query=query, course_id=course_id, limit=limit, settings=settings)
```
and `tools/rag.py::get_course_knowledge_base` binds `metadata_filter={"course_id": course_id}`.

**Impact.** For every *goal-driven* personalized generation (the entire "多智能体个性化资源" feature, `frontend/src/pages/PersonalizedResourceGenerate.jsx` → `personalized_resourcesService.generate({goal, resource_preferences})`), RAG returns zero chunks. `PublicResourceGenerator.generate_many` (`generators/public_resources.py:60-66`) then silently falls back to the "no course原文" branch, so drafts are generated from course title alone and still pass validation/review — i.e. **ungrounded content that looks approved**. The non-goal path (uses `catalog_context.catalog_id`) is correct, which is why the bug is invisible in the admin-catalog flow and visible only for students.

**Smallest fix.** Send both IDs explicitly and stop overloading the name: add `catalog_id` to the `ResourceTeamRequest` payload (`backend/.../personalized_resources.py:325-333`, `ai_chat_resource_service.py:185-194`), and in `team_app.py:33-38` pass `catalog_id` to `retrieve_course_context` while keeping `course_id` only for DB/publication scoping. One-line consumer change + one-line per producer.

---

### P0-6 — `student` / `teacher` permanent registration codes are always live (privilege escalation)
**Location:** `backend/app/api/v1/auth.py:20-23, 58-62`; blessed by `docs/10-client-api/Client-API.openapi.json:4711-4713`

**Evidence.**
```python
# auth.py:20-23
PERMANENT_REGISTRATION_CODES = {"student": "student", "teacher": "teacher"}
...
# auth.py:58-62
reg_code = result.scalar_one_or_none()
role = reg_code.role if reg_code else PERMANENT_REGISTRATION_CODES.get(req.registration_code)
if role is None: raise HTTPException(400, "注册码无效")
```
The OpenAPI doc states: `"student / teacher 为内置永久码，可重复使用"` (line 4713). The admin-managed `registration_codes` table and `/api/v1/admin/registration-codes` exist (`app/api/v1/admin.py:239-291`) but do not remove this bypass.

**Impact.** Anyone who reads the shipped OpenAPI file (it is in the deployed repo and referenced from `frontend/README.md`) can self-register a `teacher` account, then reach role-gated surfaces: `require_role("teacher")` on `POST /api/v1/resources/generate` (`resources.py:88`), `require_role("teacher","admin")` on all of `/api/v1/teaching/*` (`app/api/v1/teaching.py:16-58`), and teacher course creation (`courses.py:112`). `deploy_prod.sh` has no switch to disable it.

**Smallest fix.** Load the permanent map from config, default empty, and set it only when `DEBUG=true`:
```python
PERMANENT_REGISTRATION_CODES = json.loads(settings.PERMANENT_REGISTRATION_CODES or "{}")
```
Document one prod-only line in `deploy/env.production.example`, and add a preflight warning when it is non-empty with `DEBUG=false`.

---

### P0-7 — Knowledge ingestion is synchronous behind a `202`, racing the Backend's 60 s agent timeout
**Location:** `agent_service_v2/src/agent_service_v2/api/knowledge.py` (`create_knowledge_ingestion`: per-material `await ingest_course_material(...)` inside the request, then `KnowledgeIngestionAcceptedResponse(code=202, message="accepted", ...)`); caller `backend/app/services/catalog_ingestion_service.py:143-151` via `agent_client`; `backend/app/services/agent_client.py:41` (`timeout: float = 60.0`); upload cap `backend/app/core/config.py:47` (`COURSE_CATALOG_MAX_UPLOAD_BYTES: 20*1024*1024`)

**Evidence.** The route does full parse → 512-token chunking → embedding (batches of 32, `tools/rag.py::ingest_course_material`) *before* returning, yet its response model is literally `KnowledgeIngestionAcceptedResponse(code=202, message="accepted", status_code=202)` and `docs/20-agent-api/Agent-Service.openapi.json:121-160` documents it as `202` "成功" — the 202 semantics are false. The backend calls it with the default `AgentClient()` timeout of 60 s.

**Impact.** A 20 MB PDF (allowed by the upload cap) cannot be embedded in 60 s. `AgentClient.post_json` raises `AgentServiceError("Agent Service 响应超时", status_code=504)` (`agent_client.py:52-54`); `catalog_ingestion_service.py:151-166` then marks every material `failed`, the catalog `knowledge_status="failed"`, and the task `failed` — while the agent keeps writing chunks to Qdrant. Result: catalog is quarantined as failed but its vectors exist, and the retry path (P2/P1-adjacent `backend/tools/repair_course_catalog_knowledge_status.py`) is the only recovery.

**Smallest fix (minimal, keeps the request/response shape).** Make the route fire-and-forward: `asyncio.create_task(_run_ingestion(...))` immediately after path validation, return `202` with `data.materials[*].status="accepted"`, and have the agent POST results back to `/api/v1/webhooks/agent` (that endpoint already exists and is unused by ingestion). If a synchronous contract must be kept, document `timeout=600` on `ingestion_agent_client` and add it to `backend/tests/test_deploy_prod.py`'s extended-timeout assertions (the KG path already does exactly this at `backend/app/services/kg_generation.py:26`).

---

## 3. P1 High Tech-Debt

### P1-1 — Client API contract is materially stale (≥9 live routes absent)
`docs/10-client-api/Client-API.openapi.json` declares 53 paths (grep of `^    "/`). These are called by production code/tests but **not documented** (grep for each literal in the doc returns no match):

| Missing path | Consumer |
|---|---|
| `POST /personalized-resources/generate` | `frontend/src/api/services/personalizedResources.js:9`, `hooks/usePersonalizedResourceGeneration.js:22`, `components/personalized/GenerateModal.jsx:84` |
| `DELETE /personalized-resources/{id}` | `api/services/personalizedResources.js:12`, `hooks/usePersonalizedResources.js` |
| `POST /quiz/generate` | `app/api/v1/quiz.py:151` (route exists; only `/quiz/questions` documented) |
| `POST /profile/learning-goal`, `POST /profile/custom-instruction` | `api/services/profile.js:13,17` |
| `GET /code-problems/{id}`, `POST /code-problems/{id}/submissions` | `api/services/codeProblems.js:3-6`, `app/api/v1/code_problems.py:17,36` |
| `GET /tutoring/conversations/{id}/files/{filename}` | `components/common/MarkdownViewer.jsx:203` |
| `/admin/registration-codes` (GET/POST/DELETE) | `api/services/admin.js:30-38`, `app/api/v1/admin.py:239-291` |
| `POST /admin/course-catalogs/{id}/quiz/generations` | `api/services/catalog.js:52`, `app/api/v1/catalogs.py:313` |
| `GET /course-catalogs` (student catalog list) | `api/services/course.js:9`, `app/api/v1/catalogs.py:341` |

`docs/README.md` states "接口路径、字段和状态枚举以对应 OpenAPI 文件为准" — by that rule the shipped contract is wrong for student-facing generation and profile editing.
**Smallest fix.** Generate the doc from the app instead of hand-maintaining it: add `backend/tests/test_openapi_contract.py` asserting `set(app.openapi()["paths"]) == set(json.load(docs/10... )["paths"])`, then regenerate the JSON once. That converts this whole class of drift into a failing test.

### P1-2 — Agent contract: wrong status code documented, `team-runtime` mount invisible
- `agent_service_v2/src/agent_service_v2/api/personalized_resources.py` returns `JSONResponse(status_code=202, ...)` for `POST /agent/v2/personalized-resources/generations`, but `docs/20-agent-api/Agent-Service.openapi.json:363-401` documents only `200`. Backend tolerates both (`agent_client.py:76`), so this is silent today.
- `app.mount("/agent/v2/team-runtime", team_runtime_app)` (`agent_service_v2/src/agent_service_v2/main.py:26`) — grep for `team-runtime` in docs returns nothing; the entire multi-agent runtime surface is undocumented.
- Every documented response schema is `"schema": {}` (e.g. lines 33-37, 190-200), so **no response field is contractually pinned** anywhere: `data.resources`, `data.questions`, `data.diagnosis` are all untyped-by-contract and validated only by ad-hoc `.get()` in `backend/app/services/resource_service.py`, `quiz_service.py`, `webhook.py`.
**Smallest fix.** Same test-plus-regenerate approach; minimum viable is to add `response_model` to the three routes that drive DB writes (`resources/generations`→`{task_id,status}`, `quiz/generations`→`{questions:[...]}`, `evaluation/quiz/diagnose`→`{diagnosis:{...}}`).

### P1-3 — The Agent→Backend internal contract has no document at all
15 routes exist with zero contract coverage (grep `internal/ai-chat|internal/personalized-resources` in `docs/` → no matches):
`internal_ai_chat.py:76,91,110,122,132,142,152,188,220,245` and `internal_personalized_resources.py:37,49,80,96,113`. Yet both sides carry duplicated hand-written schemas (see P1-4). This is the single highest-value doc gap because these endpoints are what make AI-Chat "smart".
**Smallest fix.** Add `docs/30-internal-api/` generated from `backend/app.main` (routes are already in `app.openapi()` since they are mounted on the same app) and cross-check it in the same test as P1-1.

### P1-4 — Schema duplication across the service boundary (5 pairs, 2 with identical validators)
| Backend | Agent | Duplication |
|---|---|---|
| `app/schemas/internal_ai_chat.py:96-131` `ChoiceQuestionDraft` | `tools/input_models.py:19-45` `ChoiceQuestionInput` | **identical** `validate_answer_keys` logic, word-for-word |
| `app/schemas/internal_ai_chat.py:38-63` `DialogueProfileUpdateRequest` | `tools/input_models.py:88-105` `DialogueProfileUpdateInput` | same 5 fields + same "at least one fact" validator; backend adds dedupe/limits |
| `app/schemas/internal_ai_chat.py:35-36` `LearnerProfileReadRequest` | (implicit dict in `tools/learner_profile.py:35-36`) | untyped on the wire |
| `app/schemas/internal_ai_chat.py:79-92` `PersonalizedResourceStartRequest` | `tools/input_models.py:118-120` `PersonalizedResourceGenerateInput` | same literals `personal_lesson/diagram/practice/reading` |
| `app/schemas/code_problem.py:11-22` `CodeProblemDraft` | `tools/input_models.py:57-86` `PersonalCodeProblemInput` | agent re-flattens `public_inputs/hidden_inputs` → `test_inputs` in `tools/resource_drafts.py:80-90` and `tools/personal_code_problem.py:47-58` |

Also untyped in the middle: `backend/app/api/v1/personalized_resources.py:317-333` builds the Agent `ResourceTeamRequest` as a bare `dict`, so `"webhook_url"` is sent to an endpoint that ignores unknown fields (`resource_team_leader.py:5-15`, default `BaseModel` extra=ignore) — a field silently doing nothing.
**Smallest fix.** Do not build a shared package (two venvs, different Python deps — see P1-5). Instead generate `agent_service_v2/src/agent_service_v2/schemas/internal_contracts.py` from `backend/app/schemas` at build time *or*, cheaper, add one contract test per pair asserting identical `model_json_schema()` field sets, and delete the redundant agent-side `async_session_factory`-style drift risk by importing nothing.

### P1-5 — Undeclared and divergent dependencies in a single repo
- `agent_service_v2/pyproject.toml:8-15` declares only `agentscope[full]`, `fastapi`, `pydantic`, `pydantic-settings`, `sse-starlette`, `uvicorn`. Code imports **`httpx` directly** (`tools/backend_learning_client.py:6`, `api/personalized_resources.py:3`, `generators/public_resource_flow.py:7`), **`qdrant_client` directly** (`tools/rag.py` `from qdrant_client.models import FieldCondition, Filter, MatchValue`, `agents/workbench_factory.py:89` `from qdrant_client import QdrantClient`), and `mem0.configs.base` (`workbench_factory.py:51`). All resolve transitively via `agentscope[full]` (present in `uv.lock` as `qdrant-client`, `httpx`, `mem0ai`), so it works — but a transitive pin bump silently breaks the service. Dev group has only `pytest` (`pyproject.toml:22-25`), no `pytest-asyncio`, while tests use `asyncio.run(...)` throughout (e.g. `tests/test_backend_learning_client.py:36`).
- `backend/requirements.txt` has **no `qdrant-client`**, yet `backend/tools/repair_course_catalog_knowledge_status.py:15` does `from qdrant_client import AsyncQdrantClient` → the documented recovery tool for P0-7 raises `ImportError` on a clean backend venv.
- Two FastAPI/Pydantic majors in one repo: backend pins `fastapi==0.115.6`, `pydantic==2.10.4`; agent resolves `fastapi 0.138.2`, `pydantic 2.13.4` (`agent_service_v2/uv.lock:712,1962`). Different 422 body shapes between the two services is a live contract hazard for anything that inspects errors.
**Smallest fix.** Add `httpx`, `qdrant-client` to `pyproject.toml` `dependencies` and `pytest-asyncio` to the dev group; add `qdrant-client` to `backend/requirements.txt` (or move the repair tool under `agent_service_v2`). Do **not** unify FastAPI across services — but pin both in a single `docs/` "supported matrix" note.

### P1-6 — Artifact path contract relies on matching directory basenames
**Location:** `backend/app/services/catalog_material_service.py:55-58`; consumer `agent_service_v2/src/agent_service_v2/api/knowledge.py::_resolve_material_path`

```python
# catalog_material_service.py:55-58
root = Path(settings.COURSE_CATALOG_STORAGE_ROOT)
relative_path = Path(root.name) / catalog.id / material_id / filename   # -> "course_catalogs/<catalog>/<mat>/<file>"
```
The agent then has to guess that the first segment is the root name:
```python
# knowledge.py (_resolve_material_path)
parts = path.parts
if parts and parts[0] == storage_root.name:
    parts = parts[1:]
```
This works only because both services happen to configure roots ending in `course_catalogs` (`agent_service_v2/.../agents/model_provider.py:41` `COURSE_CATALOG_STORAGE_ROOT: str = "../backend/storage/course_catalogs"`; `deploy_prod.sh:263`). Rename either directory and every ingestion silently 400s with "must stay within course catalog storage root".
**Smallest fix.** Backend sends the path already relative to the root (drop `Path(root.name)`), and the agent deletes the basename heuristic. Two-line change, removes a whole failure class.

### P1-7 — `HTTPException(detail=<str>)` is reported to clients as `code: 50000`
**Location:** `backend/app/main.py:96-105`
```python
if isinstance(exc, FastAPIHTTPException):
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail: return JSONResponse(status_code=exc.status_code, content=detail)
    return JSONResponse(status_code=exc.status_code, content={"code": 50000, "message": str(exc.detail), "data": None})
```
Producers that raise bare strings: `app/api/v1/tutoring.py:55` (`detail="最后一条用户消息不存在"`), `app/api/v1/internal_personalized_resources.py:68,99` (`detail=exc.reason`), `app/api/v1/course_catalog_gate.py`-raised errors used by `resources/generate`.
**Impact.** A 400 client error carries `code=50000`, so any frontend/monitor keying on `code` treats user error as a server fault; `frontend/src/api/client.js:39` also shows a "服务器错误" toast for `status>=500` only, so behavior diverges between the two signals.
**Smallest fix.** Map by status family instead of constant: `{"code": 40000 + (status % 100) if status < 500 else 50000, ...}`, or replace the five bare-string raises with the dict form already used everywhere else.

### P1-8 — `test:e2e` silently skips half the E2E suite; backend test entry points are stale
- `frontend/package.json:12` `"test:e2e": "playwright test"` → default `playwright.config.js` with `testDir: './e2e'` (line 4), which contains only `e2e/specs.spec.js`. The other config `playwright.test.config.js:4` points at `./tests/e2e` (containing `chat-persistence.spec.js`) and is referenced by **nothing** (grep: no script, no CI file). So the chat-persistence E2E test never runs.
- `backend/run_backend_tests.sh` runs 2 files; `backend/test_runner.sh` runs 4 different files; `backend/README.md` documents `pytest tests -q` (69+ files). Two contradictory "how to test" scripts, neither matching the documented command, both with hardcoded `../.venv` relative paths.
- `backend/tests/test_deploy_prod.py:82-86` asserts exact substrings of `start_all.sh`, so any legitimate refactor of that script (e.g. P0-1's fix) breaks "tests" that are really grep assertions.
**Smallest fix.** Delete `playwright.test.config.js` and move its case into `e2e/`; delete both `*_test*.sh` and put the documented `pytest tests -q` in `backend/README.md` only.

### P1-9 — Test-integrity: a mocked symbol that the code under test never uses
**Location:** `backend/app/api/v1/evaluation.py:15-16`; `backend/tests/test_lock_async.py:162`; `backend/tests/test_refresh_async.py:276,336`
```python
# evaluation.py:15-16
# Keep legacy mock target valid
from app.services.agent_client import agent_client
```
Nothing in `evaluation.py` calls `agent_client` — the real call is `app/services/evaluation_service.py:285`. Tests patch `app.api.v1.evaluation.agent_client.post_json`, i.e. they assert on an object that no code path uses; the assertions pass for the wrong reason and would keep passing if `run_evaluation_refresh_background` were deleted.
**Smallest fix.** Retarget the three `patch(...)` targets to `app.services.evaluation_service.agent_client.post_json` and delete the import + comment in `evaluation.py`.

### P1-10 — Dev bootstrap is coupled to production preflight (npm/uv/Docker/Judge0 required to run the app)
`start_all.sh:120-124` runs `deploy_prod.sh check` (which requires `docker`, `curl`, `npm`, `python3`, `uv` — `deploy_prod.sh:75-91`) and auto-copies the *production* template with `DEBUG=false` (`deploy_prod.sh:55-61`); `start_all.sh:139` then runs `deploy_prod.sh prepare-infra`, which unconditionally provisions Judge0 (`deploy_prod.sh:236-241` → `ensure_judge0`), pulling two ~1 GB images and requiring `JUDGE0_POSTGRES_PASSWORD`/`JUDGE0_REDIS_PASSWORD` to be set for `start` to succeed.
**Impact.** A frontend contributor cannot start anything without a full Docker + Judge0 stack; and `DEBUG=false` by default means dev gets no SQL echo and production-like error hiding. This is the main reason the repo "feels" heavy.
**Smallest fix.** Give `start_all.sh` its own minimal preflight (`python3 -m venv`, `npm`, optional `docker`), gate `ensure_judge0` behind `./deploy_prod.sh prepare-infra --with-judge0` (sandbox returns `degraded` gracefully anyway — `api/v1/sandbox.py:38-50`), and ship `deploy/env.development.example` with `DEBUG=true`.

### P1-11 — Production template ships keys nothing reads, and one default that misleads
- `backend/app/core/config.py:41-43` defines `QDRANT_URL` / `QDRANT_COURSE_KNOWLEDGE_COLLECTION`, and `deploy_prod.sh:264` injects `QDRANT_URL` into the backend process — but `grep -r 'settings.QDRANT' backend/app` returns **no matches**. The only backend Qdrant access is the out-of-band tool (`backend/tools/repair_course_catalog_knowledge_status.py:39-43`), which reads `os.environ` itself. Dead config invites the belief that the backend queries Qdrant.
- `LLM_BASE_URL: str = "https://api.deepseek.com"` (`config.py:38`) while `kg_generation.py` appends `/chat/completions` and the template documents `https://your-llm-endpoint/v1` — the built-in default produces a `/chat/completions` URL without `/v1`.
**Smallest fix.** Delete the two `QDRANT_*` settings from `Backend.Settings` (and the injection in `deploy_prod.sh:264`), or move them to the tool's own argument parser; set the `LLM_BASE_URL` default to `https://api.deepseek.com/v1`.

---

## 4. P2 KISS Simplification Opportunities

### P2-1 — Dead duplicate service module in the frontend
`frontend/src/services/catalogService.js` (141 lines) re-implements `frontend/src/api/services/catalog.js` (52 lines) with identical endpoints. Importer grep: `services/catalogService` appears only in `frontend/src/services/catalogService.test.js`. All real consumers use `../api/services/catalog` (`hooks/useCatalog.js:3`, `components/admin/CatalogManagementPanel.jsx:2`). The duplicate test (`catalogService.test.js`, 150+ lines of `toHaveBeenCalledWith`) duplicates `src/api/services/__tests__/catalog.test.js`.
**Fix:** delete `frontend/src/services/` entirely (both files, ~300 LOC + 1 test file).
**Note for the audit brief itself:** the task named `frontend/src/services/` as a key file location; the live client lives in `frontend/src/api/services/`. The `.trellis/workflows/code_review.js:81,112` references have the same bug and should be corrected so future audits look in the right place.

### P2-2 — One-shot codemod/scratch scripts committed at frontend root
`frontend/fix_aichat.py`, `frontend/patch_aichat.py`, `frontend/update_icons.py`, `frontend/update_teacher_console.cjs`, `frontend/test_mermaid.cjs`, `frontend/test_mermaid2.cjs`, `frontend/test_regex.js`, `frontend/test_regex2.js`.
Evidence of rot: `update_icons.py:13,55` hardcode `'/home/yezisama/workspace/workflow/EDUagent/frontend/src'`; `update_teacher_console.cjs:1-3` and `fix_aichat.py:3` mutate `src/pages/*.jsx` by regex with no idempotency guard. Their side effects are already applied (the patterns they search for are long gone).
**Fix:** delete all eight. If icon generation is still needed, move it to `frontend/scripts/gen_icons.mjs` with a `package.json` entry.

### P2-3 — Committed agent-session state and ad-hoc reports
`frontend/.superpowers/brainstorm/*/state/server-info` (3 files) contain absolute paths and dead localhost ports; `.gitignore:76-77` only ignores `**/docs/superpowers/`, so this directory is not covered. Also `frontend/前端页面字段与布局结构数据报告.md` (one-off analysis, no owner, no date discipline).
**Fix:** add `frontend/.superpowers/` to `.gitignore` and `git rm -r --cached`; move the report under `docs/` or delete.

### P2-4 — Stale retirement markers: `agent_service/` is already gone
`.gitignore:83-84`:
```
# Retired v1 local data retained for manual archival
agent_service/knowledge_base/
```
`find` for `agent_service/**` returns **no files**, and grep for `agent_service/` (excluding `agent_service_v2/`) matches only `.gitignore:84` and the audit brief. So the retired v1 service is fully removed — excellent — but the ignore rule and comment now document a directory that does not exist and will never exist.
**Fix:** delete lines 83-84. (Also verify no local `agent_service/knowledge_base/` still holds un-archived data before deleting; `.gitignore` cannot tell us that.)

### P2-5 — Router/prefix inconsistency in the backend
Nineteen routers use `APIRouter(prefix="/api/v1/<domain>")`; `catalogs.py:39` alone uses `prefix="/api/v1"` plus fully-qualified sub-paths, which is why it owns `/admin/course-catalogs/*`, `/admin/resources/{id}` and the student-facing `/course-catalogs`. `admin.py` therefore owns only users/logs/registration-codes.
**Fix:** split `catalogs.py` into `admin_catalogs.py` (`prefix="/api/v1/admin"`) + `course_catalogs.py` (student route `GET /api/v1/course-catalogs`). Pure move, no behavior change; makes P1-1's doc regeneration mechanical.

### P2-6 — Agent exposes an SSE stream nobody consumes
`agent_service_v2/.../api/personalized_resources.py` builds `event_path: f"/agent/v2/personalized-resources/generations/{session_id}/events"` and implements the streaming handler; grep for `event_path` and `/events` in `backend/` and `frontend/src/` returns **no matches**. The frontend instead polls `processing_count` (`hooks/usePersonalizedResources.js:15`).
Additional fragility: the run registry lives in `team_runtime_app.state.message_bus`, which is `InMemoryMessageBus()` by default (`team_app.py:56`), while sessions live in Redis (`team/storage.py:6-13`) — so after a restart the event history is gone but sessions survive.
**Fix:** delete the `/events` route and `event_path` (and its test at `agent_service_v2/tests/test_resource_agent_team.py:95`), or wire the frontend to it and make the bus Redis-backed. Decide once; today it is half of each.

### P2-7 — Mock mode invents a refresh-token flow that does not exist
`frontend/src/api/mock/authMock.js:36-39` returns `token`, `access_token`, `refresh_token`, `expires_in: 1800`; the real endpoint returns `token` + `expires_in: 604800` + `user` (`backend/app/api/v1/auth.py:127-137`). `Login.jsx:56` reads `response.data.token`, so mock "works" while advertising an unimplemented contract.
**Fix:** make the mock return exactly the real shape (one object literal, 5 fields).

### P2-8 — `expires_in` hardcoded instead of derived from config
`auth.py:131` returns literal `604800` while `ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080` is configurable (`config.py:28`).
**Fix:** `"expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60` — prevents silent client-side expiry drift.

### P2-9 — Dead "legacy" import kept alive only by tests
Same site as P1-9 (`evaluation.py:15-16`). Once the tests are retargeted, the import and its `# Keep legacy mock target valid` comment must go, or the next reader will assume it matters.

### P2-10 — `backend/tests/conftest.py` hardcodes a developer machine path
`conftest.py:6`: `sys.path.insert(0, "/home/yezisama/workspace/workflow/EDUagent/.venv/lib/python3.12/site-packages")`. On any other machine this inserts a non-existent path (harmless) and the real venv resolution depends on how pytest was launched — but it also encodes a specific Python 3.12 layout. Combined with the manual `pytest_asyncio` plugin registration at `conftest.py:11-15` (because `pytest-asyncio` is not a declared dependency, P1-5), the suite is not portable.
**Fix:** delete lines 5-6; add `pytest` + `pytest-asyncio` + `asyncio_mode = auto` to a proper `backend/pytest.ini`, and delete the `pytest_configure` plugin hack.

### P2-11 — Packaging identity leftovers
`frontend/package.json:2-4`: `"name": "tmp-react-app"`, `"version": "0.0.0"`. `agent_service_v2/pyproject.toml:3-7`: `description = "Add your description here"`, and `[project.scripts] agent-service-v2 = "agent_service_v2:main"` maps to `__init__.py` which prints `"Hello from agent-service-v2!"` — a console entry point that starts no server (the real entry is `uvicorn agent_service_v2.main:app`, per `agent_service_v2/README.md`).
**Fix:** rename to `eduagent-frontend` / `eduagent-agent-service-v2`, drop the fake console script or point it at `uvicorn.run`.

### P2-12 — Unresolved-looking template tokens in committed files (verify, then decide)
Tokens of the form `{{EMAIL_…}}`, `{{PASSWORD_…}}`, `{{SECRET_…}}` appear in `README.md`, `deploy/ensure_default_admin.sh:7,67`, `backend/schema.sql:29-31`, `backend/scripts/README.md`, `backend/tests/conftest.py:30-32`, `agent_service_v2/pyproject.toml:7`, and `.git/logs/*`. In this review's output these are **redaction placeholders**, so treat them as redacted unless proven literal.
**Action (human, 10 s):** `grep -Rn '{{' backend deploy README.md agent_service_v2 | grep -v '\.venv'`. If any are literal, `ensure_default_admin.sh:7` and `schema.sql:31` agree with each other (so login still works) but the seeded admin email is unusable for password reset; fix by making the email a `DEFAULT_ADMIN_EMAIL` env var. If they are redaction artifacts, close the item.

### P2-13 — Documentation vs tooling contradiction on Qdrant ownership
`docs/00-overview/README.md` asserts "Backend 不直接访问 Qdrant", but `backend/tools/repair_course_catalog_knowledge_status.py:15,39-57` opens an `AsyncQdrantClient` directly and lives inside `backend/`. Either move the tool to `agent_service_v2/tools/` (it is Qdrant-payload surgery) or amend the doc to "runtime 服务不直接访问 Qdrant；离线修复工具除外".

---

## 5. Master Monorepo Refactoring Sequence

Ordered so that **each step is independently shippable, guarded by a test that fails before and passes after**, and no step depends on a later one. Steps 0-3 are safety net; 4-8 are the fixes; 9-11 are cleanup.

### Phase 0 — Safety net (no behavior change, ~1 PR)
1. **Add contract tests before touching contracts.**
   - `backend/tests/test_openapi_contract.py`: `set(app.openapi()["paths"]) == set(client_api_json)` — expected to **fail** (documents P1-1/P1-3).
   - `agent_service_v2/tests/test_openapi_contract.py`: same against `docs/20-agent-api` — expected to **fail** (P1-2).
   - `agent_service_v2/tests/test_dev_env_contract.py`: construct `AgentModelSettings` with the keys present in `deploy/env.production.example` and assert `build_backend_learning_client_from_settings(...)` is not `None` — expected to **fail** (P0-1).
   Run: `cd backend && ../.venv/bin/python -m pytest tests -q`; `cd agent_service_v2 && ./.venv/bin/pytest -q`.
2. **Fix test infra so the suite is meaningful:** add `pytest`, `pytest-asyncio`, `qdrant-client` (+ agent-side `httpx`, `qdrant-client`, `pytest-asyncio`) per P1-5; delete `conftest.py:5-6` and the plugin hack (P2-10); retarget the three `evaluation` patches (P1-9). *Gate: full backend suite green on a clean machine.*
3. **Collapse test entry points:** delete `backend/run_backend_tests.sh`, `backend/test_runner.sh`, `frontend/playwright.test.config.js`; move `tests/e2e/chat-persistence.spec.js` → `e2e/` so `npm run test:e2e` actually runs it (P1-8). *Gate: `npm run lint && npm run build && npm run test:e2e` and the two pytest commands pass.*

### Phase 1 — Security (ship first, small diffs)
4. **P0-2** fail-closed webhook + required-key preflight list; **P0-6** gate permanent registration codes behind config.
   *Rollback:* both are single-function changes (`deps.verify_webhook_secret`, `auth.PERMANENT_REGISTRATION_CODES`); revert independently.
   *Gate:* new tests `test_webhook_requires_secret_when_configured_prod` and `test_teacher_code_rejected_when_permanent_codes_disabled`.
5. **P0-3** replace query-token downloads with blob fetch in both MarkdownViewer files; delete `token` from `get_download_user`.
   *Gate:* `components/workspace/plugins/MarkdownViewer.test.jsx:26-29` updated to assert no `token=` in href; grep `[?&]token=` returns nothing.

### Phase 2 — Configuration & environment correctness
6. **P0-1** map `BACKEND_INTERNAL_AGENT_TOKEN` in `start_all.sh`; add agent startup warning. **P0-4** `strictPort: true` + 5173 port check + derived dev CORS. **P1-11** drop dead `QDRANT_*` settings, fix `LLM_BASE_URL` default.
   *Gate:* the Phase-0 dev-env contract test turns green; manual `./start_all.sh start` shows `Backend is ready` and AI-Chat exposes `read_learning_progress` in tool logs.
7. **P1-10** decouple dev bootstrap: minimal `start_all.sh` preflight, `--with-judge0` opt-in, `deploy/env.development.example` with `DEBUG=true`.
   *Gate:* `./start_all.sh setup && ./start_all.sh start` succeeds on a host **without** Docker; `/api/v1/sandbox/execute` returns `status="degraded"` (already implemented, `sandbox.py:38-50`).

### Phase 3 — Cross-service contract repair (highest risk, do after 1-2)
8. **P0-5** add `catalog_id` to the personalized-resource team payload (`personalized_resources.py:325-333`, `ai_chat_resource_service.py:185-194`) and use it for RAG in `team_app.py:33-38`; **P1-6** make `storage_uri` root-relative in `catalog_material_service.py:55-58` and delete the basename heuristic in `knowledge.py`.
   *Gate:* new test in `agent_service_v2/tests/` asserting `retrieve_course_context` is called with `catalog_id` from the request; new backend test asserting `storage_uri` has no leading `course_catalogs/`.
   *Rollback:* both are additive payload fields; consumers tolerate extra keys (`resource_team_leader.py:5-15`).
9. **P0-7** make ingestion asynchronous with webhook completion (or, if that is too large for the release, raise `ingestion_agent_client` timeout to 600 s and fix the doc's 202 semantics). **P1-7** status-family error codes in `main.py:96-105`.
   *Gate:* ingest a >10 MB PDF fixture end-to-end; task must end `completed` with `chunk_count>0`.

### Phase 4 — Contract documentation & de-duplication
10. **P1-1/P1-2/P1-3**: regenerate both OpenAPI files from the running apps, add `response_model` to the three DB-writing agent routes, create `docs/30-internal-api/`. Phase-0 contract tests flip to green and become the permanent regression net.
    **P1-4**: add `test_schema_pair_parity` tests for the 5 duplicated model pairs; delete the agent-side `webhook_url` send if the team request keeps ignoring it.
    **P2-5**: split `catalogs.py` into `admin_catalogs.py` + `course_catalogs.py` (do this *before* regenerating docs so the doc reflects the final prefix layout).

### Phase 5 — KISS cleanup (mechanical, one commit each)
11. Delete dead/duplicated assets with a single `git rm` batch and a `grep` proof per item: `frontend/src/services/` (**P2-1**, verify zero importers), the eight codemod scripts (**P2-2**), `frontend/.superpowers/` + `git rm -r --cached` (**P2-3**), `.gitignore:83-84` (**P2-4**), the `/events` route + `event_path` + its test (**P2-6**), mock auth shape (**P2-7**), `expires_in` from settings (**P2-8**), packaging identity (**P2-11**), doc contradiction or tool relocation (**P2-13**). Then the human check in **P2-12**.

### Sequencing rationale (why not reorder)
- Phase 0 **must** precede 4: without failing contract tests, "regenerate the docs" cannot be verified and will rot again within one feature branch.
- Phase 1 **must** precede 3: P0-2/P0-3/P0-6 are one-to-five-line diffs with zero interaction with contract work; shipping them later means shipping a known-open write primitive and token leak for the duration of a refactor.
- Phase 3 step 8 **must** precede step 9: asynchronizing ingestion changes the very response shape that step 9's doc work describes; doing docs first guarantees a second rewrite.
- Step 10 **must** follow P2-5: regenerating the Client API doc before splitting `catalogs.py` bakes in the `prefix="/api/v1"` oddity.
- Phase 5 is last and truly independent — every item there is deletion, verified by a `grep` that returns no live importer, so it can also be parallelized or dropped without affecting the release.

### Aggregate verdict
| Area | State |
|---|---|
| Port/topology coherence | Good — no action |
| Envelope & error shape | Mostly good; one exception (`main.py:96-105`) |
| Auth design | **Two P0s** (fail-open webhook, query-string JWT) + one privilege-escalation surface |
| Dev/prod parity | **One P0** (`BACKEND_INTERNAL_AGENT_TOKEN`) + heavy bootstrap coupling |
| Cross-service data contracts | **One P0** (`catalog_id` vs `course_id`), two undocumented surfaces, 5 duplicated schema pairs |
| Deployment scripts | Sound and well-guarded (env-file secrets, idempotent admin, placeholder check) but missing required-key validation and Judge0-optional mode |
| Repo hygiene | ~12 removable items, all with zero live importers; `agent_service/` already fully retired |

**Merge verdict for the *current* tree: OK with notes** — this is a review of committed baseline, not a diff; nothing here is a regression introduced by pending work. **Any release cut from this tree should first land P0-1…P0-7 (Phases 1-3)**, because P0-2 and P0-3 are unauthenticated-write and credential-leak classes, and P0-5 produces student-facing content that is silently ungrounded while appearing "approved".

---
### Supervisor action list (commands I did not run)
```bash
# contract/baseline
cd backend && ../.venv/bin/python -m pytest tests -q
cd ../agent_service_v2 && ./.venv/bin/pytest -q
cd ../frontend && npm run lint && npm run build && npm run test:e2e
# verification of the two absences this report relies on
grep -Rn 'event_path\|/events' backend frontend/src          # expect: no matches
grep -Rn "settings\.QDRANT" backend/app                       # expect: no matches
grep -Rn '{{' backend deploy README.md agent_service_v2 | grep -v '\.venv'   # P2-12 determination
```