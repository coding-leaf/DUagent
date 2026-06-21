# Scope: Core Learning Refactoring

## Architecture
- **Frontend**: Refactor `Quiz.jsx` component split or custom hook `useQuizEngine.js` to utilize SWR-based data fetching and caching (MVVM). Check `LearningPath.jsx` split correctness.
- **Backend**: `quiz.py` refactored into a thin Router, moving queries, updates, and Agent requests to `quiz_service.py` (Router-Service-DB split). Review and check `learning_path.py` and `learning_activities.py`.
- **Agent Service**: `learning_path` agent service.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|---|---|---|---|
| 1 | Baseline Verification | Capturing baseline tests for quiz, learning path and learning activities | None | PLANNED |
| 2 | Backend Core Learning Refactoring | Refactor `quiz.py` (get_questions, generate_questions, get_result, get_history) into `quiz_service.py`, keeping router thin. Update/add tests | M1 | PLANNED |
| 3 | Frontend Core Learning Refactoring | Refactor `useQuizEngine.js` to use SWR hooks for fetching and caching quiz questions (MVVM) | M2 | PLANNED |
| 4 | Final Integration & Verification | Run all pytest/Vitest suites for quiz/learning path; run Forensic Integrity Audit | M3 | PLANNED |

## Interface Contracts
- Backend `quiz` exposes endpoints for get_questions, generate, submit, result, and history.
