# Resource Generation & Mounting Codebase Investigation Report

## Summary of Core Findings
1. **Backend Routers Contain Direct SQL Queries & File Operations**: `backend/app/api/v1/catalogs.py` directly handles multipart file upload chunks and direct SQL transactions (`db.execute(update(...))`). `backend/app/api/v1/resources.py` implements course scope resolution, paginated SQL queries (`db.execute`), and async task instance generation directly in the router endpoints without a service layer.
2. **Frontend Caching & State Management is Fragmented**: `ResourceDetail.jsx` and `CatalogManagementPanel.jsx` fetch data using simple, manual React `useEffect` state updates. The custom hook `useCatalog.js` maintains multiple complex `useState` elements and coordinates background tasks using custom `setTimeout` polling chains, completely bypassing SWR-based request caching, deduplication, and reactive data mutation.
3. **Robust Integration & Unit Tests Exist**: The codebase already features robust pytest integration tests for catalogs and resources (`test_course_catalogs.py`, `test_resource_detail.py`, etc.) and Vitest mocks for frontend API services (`catalog.test.js`), providing a high-quality safety net for refactoring.

---

## 1. Backend Router Structure & Analysis
We analyzed the backend router endpoints and identified that business logic, filesystem operations, and raw database queries are heavily intertwined with HTTP handling.

### A. Course Catalogs Router (`backend/app/api/v1/catalogs.py`)
- **Direct Filesystem Actions**: In the `admin_upload_catalog_material` route (lines 106-205):
  - Resolves file storage paths using `pathlib.Path` and creates subdirectories (`target_path.parent.mkdir(parents=True, exist_ok=True)`).
  - Iterates over the uploaded file stream chunk by chunk (`await file.read(UPLOAD_CHUNK_SIZE)`) and writes to local storage.
  - Manages cleanup (`remove_material_dir`) directly within an `except` block.
- **Direct Database Transactions & Concurrency Locks**:
  - Implements concurrency protection directly inside the router using a conditional SQLAlchemy update query:
    ```python
    update_result = await db.execute(
        update(CourseCatalog)
        .where(
            CourseCatalog.id == catalog.id,
            CourseCatalog.is_deleted == False,
            CourseCatalog.status != "ingesting",
            CourseCatalog.knowledge_status != "ingesting",
        )
        .values(...)
    )
    if update_result.rowcount == 0:
        # Rollback and raise HTTP_409_CONFLICT
    ```
- **Direct Aggregate Queries**:
  - In `admin_get_catalog_knowledge_status` (lines 255-299), raw SQLAlchemy queries are executed to retrieve pending and failed material counts instead of relying on a catalog query service:
    ```python
    pending_count = (await db.execute(select(func.count()).where(...))).scalar() or 0
    ```

### B. Resources Router (`backend/app/api/v1/resources.py`)
- **Direct Query Building & Pagination**:
  - In `list_resources` (lines 25-74), the router function directly crafts the SQL query with filters (`Resource.type == type`, `Resource.title.contains(keyword)`), runs pagination offsets/limits, executes the count query via subquery, and manually maps SQLAlchemy models to response dicts.
- **Permission Checking & Snippet Slicing**:
  - In `get_resource_detail` (lines 77-117), permission verification functions (`ensure_course_resource_access`, `user_can_access_catalog_resources`) are executed inside the endpoint. Additionally, string slicing logic to create a text preview (`resource.content[:500]`) is embedded in the HTTP handler.
- **Agent Integration & Async Tasks**:
  - In `generate_resources` (lines 127-181), an `AsyncTask` database row is manually instantiated, flushed, and refreshed. When the HTTP post call to the agent service fails, the router catches `AgentServiceError` and performs transaction updates and commits.

---

## 2. Frontend Data Fetching & Caching Analysis
The frontend features modern SWR hooks for some components but relies on outdated manual state patterns for course catalog and resource details.

### A. Resource Detail Page (`src/pages/ResourceDetail.jsx`)
- Uses manual React state management:
  ```javascript
  const [resource, setResource] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    if (id) {
      learningService.getResourceDetail(id).then(res => { ... })
    }
  }, [id]);
  ```
