# Analysis of `backend/app/api/v1/evaluation.py`

This document details the analysis of the DB dependencies, database query logic, and background task management in `backend/app/api/v1/evaluation.py`. It also provides recommendations for refactoring these components to establish clean separation between the Router (API layer) and the Service (business logic) layer.

---

## 1. Direct Observations of Current Code

### 1.1 DB Dependencies
The router directly imports and interacts with the following database models (lines 13-17):
- **`Evaluation`** (`app.models.others`): Stores structured evaluation datasets including progress, mastery, resource usage tables, and generated summary text.
- **`AsyncTask`** (`app.models.others`): Tracks the state of background evaluation refresh tasks (`task_type="evaluation_refresh"`, status `processing`, `completed`, `failed`).
- **`User`** (`app.models.user`): Fetches student attributes like major, grade, and guidance level to formulate agent client payloads.
- **`UserProfile`** (`app.models.others`): Extracts cognitive blindspots, learning preferences, and current coordinates.
- **`CourseOffering`** & **`CourseCatalog`** (`app.models.catalog`): Resolves catalogs and knowledge graphs as fallbacks.
- **`LearningActivity`** (`app.models.others`): Gathers duration and count of user activities.
- **`Resource`** (`app.models.others`): Queries course content details such as counts grouped by chapters or resource types.
- **`QuizSession`**, **`QuizAnswer`**, **`QuizQuestion`** (`app.models.quiz`): Queries the last 50 quiz sessions and compiles mastery metrics by knowledge point.
- **`CourseEnrollment`** (`app.models.course`): Used directly in endpoint authorization checks.

### 1.2 DB Query Logic & Transactions
The router contains extensive inline SQL/SQLAlchemy queries across multiple helper functions and endpoints:
* **`_acquire_evaluation_lock`** (lines 39-50): Executes direct MySQL named lock queries (`SELECT GET_LOCK(:name, 5)`).
* **`_release_evaluation_lock`** (lines 53-58): Executes MySQL unlock queries (`SELECT RELEASE_LOCK(:name)`).
* **`_get_processing_refresh_task`** (lines 60-78): Queries `AsyncTask` by task type, status, and user/course keys.
* **`get_evaluation` endpoint** (lines 87-95): Directly queries `Evaluation` filtering by user and course:
  ```python
  select(Evaluation)
  .where(
      Evaluation.user_id == current_user.id,
      Evaluation.course_id == course_id,
      Evaluation.is_deleted == False,
  )
  .order_by(Evaluation.generated_at.desc())
  ```
* **`_assemble_evaluation_payload`** (lines 130-296): Executes multiple distinct database queries to construct a complex payload:
  * Select `User` profile information (lines 138-140)
  * Select `UserProfile` records (lines 147-156)
  * Select `CourseOffering` and `CourseCatalog` for fallback logic (lines 169-183)
  * Select aggregated `LearningActivity` stats (lines 191-203)
  * Select `Resource` chapter statistics (lines 212-220)
  * Select `QuizSession` list (lines 224-230)
  * Select `QuizAnswer` joined with `QuizQuestion` to calculate performance per knowledge point (lines 235-250)
  * Loop to select `Resource` counts grouped by types (lines 285-293)
* **`_run_evaluation_refresh_background`** (lines 299-423):
  * Reads `Evaluation` to mark previous records as deleted (`old.is_deleted = True`) (lines 337-345)
  * Inserts new `Evaluation` model (lines 347-356)
  * Updates `AsyncTask` status to `completed` or `failed` (lines 358-366, 387-396, 407-417)
  * Manages transactional states manually via `db.flush()`, `db.commit()`, and `db.rollback()`.
* **`refresh_evaluation` endpoint** (lines 425-484):
  * Validates course enrollments using `CourseEnrollment` (lines 438-444)
  * Creates and commits `AsyncTask` (lines 462-471).

### 1.3 Background Task Management
* **Trigger Mechanism**: Uses Python's standard `asyncio.create_task(...)` to spin up a background worker task (`_run_evaluation_refresh_background`) asynchronously (lines 474-479).
* **Task State Tracking**: Handled via `AsyncTask` DB records. The HTTP request immediately returns `202 Accepted` with the generated `task_id` after writing the task to the database.
* **Session Lifecycle**: The background worker manages its own session lifecycle using `async_session_factory()` (line 312), preventing session sharing or concurrency issues with the request context.
* **Concurrence Control**: Employs named database locks via MySQL's `GET_LOCK` and `RELEASE_LOCK` (lines 313-325, 368-370) to serialize writes for the same `(user_id, course_id)` combination, preventing concurrent tasks from corrupting or writing duplicate records.

---

## 2. Refactoring Recommendations

