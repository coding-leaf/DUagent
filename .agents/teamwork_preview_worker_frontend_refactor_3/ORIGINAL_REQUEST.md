## 2026-06-21T04:57:05+08:00
You are spawned to execute the frontend AIChat MVVM and SWR refactoring task.

Please refer to the implementation plan written at:
/home/yezisama/workspace/workflow/EDUagent/.agents/sub_orch_ai_chat_tutoring/frontend_refactor_plan.md

Your tasks:
1. Create `frontend/src/hooks/useRecommendedResources.js` using SWR to fetch and filter resources.
2. Refactor `frontend/src/components/chat/SidebarResources.jsx` to consume `useRecommendedResources` and remove manual fetching/state logic.
3. Refactor `frontend/src/context/ChatContext.jsx` to fetch and manage chat sessions using SWR, including optimistic updates on deletion and automatic revalidation.
4. Run `npm run lint` and `npm run test:unit` in `frontend` directory to verify code cleanliness and ensure no regressions.
5. Run `npm run build` to verify compilation.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Write your final handoff to /home/yezisama/workspace/workflow/EDUagent/.agents/teamwork_preview_worker_frontend_refactor_3/handoff.md and report back to me when done.

## 2026-06-21T09:26:09+08:00
Your task is to implement Milestone 3: Frontend ResourceDetail & Catalogs Refactoring:
1. Create/refactor custom SWR hooks (e.g. `useResourceDetail`) in `frontend/src/hooks/` or inside their respective component directory to fetch and cache resource details using `learningService.getResourceDetail`.
2. Refactor `frontend/src/pages/ResourceDetail.jsx` to use your custom SWR hook `useResourceDetail` for fetching and caching data, completely eliminating the manual `useState`/`useEffect` data-fetching pattern.
3. Refactor the custom hook `frontend/src/hooks/useCatalog.js` and catalogs components. Simplify the complex manual `setTimeout` polling intervals and sequence refs by utilizing SWR conditional polling (`refreshInterval` config on SWR) and automatic revalidation/mutation.
4. Ensure the React frontend compiles cleanly by running `npm run build` and `npm run lint` inside `frontend`.
5. Run Vitest unit tests via `npm run test:unit` inside `frontend` to verify all components and services.
6. Document all frontend changes and compilation/test results in `/home/yezisama/workspace/workflow/EDUagent/.agents/teamwork_preview_worker_frontend_refactor_3/handoff.md` and send a message back.
