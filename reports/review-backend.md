## Review

**Scope:** entire `backend/app/` (FastAPI + SQLAlchemy 2.0 async), 21 routers, 60 service modules, 8 model modules, exception/config/auth layer. Findings below are all traced to concrete code; no hypothetical goals.

**Note on workflow state:** this is a read-only audit; I did not create a Trellis task or write `progress.md` (no-edit/audit-only wins). Artifact returned inline below.

---

# Backend (FastAPI) Codebase Review Report

## 1. Executive Summary & Architecture Health

**Overall shape.** The layering is nominally correct — `api/v1 → services → models`, with `core/` (config, JWT, captcha), `db/` (engine + session dependency), `exceptions/` (DomainException + handler), `infrastructure/locks.py` (MySQL named locks). Recent refactors clearly moved real logic out of routers (`teaching_service.py`, `class_insights_query.py`, `student_report_query.py`, `tutoring_service.py`, `tutoring_stream_adapter.py`, `personalized_resource_generation_service.py` are all clean, testable, single-purpose units). Background-task lifecycle (AsyncTask + webhook + startup recovery) is a coherent design.

**Where it is unhealthy.**

1. **Introduce a two-tier standard that is only half-applied.** `services/` sometimes raises `DomainException` (2 classes), sometimes raw `HTTPException` (28 sites), sometimes bare `ValueError/RuntimeError` (`infrastructure/locks.py:50`, `*_query.py`, `code_problem_service.py`). The `DomainException` layer is effectively dead weight — nothing but `CatalogNotFoundError` and `LockAcquisitionTimeout` use it.
2. **Routers are inconsistent in thickness.** `learning_path.py` (28 lines) and `teaching.py` are textbook-thin; `quiz.py` (400 lines), `personalized_resources.py` (430 lines) and `courses.py` carry query building, aggregation, LLM-response persistence and N+1 loops inline.
3. **Authorization is opt-in and forgotten in three routers** (`learning_path`, `quiz/questions`, `tasks` for null-owner rows) — the single highest-risk theme in this codebase.
4. **Async discipline has real holes**: blocking file I/O in async handlers, `eval()` on LLM-derived data, per-request `httpx.AsyncClient` construction, per-request `select(User)` that fans out into `lazy="selectin"` relationship loads on *every* authenticated request.
5. **Whole-catalog maintenance operations are implemented as "delete everything that wasn't in this run"** (`catalog_quiz_generation_service.py:199-226`) — a partial failure silently destroys the baseline question bank.

**Health verdict:** functional and test-covered in the happy paths (≈90 test modules), but not safe to expose to untrusted multi-tenant traffic as-is. Fix the P0 set before any further feature work; the P1 set is a 2–3 day concentrated refactor, not a rewrite.

---

## 2. P0 Critical Issues (Bugs, data corruption risk, severe async blocking)

### P0-1 — Privilege escalation: teacher registration code is a hardcoded literal
`backend/app/api/v1/auth.py:19-22`
```python
PERMANENT_REGISTRATION_CODES = {
    "student": "student",
    "teacher": "teacher",
}
```
`auth.py:56-60` falls back to this dict whenever no `registration_codes` row matches, so `POST /api/v1/auth/register {"registration_code": "teacher"}` creates a **teacher account with zero admin involvement**. This is not incidental — it is asserted as intended behaviour in `backend/tests/test_auth_register_contract.py::test_register_accepts_builtin_teacher_code_without_db_seed`.

Compounding: `RegistrationCode.is_used` / `used_by` (`models/user.py:44-45`) are **never written anywhere** (grep: only the model declares them), so DB-issued codes are infinitely reusable — `test_auth_register_contract.py:96-107` explicitly asserts a code can be reused.

**Smallest fix:** delete `PERMANENT_REGISTRATION_CODES`; require a live, unused `RegistrationCode`; set `is_used=True, used_by=user.id` inside the same transaction as user creation; add a partial unique guard (or `SELECT ... FOR UPDATE` on the code row) to close the reuse race.

### P0-2 — `eval()` on Agent/LLM-derived quiz answer strings (RCE)
`backend/app/services/quiz_service.py:232-246`
```python
correct_sorted = sorted(eval(correct_answer)) if correct_answer.startswith("[") else ...
...
correct_for_agent = eval(correct_for_agent)
```
`QuizQuestion.correct_answer` is written from **untrusted model output** at `api/v1/quiz.py:200` (`correct_answer=str(q.get("answer", ""))` from `data["questions"]`) and `ai_chat_choice_quiz_service.py:75` (`json.dumps(draft.answer)`). Any prompt-injected generation that yields a `correct_answer` beginning with `[` reaches `eval()` on submit.

