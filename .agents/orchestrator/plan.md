# Refactoring Plan — EDUagent Phase 2

This plan outlines the structured phases for refactoring the EDUagent full-stack project (frontend, backend, and agent service) by functional modules.

## Goals
- Clean up complex, redundant, and bloated code.
- Align code with the architectural layout guidelines (MVVM on the frontend, Router-Service-DB separation on the backend, and strict stateless boundaries on the Agent Service).
- Maintain 100% functional correctness (demo integrity mode).
- Ensure all automated unit and integration tests pass before and after each phase.
- Compile and deliver a comprehensive "Architecture & Flow Overview" document (`docs/architecture_flow_overview.md`) covering the complete project structure and the specific data flows of each major module at a glance by the end of this project.

## Phase 1: AI Chat & Tutoring Module
- **Frontend `AIChat`**: Verify that the split of `AIChat.jsx` into `SidebarHistory.jsx`, `SidebarResources.jsx`, and `ChatArea.jsx` is clean, robust, and matches the MVVM model.
- **Backend `tutoring` & `evaluation`**:
  - The `tutoring` router has been refactored; we will verify its correctness and tests.
  - The `evaluation` router (`backend/app/api/v1/evaluation.py`) is currently a fat file containing business logic and background runners. We will extract its logic to `backend/app/services/evaluation_service.py` (or a similar service file), separating route handling from logic.
- **Agent `tutoring`**: Inspect and refactor/clean up agent tutoring prompts/controllers if needed.
- **Verification**: Run tutoring and evaluation test suites.

## Phase 2: Resource Generation & Mounting Module
- **Frontend `ResourceDetail` & Catalogs**:
  - Inspect `ResourceDetail.jsx` and catalogs components.
  - Ensure clear separation of API requests from UI components.
- **Backend `resources` & `catalogs`**:
  - Refactor `backend/app/api/v1/catalogs.py` (which is quite large) into a layered structure: Router (`catalogs.py`) and corresponding Service layers.
  - Refactor `backend/app/api/v1/resources.py` if needed.
- **Agent `resources`**: Inspect and clean up resources agent files.
- **Verification**: Run catalog and resource test suites.

## Phase 3: Core Learning Module
- **Frontend `LearningPath` & `Quiz`**:
  - Verify `LearningPath.jsx` split.
  - Refactor `Quiz.jsx` to split large components and extract logic/hooks if needed.
- **Backend `learning-path` & `learning-activities` & `quiz`**:
  - Refactor `backend/app/api/v1/quiz.py` into a thin Router and move business logic to `quiz_service.py` or separate service classes.
  - Refactor/check `learning_path.py` and `learning_activities.py`.
- **Agent `learning_path`**: Inspect and verify agent learning path logic.
- **Verification**: Run learning path and quiz test suites.

## Quality Gate Criteria
1. **Compilation & Build**: Both backend `py_compile` and frontend `npm run build` must succeed with zero errors.
2. **Linting**: Frontend `npm run lint` must pass.
3. **Automated Tests**: Relevant pytest suites (backend & agent_service) and Playwright/Vitest (frontend) must pass.
4. **Adversarial / Review**: Code quality review must confirm removal of redundancy.
5. **Architecture Documentation**: Document the workflows and data flows of each refactored module in the final overview document.
