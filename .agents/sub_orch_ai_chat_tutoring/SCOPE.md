# Scope: AI Chat & Tutoring Refactoring

## Architecture
- Frontend: `AIChat.jsx` component split into subcomponents (`SidebarHistory.jsx`, `SidebarResources.jsx`, `ChatArea.jsx`) and SWR hook for state/data fetch.
- Backend: `tutoring.py` (already refactored), `evaluation.py` (needs refactoring into thin Router, moving business logic and background refresh tasks into `evaluation_service.py`).
- Agent Service: `tutoring` agent service.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|---|---|---|---|
| 1 | Baseline Verification | Query/establish boundaries, run pytest on tutoring/evaluation to capture baseline | None | DONE |
| 2 | Backend Evaluation Refactoring | Refactor `evaluation.py` to extract `evaluation_service.py` (Router-Service-DB split), add unit tests | M1 | DONE |
| 3 | Frontend AIChat Audit & Refactoring | Audit component split and SWR usage in `AIChat`, clean up unused imports or console logs | M2 | DONE |
| 4 | Final Integration & Verification | Run full unit, integration, and E2E tests for the AI Chat & Tutoring module | M3 | DONE |

## Interface Contracts
- Backend `evaluation` router exposes standard REST endpoints: `/api/v1/evaluation` (GET) and `/api/v1/evaluation/refresh` (POST).
- Interacts with Agent `POST /agent/v1/evaluation/generate` for background refresh.
