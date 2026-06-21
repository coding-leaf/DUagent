# Refactoring and Testing Strategy for Evaluation Module

This document outlines the testing strategy for the refactored evaluation router (`backend/app/api/v1/evaluation.py`) and the new evaluation service (`backend/app/services/evaluation.py`). It includes the design of unit tests for both the thin router and the new service, as well as an assessment of how existing integration tests are affected.

---

## 1. Context and Refactoring Plan

The `evaluation` module currently operates with a fat router in `backend/app/api/v1/evaluation.py`. The plan is to separate concerns by:
1. **Thin Router**: The route handlers will only handle HTTP-level concerns (extracting dependencies, user session retrieval, validation, input validation, and calling the service).
2. **Evaluation Service**: A new service class `EvaluationService` inside `backend/app/services/evaluation.py` will encapsulate all business logic, database queries, and async background task triggering.
3. **Background Runner**: The asynchronous function `_run_evaluation_refresh_background` will be extracted to `backend/app/services/evaluation.py` as a standalone function `run_evaluation_refresh_background`.

### Directory Layout Compliance
The new code and tests will be placed as follows:
- Service logic: `backend/app/services/evaluation.py`
- Router logic: `backend/app/api/v1/evaluation.py`
- New unit tests:
  - Router unit tests: `backend/tests/test_evaluation_routes_refactored.py`
  - Service unit tests: `backend/tests/test_evaluation_service_refactored.py`

---

## 2. Test Architecture Strategy

We will use Pytest with its async extension (`pytest-asyncio`) and Python's standard `unittest.mock` framework to test each layer in isolation:

```
┌───────────────────────────────────────────────┐
│     test_evaluation_routes_refactored.py       │ (Router Unit Tests)
└───────────────────────┬───────────────────────┘
                        │
                        ▼ (Mocks)
┌───────────────────────────────────────────────┐
│              EvaluationService                │
└───────────────────────┬───────────────────────┘
                        │
                        ▼ (Mocks DB and Agent Client)
┌───────────────────────────────────────────────┐
│     test_evaluation_service_refactored.py      │ (Service Unit Tests)
└───────────────────────────────────────────────┘
```

---

## 3. Router Unit Tests Design (`test_evaluation_routes_refactored.py`)

Router unit tests will mock `EvaluationService` and verify that the thin router correctly coordinates API requests, performs course enrollment validation, handles existing processing tasks, and schedules background tasks.

Here is the design for `backend/tests/test_evaluation_routes_refactored.py`:

```python
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@patch("app.api.v1.evaluation.EvaluationService")
@patch("app.api.v1.evaluation.get_current_user")
@patch("app.api.v1.evaluation.get_db")
@pytest.mark.asyncio
async def test_get_evaluation_route_success(mock_get_db, mock_get_current_user, mock_service_cls):
    """Test GET /api/v1/evaluation successfully calls the service."""
    mock_service = AsyncMock()
    mock_service.get_evaluation.return_value = {
        "course_id": "course_123",
        "summary_text": "Excellent progress",
        "progress_table": {"columns": [], "rows": []},
        "mastery_table": {"columns": [], "rows": []},
        "resource_usage_table": {"columns": [], "rows": []},
        "node_progress": [],
        "generated_at": "2026-06-21T00:00:00Z"
    }
    mock_service_cls.return_value = mock_service

    mock_user = MagicMock()
    mock_user.id = "user_123"
    mock_user.role = "student"
    mock_get_current_user.return_value = mock_user

    response = client.get("/api/v1/evaluation?course_id=course_123")
    assert response.status_code == 200
    assert response.json()["code"] == 200
    assert response.json()["data"]["course_id"] == "course_123"
    mock_service.get_evaluation.assert_called_once_with("user_123", "course_123")


@patch("app.api.v1.evaluation.EvaluationService")
@patch("app.api.v1.evaluation.get_current_user")
@patch("app.api.v1.evaluation.get_db")
@pytest.mark.asyncio
async def test_refresh_evaluation_route_existing_task(mock_get_db, mock_get_current_user, mock_service_cls):
    """Test POST /api/v1/evaluation/refresh returns 202 when a task is already processing."""
    mock_service = AsyncMock()
    mock_task = MagicMock()
    mock_task.id = "task_999"
    mock_service.get_processing_refresh_task.return_value = mock_task
    mock_service_cls.return_value = mock_service

    mock_user = MagicMock()
    mock_user.id = "user_123"
    mock_user.role = "student"
    mock_get_current_user.return_value = mock_user

    # Mock course enrollment check (since user is student)
    mock_db = AsyncMock()
    mock_db.execute.return_value = MagicMock(scalar_one_or_none=lambda: MagicMock())
    mock_get_db.return_value = mock_db

    response = client.post("/api/v1/evaluation/refresh", json={"course_id": "course_123"})
    assert response.status_code == 202
    assert response.json()["code"] == 202
    assert response.json()["data"]["task_id"] == "task_999"
    mock_service.get_processing_refresh_task.assert_called_once_with("user_123", "course_123")
    mock_service.assemble_evaluation_payload.assert_not_called()


@patch("app.api.v1.evaluation.EvaluationService")
@patch("app.api.v1.evaluation.run_evaluation_refresh_background")
@patch("app.api.v1.evaluation.get_current_user")
@patch("app.api.v1.evaluation.get_db")
@pytest.mark.asyncio
async def test_refresh_evaluation_route_new_task(
    mock_get_db, mock_get_current_user, mock_run_bg, mock_service_cls
):
    """Test POST /api/v1/evaluation/refresh creates new task and schedules background runner."""
    mock_service = AsyncMock()
    mock_service.get_processing_refresh_task.return_value = None
    mock_service.assemble_evaluation_payload.return_value = {"payload": "data"}
    
    mock_new_task = MagicMock()
    mock_new_task.id = "task_888"
    mock_service.create_refresh_task.return_value = mock_new_task
    mock_service_cls.return_value = mock_service

    mock_user = MagicMock()
    mock_user.id = "user_123"
    mock_user.role = "student"
    mock_get_current_user.return_value = mock_user

    # Mock course enrollment check
    mock_db = AsyncMock()
    mock_db.execute.return_value = MagicMock(scalar_one_or_none=lambda: MagicMock())
    mock_get_db.return_value = mock_db

    with patch("asyncio.create_task") as mock_create_task:
        response = client.post("/api/v1/evaluation/refresh", json={"course_id": "course_123"})
        assert response.status_code == 202
        assert response.json()["code"] == 202
        assert response.json()["data"]["task_id"] == "task_888"
        
        mock_service.assemble_evaluation_payload.assert_called_once_with("user_123", "course_123")
        mock_service.create_refresh_task.assert_called_once_with("user_123", "course_123")
        mock_create_task.assert_called_once()
```

