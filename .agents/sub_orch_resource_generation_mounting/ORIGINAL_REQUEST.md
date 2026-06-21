# Original User Request

## 2026-06-21T09:03:15+08:00

Identity: teamwork_preview_orchestrator
Working Directory: /home/yezisama/workspace/workflow/EDUagent/.agents/sub_orch_resource_generation_mounting

Your task is to refactor the Resource Generation & Mounting module of the EDUagent full-stack project (frontend, backend, and agent service).
Specifically:
1. Move business logic, file operations, and direct SQL queries out of backend Routers (`backend/app/api/v1/catalogs.py` and `backend/app/api/v1/resources.py`) to their corresponding service files (`catalog_service.py` etc.). Ensure thin routers.
2. Refactor frontend `ResourceDetail.jsx` and any catalogs hook/component to use custom SWR hooks for fetching and caching resource detail data, adhering to MVVM design principles.
3. Add and execute comprehensive unit tests for both catalogs and resources refactoring.
4. Perform integration tests and Forensic Integrity Audit verification to guarantee clean, facade-free execution.
