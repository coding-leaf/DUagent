## 2026-06-20T20:36:21Z

You are spawned to execute the refactoring of the backend evaluation module and fix related test assertion issues.

Please refer to the implementation plan written at:
/home/yezisama/workspace/workflow/EDUagent/.agents/sub_orch_ai_chat_tutoring/evaluation_refactor_plan.md

Your tasks:
1. Update `backend/app/infrastructure/locks.py` to add `evaluation_lock` with SQLite dialect check.
2. Create `backend/app/services/evaluation_service.py` to hold `EvaluationService` class and `run_evaluation_refresh_background` function.
3. Refactor `backend/app/api/v1/evaluation.py` to be a thin router using the new `EvaluationService`. To keep legacy mock targets valid, import `agent_client` in `evaluation.py`.
4. Implement new unit tests:
   - `backend/tests/test_evaluation_routes_refactored.py`
   - `backend/tests/test_evaluation_service_refactored.py`
   (You can use the designs provided in the Test Architect's analysis report or the plan document.)
5. Fix the two assertion failures in `agent_service/tests/test_evaluation_agent.py`:
   - In `test_generate_evaluation_data_builds_mastery_table_from_quizzes`, update columns and expected rows to use `knowledge_point` (instead of `chapter`) and include `personalized_count` column and row values.
   - In `test_generate_evaluation_data_builds_summary_text`, update "薄弱章节：导数。" to "薄弱知识点：导数。" in the asserted string.
6. Verify all test files run and pass. Ensure existing integration tests (like test_refresh_async.py and test_lock_async.py) compile and execute.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Write your final handoff to /home/yezisama/workspace/workflow/EDUagent/.agents/teamwork_preview_worker_evaluation_refactor_2/handoff.md and report back to me when done.