---

## 4. Service Unit Tests Design (`test_evaluation_service_refactored.py`)

Service unit tests will verify payload assembly, task creation, retrieval logic, and the asynchronous background runner execution logic (including lock management and database rollbacks on failure).

Here is the design for `backend/tests/test_evaluation_service_refactored.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from app.services.evaluation import EvaluationService, run_evaluation_refresh_background
from app.models.others import AsyncTask, Evaluation, UserProfile
from app.services.agent_client import AgentServiceError

@pytest.mark.asyncio
async def test_get_evaluation_empty():
    """Verify get_evaluation returns default empty tables when no record exists in DB."""
    db = AsyncMock()
    
    # Mock build_node_progress_rows return value
    with patch("app.services.evaluation.build_node_progress_rows", new_callable=AsyncMock) as mock_build_rows:
        mock_build_rows.return_value = [{"node_id": "node_1", "status": "unstarted"}]
        
        # Mock DB execute result to return None (no evaluation record)
        mock_res = MagicMock()
        mock_res.scalars().first.return_value = None
        db.execute.return_value = mock_res
        
        service = EvaluationService(db)
        res = await service.get_evaluation("user_123", "course_123")
        
        assert res["course_id"] == "course_123"
        assert res["summary_text"] == ""
        assert res["generated_at"] is None
        assert res["node_progress"] == [{"node_id": "node_1", "status": "unstarted"}]


@pytest.mark.asyncio
async def test_get_evaluation_existing():
    """Verify get_evaluation fetches and parses the active record correctly."""
    db = AsyncMock()
    
    with patch("app.services.evaluation.build_node_progress_rows", new_callable=AsyncMock) as mock_build_rows:
        mock_build_rows.return_value = []
        
        mock_eval = Evaluation(
            user_id="user_123",
            course_id="course_123",
            summary_text="Great work",
            progress_table={"rows": []},
            generated_at=datetime.now(timezone.utc)
        )
        mock_res = MagicMock()
        mock_res.scalars().first.return_value = mock_eval
        db.execute.return_value = mock_res
        
        service = EvaluationService(db)
        res = await service.get_evaluation("user_123", "course_123")
        
        assert res["summary_text"] == "Great work"
        assert res["generated_at"] is not None


@pytest.mark.asyncio
async def test_create_refresh_task():
    """Verify create_refresh_task inserts a new task in the database."""
    db = AsyncMock()
    service = EvaluationService(db)
    
    task = await service.create_refresh_task("user_123", "course_123")
    
    assert isinstance(task, AsyncTask)
    assert task.user_id == "user_123"
    assert task.course_id == "course_123"
    assert task.task_type == "evaluation_refresh"
    assert task.status == "processing"
    
    db.add.assert_called_once_with(task)
    db.flush.assert_awaited_once()
    db.refresh.assert_awaited_once_with(task)


@pytest.mark.asyncio
@patch("app.services.evaluation.agent_client")
@patch("app.services.evaluation.build_node_progress_rows")
@patch("app.services.evaluation.async_session_factory")
async def test_run_evaluation_refresh_background_success(
    mock_session_factory,
    mock_build_rows,
    mock_agent_client
):
    """Test run_evaluation_refresh_background updates DB on success."""
    db = AsyncMock()
    mock_session_factory.return_value.__aenter__.return_value = db
    db.bind.dialect.name = "sqlite"  # Bypass mysql locks in tests

    # Mock agent service response
    mock_agent_client.post_json = AsyncMock(return_value={
        "progress_table": {"columns": [], "rows": []},
        "mastery_table": {"columns": [], "rows": []},
        "resource_usage_table": {"columns": [], "rows": []},
        "summary_text": "Good progress"
    })
    
    mock_build_rows.return_value = [{"node_id": "n1"}]
    
    # Mock old evaluations query return value
    mock_old_evals = MagicMock()
    mock_old_evals.scalars().all.return_value = []
    db.execute.return_value = mock_old_evals
    
    await run_evaluation_refresh_background("task_123", "user_123", "course_123", {"payload": "data"})
    
    # Verify new Evaluation record was added
    db.add.assert_called_once()
    added_obj = db.add.call_args[0][0]
    assert isinstance(added_obj, Evaluation)
    assert added_obj.summary_text == "Good progress"
    
    # Verify task state update and commit
    db.commit.assert_called_once()


@pytest.mark.asyncio
@patch("app.services.evaluation.agent_client")
@patch("app.services.evaluation.async_session_factory")
async def test_run_evaluation_refresh_background_agent_failure(
    mock_session_factory,
    mock_agent_client
):
    """Test background runner updates task status to failed when agent client errors."""
    db = AsyncMock()
    mock_session_factory.return_value.__aenter__.return_value = db
    db.bind.dialect.name = "sqlite"

    # Mock agent client raising exception
    mock_agent_client.post_json.side_effect = AgentServiceError(
        message="Agent down", status_code=500, agent_code=50001
    )
    
    await run_evaluation_refresh_background("task_123", "user_123", "course_123", {"payload": "data"})
    
    # Verify rollback was called and task was marked failed
    db.rollback.assert_called_once()
    db.execute.assert_called_once()  # Called to update task status
    db.commit.assert_called_once()   # Called to commit task failure status
```

