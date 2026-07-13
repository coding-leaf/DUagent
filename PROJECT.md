# Project: EDUagent v3

## Architecture
- **Frontend**: React SPA. MVVM architecture where custom SWR hooks act as ViewModels, Page files act as View Containers, and sub-components in `src/components/` act as Views.
- **Backend**: FastAPI. Layered architecture: Router (`backend/app/api/v1/`) -> Service (`backend/app/services/`) -> DB/Repository.
- **Agent Service v2**: AgentScope 2.x + FastAPI microservice. It owns LLM, tools, RAG, workspaces and agent-team execution, does not access MySQL, and communicates with Backend through HTTP and webhooks.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|---|---|---|---|
| 1 | AI Chat & Tutoring | Frontend `AIChat`, Backend `tutoring` & `evaluation`, Agent `tutoring` | None | DONE (Conv: d67cefab-553f-4f69-9acf-01899594be20) |
| 2 | Resource Generation & Mounting | Frontend `ResourceDetail` & Catalogs, Backend `resources` & `catalogs`, Agent `resources` | None | DONE (Conv: e661892b-3a1c-4442-b648-d4f645404d06) |
| 3 | Core Learning | Frontend `LearningPath` & `Quiz`, Backend `learning-path` & `learning-activities`, Agent `learning_path` | None | IN_PROGRESS (Conv: 77866b9b-6ff5-4d92-8e3e-4c7274b142db) |

## Interface Contracts
### Backend ↔ Agent Service
- **Workbench tutoring**: `POST /agent/v2/workbench/chat`.
- **Knowledge ingestion / KG / quiz / resources**: `/agent/v2/knowledge/*`.
- **Evaluation and answer diagnosis**: `/agent/v2/evaluation/*`.
- **Personalized resources**: `/agent/v2/personalized-resources/*`.
- **Learning path**: Backend derives the current path from the active KG and real-time learning progress; there is no Agent learning-path generation endpoint.
Agent callbacks write authoritative business results to MySQL through Backend webhooks or internal Backend APIs.

## Code Layout
- Frontend: `frontend/src/`
  - Pages: `frontend/src/pages/`
  - Components: `frontend/src/components/`
  - Custom SWR Hooks: `frontend/src/hooks/`
- Backend API: `backend/app/api/v1/`
- Backend Services: `backend/app/services/`
- Agent Service: `agent_service_v2/src/agent_service_v2/`
