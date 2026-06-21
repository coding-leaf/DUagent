# Resource Generation & Mounting Codebase Baseline Analysis

## 1. Executive Summary
This report analyzes the backend and frontend architecture for the **Resource Generation & Mounting** module of the `EDUagent` system. 
- **Backend:** The router `catalogs.py` has a mixture of service calls and raw file operations/DB operations (specifically on material upload/status checks). The router `resources.py` completely lacks a service layer, performing direct ORM database queries, pagination, and external Agent client requests inline.
- **Frontend:** `ResourceDetail.jsx` and `CatalogManagementPanel.jsx` rely on manual, stateful `useEffect` data fetching and do not use the caching/deduplication capabilities of SWR. The custom hook `useCatalog.js` contains complex manual `setTimeout` polling loops for four different types of asynchronous tasks, which is highly error-prone.
- **Recommendation:** Implement a clean MVVM pattern on the frontend with custom SWR hooks (replacing manual effects and polling loops) and build a robust `ResourceService` (together with expanding `CatalogMaterialService`/`CatalogService`) on the backend to separate routing from business and query logic.

---

## 2. Backend Router Analysis

### A. Course Catalogs (`backend/app/api/v1/catalogs.py`)
- **Structure:** Mostly delegates to `CatalogService`, `CatalogMaterialService`, `CatalogKGService`, etc.
- **Direct SQL / ORM Queries in Router:**
  - `GET /admin/course-catalogs/{catalog_id}/knowledge-status` (Lines 262-283): Direct ORM calls using `select(func.count())` to calculate pending and failed materials:
    ```python
    pending_count = (await db.execute(
        select(func.count()).select_from(CourseCatalogMaterial).where(...)
    )).scalar() or 0
    ```
- **File System & Transaction Operations in Router:**
  - `POST /admin/course-catalogs/{catalog_id}/materials/upload` (Lines 106-205): Handled completely inline.
    - File storage check (`SUPPORTED_MATERIAL_SUFFIXES` and `UPLOAD_CHUNK_SIZE`).
    - File system directory path computation and writing binary streams to disk:
      ```python
      with target_path.open("wb") as f:
          while chunk := await file.read(UPLOAD_CHUNK_SIZE):
              ...
      ```
    - Direct transactional `db.execute(update(CourseCatalog)...)` and row count validation.
    - Exception handling calling file cleanup `remove_material_dir(target_path)` and `db.rollback()`.
  - `DELETE /admin/course-catalogs/{catalog_id}/materials/{material_id}` (Lines 237-252): Calls `await db.commit()` directly inside the router.

### B. Resources (`backend/app/api/v1/resources.py`)
- **Structure:** Completely lacks a service layer. The router does all data querying, authorization checks, pagination, and external API requests.
- **Direct SQL / ORM Queries in Router:**
  - `GET /api/v1/resources` (Lines 25-74): Direct `select(Resource).where(...)` ORM statement building, subquery count selection (`db.execute(select(func.count()).select_from(query.subquery()))`), offset/limit calculations, and dict mapping inside the router.
  - `GET /api/v1/resources/{id}` (Lines 77-117): Direct ORM query `select(Resource).where(Resource.id == id)` execution.
- **Inline Business Logic:**
  - Access control validation inside `get_resource_detail` (determining whether resource has `catalog_id` and conditionally checking catalog access vs course access).
  - Preview generation logic: `preview = resource.content[:500]` for `document`/`reading` resources.
- **Agent Service Coordination:**
  - `POST /api/v1/resources/generate` (Lines 126-181): Direct instantiation and management of `AsyncTask` in DB (flushing, updating status, error handling on `AgentServiceError`, and committing).

---

## 3. Frontend Data Fetching & Caching Analysis

### A. Resource Detail Page (`frontend/src/pages/ResourceDetail.jsx`)
- **Data Fetching:** Uses standard React state (`resource`, `loading`) and a raw `useEffect` hook to call `learningService.getResourceDetail(id)`.
- **Issues:**
  - **No Caching:** Every visit to the page triggers a fresh HTTP request.
  - **No Deduplication:** Simultaneous mounts of resource detail components would result in duplicate requests.
  - **No Automatic Revalidation:** Does not support automatic background updates (e.g., on focus or network reconnect).

### B. Catalog Management (`frontend/src/components/admin/CatalogManagementPanel.jsx`)
- **Data Fetching:** Performs manual fetching inside `fetchCatalogs` using `catalogService.getCourseCatalogs()`, triggered by a `useEffect` with a timer.
- **Issues:** Lacks SWR data management; has to maintain manual `loading` and `error` states, which increases boilerplate code.

### C. Course Catalog Drawer Hook (`frontend/src/hooks/useCatalog.js`)
- **Monolithic State:** Manages over 20 state variables (`materials`, `resources`, `activeTask`, `generationTask`, `knowledgeGraphTask`, etc.).
- **Manual Details Refresh:** A huge `Promise.all` (Lines 127-204) fetches four endpoints simultaneously. It requires custom sequence checking (`canWriteRequest`) to avoid state overrides from out-of-order responses.
- **Manual Task Polling (Lines 244-449):** Implements four parallel `useEffect` polling setups using `setTimeout(pollTask, 2000)`.
  - Highly complex: must handle cancellations, keep refs (`activeTaskRef`, `generationTaskRef`), and manually trigger detail refreshes and callbacks on completion.
  - SWR is not utilized, despite being installed in the project (`swr` dependency: `^2.4.1` in `package.json`).

---