---

## 5. Compatibility Analysis for Existing Integration Tests

There are three key files containing existing integration/refresh tests that interact with evaluation logic:
1. `backend/tests/test_refresh_async.py`:
   - Contains tests for evaluation/refresh success (`test_refresh_async.py:296`), agent failure (`test_refresh_async.py:413`), and duplicate refresh reuse (`test_refresh_async.py:433`).
   - Uses `patch("app.api.v1.evaluation.agent_client.post_json")` to mock agent responses.
2. `backend/tests/test_lock_async.py`:
   - Verifies evaluation refresh acquisition locks (`test_lock_async.py:151`).
   - Uses `patch("app.api.v1.evaluation.agent_client.post_json")`.
3. `backend/tests/test_agent_integration.py` (`TestEvaluationLearningPathIntegration`):
   - Verifies REST endpoints directly using client request payloads. Does not patch python functions.

### Ensuring No-Modification Compatibility
Because the existing integration tests use `patch("app.api.v1.evaluation.agent_client.post_json")` to mock agent interactions, if we refactor the background runner to `app.services.evaluation` and remove `agent_client` from `app.api.v1.evaluation`, those mock targets will cease to exist, resulting in `AttributeError` when running tests.

**To ensure these tests pass with zero modification, we must:**
1. Leave the import `from app.services.agent_client import agent_client` inside the thin router `backend/app/api/v1/evaluation.py` even if it is not directly used for routing logic.
2. This preserves the namespace mapping (`app.api.v1.evaluation.agent_client`), allowing Python's `unittest.mock.patch` to find the target object and patch the singleton instance successfully.

### Minimum Required Updates (Alternative)
If we prefer not to leave unused imports in the router, we should update the mock targets in the integration tests:
- In `backend/tests/test_refresh_async.py` (lines 358, 416):
  Change:
  `patch("app.api.v1.evaluation.agent_client.post_json")`
  To:
  `patch("app.services.evaluation.agent_client.post_json")`
- In `backend/tests/test_lock_async.py` (line 162):
  Change:
  `patch("app.api.v1.evaluation.agent_client.post_json")`
  To:
  `patch("app.services.evaluation.agent_client.post_json")`

---

## 6. Verification Commands

To verify that the testing strategy is correctly implemented and all evaluation routes/service/integration tests are passing, run the following commands from the `backend/` directory:

```bash
# 1. Run the new router unit tests
python3 -m pytest tests/test_evaluation_routes_refactored.py -v

# 2. Run the new service unit tests
python3 -m pytest tests/test_evaluation_service_refactored.py -v

# 3. Run the existing evaluation-related async/lock tests to ensure backward compatibility
python3 -m pytest tests/test_refresh_async.py tests/test_lock_async.py -v

# 4. Run the full agent integration suite
python3 -m pytest tests/test_agent_integration.py -v
```
