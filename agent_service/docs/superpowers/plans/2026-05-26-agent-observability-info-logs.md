# Agent Observability Info Logs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add INFO-level success-path observability for LLM enrichment and RAG retrieval so integration debugging can distinguish LLM/RAG hits from fallback behavior.

**Architecture:** Keep all behavior unchanged and add one-line `logger.info(...)` calls at existing agent success paths. Existing WARNING logs for failures and fallback remain unchanged. API schemas, OpenAPI contracts, return payloads, prompts, and provider construction do not change.

**Tech Stack:** Python logging, existing FastAPI agent modules, pytest.

---

## Scope

This plan intentionally allows more than 5 files because the user explicitly approved a cross-cutting observability pass.

### Modify

- `agents/assessment.py`
- `agents/profile.py`
- `agents/evaluation.py`
- `agents/learning_path.py`
- `agents/memory.py`
- `agents/resources.py`
- `agents/tutoring_tools.py`
- `agents/tutoring.py`
- `agents/tutoring_react_flow.py` if ReAct success/fallback path logging is clearer there after inspection
- `WORKFLOW.md`

### Do Not Modify

- `schemas/`
- `api/`
- `prompts/`
- `../docs/`
- OpenAPI specs

---

## Logging Contract

Use stable, grep-friendly messages:

```python
logger.info("LLM enrichment succeeded: %s", endpoint)
logger.info("LLM generation succeeded: %s", endpoint)
logger.info("RAG retrieved %d chunks for course_id=%s", chunk_count, course_id)
logger.info("User memory RAG retrieved %d facts for user_id=%s", fact_count, user_id)
logger.info("Tutoring ReAct succeeded")
logger.info("Tutoring structured output succeeded")
```

Guidelines:

- Do not log user answers, prompts, facts, resource content, or full chunks.
- IDs such as `course_id` and `user_id` are acceptable because current code already uses them as routing keys; avoid logging free-form user content.
- Keep existing WARNING logs for exceptions/fallbacks.
- Add no new tests unless an existing test becomes brittle.

---

## Task 1: Add LLM Success Logs For Enrichment Endpoints

**Files:**

- Modify: `agents/assessment.py`
- Modify: `agents/profile.py`
- Modify: `agents/evaluation.py`
- Modify: `agents/learning_path.py`
- Modify: `agents/memory.py`

- [ ] **Step 1: Inspect existing logger names and success return points**

Run:

```bash
rg "logger =|return enriched|return result|with_llm|succeeded|warning" agents/assessment.py agents/profile.py agents/evaluation.py agents/learning_path.py agents/memory.py
```

Expected: identify the exact post-parse / post-enrichment success return point in each LLM helper.

- [ ] **Step 2: Add INFO logs only after successful coercion/enrichment**

Add logs at these logical points:

```python
logger.info("LLM enrichment succeeded: %s", "assessment/evaluate")
logger.info("LLM enrichment succeeded: %s", "profile/generate")
logger.info("LLM enrichment succeeded: %s", "evaluation/generate")
logger.info("LLM generation succeeded: %s", "learning-path/generate")
logger.info("LLM generation succeeded: %s", "memory/compress")
```

Place the log immediately before returning the LLM-produced/enriched result, not before parsing, so invalid JSON and coercion failures do not log success.

- [ ] **Step 3: Run focused tests**

Run:

```bash
./.venv/bin/pytest tests/test_assessment_agent.py tests/test_profile_agent.py tests/test_evaluation_agent.py tests/test_learning_path_agent.py tests/test_memory_agent.py -q
```

Expected: all selected tests pass.

---

## Task 2: Add RAG Retrieval Count Logs

**Files:**

- Modify: `agents/assessment.py`
- Modify: `agents/resources.py`
- Modify: `agents/tutoring_tools.py`

- [ ] **Step 1: Inspect RAG helper return shapes**

Run:

