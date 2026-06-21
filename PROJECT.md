# Project: EDUagent Refactoring Phase 2

## Architecture
- **Frontend**: React SPA. MVVM architecture where custom SWR hooks act as ViewModels, Page files act as View Containers, and sub-components in `src/components/` act as Views.
- **Backend**: FastAPI. Layered architecture: Router (`backend/app/api/v1/`) -> Service (`backend/app/services/`) -> DB/Repository.
- **Agent Service**: Python FastAPI microservice. Zero direct DB access (stateless AI reasoning). Communicates with Backend via HTTP callbacks and Webhooks.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|---|---|---|---|
| 1 | AI Chat & Tutoring | Frontend `AIChat`, Backend `tutoring` & `evaluation`, Agent `tutoring` | None | DONE (Conv: d67cefab-553f-4f69-9acf-01899594be20) |
| 2 | Resource Generation & Mounting | Frontend `ResourceDetail` & Catalogs, Backend `resources` & `catalogs`, Agent `resources` | None | IN_PROGRESS (Conv: fb6ae602-7f1d-4a3e-a8fd-788cb518196a) |
| 3 | Core Learning | Frontend `LearningPath` & `Quiz`, Backend `learning-path` & `learning-activities`, Agent `learning_path` | None | PLANNED |

## Interface Contracts
### Backend ↔ Agent Service
- **Tutoring**: `POST /agent/v1/tutoring/chat` for stream generation.
- **Evaluation**: `POST /agent/v1/evaluation/generate` for offline background report generation.
- **Resource**: `POST /agent/v1/resources/generate` for custom resource material.
- **Learning Path**: `POST /agent/v1/learning-path/refresh` for map nodes optimization.
All callback flows write back to MySQL via Backend webhooks (`POST /api/v1/webhooks/`).

## Code Layout
- Frontend: `frontend/src/`
  - Pages: `frontend/src/pages/`
  - Components: `frontend/src/components/`
  - Custom SWR Hooks: `frontend/src/hooks/`
- Backend API: `backend/app/api/v1/`
- Backend Services: `backend/app/services/`
- Agent Service: `agent_service/`