Secondary correctness bug in the same block: `sorted(str(user_answer))` sorts *characters* of a single-answer string, so `"AB"` vs `"BA"` compares equal — multi-choice grading is silently wrong.

**Smallest fix:** replace both `eval` calls with `json.loads` inside a `try/except json.JSONDecodeError`; for non-JSON, `[s.strip() for s in correct_answer.split(",") if s.strip()]`; normalize both sides through one `_split_multi(answer) -> list[str]` helper.

### P0-3 — IDOR: `GET /api/v1/quiz/questions` has no course authorization and mints sessions
`backend/app/api/v1/quiz.py:40-120`
```python
scope = await resolve_course_resource_scope(db, course_id)   # line 53 — pure lookup, no permission check
...
query = select(QuizQuestion).where(or_(...), QuizQuestion.is_deleted == False, ...)
```
`resolve_course_resource_scope` (`services/resource_scope.py:62-77`) resolves `catalog_id` and **never checks enrollment/ownership**. Contrast with the correctly-guarded siblings `node_resource_service.py:21`, `resource_service.py:33`, `learning_activity_service.py:86-110`, all of which call `ensure_course_resource_access`. Consequence: any authenticated student can enumerate any course's questions (content, options, answers are *not* returned — good — but the whole catalog question bank is exposed by `course_id`/`catalog_id` guessing), and each call inserts a `QuizSession` row (`quiz.py:114-120`) for the attacker, i.e. an unauthenticated-in-scope write amplification.

Same class in **`backend/app/api/v1/learning_path.py:12-24`** — `LearningPathService.get_learning_path(current_user.id, course_id)` performs zero access validation; a student can read the KG-derived node list (chapter + knowledge-point names) of an arbitrary course, and `backend/tests/test_learning_path_fallback.py:233-239` asserts this returns **200 for `course_id=nonexistent_course`**, cementing the bug as contract.

**Smallest fix:** in `quiz.get_questions` and `learning_path.get_learning_path`, call `await ensure_course_resource_access(db, current_user, course_id)` before the scope lookup, and return 404 for unknown courses (update the fallback test to expect 404 and use it only for existing-but-pathless courses).

### P0-4 — Startup recovery corrupts live tasks in any multi-worker deployment
`backend/app/main.py:25-63`
```python
result = await db.execute(
    sql_update(AsyncTask)
    .where(AsyncTask.status == "processing",
           AsyncTask.task_type.in_(_recoverable_task_types))     # no owner/worker scoping
    .values(status="failed", error_message="服务重启，后台任务丢失", ...)
)
```
`_recoverable_task_types` includes `resource_generation`, `quiz_generation`, `course_catalog_ingestion`, `code_problem_judging` — all of which are genuinely long-running. With `uvicorn --workers N`, worker 2 booting marks worker 1's in-flight tasks `failed`; the webhook then finds `task.status == "completed"`? No — it finds `failed` and, at `webhooks.py:203`, only short-circuits on `completed`, so it flips them back and inserts resources while the original job is still running → duplicate resources + confused client state.

**Smallest fix:** add `worker_id`/`heartbeat_at` to `async_tasks`, only reap rows whose heartbeat is older than N minutes, and make the reap conditional (`WHERE status='processing' AND heartbeat_at < :cutoff`). Minimal stopgap: gate the whole reap behind `settings.RECOVER_ORPHANED_TASKS` and document single-worker-only until heartbeats exist.

### P0-5 — Partial quiz-generation runs delete the surviving baseline question bank
`backend/app/services/catalog_quiz_generation_service.py:193-227`
```python
inserted_question_ids = [ ...only ids from children that returned completed... ]
if inserted_question_ids:
    await db.execute(
        update(QuizQuestion)
        .where(QuizQuestion.catalog_id == fanout_catalog_id,
               QuizQuestion.source == "baseline",
               QuizQuestion.is_deleted == False,
               ~QuizQuestion.id.in_(inserted_question_ids))
        .values(is_deleted=True))
```
If 3 of 40 KG nodes fail (`parent.status = "partial"` at line 228), every baseline question belonging to those 3 nodes is soft-deleted, and the "partial" parent still reports success to the admin. There is no restore path.

**Smallest fix:** compute the prune set only from *completed* child node_names/chapters (`DELETE ... WHERE knowledge_point IN (:completed_nodes)`), never from the complement of `inserted_question_ids`; and skip pruning entirely when `failed > 0`.

---

## 3. P1 High Tech-Debt & Spaghetti Code

### 3.1 N+1 queries and missing eager loading