### Recommendation 1: Service Layer Extraction (Thin Router Design)

To adhere to the **Clean Architecture / Router-Service-DB** layout, we should extract all database interactions and business actions from the router into a dedicated Service class: `EvaluationService`.

* **What remains in the Router (`backend/app/api/v1/evaluation.py`):**
  * FastAPI route mappings (`@router.get`, `@router.post`).
  * Request parameter validation and schemas mapping.
  * Injecting dependencies: `Depends(get_current_user)` and `Depends(get_db)`.
  * Instantiating the service layer and orchestrating the output into JSON responses or HTTP-specific envelope formats.
* **What moves to the Service Layer (`backend/app/services/evaluation_service.py`):**
  * Fetching the active evaluation data and mapping it to the API expected dictionary.
  * Triggering the refresh action (validating authorization, checking for existing tasks, and creating the `AsyncTask`).
  * The complex `_assemble_evaluation_payload` payload builder.
  * The background worker function `_run_evaluation_refresh_background` (could be kept as a top-level service utility or worker function, instantiating its own `EvaluationService` with `async_session_factory`).
* **What moves to the Infrastructure Layer (`backend/app/infrastructure/locks.py`):**
  * The named lock logic should be wrapped in a reusable context manager, mirroring the current `profile_lock` in `locks.py`:
    ```python
    @asynccontextmanager
    async def evaluation_lock(db: AsyncSession, user_id: str, course_id: str):
        raw = f"evaluation_{user_id}_{course_id}"
        lock_name = hashlib.md5(raw.encode()).hexdigest()[:32]
        
        lock_result = await db.execute(
            text("SELECT GET_LOCK(:key, 5)"),
            params={"key": lock_name}
        )
        acquired = lock_result.scalar()
        if not acquired:
            raise LockAcquisitionTimeout(f"Lock timeout for evaluation of user: {user_id}, course: {course_id}")
            
        try:
            yield lock_name
        finally:
            await db.execute(
                text("SELECT RELEASE_LOCK(:key)"),
                params={"key": lock_name}
            )
    ```

---

### Recommendation 2: DB Session & Context Passing

* **Passing the Session**:
  * Instantiate the `EvaluationService` inside the router handler per request, passing the dependency-injected session:
    ```python
    @router.get("")
    async def get_evaluation(
        course_id: str = Query(...),
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        service = EvaluationService(db)
        data = await service.get_evaluation(current_user.id, course_id)
        return {"code": 200, "message": "success", "data": data}
    ```
* **Passing the User Context**:
  * Pass granular context details (`user_id`, `course_id`, `role`) as arguments to service methods rather than passing the raw FastAPI ORM `User` class. This decreases coupling, simplifies unit testing, and isolates the service layer from API-specific model definitions.
  * Let's define the interface for `EvaluationService`:
    ```python
    class EvaluationService:
        def __init__(self, db: AsyncSession):
            self.db = db

        async def get_evaluation(self, user_id: str, course_id: str) -> dict:
            # Queries Evaluation and node progress, formatting standard return payload
            ...

        async def request_refresh(self, user_id: str, user_role: str, course_id: str) -> str:
            # 1. Performs enrollment check (raises DomainException if not enrolled)
            # 2. Checks active tasks
            # 3. Assembles agent payload
            # 4. Creates AsyncTask, commits and triggers background worker
            # 5. Returns task_id
            ...
    ```

---

### Recommendation 3: Error Handling & Response Formatting Separation

The application already has a global exception handler for `DomainException` defined in `backend/app/exceptions/handlers.py`. We should utilize this mechanism to separate error throwing from HTTP formatting.

* **Domain Exceptions**:
  * Instead of raising `HTTPException` inside the router or service logic, the service should raise domain-specific exceptions inheriting from `DomainException`:
    * Raise `NotEnrolledInCourseError` (new, maps to 403 Forbidden):
      ```python
      class NotEnrolledInCourseError(DomainException):
          def __init__(self, message: str = "未加入该课程"):
              super().__init__(
                  message=message,
                  code=40300,
                  status_code=status.HTTP_403_FORBIDDEN
              )
      ```
    * Raise `LockAcquisitionTimeout` (existing in `app.infrastructure.locks`, maps to 503 Service Unavailable).
  * This keeps service layer functions entirely free of FastAPI `HTTPException` imports, making the business logic purely Python-based.
* **Separation of Response Formatting**:
  * The Service layer only returns raw Python dictionaries or structured Pydantic models representing the clean, processed business data.
  * The Router layer receives this data and wraps it in the unified API response wrapper (e.g. `{"code": 200, "message": "success", "data": result}`).
  * If an exception occurs, the global FastAPI middleware translates the raised `DomainException` to the structured error JSON block, assuring consistency.