## 4. Test Suite Assessment
The module is covered by several integration and unit test suites:
- **Backend Tests:**
  - `backend/tests/test_course_catalogs.py`: Verifies CRUD on catalogs, material creation (checks that uploads fail with 409 if catalog status is `ingesting`), and course-catalog binding constraint checks.
  - `backend/tests/test_resource_detail.py`: Validates the `GET /api/v1/resources/{id}` route under multiple scenarios (401 unauthorized, 404 not found, 403 forbidden, document preview slicing, all other type full content returns, and response schema checking).
  - `backend/tests/test_catalog_material_service.py` & `test_catalog_service.py`: Verify service-level unit logic.
- **Frontend Tests:**
  - `frontend/src/api/services/__tests__/catalog.test.js`: Mock-asserts that `catalogService` calls the correct backend routes with expected payloads.
  - `frontend/src/services/catalogService.test.js`: Uses `axios-mock-adapter` to verify route mapping and responses.
  - **Gap:** There are no tests for the `useCatalog.js` hook, making it a high-risk area during refactoring.

---

## 5. Proposed Refactoring Plan (MVVM & Service separation)

### Part A: Backend Refactoring Plan

#### 1. Implement `ResourceService`
Create a new file `backend/app/services/resource_service.py`:
- **Methods:**
  - `list_resources(db, course_id, resource_type, keyword, page, page_size, current_user)`: encapsulates access validation, ORM query construction, pagination, and total count fetching.
  - `get_resource_detail(db, resource_id, current_user)`: checks permissions (catalog vs course scope), fetches resource, slices preview for reading/document types, and increments views.
  - `start_resource_generation(db, course_id, chapter, knowledge_point, resource_types, current_user, webhook_url)`: manages catalog resolution, creates the database `AsyncTask`, calls `agent_client.post_json`, and handles `AgentServiceError` gracefully.

#### 2. Clean Router `resources.py`
Rewrite routes to delegate all logic to the new `ResourceService`:
```python
# app/api/v1/resources.py
@router.get("")
async def list_resources(
    course_id: str = Query(...),
    type: str = Query(None),
    keyword: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ResourceService(db)
    data = await service.list_resources(
        course_id=course_id,
        resource_type=type,
        keyword=keyword,
        page=page,
        page_size=page_size,
        current_user=current_user
    )
    return {"code": 200, "message": "success", "data": data}
```

#### 3. Refactor File Handling in `catalogs.py`
Move the file saving, transaction handling, and file system checking from `admin_upload_catalog_material` into `CatalogMaterialService`:
- **New Method:** `CatalogMaterialService.save_uploaded_material(catalog, file, storage_root, max_upload_bytes) -> CourseCatalogMaterial`
- Move `remove_material_dir` and `safe_filename` helpers into `CatalogMaterialService`.
- Move the database counts from `admin_get_catalog_knowledge_status` into `CatalogService.get_catalog_knowledge_status(catalog_id)`.

---

### Part B: Frontend Refactoring Plan

#### 1. Implement Custom SWR Hooks
Create new custom hooks to handle data fetching:
- **`useResourceDetail(id)`**:
  ```javascript
  import useSWR from 'swr';
  import { learningService } from '../api/services/learning';

  export function useResourceDetail(id) {
    const { data, error, isLoading, mutate } = useSWR(
      id ? ['/resources', id] : null,
      () => learningService.getResourceDetail(id)
    );
    return {
      resource: data?.data || null,
      loading: isLoading,
      error,
      mutate
    };
  }
  ```
- **`useCourseCatalogs(params)`**:
  ```javascript
  import useSWR from 'swr';
  import { catalogService } from '../api/services/catalog';

  export function useCourseCatalogs(params) {
    const { data, error, isLoading, mutate } = useSWR(
      ['/admin/course-catalogs', params],
      () => catalogService.getCourseCatalogs(params)
    );
    return {
      catalogs: data?.data?.catalogs || [],
      total: data?.data?.total || 0,
      loading: isLoading,
      error,
      mutate
    };
  }
  ```

#### 2. Simplify `useCatalog.js` with SWR Polling
- Eliminate the large `Promise.all` inside `refreshDetails` and instead define SWR keys for each sub-endpoint:
  - `materials`: `useSWR(catalogId ? ['/catalog', catalogId, 'materials'] : null, ...)`
  - `resources`: `useSWR(catalogId ? ['/catalog', catalogId, 'resources'] : null, ...)`
  - `status`: `useSWR(catalogId ? ['/catalog', catalogId, 'status'] : null, ...)`
  - `kgStatus`: `useSWR(catalogId ? ['/catalog', catalogId, 'kgStatus'] : null, ...)`
- **SWR-based Polling:** Replace manual `setTimeout` loops with SWR conditional polling:
  ```javascript
  // Poll a task if task_id is present and status is 'processing'
  const { data: taskData } = useSWR(
    activeTaskId ? ['/tasks', activeTaskId] : null,
    () => taskService.getTaskStatus(activeTaskId),
    {
      refreshInterval: (data) => (data?.status === 'processing' ? 2000 : 0),
      onSuccess: (data) => {
        if (data.status === 'completed' || data.status === 'failed') {
          // Revalidate catalog details automatically
          mutate(['/catalog', catalogId, 'status']);
        }
      }
    }
  );
  ```

#### 3. Update Components (MVVM)
- **`ResourceDetail.jsx`**:
  - Remove manual state tracking and raw `useEffect` for data fetching.
  - Call `const { resource, loading, error } = useResourceDetail(id)`.
  - Extract the activity tracking logic into a simple companion hook: `useResourceTracking(resource, nodeContext)`.
- **`CatalogManagementPanel.jsx`**:
  - Replace `catalogs`, `loadingCatalogs`, `fetchCatalogs` state management with `const { catalogs, loading, error, mutate } = useCourseCatalogs()`.
  - Re-fetch by calling SWR's `mutate()`.
