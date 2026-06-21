# Scope: Resource Generation & Mounting Refactoring

## Architecture
- **Frontend**: `ResourceDetail.jsx` refactored to use custom SWR hook `useResourceDetail` (separating View from data-fetching, MVVM). Refactor catalogs components/hooks to utilize cleaner separation or SWR-based status fetches if applicable.
- **Backend**: `catalogs.py` and `resources.py` refactored into thin Routers, moving business logic, file chunking/writes, and direct SQL queries to their corresponding service files (`catalog_service.py`, `resource_service.py` etc.).
- **Agent Service**: `resources` agent service.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|---|---|---|---|
| 1 | Baseline Verification | Capturing baseline tests for catalogs, resources and personalized resources | None | DONE |
| 2 | Backend Catalogs & Resources Refactoring | Refactor `catalogs.py` and `resources.py` to move business logic and direct queries to services, ensuring thin routers. Update/add tests | M1 | DONE |
| 3 | Frontend ResourceDetail & Catalogs Refactoring | Refactor `ResourceDetail.jsx` to use custom SWR hooks (`useResourceDetail`), separate view from API calls (MVVM) | M2 | DONE |
| 4 | Final Integration & Verification | Run all pytest/Vitest suites for catalogs/resources; run Forensic Integrity Audit | M3 | IN_PROGRESS |

## Interface Contracts
- Backend `catalogs` exposes admin endpoints for uploading material, starts ingestion, generates KG and resources.
- Backend `resources` router exposes `/api/v1/resources` (GET list, GET detail, POST generate).
