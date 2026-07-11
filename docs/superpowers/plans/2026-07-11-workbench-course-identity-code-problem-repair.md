# Workbench Course Identity And Code Problem Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve Course Offering identity for authorization and code problems while using Course Catalog identity only for textbook RAG, and return stable code-problem rejection reasons.

**Architecture:** Backend sends both `course_id` and `catalog_id` to Agent Service v2. The workbench session and workspace remain scoped by offering `course_id`; the factory binds code-problem tools to the offering ID and RAG tools to `catalog_id`. Backend validation errors expose allowlisted reason codes through the internal Agent API and Agent tool result.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, AgentScope 2.0.3, pytest.

## Global Constraints

- Frontend continues to call Backend only; Backend calls Agent Service over HTTP.
- Agent Service does not access MySQL and Backend does not access Qdrant.
- No new dependencies and no public Client API changes.
- Runtime workspace isolation uses Course Offering ID.
- RAG filtering uses Course Catalog ID.
- Hidden test inputs, expected outputs, and reference solutions never enter error responses.

---

### Task 1: Split Offering And Catalog Identity

**Files:**
- Modify: `backend/app/services/tutoring_stream_adapter.py`
- Test: `backend/tests/test_tutoring_stream_adapter.py`
- Modify: `agent_service_v2/src/agent_service_v2/schemas/workbench.py`
- Modify: `agent_service_v2/src/agent_service_v2/api/workbench.py`
- Modify: `agent_service_v2/src/agent_service_v2/session/workbench_session.py`
- Modify: `agent_service_v2/src/agent_service_v2/agents/workbench_factory.py`
- Test: `agent_service_v2/tests/test_workbench_api.py`
- Test: `agent_service_v2/tests/test_workbench_factory.py`

**Interfaces:**
- Consumes: Backend tutoring payload fields `course_id` and `catalog_id`.
- Produces: `WorkbenchChatRequest.catalog_id: str | None`; `WorkbenchAgentFactory.create_agent(..., course_id, catalog_id, ...)`.

- [x] Add failing Backend test asserting `_build_workbench_payload()` preserves offering `course_id` and forwards `catalog_id` separately.
- [x] Add failing Agent tests asserting the API/factory propagate both IDs and bind RAG to catalog while code problems retain offering ID.
- [x] Run focused tests and confirm failures are caused by the missing split identity.
- [x] Add `catalog_id` to the Agent v2 request/session/factory path and select IDs only at tool binding boundaries.
- [x] Run focused Backend and Agent tests until green.
- [x] Commit the identity repair as one cross-module contract change.

### Task 2: Preserve Stable Validation Reasons

**Files:**
- Modify: `backend/app/services/code_problem_service.py`
- Modify: `backend/app/api/v1/internal_ai_chat.py`
- Test: `backend/tests/test_code_problem_service.py`
- Test: `backend/tests/test_internal_ai_chat.py`
- Modify: `agent_service_v2/src/agent_service_v2/tools/backend_learning_client.py`
- Modify: `agent_service_v2/src/agent_service_v2/tools/personal_code_problem.py`
- Test: `agent_service_v2/tests/test_backend_learning_client.py`
- Test: `agent_service_v2/tests/test_personal_code_problem_tools.py`

**Interfaces:**
- Consumes: Backend HTTP error envelope `detail.data.reason`.
- Produces: Agent tool result `{status: "rejected", reason: <stable_reason_code>}`.

- [x] Add failing Backend tests for stable `conversation_ownership_check_failed`, `course_enrollment_check_failed`, and draft validation reason codes.
- [x] Add failing Agent client/tool tests asserting Backend detail reasons survive HTTP classification.
- [x] Run focused tests and confirm failures reflect current generic `backend_rejected` behavior.
- [x] Add a `reason` field to `CodeProblemValidationError`, return it in the internal error envelope, and parse it in `BackendLearningClientError`.
- [x] Keep HTTP category separate from safe detail reason and expose only the detail reason in rejected tool observations.
- [x] Run focused Backend and Agent tests until green.
- [x] Commit error reason preservation separately.

### Task 3: Verification And WorkLine

**Files:**
- Modify: `WorkLine.md`

**Interfaces:**
- Consumes: completed identity and error-reason changes.
- Produces: verification record and interface-drift statement.

- [x] Run Python syntax checks for every changed Python source file.
- [x] Run related Backend tests and the full Agent Service v2 test suite.
- [x] Verify Agent Service OpenAPI includes optional `catalog_id`.
- [x] Run a request-level smoke check proving offering and catalog IDs reach their intended tool boundaries.
- [x] Append implementation, tests, and `/agent/v2/workbench/chat` internal field expansion to `WorkLine.md`.
- [x] Commit the verification record without including unrelated user changes.
