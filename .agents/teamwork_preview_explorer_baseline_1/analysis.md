# Resource Generation & Mounting Baseline Codebase Analysis

## 1. Backend Router Structure & Flaws

During our read-only investigation of the backend, we analyzed the router files `backend/app/api/v1/catalogs.py` and `backend/app/api/v1/resources.py`. We observed significant business logic leakages and direct SQL queries within the route handlers:

### `backend/app/api/v1/catalogs.py`
- **File Stream & Operation Leakage**: The route `admin_upload_catalog_material` (lines 106-205) handles chunk-by-chunk file parsing (`await file.read(UPLOAD_CHUNK_SIZE)`), disk storage directory creation (`target_path.parent.mkdir`), validation (file size constraints, file type checks), and error cleanup (`remove_material_dir`).
- **Transaction & DB Controller Leakage**: It also handles transactional SQL operations directly, executing manual database updates to `CourseCatalog` (incrementing material count, changing status and knowledge status) and additions to `CourseCatalogMaterial` under a `try/except` block with manual rollbacks (`await db.rollback()`).
- **Direct Queries**: The route `admin_get_catalog_knowledge_status` (lines 255-299) directly builds and executes SQL aggregation queries (`select(func.count()).where(...)`) to count `uploaded` and `failed` materials:
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

### `backend/app/api/v1/resources.py`
- **Direct Database Queries & Formatting**:
  - `list_resources` (lines 25-74) executes direct SQL query selection on the `Resource` table filtering by `course_id`, `type`, and `keyword`. It calculates offset pagination, executes `db.execute()`, maps records to scalars, and formats JSON outputs within the router.
  - `get_resource_detail` (lines 77-117) performs a manual query, checks authorization permissions (course members vs. catalog access), generates text previews (`content[:500]`), and maps the JSON response structure.
- **External API & Task Control**: `generate_resources` (lines 127-181) handles creation of the `AsyncTask`, handles error response mappings for `AgentServiceError`, updates state, and manages transaction commits.

---

## 2. Frontend Architecture & Flaws

We inspected the catalog drawer component `CourseCatalogDrawer.jsx`, page `ResourceDetail.jsx`, and custom hooks.

### `ResourceDetail.jsx`
- **Lack of Caching**: It uses a standard React `useEffect` to fetch data via `learningService.getResourceDetail(id)` (lines 39-46) and manages local component state via `useState`. There is no caching, resulting in redundant network requests upon component remounts.
- **Manual Loading/Error States**: Loading (`loading`) and data states are handled completely manually.

### `useCatalog.js` (Custom Drawer Hook)
- **Excessive Complexity (775 lines)**: This hook maintains more than 20 individual React states manually (e.g. `materials`, `resources`, `knowledgeStatus`, `uploadQueue`, `activeTask`, `generationTask`, `knowledgeGraphTask`, etc.).
- **Manual Data Syncing**: Inside `refreshDetails` (lines 127-204), it issues parallel API requests using `Promise.all` and maps responses back to separate states, relying on a manual `requestSeqRef` counter to safeguard against out-of-order responses.
- **Manual Polling Loops**: It sets up four distinct `useEffect` hooks with recursive `setTimeout` pollers (polling every 2000ms) to check background task updates from `taskService.getTaskStatus`. This is highly verbose, error-prone, and ignores standard HTTP caching conventions.

---

## 3. Baseline Test Coverage

We examined the following existing tests:

### Backend Tests
- `backend/tests/test_course_catalogs.py`:
  - Validates CourseCatalog, CourseCatalogMaterial, and CourseOffering SQLAlchemy schema models.
  - Integration tests for Admin catalogs CRUD (`/api/v1/admin/course-catalogs` and `/api/v1/admin/course-catalogs/{id}`) and material creation constraints (ensuring uploads are blocked when in-progress).
  - Verifies Teacher catalog-to-offering binding gates.
- `backend/tests/test_resource_detail.py`:
  - Integration tests for `GET /api/v1/resources/{id}` covering authorization, 404 handling, cross-course access checks, and `content_preview` truncation logic.
- `backend/tests/test_resources_async.py`:
  - Integration tests for the async resource generation pipeline. Covers the `/generate` endpoint, webhook handler verification, payload authentication (`X-Webhook-Secret`), and webhook idempotency.

### Frontend Tests
- `frontend/src/api/services/__tests__/catalog.test.js` & `frontend/src/services/catalogService.test.js`:
  - Uses `vitest` and Axios mock clients to verify API dispatch endpoints and payload formatting.
- `frontend/src/hooks/__tests__/useRecommendedResources.test.js`:
  - Unit tests for SWR hook `useRecommendedResources`, mocking `learningService.getResources`.

---

## 4. Proposed Refactoring Plan (MVVM Pattern)

### Backend: Refactor Business Logic & Queries into Services
1. **Create `ResourceService` (`backend/app/services/resource_service.py`)**:
   Encapsulate all querying, task creations, and agent generation calls out of `resources.py`.
   - `list_resources(self, course_id, current_user, type, keyword, page, page_size) -> tuple[list[Resource], int]`
   - `get_resource_detail(self, id, current_user) -> Resource`
   - `generate_resources(self, req, current_user, webhook_url) -> AsyncTask`
2. **Clean up `resources.py` Router**:
   Inject `ResourceService(db = Depends(get_db))` and delegation routes.
3. **Move Upload & Knowledge Status queries from `catalogs.py` to `CatalogMaterialService`**:
   - Move stream writing and file validation in `admin_upload_catalog_material` to `CatalogMaterialService.upload_material(...)`.
   - Move pending/failed count queries in `admin_get_catalog_knowledge_status` to `CatalogMaterialService.get_catalog_status_summary(...)`.

### Frontend: SWR-Based MVVM Design
1. **Migrate Views to Custom SWR Hooks (ViewModels)**:
   - **`useResourceDetail(id)`**: Wraps SWR caching for resource detail.
     ```javascript
     export function useResourceDetail(id) {
       const { data: res, error, isLoading } = useSWR(
         id ? `/api/v1/resources/${id}` : null,
         () => fetcherWrapper(learningService.getResourceDetail(id))
       );
       return { resource: res?.data || null, error, isLoading };
     }
     ```
   - **`useCourseCatalogs(params)`**: Manages catalogs listing, cache mutation on creation, and loading indicators.
2. **Refactor `useCatalog.js` to utilize Independent SWR Sub-Hooks**:
   Instead of one bloated state machine, fetch each drawer dependency as an SWR subscription:
   - `useCatalogMaterials(catalogId)`
   - `useCatalogResources(catalogId)`
   - `useCatalogKnowledgeGraph(catalogId)`
   - `useCatalogKnowledgeStatus(catalogId)`
3. **Dynamic Polling via SWR `refreshInterval`**:
   Replace manual `setTimeout` polling with SWR's native, reactive polling capability:
   ```javascript
   const isIngesting = statusData?.status === 'ingesting' || statusData?.knowledge_status === 'ingesting';
   const { data: statusRes } = useSWR(
     open && catalogId ? `/admin/course-catalogs/${catalogId}/knowledge-status` : null,
     () => fetcherWrapper(catalogService.getCourseCatalogStatus(catalogId)),
     { refreshInterval: isIngesting ? 2000 : 0 }
   );
   ```
   This guarantees that if the background task completes, SWR will automatically cease polling, update the local cache, and trigger reactive UI updates cleanly.
