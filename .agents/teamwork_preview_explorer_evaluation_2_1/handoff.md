# Handoff Report - Evaluation Router Refactoring Analysis

## 1. Observation
We analyzed the codebase and verified the following:
* **File Under Investigation**: `backend/app/api/v1/evaluation.py` (total 485 lines).
* **Direct DB Dependencies & Queries**:
  * Line 11: `from app.api.deps import get_current_user, get_db`
  * Line 12: `from app.db.session import async_session_factory`
  * Lines 13-17: Imports of `CourseCatalog`, `CourseOffering`, `CourseEnrollment`, `AsyncTask`, `Evaluation`, `LearningActivity`, `Resource`, `UserProfile`, `QuizAnswer`, `QuizQuestion`, `QuizSession`, `User`.
  * Lines 39-50 & 53-58: Manual implementation of database named lock logic:
    ```python
    lock_result = await db.execute(text("SELECT GET_LOCK(:name, 5)"), {"name": lock_name})
    ```
  * Lines 86-96: Inline query to construct evaluation response:
    ```python
    node_progress = await build_node_progress_rows(current_user.id, course_id, db)
    result = await db.execute(select(Evaluation)...)
    ```
  * Lines 130-296: Helper function `_assemble_evaluation_payload` querying and aggregating data across 11 different database models (`User`, `UserProfile`, `CourseOffering`, `CourseCatalog`, `LearningActivity`, `Resource`, `QuizSession`, `QuizAnswer`, `QuizQuestion`, etc.) to compile an agent API payload.
  * Lines 299-423: Worker `_run_evaluation_refresh_background` instantiating its own DB session via `async_session_factory()`, managing transaction controls (`db.commit()`, `db.rollback()`), checking and marking old evaluations as deleted (`is_deleted = True`), and recording success/failure statuses on `AsyncTask`.
  * Lines 437-444: Inline student enrollment check query on `CourseEnrollment`.
* **Background Tasking**:
  * Lines 474-479: Background task dispatched inside request thread context:
    ```python
    asyncio.create_task(_run_evaluation_refresh_background(
        task_id=task.id,
        user_id=current_user.id,
        course_id=course_id,
        payload=payload,
    ))
    ```
* **Reference Infrastructure**:
  * `backend/app/services/profile_refresh_service.py` is an example of decoupling. It utilizes `ProfileService` and `from app.infrastructure.locks import profile_lock`.
  * `backend/app/exceptions/base.py` defines `DomainException` (lines 1-8).
  * `backend/app/exceptions/handlers.py` handles `DomainException` globally (lines 5-10).

---

## 2. Logic Chain
1. **Observation 1.2 & 1.3**: The file `evaluation.py` defines routing logic (HTTP routes) but also handles payload assembly, transactions, locks, and task updates.
2. **Reference to AGENTS.md Rules**: The project phase mandates "Clean up fat controller/router files, establish clean分层架构 (Router -> Service -> DB)".
3. **Inference 1**: Therefore, all direct ORM queries, inserts, named locks, and payloads should be relocated to the Service layer (`app/services/evaluation_service.py`).
4. **Observation 1.3**: The named database lock is implemented manually inside `evaluation.py`.
5. **Reference to locks.py**: The `app/infrastructure/locks.py` file already provides a contextual `profile_lock` helper.
6. **Inference 2**: Therefore, evaluation locks should be extracted into `locks.py` as an `evaluation_lock` async context manager to reuse pattern and enforce lock safety.
7. **Observation 1.3**: Background tasks are spun off via `asyncio.create_task` and track status using `AsyncTask`.
8. **Inference 3**: Triggering and worker functions can be structured in `evaluation_service.py` using `async_session_factory` to preserve database session boundary hygiene.
9. **Observation 1.4**: The codebase already registers a global HTTP interceptor for `DomainException`.
10. **Inference 4**: The service layer can raise subclasses of `DomainException` (e.g. `NotEnrolledInCourseError` or `LockAcquisitionTimeout`) instead of `HTTPException`. This completely decouples HTTP response structures and status codes from business logic.

---

## 3. Caveats
* We did not execute the Python code or run unit tests in this step, as it is a read-only investigation.
* We assume that other database transactions are not affected by moving this module to a separate service file.
* We assume no external services rely on importing `_assemble_evaluation_payload` directly from `app.api.v1.evaluation`.

---

## 4. Conclusion
We recommend:
1. **Extraction**: Create `app/services/evaluation_service.py` containing `EvaluationService` and worker helper functions, shifting all 11 model query statements, locks, and transaction states out of the router.
2. **Context Passing**: Have the Router initialize `EvaluationService(db)` and pass `user_id`, `course_id`, and `role` as basic parameters.
3. **Locks Refactoring**: Move named lock logic to `app/infrastructure/locks.py` as `evaluation_lock`.
4. **Exception Handling**: Replace `HTTPException` with domain-specific subclasses of `DomainException` to separate business validation errors from HTTP responses.

---

## 5. Verification Method
To verify the analysis and ensure readiness:
* Inspect `/home/yezisama/workspace/workflow/EDUagent/.agents/teamwork_preview_explorer_evaluation_2_1/analysis.md` for the detailed refactoring plan.
* Validate python files syntax after future implementation:
  ```bash
  python3 -m py_compile backend/app/api/v1/evaluation.py
  python3 -m py_compile backend/app/services/evaluation_service.py
  ```
* Run existing API/Agent integration tests:
  ```bash
  cd backend && python3 -m pytest tests/test_agent_integration.py -v
  ```