| # | Location | Evidence | Impact | Smallest fix |
|---|---|---|---|---|
| 1 | `api/v1/courses.py:82-98` | Per course: `select(User)` (83), `count(CourseEnrollment)` (87), plus `_catalog_summary` → 2 more queries (25-47) | **4 queries × N courses**; 20-course page = 81 queries | One `select(Course, User, func.count(...)).join(User).outerjoin(CourseOffering).outerjoin(CourseEnrollment).group_by(...)`; or batch `CourseOffering`/`User` by `IN` and build dicts (the pattern already used in `personalized_resources.py:60-113` — copy it) |
| 2 | `models/user.py:34-35`, `models/course.py:29`, `models/catalog.py:34-35` | `lazy="selectin"` on `User.taught_courses`, `User.enrollments`, `Course.enrollments`, `CourseCatalog.materials`, `CourseCatalog.offerings` | `get_current_user` (`api/deps.py:40`) does `select(User)` on **every authenticated request** → +2 queries; `select(CourseCatalog)` anywhere → +2 full material/offering loads | Make relationships `lazy="raise"` (or `noload`) and opt in with `selectinload` only where needed. `teaching_service.py:24` is currently the *only* place using `noload` — that pattern should be the default |
| 3 | `services/node_resource_service.py:22-120` | `get_node_resources` issues 9+ sequential queries; `_resolve_catalog_context` (50-76) and `_resolve_active_kg` (78-100) **both** re-query `CourseOffering` + `CourseCatalog` for the same ids | 2× redundant round trips per node view, plus 4 more from `_weak_point_tutorials`/`_node_exercises`/`_full_exercise_count`/`_full_exercise_set` | Merge the two resolvers into one `_catalog_context()` returning `(catalog_id, host_course_id, active_kg)`; run the three question counts in one `UNION`-free aggregate query |
| 4 | `services/knowledge_progress.py:124-160` | `select(QuizQuestion)` — **whole entity** — just to build `{id: knowledge_point}` and counts; then `select(QuizSession)` all rows for the user | Full row payloads (incl. `content` TEXT, `options` JSON) for every question in the course, on every progress/evaluation/learning-path request; called 2× per evaluation refresh (`evaluation_service.py:98`, `:321`) | `select(QuizQuestion.id, QuizQuestion.knowledge_point)`; push `session_id.in_(...)`/count aggregation into SQL instead of Python loops |
| 5 | `api/v1/webhooks.py:118-140` | `select(AsyncTask).where(task_type=="resource_generation", is_deleted==False)` — **no parent filter, no limit** — then Python-filter `item.result.get("parent_task_id") == parent_id` | Full scan of the async_tasks table on **every** webhook callback, growing unbounded with history | `WHERE json_unquote(json_extract(result,'$.parent_task_id')) = :pid` (the codebase already uses this idiom at `catalog_kg_service.py:27`) or add an indexed `parent_task_id` column |
| 6 | `services/ai_chat_learning_context.py:108-112` | `get_learning_path()` *and* `build_node_progress_rows()` back-to-back; both resolve the effective KG and iteratively query answers | ~2× KG resolution + duplicate progress work per internal Agent call | Fetch `progress_rows` once and pass it into the path builder (it already accepts `progress_by_id` internally) |
| 7 | `services/ai_chat_choice_quiz_service.py:66-104` | `await db.flush()` inside the per-question loop | N round trips per quiz persist | Hoist a single `flush()` after the loop (ids are client-generatable via `gen_id`) |

### 3.2 Fat routers that should be services

- **`api/v1/quiz.py:251-380` (`get_result`)** — 130 lines of inline analytics: score trend, per-knowledge-point error aggregation, templated Chinese prose summaries, and Agent-diagnosis merge. This is a read model with zero HTTP concerns. Sibling refactors (`class_insights_query.py`, `student_report_query.py`) prove the right pattern; this one was skipped. → extract `services/quiz_diagnosis_query.py`.
- **`api/v1/personalized_resources.py:212-292`** — duplicates `quiz.py:151-220` (Agent call + `QuizQuestion` construction + `ChoiceQuestionDraft` validation) with a *different error contract* (500 vs 202-accepted-with-failed-task). Two implementations of one flow. → one `services/personalized_quiz_service.py`, one error contract.
- **`api/v1/personalized_resources.py:294-359`** — router builds the Agent payload dict inline for the resource path.
- **`api/v1/courses.py:22-104`** — see N+1 #1; the whole list endpoint plus `_catalog_summary` belongs in a `CourseQueryService`.

### 3.3 Blocking synchronous calls inside async handlers

