# Original User Request

## 2026-06-21T14:19:01+08:00

Identity: teamwork_preview_orchestrator
Working Directory: /home/yezisama/workspace/workflow/EDUagent/.agents/sub_orch_core_learning

Your task is to refactor the Core Learning module of the EDUagent full-stack project (frontend, backend, and agent service).
Specifically:
1. Move business logic and direct SQL queries out of backend Router (`backend/app/api/v1/quiz.py`) to its corresponding service file (`quiz_service.py`). Ensure thin routers.
2. Refactor frontend `useQuizEngine.js` to use SWR hooks for fetching and caching quiz questions, adhering to MVVM design principles.
3. Check correctness of frontend `LearningPath.jsx` split, and review backend `learning_path.py` and `learning_activities.py` if needed.
4. Add and execute comprehensive unit tests for both quiz and learning path refactoring.
5. Perform integration tests and Forensic Integrity Audit verification to guarantee clean, facade-free execution.
