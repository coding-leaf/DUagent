# Backend Evaluation Refactoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the backend evaluation module to separate router concerns from service concerns (Router-Service-DB split), add comprehensive unit tests, and maintain backward compatibility.

**Architecture:** 
1. **API Router**: `backend/app/api/v1/evaluation.py` becomes a thin wrapper around `EvaluationService`.
2. **Service Layer**: `backend/app/services/evaluation_service.py` encapsulates SQL queries, payload assembly, and background worker logic.
3. **Infrastructure Locks**: Add `evaluation_lock` to `backend/app/infrastructure/locks.py` with SQLite compatibility.
4. **Router Unit Tests**: `backend/tests/test_evaluation_routes_refactored.py` verifies routing and HTTP interactions using service mocks.
5. **Service Unit Tests**: `backend/tests/test_evaluation_service_refactored.py` verifies payload construction, task states, database inserts, and error/rollback flows.
6. **Backward Compatibility**: Keep the `agent_client` import in the thin router so legacy mock patch targets in integration tests remain valid, or update the patch targets to point to `evaluation_service`.

**Tech Stack:** FastAPI, SQLAlchemy, pytest, pytest-asyncio, unittest.mock

---

### Task 1: Update Concurrency Locks
**Files:**
- Modify: `backend/app/infrastructure/locks.py`

- [ ] **Step 1.1: Add `evaluation_lock` context manager**
  Add the `evaluation_lock` implementation supporting SQLite dialect detection.
  
  ```python
  @asynccontextmanager
  async def evaluation_lock(db: AsyncSession, user_id: str, course_id: str):
      raw = f"evaluation_{user_id}_{course_id}"
      if db.bind.dialect.name == "sqlite":
          yield raw
          return
      lock_result = await db.execute(text("SELECT GET_LOCK(:name, 5)"), {"name": raw})
      if not lock_result.scalar():
          raise RuntimeError(f"GET_LOCK timeout: {raw}")
      try:
          yield raw
      finally:
          await db.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": raw})
  ```

- [ ] **Step 1.2: Verify syntax**
  Run: `python3 -m py_compile backend/app/infrastructure/locks.py`
  Expected: Successful compilation without errors.

---

### Task 2: Create Evaluation Service
**Files:**
- Create: `backend/app/services/evaluation_service.py`

- [ ] **Step 2.1: Write `EvaluationService` and background runner**
  Write the class `EvaluationService` and standalone function `run_evaluation_refresh_background` extracted from `evaluation.py`.
  Make sure to import and use the new `evaluation_lock` context manager.

- [ ] **Step 2.2: Verify syntax**
  Run: `python3 -m py_compile backend/app/services/evaluation_service.py`
  Expected: Successful compilation without errors.

---

### Task 3: Refactor Evaluation Router
**Files:**
- Modify: `backend/app/api/v1/evaluation.py`

- [ ] **Step 3.1: Clean up router endpoints**
  Refactor the routes to instantiate `EvaluationService` and call its methods. Keep `from app.services.agent_client import agent_client` import at the module level for legacy test mocking support.

- [ ] **Step 3.2: Verify syntax**
  Run: `python3 -m py_compile backend/app/api/v1/evaluation.py`
  Expected: Successful compilation without errors.

---

### Task 4: Implement Unit Tests
**Files:**
- Create: `backend/tests/test_evaluation_routes_refactored.py`
- Create: `backend/tests/test_evaluation_service_refactored.py`

- [ ] **Step 4.1: Write router unit tests**
  Create mock-based tests verifying GET/POST routing and responses.
  
- [ ] **Step 4.2: Write service unit tests**
  Create mock-based tests verifying service actions, payload assembly, and background worker state transitions.

- [ ] **Step 4.3: Execute new unit tests**
  Run: `cd backend && ../.venv/bin/python3 -m pytest tests/test_evaluation_routes_refactored.py tests/test_evaluation_service_refactored.py -v`
  Expected: All new unit tests PASS.

---

### Task 5: Verify Integration and Compatibility
**Files:**
- Modify (optional): Update mock patch targets in `backend/tests/test_refresh_async.py` and `backend/tests/test_lock_async.py` if necessary.

- [ ] **Step 5.1: Run existing integration tests**
  Run: `cd backend && ../.venv/bin/python3 -m pytest tests/test_agent_integration.py tests/test_refresh_async.py tests/test_lock_async.py -v`
  Expected: No new regressions; same status as baseline.