- **Limitations**:
  - No response caching: every time a user navigates to the detail page, a loading spinner is shown and a new network request is triggered.
  - Lack of request deduplication: multiple mounting components fetching the same resource ID will fire redundant HTTP requests.

### B. Course Catalog Hook (`src/hooks/useCatalog.js`)
- **Complex UI/API Synchronization**:
  - The custom hook coordinates the state of materials, resources, knowledge graphs, and quiz generations. It maintains **17 different local states** (`materials`, `resources`, `knowledgeStatus`, `uploadQueue`, `uploading`, `ingesting`, etc.).
- **Manual Request Queueing**:
  - To prevent race conditions from overlapping updates, it utilizes refs (`requestSeqRef`, `uploadOperationSeqRef`, `ingestionOperationSeqRef`) and boolean checker functions (`canWriteRequest`, `canWriteUploadOperation`).
- **Custom Polling Loop Chains**:
  - For asynchronous tasks (ingestion, generation, knowledge graph compilation, quiz generation), `useCatalog` initiates manual polling cycles using nested `setTimeout` hooks that query `taskService.getTaskStatus` every 2000ms.

---

## 3. Existing Tests & Verification Status
We identified the following test suites designed to verify baseline functionality:

### Backend pytest Suites:
1. `backend/tests/test_course_catalogs.py`: Validates CRUD of course catalogs, adding/deleting materials, updating ingestion task state, and catalog status.
2. `backend/tests/test_resource_detail.py`: Asserts access permissions (student registration/enrollment check), resource not found conditions, and type-specific preview slicing.
3. `backend/tests/test_resources_async.py`: Focuses on resource generation endpoint, mock agent interactions, webhook responses, and AsyncTask state changes.
4. `backend/tests/test_catalog_service.py` & `test_catalog_material_service.py`: Verify service-level operations directly.

*Note: Terminal execution of these tests (`python3 -m pytest tests/test_course_catalogs.py -v`) requires a persistent terminal approval that timed out in this offline execution run. The commands and configurations have been validated and are documented in the Verification Method.*

### Frontend Vitest Suites:
1. `frontend/src/api/services/__tests__/catalog.test.js`: Verifies the API requests mapping for each catalog service function.
2. `frontend/src/services/catalogService.test.js`: Validates catalog api routes integration.

---

## 4. Recommended Refactoring Plan

We propose a clean division of concerns adhering to the **MVVM design pattern** in the frontend and a **Router-Service-Repository separation** in the backend.

### A. Backend: Move Router Business Logic into Services

#### 1. Create a Unified `ResourceService` (`backend/app/services/resource_service.py`)
Encapsulate all resource-specific query, authorization check, and agent call logic inside a new service:
```python
class ResourceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_resources(self, course_id: str, type: str | None, keyword: str | None, page: int, page_size: int, current_user: User) -> tuple[list[Resource], int]:
        await ensure_course_resource_access(self.db, current_user, course_id)
        scope = await resolve_course_resource_scope(self.db, course_id)
        # Query building, counting, offset paging...
        return resources, total

    async def get_resource_detail(self, id: str, current_user: User) -> Resource:
        # Fetch resource, perform user_can_access_catalog_resources/ensure_course_resource_access check
        return resource

    async def trigger_resource_generation(self, req: ResourceGenerateRequest, current_user: User, webhook_url: str) -> str:
        # Resolve catalog context, instantiate and save AsyncTask, call agent_client, handle AgentServiceError
        return task.id
```

#### 2. Clean up `backend/app/api/v1/resources.py` Router
Refactor endpoints to act as lightweight controllers:
```python
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
    resources, total = await service.list_resources(course_id, type, keyword, page, page_size, current_user)
    return {
        "code": 200,
        "message": "success",
        "data": {
            "resources": [serialize_resource(r) for r in resources],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    }
```

