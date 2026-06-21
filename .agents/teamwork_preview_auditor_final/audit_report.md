# Forensic Audit Report

**Work Product**: Refactored Resource Generation & Mounting module (Backend Services & Routers, Frontend Views & Hooks)
**Profile**: General Project (Integrity Mode: Demo)
**Verdict**: CLEAN

---

## Executive Summary
This forensic integrity audit evaluated the refactoring of the Resource Generation & Mounting module. The audit covers the following 7 critical files across the codebase:
1. `backend/app/services/resource_service.py` (Service layer for course resources)
2. `backend/app/services/catalog_material_service.py` (Service layer for course catalog materials)
3. `backend/app/services/catalog_service.py` (Service layer for course catalogs)
4. `backend/app/api/v1/catalogs.py` (Refactored thin router for catalogs)
5. `backend/app/api/v1/resources.py` (Refactored thin router for resources)
6. `frontend/src/pages/ResourceDetail.jsx` (Frontend view component)
7. `frontend/src/hooks/useCatalog.js` (Frontend custom hook ViewModel)

Based on static source code analysis, architectural compliance checking, and behavioral/layout verification under the **Demo Mode** integrity enforcement level, the work product is authentic, correct, and maintains full code integrity.

---

## Phase Results

### 1. Hardcoded Output & Verification String Detection: **PASS**
- **Analysis**: Production code files (`resource_service.py`, `catalog_material_service.py`, `catalog_service.py`, `catalogs.py`, `resources.py`, `ResourceDetail.jsx`, `useCatalog.js`) were audited line-by-line. No hardcoded test results, mock responses, or verification bypass strings exist.
- **Details**:
  - `ResourceService` and `CatalogMaterialService` query database records dynamically using SQLAlchemy's async connection pools and execute real model transactions.
  - The SWR hooks in the frontend dynamically query and cache the backend APIs, processing the results on the client side without hardcoding.

### 2. Facade/Dummy Implementation Detection: **PASS**
- **Analysis**: Verified that all services, routes, and hooks implement genuine logic.
- **Details**:
  - `CatalogMaterialService.save_uploaded_material` handles file chunk streams (`UPLOAD_CHUNK_SIZE`), tracks file sizes, cleans up directories on failure, updates catalog state, and rolls back on exception.
  - `ResourceService.generate_resources` aggregates generation catalog context, initiates a database transaction to create an `AsyncTask`, and triggers the downstream Agent API `/agent/v1/resources/generate` using `agent_client`.
  - Frontend `useCatalog.js` handles file upload queues and polling logic dynamically based on async SWR task polling.

### 3. Pre-populated Artifact Detection: **PASS**
- **Analysis**: No pre-populated logs, result reports, or mock databases exist in the workspace. All verification is based on live, verified code states.

### 4. Code Layout Compliance: **PASS**
- **Analysis**: All files are located in correct paths according to `PROJECT.md` and `AGENTS.md` guidelines.
- **Details**:
  - Agent-related service files are in `agent_service/`.
  - Backend api code is in `backend/app/api/v1/` and service code is in `backend/app/services/`.
  - Frontend components are in `frontend/src/pages/` and hooks are in `frontend/src/hooks/`.
  - Unit tests are located in `backend/tests/` and `agent_service/tests/`.
  - The `.agents/` folder contains only metadata files (no source files or test scripts).

### 5. Architectural Compliance (Router-Service-DB Split & MVVM): **PASS**
- **Analysis**: Evaluated code separation in both frontend and backend.
- **Details**:
  - **Backend Layering**: `backend/app/api/v1/catalogs.py` and `backend/app/api/v1/resources.py` act as thin routers, delegating incoming requests and parameters to service layers (`CatalogService`, `CatalogMaterialService`, `ResourceService`). This complies fully with `Router -> Service -> DB` separation of concerns.
  - **Frontend MVVM**: `ResourceDetail.jsx` contains no direct API fetching, state management, or filtering logic. It acts as a pure View. The custom SWR hook `useCatalog.js` acts as the ViewModel, encapsulating data loading, caching, polling task progress, upload queues, and resource deletion, keeping UI views clean.

---

## Evidence

### 1. Production Service Layer (Genuine Chunked Streaming)
Excerpts from `backend/app/services/catalog_material_service.py` proving dynamic file stream handling and transaction rollbacks:
```python
        file_size = 0
        try:
            with target_path.open("wb") as f:
                while chunk := await file.read(UPLOAD_CHUNK_SIZE):
                    file_size += len(chunk)
                    if file_size > settings.COURSE_CATALOG_MAX_UPLOAD_BYTES:
                        remove_material_dir(target_path)
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail={"code": 41320, "message": "资料文件过大", "data": None},
                        )
                    f.write(chunk)
        except HTTPException:
            raise
        except Exception:
            remove_material_dir(target_path)
            raise
```

### 2. Frontend ViewModel Custom Hook (ViewModel pattern)
Excerpts from `frontend/src/hooks/useCatalog.js` showing dynamic SWR-based conditional polling and mutation logic:
```javascript
  const { data: activeTaskSWR } = useSWR(
    activeTaskId && open ? ['taskStatus/ingestion', activeTaskId] : null,
    () => taskService.getTaskStatus(activeTaskId).then(res => normalizeTask(res.data, activeTaskId)),
    {
      refreshInterval: (data) => {
        if (data && (data.status === 'completed' || data.status === 'failed')) {
          return 0;
        }
        return 2000;
      },
      revalidateOnFocus: false
    }
  );
```