| Location | Evidence | Fix |
|---|---|---|
| `services/catalog_material_service.py:56-80` | `with target_path.open("wb") as f:` + `f.write(chunk)` and `target_path.parent.mkdir()` inside an `async def` endpoint | `await file.read()` loop → `await anyio.to_thread.run_sync(_write, ...)` (or `aiofiles`) |
| `services/catalog_material_service.py:269` | `shutil.rmtree(..., ignore_errors=True)` called from async paths | `anyio.to_thread.run_sync` |
| `services/content_safety.py:22-27` | `WORDLIST_PATH.read_text()` on **every** `count_sensitive_matches` call; called per question in `persist_personal_choice_questions` and per profile update | `@lru_cache` on `_words()` (or load once at import into a frozenset) |
| `services/agent_client.py:48-60, 92-103, 118-155` | New `httpx.AsyncClient(...)` per request (incl. the 300s SSE stream) — no connection pooling, no keep-alive | Module-level client created in `lifespan`, closed on shutdown; keep `transport` injectable for tests |
| `services/kg_generation.py:100-110` | Direct `httpx.AsyncClient(timeout=90)` bypassing `AgentClient` entirely — contradicting `agent_client.py`'s own docstring ("路由层不要散落 httpx 调用") | Reuse `AgentClient` with a custom `base_url` |

### 3.4 Exception handling and error-contract inconsistency

1. **`main.py:92-104` swallows every unexpected exception without logging and rewrites the body shape.**
   ```python
   @app.exception_handler(Exception)
   async def global_exception_handler(request, exc):
       ...
       return JSONResponse(status_code=500, content={"code": 50000, "message": "服务端内部错误", "data": None})
   ```
   No `logger.exception(...)` anywhere ⇒ production 500s are invisible. Also, any `HTTPException` raised with a *string* detail (`quiz.py:68`, `tutoring.py:98`) is converted to `{"code": 50000, "message": "<string>"}` — a 400 response carrying error code `50000`, while the rest of the API uses 4xxxx codes.
2. **`DomainException` is a two-class fig leaf.** Only `CatalogNotFoundError` and `LockAcquisitionTimeout` use it (`grep`: 2 subclasses), while 28 sites raise `HTTPException` from inside `services/` (`resource_scope.py:19,26`, `teaching_service.py:32,37,62`, `learning_activity_service.py:77,95,103`, `catalog_*_service.py`, `quiz_service.py:314`, `resource_service.py:77,87,92`). Services now import FastAPI ⇒ untestable without an ASGI app and impossible to reuse from CLI tools (`backend/tools/*` import these modules).
3. **Three different error-code vocabularies for the same condition:** `course_catalog_gate.py:17-47` uses string codes (`"course_material_missing"`), while `catalog_resource_generation_service.py:26-44` and `catalog_quiz_generation_service.py:28-46` use numerics (`40913/40914/40915`) for identical semantics. Tests assert both (`test_resources_async.py:171` vs `test_admin_catalog_resource_generation.py:823`) — so the contract is now frozen in a contradictory state.
4. **Bare `except Exception: pass`,** `quiz_service.py:235` and `:245`, hides malformed `correct_answer` corruption instead of logging it.
5. **`evaluation_lock` (`infrastructure/locks.py:39-56`) is not a sibling of `profile_lock`:** no MD5 truncation (MySQL `GET_LOCK` caps at 64 chars; `f"evaluation_{user_id}_{course_id}"` is ~76 with 32-char ids ⇒ `ER_USER_LOCK_WRONG_NAME` risk) and raises `RuntimeError(...)` rather than `LockAcquisitionTimeout`, while `evaluation_service.py:349` then needs a fragile `"GET_LOCK timeout" in str(e)` string sniff for `error_code`. Also `profile_lock` has no SQLite branch, so profile endpoints cannot run on SQLite at all (every test monkeypatches it — `tests/test_profile_service.py:56`).

### 3.5 Transaction and session semantics

