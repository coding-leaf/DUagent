# Original Request for Frontend SWR Refactoring

Refactor `useCatalog.js` and catalogs components to use SWR conditional polling instead of complex manual timeout polling.
Specifically:
1. Load materials, ingestion status, resources, and knowledge graph status using SWR hooks in `useCatalog.js`.
2. Track running background tasks (`activeTask`, `generationTask`, `knowledgeGraphTask`, `quizGenTask`) using SWR polling with conditional keys.
3. Eliminate all manual `setTimeout` intervals, `cancelled` variables, and request sequence refs in `useCatalog.js`.
4. Mutate/revalidate the SWR caches after upload, ingestion start, generation start, and deletions to keep data in sync.
5. Create comprehensive unit tests for `useResourceDetail.js` and `useCatalog.js` using Vitest.
6. Verify with `npm run build`, `npm run lint`, and `npm run test:unit`.

## 2026-06-21T05:52:17Z
Resume work at /home/yezisama/workspace/workflow/EDUagent/.agents/teamwork_preview_worker_frontend_refactor_3_repl_2.
Read ORIGINAL_REQUEST.md, BRIEFING.md, and progress.md for current state.
Your parent is e661892b-3a1c-4442-b648-d4f645404d06 — use this ID for all escalation and status reporting (send_message).

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT
hardcode test results, create dummy/facade implementations, or
circumvent the intended task. A Forensic Auditor will independently
verify your work. Integrity violations WILL be detected and your
work WILL be rejected.

