# AIChat AgentScope Runtime Safety Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade AIChat AgentScope v2 runtime so it consumes Backend conversation context, stores lightweight run state in workspace, and emits post-reply content-safety review events.

**Architecture:** Keep a single AgentScope `Agent` as the reasoning/acting engine. Backend remains the authority for conversation persistence; Agent Service v2 converts Backend context into AgentScope messages and emits stable EDU SSE events. Content review runs after the complete assistant reply through middleware-like runtime logic and only classifies content safety, not knowledge correctness.

**Tech Stack:** Python 3.12, AgentScope 2.0.3, FastAPI SSE, pytest, React/Vitest, existing MySQL-backed Backend persistence.

---

### Task 1: AgentScope Input Context

**Files:**
- Create: `agent_service_v2/src/agent_service_v2/session/workbench_input.py`
- Modify: `agent_service_v2/src/agent_service_v2/session/workbench_session.py`
- Test: `agent_service_v2/tests/test_workbench_input.py`
- Test: `agent_service_v2/tests/test_workbench_session.py`

- [ ] **Step 1: Write failing tests**

Create tests proving Backend `recent_messages`, summary, profile, and KG context become AgentScope messages, current user message remains last, and empty assistant placeholders are filtered.

- [ ] **Step 2: Run RED tests**

Run: `cd agent_service_v2 && ./.venv/bin/pytest tests/test_workbench_input.py tests/test_workbench_session.py::test_workbench_session_passes_context_messages_to_agent -q`

Expected: fail because `workbench_input.py` does not exist and session still passes one `Msg`.

- [ ] **Step 3: Implement minimal input builder**

Create `build_workbench_agent_input(message: str, context: dict) -> list[Msg]` using `UserMsg` and `AssistantMsg`. Include a dynamic context `UserMsg` only when summary/profile/KG data exists.

- [ ] **Step 4: Wire session to input builder**

Pass `agent.reply_stream(agent_inputs)` instead of a single current message.

- [ ] **Step 5: Run GREEN tests**

Run the same tests and confirm pass.

### Task 2: Workspace Run Store

**Files:**
- Create: `agent_service_v2/src/agent_service_v2/workspaces/run_store.py`
- Modify: `agent_service_v2/src/agent_service_v2/session/workbench_session.py`
- Test: `agent_service_v2/tests/test_workbench_run_store.py`

- [ ] **Step 1: Write failing tests**

Test that a run store writes `state.json` and append-only `events.jsonl` under the conversation workspace without escaping root.

- [ ] **Step 2: Run RED tests**

Run: `cd agent_service_v2 && ./.venv/bin/pytest tests/test_workbench_run_store.py -q`

Expected: fail because store does not exist.

- [ ] **Step 3: Implement run store**

Implement `WorkbenchRunStore` with `write_state(run_id, payload)`, `append_event(run_id, payload)`, and `write_review(run_id, payload)`.

- [ ] **Step 4: Wire lightweight state writes**

In session start, write run state; while adapting EDU events, append event dicts.

- [ ] **Step 5: Run GREEN tests**

Run run-store and session tests.

### Task 3: Content Safety Review Runtime

**Files:**
- Create: `agent_service_v2/src/agent_service_v2/safety/__init__.py`
- Create: `agent_service_v2/src/agent_service_v2/safety/schemas.py`
- Create: `agent_service_v2/src/agent_service_v2/safety/content_review_client.py`
- Create: `agent_service_v2/src/agent_service_v2/safety/content_review_middleware.py`
- Modify: `agent_service_v2/src/agent_service_v2/session/workbench_session.py`
- Modify: `agent_service_v2/src/agent_service_v2/runtime/edu_events.py`
- Test: `agent_service_v2/tests/test_content_review_middleware.py`
- Test: `agent_service_v2/tests/test_workbench_session.py`

- [ ] **Step 1: Write failing tests**

Test the review classifies `none/low` as allow, `medium/high` as flag, `critical` as block, and review client errors as fail-open allow/skipped. Test session emits `content_safety_reviewed` after complete reply.

- [ ] **Step 2: Run RED tests**