- **`db/session.py:9-20` auto-commits every request**, while routers *also* commit/rollback manually: `profile.py:50,53,77,80,93,96,124`, `tutoring.py:99,107,203,205`, `personalized_resources.py:291,359,421`, `internal_ai_chat.py:60,200,233,258`, `internal_personalized_resources.py:65`. Two competing commit owners means a handler's `except: await db.rollback(); raise` is followed by the dependency's `await session.commit()` on a *fresh* transaction that may still hold post-rollback flushed state. Make ownership explicit: either `get_db` only `close()`s (routers/services own commit), or nothing else commits.
- **`tutoring.py:118-128`** depends on `db.in_transaction()` + a manual rollback inside a `finally` to avoid committing while an SSE stream runs — a symptom of the above, not a fix.
- **Extremely long-lived transactions:** `catalog_resource_generation_service.py:348-369` awaits the Agent HTTP call (`timeout=60s`, `AgentClient.__init__`) **inside a loop over every selected KG node**, then commits at 369. N=20 nodes × up to 60s = a 20-minute request holding an open MySQL transaction and one pooled connection. Same shape at `:210-230` and `catalog_ingestion_service.py:157` (`ingestion_agent_client` timeout is **300s**). → persist task rows and commit first, then fan out; or move fanout into a background task (the `asyncio.create_task(run_quiz_generation_background...)` pattern already exists in the same file family).
- **Duplicate webhook deliveries race** (`webhooks.py:183-196` — the `AsyncTask` SELECT has no `.with_for_update()`, unlike the parent recompute at `:116`): two concurrent identical `completed` callbacks both pass the `status == "completed"` idempotency gate and both insert resources.

### 3.6 Other P1 correctness/robustness

- **`learning_path` returns 200 for nonexistent courses** (`learning_path.py:12-24`, asserted at `test_learning_path_fallback.py:233-239`) — a 404 contract gap that also masks the P0-3 auth hole.
- **`tasks.py:31-41`**: `if task.user_id and task.user_id != current_user.id:` — tasks with `user_id IS NULL` (all catalog/admin tasks) are readable **by any authenticated user**, including `result` payloads (`fanout_course_ids`, `target_nodes`, error internals).
- **`quiz.py:66-70`**: when `question_ids` is supplied the `limit` is skipped entirely, so up to 100 questions bypass the intended `le=50` cap on the default path.
- **`quiz.py:114-120`**: a `QuizSession` row is created on every read of `/questions`, including for zero-result queries; combined with `_validate_submission_shape`'s early return at `total_count <= 0` (`quiz_service.py:194-196`), empty sessions become submittable with arbitrary answers.
- **Fire-and-forget `asyncio.create_task` with no strong reference and no persistence of the coroutine identity:** `catalogs.py:246`, `catalogs.py:326`, `profile.py:131`, `evaluation_service.py:266`, `code_problem_submission_service.py:104`, `quiz.py:236`. For `run_diagnosis_background` (`quiz_service.py:108`) there is *no* `AsyncTask` row at all, so startup recovery (`main.py:25-63`) cannot detect it — a restart silently drops LLM diagnoses with no user-visible signal. Keep references in a module-level set and/or persist a task row.
- **`init_db()` (`db/session.py:28-29`) runs `Base.metadata.create_all` on every boot** while the real schema lives in `backend/schema.sql` + 13 hand-written `backend/migrations/*.sql` files that are never applied by code or by `lifespan`. On an existing DB, `create_all` silently skips tables ⇒ model/migration divergence is undetectable except in production. Either adopt Alembic or make `create_all` dev-only behind `settings.DEBUG`.
- **`courses.py:19-21`** identifies system KG-host courses by string-matching the description literally written at `catalog_kg_service.py:117`: `Course.description.like("System host course for catalog % knowledge graphs")`. One copy-edit to that sentence leaks host courses into every teacher/student course list **and** into `/courses/join`. Use a dedicated `is_system`/`origin` column.
- **`create_course` (`courses.py:139-163`) writes the same id into `courses` and `course_offerings`** — a de-facto 1:1 join table encoded as duplicated ids, with no FK from `courses.id → course_offerings.id`. This dual identity is the root cause of the five copy-pasted "offering → catalog → host course → KG" chains (see P2-2).
- **Config defaults are production-hostile:** `DEBUG=True` (`config.py:7`) which feeds `create_async_engine(echo=...)` (`db/session.py:6`) ⇒ full SQL echo unless overridden; `DB_PASSWORD="123456"` (`config.py:13`); `JWT_SECRET_KEY="duagent-jwt-secret-change-in-production"` (`config.py:24`) ⇒ forgeable tokens on any deployment missing `.env`. Add a `model_validator` that refuses to boot when `not DEBUG` and any of these are still at default.
- **In-memory captcha store** (`core/security.py:14-15,46-67`) is per-process: with `--workers N` (or behind multiple containers) `POST /auth/login` and `/auth/register` fail ~50%+ of the time with `40002 验证码错误或过期`. It also grows unboundedly (expired entries are only removed when that exact token is verified). Move to Redis, or at minimum add a size cap + periodic sweep and document single-worker-only.

### 3.7 Test infrastructure debt