```bash
rg "_build_.*knowledge_context|search_course_knowledge|search_user_memory|retrieve_course_knowledge|retrieve_user_memory" agents/assessment.py agents/resources.py agents/tutoring_tools.py
```

Expected: identify where retrieved chunks/facts are still available as a list before being formatted into prompt/tool text.

- [ ] **Step 2: Log course RAG chunk counts**

Add logs after successful retrieval and before formatting:

```python
logger.info("RAG retrieved %d chunks for course_id=%s", len(results), course_id)
```

Apply to:

- `assessment/generate-questions` course knowledge context
- `resources/generate` course knowledge context
- `tutoring/chat` `retrieve_course_knowledge` tool

If a helper returns early because embedding/vector store is unavailable, do not add INFO success logs. Existing fallback behavior remains unchanged.

- [ ] **Step 3: Log user memory RAG fact counts**

In `retrieve_user_memory`, after successful `search_user_memory(...)`, add:

```python
logger.info("User memory RAG retrieved %d facts for user_id=%s", len(results), user_id)
```

Do not log fact text.

- [ ] **Step 4: Run focused RAG tests**

Run:

```bash
./.venv/bin/pytest tests/test_assessment_agent.py tests/test_resources_agent.py tests/test_tutoring_tools.py -q
```

Expected: all selected tests pass.

---

## Task 3: Add Tutoring Path Hit Logs

**Files:**

- Modify: `agents/tutoring.py`
- Modify: `agents/tutoring_react_flow.py` if the ReAct path success is only visible there

- [ ] **Step 1: Inspect tutoring fallback chain**

Run:

```bash
rg "structured|parse_tutoring|ReAct|react|fallback|rule" agents/tutoring.py agents/tutoring_react_flow.py agents/tutoring_react.py
```

Expected: locate these points:

- structured output success
- text JSON parse success
- ReAct response success

- [ ] **Step 2: Add success-path INFO logs**

Use these messages where appropriate:

```python
logger.info("Tutoring structured output succeeded")
logger.info("Tutoring text JSON parse succeeded")
logger.info("Tutoring ReAct succeeded")
```

Only log after a valid `TutoringModelResponse` / ReAct response exists.

- [ ] **Step 3: Run tutoring tests**

Run:

```bash
./.venv/bin/pytest tests/test_tutoring_agent.py tests/test_tutoring_react_flow.py tests/test_tutoring_tools.py -q
```

Expected: all selected tests pass.

---

## Task 4: Update Workflow And Verify

**Files:**

- Modify: `WORKFLOW.md`

- [ ] **Step 1: Update current state**

Add a concise bullet under current confirmed capabilities:

```markdown
- INFO 级路径命中日志已补齐：LLM enrichment/generation 成功、RAG 检索 chunk/fact 数、tutoring structured/ReAct 命中均可通过日志判断；WARNING fallback/异常日志保持不变。
```

Update recent verification from `228 passed` to the latest result after running the full suite.

- [ ] **Step 2: Run full tests**

Run:

```bash
./.venv/bin/pytest -q
```

Expected: `234 passed` or higher, depending on any already-merged tests.

- [ ] **Step 3: Commit**

Run:

```bash
git add agents/assessment.py agents/profile.py agents/evaluation.py agents/learning_path.py agents/memory.py agents/resources.py agents/tutoring_tools.py agents/tutoring.py agents/tutoring_react_flow.py WORKFLOW.md
git commit -m "chore(agent): add info logs for LLM and RAG path hits"
```

If `agents/tutoring_react_flow.py` was not modified, omit it from `git add`.

---

## Acceptance Criteria

- LLM success paths emit INFO logs after successful parsing/coercion/enrichment.
- RAG retrieval paths emit INFO logs with count and routing ID only.
- Existing WARNING logs for fallback and exceptions remain.
- No API/schema/OpenAPI changes.
- No prompt changes.
- Full test suite passes.
- `WORKFLOW.md` records the observability improvement and latest verification result.