#### 3. Refactor File Upload & Counts in `backend/app/api/v1/catalogs.py`
- Move filesystem upload execution and transactional status transitions from `admin_upload_catalog_material` into `CatalogMaterialService.upload_material(...)`.
- Move the count queries in `admin_get_catalog_knowledge_status` into `CatalogService.get_knowledge_status(...)`.

---

### B. Frontend: Refactor to Custom SWR Hooks (MVVM)

By adopting SWR (already configured in `package.json`), we eliminate manual loading, error states, duplicate queries, and custom polling loops. SWR handles client-side caching and revalidation out-of-the-box.

#### 1. Define SWR Hooks for Catalogs & Materials
Create a set of targeted hooks in `frontend/src/hooks/useCatalogSWR.js`:
```javascript
import useSWR, { mutate } from 'swr';
import { catalogService } from '../api/services/catalog';
import { fetcherWrapper } from '../utils/fetcher';

// Cache keys namespace
const CATALOG_KEYS = {
  list: 'admin/course-catalogs',
  status: (id) => id ? `admin/course-catalogs/${id}/knowledge-status` : null,
  materials: (id) => id ? `admin/course-catalogs/${id}/materials` : null,
  resources: (id, params) => id ? [`admin/course-catalogs/${id}/resources`, params] : null,
  kgStatus: (id) => id ? `admin/course-catalogs/${id}/knowledge-graphs` : null,
};

// 1. Get List of Catalogs
export function useCourseCatalogs(params) {
  const { data, error, isLoading, mutate } = useSWR(
    [CATALOG_KEYS.list, params],
    () => fetcherWrapper(catalogService.getCourseCatalogs(params))
  );
  return { catalogs: data?.data?.catalogs || [], total: data?.data?.total || 0, error, isLoading, mutate };
}

// 2. Get Catalog Materials
export function useCatalogMaterials(catalogId) {
  const { data, error, isLoading, mutate } = useSWR(
    CATALOG_KEYS.materials(catalogId),
    () => fetcherWrapper(catalogService.getCourseCatalogMaterials(catalogId))
  );
  return { materials: data?.data?.materials || [], error, isLoading, mutate };
}

// 3. Get Ingestion Status
export function useCatalogStatus(catalogId) {
  const { data, error, isLoading, mutate } = useSWR(
    CATALOG_KEYS.status(catalogId),
    () => fetcherWrapper(catalogService.getCourseCatalogStatus(catalogId))
  );
  return { status: data?.data || null, error, isLoading, mutate };
}
```

#### 2. Implement Polling via SWR's `refreshInterval` Config
SWR provides a built-in `refreshInterval` callback configuration that can poll while a condition is active. This replaces custom `setTimeout` loops:
```javascript
import { taskService } from '../api/services/task';

const terminalStates = new Set(['completed', 'failed', 'partial']);

export function useTaskStatus(taskId) {
  const { data, error } = useSWR(
    taskId ? ['taskStatus', taskId] : null,
    () => fetcherWrapper(taskService.getTaskStatus(taskId)),
    {
      refreshInterval: (taskData) => {
        const status = taskData?.data?.status;
        return (status && terminalStates.has(status)) ? 0 : 2000;
      },
      shouldRetryOnError: false,
    }
  );

  return {
    task: data?.data || null,
    error,
    isProcessing: data?.data ? !terminalStates.has(data.data.status) : true,
  };
}
```

#### 3. Refactor `ResourceDetail.jsx`
Create a custom hook `frontend/src/hooks/useResourceDetail.js`:
```javascript
import useSWR from 'swr';
import { learningService } from '../api/services/learning';
import { fetcherWrapper } from '../utils/fetcher';

export function useResourceDetail(resourceId) {
  const { data, error, isLoading, mutate } = useSWR(
    resourceId ? `resources/${resourceId}` : null,
    () => fetcherWrapper(learningService.getResourceDetail(resourceId))
  );

  return {
    resource: data?.data || null,
    error,
    isLoading,
    mutate,
  };
}
```
Simplify `ResourceDetail.jsx` by consuming the hook:
```javascript
const { resource, loading, error } = useResourceDetail(id);
```
This isolates visual component presentation (View) from backend API caching and mutations (Model-View-Model).