Run: `cd agent_service_v2 && ./.venv/bin/pytest tests/test_content_review_middleware.py tests/test_workbench_session.py::test_workbench_session_emits_content_safety_review_after_reply -q`

Expected: fail because safety package and event do not exist.

- [ ] **Step 3: Implement schemas and deterministic fallback client**

Implement `ContentSafetyReview` dataclass and `ContentReviewClient` protocol/fallback. The fallback returns skipped allow when no reviewer is configured.

- [ ] **Step 4: Implement reply collector**

Implement a small collector that watches `TextBlockDeltaEvent` while session streams and calls the reviewer after `ReplyEndEvent`.

- [ ] **Step 5: Emit review event**

Publish `EduEventType.CONTENT_SAFETY_REVIEWED` with payload containing `scope=content_safety_only` and `knowledge_reviewed=false`.

- [ ] **Step 6: Run GREEN tests**

Run safety and session tests.

### Task 4: Backend Persistence

**Files:**
- Modify: `backend/app/services/tutoring_stream_adapter.py`
- Test: `backend/tests/test_tutoring_stream_adapter.py`

- [ ] **Step 1: Write failing test**

Test `content_safety_reviewed` is forwarded to frontend and persisted in assistant message metadata.

- [ ] **Step 2: Run RED test**

Run: `cd backend && ../.venv/bin/python -m pytest tests/test_tutoring_stream_adapter.py::test_stream_adapter_persists_content_safety_review_meta -q`

Expected: fail because persistence callback does not accept meta.

- [ ] **Step 3: Extend stream state and persistence callback**

Add `meta` accumulation to `StreamState` and update `persist_tutoring_result` to merge `content_safety_review` into `Message.meta_json`.

- [ ] **Step 4: Run GREEN test**

Run targeted backend stream adapter tests.

### Task 5: Frontend Rendering

**Files:**
- Modify: `frontend/src/utils/chatStreamEvents.js`
- Modify: `frontend/src/components/chat/ChatMessage.jsx`
- Test: `frontend/src/utils/__tests__/chatStreamEvents.test.js`
- Test: `frontend/src/components/chat/ChatMessage.test.jsx`

- [ ] **Step 1: Write failing tests**

Test `content_safety_reviewed` adds an ordered safety part, `flag` preserves content, and `block` marks message blocked for replacement display.

- [ ] **Step 2: Run RED tests**

Run: `cd frontend && npm run test:unit -- src/utils/__tests__/chatStreamEvents.test.js src/components/chat/ChatMessage.test.jsx`

Expected: fail because event is unknown.

- [ ] **Step 3: Implement reducer and UI**

Add safety part handling and render compact status in `ChatMessage`. For block, display replacement text instead of model content.

- [ ] **Step 4: Run GREEN tests**

Run frontend targeted tests.

### Task 6: Docs, Full Verification, Commit

**Files:**
- Modify: `docs/10-client-api/API_前端接口规范.md`
- Modify: `docs/20-agent-api/API_Agent内部接口规范.md`
- Modify: `WorkLine.md`

- [ ] **Step 1: Update docs**

Document `content_safety_reviewed` and note `knowledge_reviewed=false`.

- [ ] **Step 2: Run verification**

Run:
- `cd agent_service_v2 && ./.venv/bin/pytest tests -q`
- `cd agent_service_v2 && ./.venv/bin/python -m py_compile src/agent_service_v2/session/workbench_session.py src/agent_service_v2/session/workbench_input.py src/agent_service_v2/workspaces/run_store.py src/agent_service_v2/safety/content_review_middleware.py src/agent_service_v2/safety/content_review_client.py src/agent_service_v2/safety/schemas.py`
- `cd backend && ../.venv/bin/python -m pytest tests/test_tutoring_stream_adapter.py tests/test_tutoring_privacy.py -q`
- `cd backend && ../.venv/bin/python -m py_compile app/services/tutoring_stream_adapter.py`
- `cd frontend && npm run test:unit -- src/utils/__tests__/chatStreamEvents.test.js src/components/chat/ChatMessage.test.jsx src/context/ChatContext.test.jsx`
- `cd frontend && npm run lint && npm run build`

- [ ] **Step 3: Commit**

Commit message: `重构AIChat AgentScope运行时与内容安全审核`