- **`tests/conftest.py:6`** hardcodes `sys.path.insert(0, "/home/yezisama/workspace/workflow/EDUagent/.venv/lib/python3.12/site-packages")` — tests are not portable off one machine.
- **`tests/conftest.py:34`** defaults every module to a live MySQL DSN (`mysql+aiomysql://root:...@127.0.0.1:3306/duagent_test`) with a checked-in password; only 5 modules get SQLite. So `pytest tests -q` cannot run in CI without a MySQL service.
- **`tests/conftest.py:59-75`** rebinds `async_session_factory`/`engine` by reflecting over every loaded module's attributes — order-dependent global mutation; a module imported after the fixture runs silently keeps the old factory.
- **`tests/test_refresh_async.py:90-99`** defines `chk()` that calls `assert` inside a printer, and `test_quiz_async.py` / `simulate_real_study.py` follow the same pattern: these are smoke scripts wearing pytest's clothes (`if __name__ == "__main__"` at `test_refresh_async.py:395`). They assert sequential side effects across a 400-line `test()` function — one early failure hides everything after it.
- **Coverage runner scripts cover 6 of ~90 modules**: `run_backend_tests.sh` (2 files), `test_runner.sh` (4 files).

---

## 4. P2 KISS Simplification Opportunities

**P2-1 Dead modules / symbols**
- `app/schemas/common.py` — all six models (`ResponseBase`, `PaginatedData`, `CaptchaResponse`, `TokenResponse`, `RefreshResponse`, `TaskIdResponse`) are imported by nothing (`grep` across `backend/` returns only the definitions). `TokenResponse` even describes a refresh-token flow (`access_token`/`refresh_token`) that no longer exists (v1 single-token per `core/security.py:27`). Delete the file.
- `app/exceptions/__init__.py` — contains only `# exceptions package`.
- `catalogs.py:3-4` — `HTTPException`, `status`, `CourseCatalog`, `select` imported but unused in that module; `catalogs.py:49-50` `_async_task_catalog_id_expr()` is a byte-for-byte duplicate of `catalog_kg_service.py:27` and is **never called**.
- `agent_client.py:13` — `from fastapi import HTTPException, status` unused.
- `evaluation_service.py:7` — `text` imported, unused.
- `quiz.py:7,11` — `update`, `async_session_factory` imported, unused.
- `quiz_service.py:1` — `asyncio` imported, unused.
- `evaluation.py:11-12,14` — `agent_client` import and `logger` exist only to keep a mock path alive ("Keep legacy mock target valid"); after `test_evaluation_routes_refactored.py` is updated, drop both.

**P2-2 Duplicated logic that should be one function**
- `now_utc()` defined 4×: `catalog_kg_service.py:23`, `catalog_ingestion_service.py:21`, `catalog_quiz_generation_service.py:24`, `catalog_resource_generation_service.py:18` → `app/core/time.py`.
- `_webhook_url()` defined 3×: `catalogs.py:44`, `personalized_resources.py:25`, `resources.py:87` (identical bodies) → one helper in `app/api/deps.py`.
- **"offering → catalog → host course → active KG"** resolved independently in 5 places with 5 subtle variations: `quiz.py:85-100`, `evaluation_service.py:138-155`, `learning_path_service.py:107-135`, `node_resource_service.py:50-100`, `learning_activity_service.py:47-62` — plus `course_knowledge_graphs.get_effective_knowledge_graph` which *already implements exactly this* (`course_knowledge_graphs.py:32-54`) and is only used by `knowledge_progress.py:100` / `ai_chat_learning_context.py:47`. Standardize on `get_effective_knowledge_graph` and delete the four hand-rolled copies.
- `_resolve_catalog_id` (`ai_chat_choice_quiz_service.py:132-142`) duplicates the first half of `resolve_course_resource_scope` (`resource_scope.py:62-77`).
- Pagination boilerplate `select(func.count()).select_from(query.subquery())` repeated at `admin.py:33,157,208`, `personalized_resources.py:47,116`, `quiz.py:390`, `resource_service.py:58`, `tutoring_service.py:302`, `catalog_resource_generation_service.py:79`, `catalog_service.py:28` → `paginate(db, query, page, page_size)` returning `(rows, total)`.
- Conflict/dependency gate checks triplicated with divergent codes: `catalog_resource_generation_service.py:84-92`, `catalog_quiz_generation_service.py:80-88`, `course_catalog_gate.py:51-88`.

