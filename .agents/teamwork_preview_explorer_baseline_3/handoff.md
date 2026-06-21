# Handoff Report — teamwork_preview_explorer_baseline_3

## 1. Observation
I directly observed the following code sections and structures:
- **`backend/app/api/v1/catalogs.py`**:
  - Direct file chunk operations and SQL transaction logic in the router `admin_upload_catalog_material` (lines 120-158):
    ```python
    with target_path.open("wb") as f:
        while chunk := await file.read(UPLOAD_CHUNK_SIZE):
            file_size += len(chunk)
            ...
            f.write(chunk)
    ```
  - Direct DB update in router: `await db.execute(update(CourseCatalog)...)` (lines 171-185).
  - Explicit database count check in the router (lines 262-283):
    ```python
    pending_count = (
        await db.execute(
            select(func.count())
            .select_from(CourseCatalogMaterial)
            .where(
                CourseCatalogMaterial.catalog_id == catalog.id,
                CourseCatalogMaterial.is_deleted == False,
                CourseCatalogMaterial.status == "uploaded",
            )
        )
    ).scalar() or 0
    ```
- **`backend/app/api/v1/resources.py`**:
  - Direct queries, offsets, and count calculation inside the router in `list_resources` (lines 38-54):
    ```python
    query = select(Resource).where(
        resource_scope_clause(course_id, scope.catalog_id),
        Resource.is_deleted == False,
    )
    ...
    count_r = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_r.scalar() or 0
    ...
    result = await db.execute(
        query.order_by(Resource.create_time.desc()).offset(offset).limit(page_size)
    )
    ```
  - Direct database queries, authorization checks, and preview generation logic in `get_resource_detail` (lines 83-98):
    ```python
    result = await db.execute(
        select(Resource).where(Resource.id == id, Resource.is_deleted == False)
    )
    ...
    preview = None
    if resource.type in ("document", "reading") and resource.content:
        preview = resource.content[:500]
    ```
  - Direct task management and call to the external agent client in `generate_resources` (lines 137-170):
    ```python
    task = AsyncTask(
        task_type="resource_generation",
        status="processing",
        user_id=current_user.id,
        course_id=req.course_id,
        result=catalog_context.model_dump(),
    )
    db.add(task)
    ...
    await agent_client.post_json("/agent/v1/resources/generate", payload)
    ```
- **`frontend/src/pages/ResourceDetail.jsx`**:
  - Custom React state and manual `useEffect` tracking (lines 33-46):
    ```javascript
    const [resource, setResource] = useState(null);
    const [loading, setLoading] = useState(true);
    ...
    useEffect(() => {
      if (id) {
        learningService.getResourceDetail(id).then(res => {
          if (res.code === 200) setResource(res.data);
        }).catch(() => setResource(null))
        .finally(() => setLoading(false));
      }
    }, [id]);
    ```
- **`frontend/src/hooks/useCatalog.js`**:
  - Custom React states for data loading, task statuses, and manual polling loops via `setTimeout` (lines 267-291, 324-348, etc.):
    ```javascript
    const pollTask = async () => {
      try {
        const res = await taskService.getTaskStatus(activeTask.task_id);
        ...
        if (task.status === 'completed' || task.status === 'failed') {
          authoritativeTerminalTaskIdsRef.current.add(task.task_id);
          await handleTerminalTask(task);
        } else if (!cancelled) {
          timeoutId = setTimeout(pollTask, 2000);
        }
      } catch (err) { ... }
    };
    ```
- **`backend/tests/test_course_catalogs.py`**:
  - Covers CRUD actions on `GET/POST /api/v1/admin/course-catalogs` and materials creation.
- **`backend/tests/test_resource_detail.py`**:
  - Covers unauthorized, not found, forbidden, preview content slicing, and resource response schema matching.

---

## 2. Logic Chain
1. Direct file writing, update queries, and count check queries in `catalogs.py` routes violate the Clean Architecture principle of separating routing logic from core domain services.
2. In `resources.py`, all endpoints query database sessions directly, perform pagination calculations, check access, and generate content previews inline. This results in heavy controllers (fat routers) and complete lack of testable/reusable service logic.
3. On the frontend, `ResourceDetail.jsx` and `CatalogManagementPanel.jsx` fetch data manually via `useEffect` hooks, leading to duplicate code, lack of request deduplication, lack of global caching, and no background sync capabilities.
4. The hook `useCatalog.js` implements a monolithic manual state machine and 4 parallel custom `setTimeout` polling handlers. This requires complex sequence refs (`requestSeqRef`, `openRef`, `catalogIdRef`, `authoritativeTerminalTaskIdsRef`) to avoid race conditions.
5. In contrast, the project already uses SWR (e.g. `useLearningEffects.js`, `useTeacherConsoleData.js`).
6. Replacing manual fetching/polling with custom SWR hooks (`useResourceDetail`, `useCourseCatalogs`, and standard conditional SWR task polling) would drastically simplify state management, eliminate race conditions, and clean up boilerplate.
7. Similarly, moving all backend router queries/mutations to `ResourceService`, `CatalogMaterialService`, and `CatalogService` would result in thin, declarative routers.

---

## 3. Caveats
- I did not execute the backend tests or frontend tests because the non-interactive permission prompt timed out.
- The refactoring plan relies on the presence of standard SWR and SQLAlchemy configurations, which match the pattern observed in other modules (e.g., `useLearningEffects` and `CatalogService`).

---

## 4. Conclusion
The Resource Generation & Mounting module needs refactoring to separate routing logic from business logic (adhering to MVVM on the frontend and Router-Service-DB division on the backend). The proposed refactoring plan is fully detailed in `analysis.md`.

---

## 5. Verification Method
- **Backend Verification:**
  - Verify that the pytest tests still pass after refactoring by running:
    ```bash
    cd backend && python3 -m pytest tests/test_course_catalogs.py tests/test_resource_detail.py -v
    ```
  - Verify syntax using compilation check:
    ```bash
    python3 -m py_compile backend/app/api/v1/catalogs.py backend/app/api/v1/resources.py backend/app/services/resource_service.py
    ```
- **Frontend Verification:**
  - Build the React app successfully without any linting or compilation errors:
    ```bash
    cd frontend && npm run lint && npm run build
    ```
  - Run unit tests to verify mocked services:
    ```bash
    cd frontend && npm run test:unit
    ```
