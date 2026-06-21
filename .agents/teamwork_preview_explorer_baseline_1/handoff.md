# Handoff Report — teamwork_preview_explorer_baseline_1

## 1. Observation
We have inspected the following key files in the codebase:
- **Backend routers**:
  - `backend/app/api/v1/catalogs.py` (Lines 106-205, `admin_upload_catalog_material` contains manual file stream chunks reading/writing, size limit validation, custom exception rollbacks, and DB insertions. Lines 255-299, `admin_get_catalog_knowledge_status` contains direct SQL queries `select(func.count()).select_from(CourseCatalogMaterial)...` to count materials).
  - `backend/app/api/v1/resources.py` (Lines 25-74, `list_resources` contains offset pagination calculation, keyword filtering, and direct query execution `await db.execute(...)`. Lines 77-117, `get_resource_detail` performs direct querying, permission checks, and text previews extraction).
- **Frontend pages / hooks**:
  - `frontend/src/pages/ResourceDetail.jsx` (Lines 39-46 contains `useEffect` making raw API calls with `learningService.getResourceDetail(id)` without caching).
  - `frontend/src/hooks/useCatalog.js` (A 775-line hook maintaining manual state logic, parallel data synchronization, and recursive `setTimeout` polling intervals to fetch background task status).
- **Existing tests**:
  - `backend/tests/test_course_catalogs.py` (CRUD, status ready gates)
  - `backend/tests/test_resource_detail.py` (detailed authorization checks)
  - `backend/tests/test_resources_async.py` (resource generation & webhooks)
  - `frontend/src/api/services/__tests__/catalog.test.js` & `frontend/src/services/catalogService.test.js` (axios mock adapter checks)
  - `frontend/src/hooks/__tests__/useRecommendedResources.test.js` (useRecommendedResources SWR hook mock test)
- **Command execution**:
  - Command: `../.venv/bin/pytest tests/test_course_catalogs.py tests/test_resource_detail.py -v` inside `/home/yezisama/workspace/workflow/EDUagent/backend`
  - Result: `Encountered error in step execution: Permission prompt for action 'command' on target '../.venv/bin/pytest tests/test_course_catalogs.py tests/test_resource_detail.py -v' timed out waiting for user response.`

## 2. Logic Chain
- **Leakage in Routers**: The direct presence of SQL queries and filesystem stream management in `catalogs.py` and `resources.py` violates the project-scoped architecture directive (from `AGENTS.md`) which dictates a clean, layered partition (`Router -> Service -> DB`).
- **Bloat in Frontend Hooks**: The manual polling loops and state synchronization inside `useCatalog.js` introduce unnecessary complexity and susceptibility to race conditions.
- **SWR & MVVM Alignment**: Transitioning frontend requests to SWR hooks like `useResourceDetail` and using SWR's native `refreshInterval` configuration eliminates local UI component state management. SWR hooks act as ViewModels containing data syncing logic, and views remain stateless representations.

## 3. Caveats
- Since command permissions timed out, we were not able to execute the backend tests or frontend tests in the shell. We assumed the codebase is currently functional.

## 4. Conclusion
We recommend refactoring:
- **Backend**: Move file/stream processing and count queries in `catalogs.py` to `CatalogMaterialService`. Move SQL queries, permission checks, and AsyncTask generation from `resources.py` into a new `ResourceService` class.
- **Frontend**: Replace manual `useEffect` fetches and local state-based polling loops with custom SWR hooks leveraging native cache and `refreshInterval` polling mechanism.

## 5. Verification Method
To verify:
1. Run the backend tests:
   ```bash
   cd backend
   ../.venv/bin/pytest tests/test_course_catalogs.py tests/test_resource_detail.py tests/test_resources_async.py -v
   ```
2. Run the frontend unit tests:
   ```bash
   cd frontend
   npm run test:unit
   ```
3. Inspect `analysis.md` in `/home/yezisama/workspace/workflow/EDUagent/.agents/teamwork_preview_explorer_baseline_1/analysis.md`.
