## Current Status
Last visited: 2026-06-21T14:18:00+08:00
- [x] Milestone 1: Baseline Verification [completed]
- [x] Milestone 2: Backend Catalogs & Resources Refactoring [completed]
- [x] Milestone 3: Frontend ResourceDetail & Catalogs Refactoring [completed]
- [x] Milestone 4: Final Integration & Verification [completed]

## Iteration Status
Current iteration: 1 / 32

## Retrospective Notes
- **What worked**: Decoupling the frontend fetching layer into custom SWR hooks (`useResourceDetail` and `useCatalog`) worked extremely well. In `useCatalog`, leveraging SWR conditional polling based on active task IDs simplified a large class of manual polling timers (`setTimeout`) and state syncing logic.
- **What didn't work**: Initially, running pytest across all files in the test suite caused connection pool leaks and event loop race conditions, as previous modules pre-loaded database sessions on stale MySQL engines. Recreating the engine dynamically with `NullPool` and traversing `sys.modules` to rebind connections resolved the cross-test race issues.
- **Lessons learned**: Dynamic database schema configuration and connection lifecycle management are critical in async Python tests. SWR conditional polling is an elegant solution to state sync, but proper cache key isolation must be maintained in Vitest environments to prevent test pollution.

