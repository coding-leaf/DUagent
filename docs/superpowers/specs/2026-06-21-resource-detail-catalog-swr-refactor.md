# Spec: ResourceDetail & Catalogs SWR Refactoring

## 1. Context & Motivation
Currently, `ResourceDetail.jsx` and the custom hook `useCatalog.js` rely on manual data fetching using `useState` and `useEffect`.
For `useCatalog.js`, task status polling is implemented using nested `setTimeout` logic and complex refs (`requestSeqRef`, `cancelled` flags, etc.) to prevent memory leaks and out-of-order state updates. This manual polling state is error-prone, hard to test, and violates the "Reuse-First Principle" where SWR's native capabilities (conditional fetching, automatic revalidation, dynamic `refreshInterval`) can be leveraged instead.

## 2. Design Decisions
- **Architectural Pattern**: MVVM (Model-ViewModel-View). Hooks act as the ViewModel providing state and mutations to the view pages/components.
- **Data Fetching Layer**: SWR. Replace all manual API calls in `ResourceDetail.jsx` and `useCatalog.js` with SWR hooks.
- **Polling Pattern**: SWR Conditional Polling. By toggling SWR keys to `null` when polling is inactive and setting `refreshInterval` when active, SWR naturally manages polling lifecycles without manual timers.

## 3. Detailed Plan
### Task 1: Create `useResourceDetail` Custom Hook
- File: `frontend/src/hooks/useResourceDetail.js`
- Responsibilities: Fetch and cache resource details using `learningService.getResourceDetail(id)`.
- Export: `{ resource, loading, error, mutate }`.

### Task 2: Refactor `ResourceDetail.jsx`
- Replace `useState`/`useEffect` for fetching resource with `useResourceDetail(id)`.
- Retain the activity tracking `useEffect` but clean up logic to respond to `resource` changes from SWR.

### Task 3: Refactor `useCatalog.js`
- Load materials, ingestion status, resources, and knowledge graph status using SWR hooks.
- Track running background tasks (`activeTask`, `generationTask`, `knowledgeGraphTask`, `quizGenTask`) using SWR polling with conditional keys.
- Eliminate all manual `setTimeout` intervals, `cancelled` variables, and request sequence refs.
- Mutate/revalidate the SWR caches after upload, ingestion start, generation start, and deletions to keep data in sync.

### Task 4: Verification
- Run `npm run lint` and `npm run test:unit`.
- Create unit tests for `useResourceDetail.js` and `useCatalog.js`.
- Run `npm run build` to confirm compilation.