**P2-3 Redundant abstractions**
- `DomainException` + `exceptions/base.py` + `handlers.py` (10 lines) + `catalog_exceptions.py` (1 class) = 4 files for 2 exception types. Either finish the migration (make every service raise `DomainException`) or delete the package and keep FastAPI exceptions. Half-migrated is the worst option — it is why `services/` imports `fastapi` today.
- `core/security.py` captcha generation is a domain feature (arithmetic challenge) living in the crypto module; `generate_captcha` returns a presentation-shaped dict. Belongs in `services/captcha_service.py` with a store abstraction (memory now, Redis later) — that also makes the P1-3.6 multi-worker issue a one-line swap.
- `api/deps.py:44-73` `get_download_user` is `get_current_user` with a query-param fallback: 30 duplicated lines, two copies of the same 401 payloads. Extract `_authenticate(token) -> User` and let both wrappers call it.

**P2-4 Small correctness/hygiene wins**
- `models/others.py` `CourseKnowledgeGraph.nodes` / `edges` are typed `Mapped[dict]` but every writer passes a `list` (`kg_generation.py:245`, `course_knowledge_graphs.py:88`). Type as `Mapped[list[dict]]` (JSON column, no migration needed).
- `Auth` `RegistrationCode.is_used` dead columns → see P0-1.
- `oj_execution_service.py:78` uses `{"base64_encoded": "false", "wait": "true"}` for the single-shot path but base64 for the batch path — two encodings for one external service; unify on base64 to stop the `_decode_judge0_text` line-break workaround from being needed on one path and not the other.
- `profile.py:41-56, 68-81, 84-97` — three identical `try/commit/except rollback/raise` blocks that only exist because `get_db` also commits. Deleting them is the easiest KISS win (see P1-3.5).

---

## 5. Actionable Backend Refactoring Roadmap

**Sequencing rule:** stop the bleeding (authorization, RCE, data loss) before touching structure; do the structural work behind the existing test suite; then pay down perf and duplication. Each phase is independently shippable.

### Phase 0 — Emergency hardening (½–1 day, no structural change)
1. **Delete `PERMANENT_REGISTRATION_CODES`** (`auth.py:19-22`); enforce single-use registration codes (`is_used`/`used_by` written in the user-creation transaction) — update `test_auth_register_contract.py`. *(P0-1)*
2. **Replace both `eval()` calls** with `json.loads`/`split(",")` and add a `_split_multi()` helper (`quiz_service.py:232-246` + unit test with `"AB"` vs `"BA"`). *(P0-2)*
3. **Add `ensure_course_resource_access` to `quiz.get_questions` and `learning_path.get_learning_path`**; return 404 for unknown courses; update `test_learning_path_fallback.py:233-239` to assert 404. *(P0-3)*
4. **Disable `_recover_orphaned_background_tasks` unless explicitly enabled**, and add the flag to `Settings`. *(P0-4)*
5. **Restrict quiz-bank pruning** to completed nodes (`catalog_quiz_generation_service.py:199-226`). *(P0-5)*
6. **Add `logger.exception` to `global_exception_handler`** (`main.py:93-104`) and normalize string-detail `HTTPException`s into the `{code,message,data}` envelope.
7. Boot-time guard in `Settings`: refuse to start when `not DEBUG` and `JWT_SECRET_KEY`/`DB_PASSWORD` are at defaults (`config.py:13,24,7`).

### Phase 1 — Consistency pass (1–2 days)
8. **Pick one error strategy.** Recommended: `DomainException` for domain rules (raise from services), `HTTPException` only in `api/deps.py` for auth/transport. Convert the 28 service-layer `HTTPException` sites; extend `domain_exception_handler`. This is mechanical and is the prerequisite for Phase 2 cleanups.
9. **Resolve the `40913/40914/40915` vs `"course_material_missing"` split** (`course_catalog_gate.py` vs `catalog_resource_*_service.py`): pick numeric codes, update both test files, delete `course_catalog_gate.py`'s duplicates.
10. **Fix `evaluation_lock`** to mirror `profile_lock`: MD5-truncate the key, raise `LockAcquisitionTimeout`, add a SQLite branch; delete the `"GET_LOCK timeout" in str(e)` sniff in `evaluation_service.py:349`.
11. **Make transaction ownership explicit**: either drop the implicit commit from `get_db` and add an explicit commit to the few read-only endpoints that need it, or remove all 30+ manual commits. Do not leave both.
12. **Add `worker_id`/`heartbeat_at`** to `async_tasks` and re-enable startup recovery conditionally; move the 6 `asyncio.create_task` sites onto a single `BackgroundRunner` helper that keeps strong references and, where appropriate, creates an `AsyncTask` row (covers the silent `run_diagnosis_background` loss).

