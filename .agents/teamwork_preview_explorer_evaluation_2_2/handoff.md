# Handoff Report: Evaluation API Refactoring Analysis

## 1. Observation
- The controller `backend/app/api/v1/evaluation.py` currently contains mixed responsibilities (lines 39-485):
  - In-line validation, SQL query assembly, and data mapping within endpoint `get_evaluation` (lines 80-128).
  - MySQL named lock management using raw SQL statements (lines 39-59):
    ```python
    lock_result = await db.execute(text("SELECT GET_LOCK(:name, 5)"), {"name": lock_name})
    ```
  - Payload construction spanning over 150 lines (lines 130-296), touching multiple ORM models like `User`, `UserProfile`, `CourseOffering`, `CourseCatalog`, `LearningActivity`, `Resource`, `QuizSession`, `QuizAnswer`, and `QuizQuestion`.
  - Concurrency control and async execution utilizing `async_session_factory()` inside a private coroutine `_run_evaluation_refresh_background` (lines 299-423).
- The infrastructure locks module `backend/app/infrastructure/locks.py` (lines 15-36) contains a clean, hashed MySQL lock implementation:
  ```python
  @asynccontextmanager
  async def profile_lock(db: AsyncSession, user_id: str, course_id: str):
      ...
  ```
- Sister features like `profile` and `learning_path` follow clean Service patterns split into data retrieval service classes (e.g., `ProfileService`, `LearningPathService`) and refresh orchestration service classes (e.g., `ProfileRefreshService`, `LearningPathRefreshService`) with separate background run coroutines (lines 16-189 of `backend/app/services/learning_path_refresh_service.py` and lines 14-128 of `backend/app/services/profile_refresh_service.py`).

## 2. Logic Chain
1. Moving heavy database query compilation, formatting, lock handling, and agent payload construction from routers to dedicated service classes conforms to clean separation of concerns and matches the patterns in `profile` and `learning_path` modules (Observation 1, 3).
2. The asynchronous task runner `_run_evaluation_refresh_background` cannot use the request-level DB session because the request context exits before the agent generation finishes. Opening an independent session inside `run_evaluation_refresh_background` via `async_session_factory()` is a proven design pattern that matches `run_profile_refresh_background` and `run_learning_path_refresh_background` (Observation 3).
3. The custom `LockAcquisitionTimeout` exception integrates with the global exception handlers (Observation 2). Extracting `evaluation_lock` as an async context manager handles MySQL Named Locks cleanly with MD5 hashing to prevent named lock key lengths exceeding 64 characters (Observation 1, 2).

## 3. Caveats
- The execution of tests has not been performed locally because this task is strictly a read-only architectural investigation.
- No source files have been edited. All proposed changes must be implemented and tested by the Implementer agent.

## 4. Conclusion
- The refactoring of `evaluation.py` should proceed by:
  1. Creating `backend/app/services/evaluation_service.py` containing `EvaluationService` and `run_evaluation_refresh_background`.
  2. Introducing `evaluation_lock` to `backend/app/infrastructure/locks.py`.
  3. Simplifying `backend/app/api/v1/evaluation.py` to only coordinate and route incoming requests.

## 5. Verification Method
1. Verify the layout compliance:
   - Make sure no new files or logic are placed inside `.agents/`.
   - Implement the proposed code in `backend/app/services/evaluation_service.py` and update the routes in `backend/app/api/v1/evaluation.py`.
2. Run backend syntax check and unit tests (if any exist):
   ```bash
   python3 -m py_compile backend/app/services/evaluation_service.py backend/app/api/v1/evaluation.py backend/app/infrastructure/locks.py
   ```
3. Test suite execution command:
   ```bash
   cd backend && python3 -m pytest tests/ -v
   ```
4. Verify from the frontend UI or Swagger Docs that get and refresh APIs return HTTP 200/202 responses and properly refresh evaluation progress tables.