### Phase 2 — Performance and blocking-call elimination (2–3 days)
13. **Kill the N+1 in `courses.list_courses`** (`courses.py:82-98`) with the batch-`IN` pattern already used in `personalized_resources.py:60-113`.
14. **Flip the `lazy="selectin"` defaults** (`user.py:34-35`, `course.py:29`, `catalog.py:34-35`) to `noload`/`raise`, then add explicit `selectinload` in the 3 places that actually need them (`teaching_service._require_enrolled_student`, `catalog_kg_service.get_or_create_catalog_kg_host_course`, `tutoring_payload_builder`). Expect immediate wins on `get_current_user` (3 queries → 1) and every catalog listing.
15. **Consolidate the offering→catalog→KG chain onto `get_effective_knowledge_graph`** and delete the 4 duplicate resolvers; while in there, add the missing `selectin`/column projection to `build_node_progress_rows` (`knowledge_progress.py:124-160`).
16. **Move blocking I/O off the event loop**: file writes + `rmtree` in `catalog_material_service.py:56-80,269`; memoize `content_safety._words()`.
17. **Share one `httpx.AsyncClient`** across `AgentClient`/`oj_execution_service` (create in `lifespan`, close on shutdown); route `kg_generation.py:100-110` through `AgentClient`.
18. **Shorten transactions**: commit the `AsyncTask`/parent rows before fanning out to the Agent (`catalog_resource_generation_service.py:348-369`, `:210-230`, `catalog_ingestion_service.py:157`); move the fanout into a background task.
19. **Add `with_for_update()` to the webhook idempotency read** (`webhooks.py:183-196`) and add an indexed `parent_task_id` (`webhooks.py:118-140`).
20. **Move the captcha store to Redis** (or single-worker guard + LRU/sweep) and document the `--workers` constraint in `deploy/`.

### Phase 3 — Router slimming and deduplication (2–3 days)
21. Extract `services/quiz_diagnosis_query.py` from `quiz.py:251-380`; extract `services/personalized_quiz_service.py` and make `quiz.generate` + `personalized_resources.generate` call it (unifying the 202-with-failed-task contract).
22. Extract `CourseQueryService` from `courses.py:22-104`; replace the description-string host-course filter with a real `is_system` column (`courses.py:19-21` + `catalog_kg_service.py:117`) and a data backfill migration.
23. Delete dead code in one sweep: `schemas/common.py`, `catalogs.py` unused imports + `_async_task_catalog_id_expr`, `agent_client.py:13`, `evaluation.py:11-14` mock anchor, `quiz.py`/`quiz_service.py`/`evaluation_service.py` unused imports.
24. Add shared helpers: `now_utc()`, `webhook_url(request)`, `paginate(db, query, page, size)`, `_authenticate(token)` — and fold `get_download_user` into it (`deps.py:44-73`).

### Phase 4 — Test and deployment hygiene (1–2 days, continuous)
25. De-hardcode `tests/conftest.py:6` (drop the absolute `.venv` path), make SQLite the default (`conftest.py:32-36`), and require an explicit `TEST_DATABASE_URL` for MySQL-only modules. Keep `test_quiz_async.py`/`test_refresh_async.py` as `tools/` smoke scripts, not pytest modules.
26. Replace `chk()`-style aggregate tests with discrete `async def test_*` functions so failures are attributable.
27. Widen `run_backend_tests.sh`/`test_runner.sh` to the full `tests/` tree, and add a CI job that runs it against SQLite plus one MySQL matrix entry.
28. Add a regression test per Phase 0 item (IDOR 403/404, `eval` payload, partial-quiz prune, single-use registration code, startup reap). These are the only items in this report that can regress invisibly today.

**Verification the supervisor must run** (I cannot execute shell commands): from `backend/`, `../.venv/bin/python -m pytest tests -q` — note it needs live MySQL for all modules except the 5 SQLite-mapped ones in `tests/conftest.py:23-29`; the focused suites `tests/test_learning_path_fallback.py tests/test_auth_register_contract.py tests/test_quiz_submission_validation.py tests/test_course_catalog_ingestion.py` cover the Phase 0 items most directly.

---

**Merge verdict: BLOCK** — five P0 items (privilege escalation via hardcoded teacher code, `eval()` on LLM-derived answers, two authorization holes, multi-worker task corruption, destructive quiz-bank prune) must land before this backend is exposed beyond a single trusted user. The P1 inventory is concentrated around three repeatable patterns (missing `ensure_course_resource_access`, `lazy="selectin"` defaults, duplicated offering→catalog→KG resolution) that a 2–3 day focused pass can retire without architectural change; the layering itself is sound and does not need a rewrite.