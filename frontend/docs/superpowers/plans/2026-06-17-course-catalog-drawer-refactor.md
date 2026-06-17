# CourseCatalogDrawer Refactoring Plan

## Context
As part of the Phase 2 Architecture Refactoring, we are applying the Vertical Slicing strategy (Option B) to decouple the massive `CourseCatalogDrawer.jsx` (1332 lines). 
This frontend refactoring mirrors the backend's `CatalogService` pattern, creating a clean `View -> Hook -> Service` architecture.

## Execution Strategy
This plan will be executed via Subagent-Driven Development. Each task will be dispatched to a dedicated implementation subagent, followed by strict Spec Compliance and Code Quality reviews.

---

## Tasks

### Task 1: Establish Vitest Testing Infrastructure
- **Goal**: Setup a unit testing safety net before refactoring.
- **Implementation**:
  1. Install `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, and `jsdom`.
  2. Configure `vite.config.js` for testing.
  3. Create `vitest.setup.js` for global mocks.
  4. Write a simple baseline test for an existing utility (e.g., `src/utils/chatContent.js` or formatters) to verify the runner works.
- **Acceptance Criteria**: `npm run test:unit` executes successfully.

### Task 2: Extract `catalogService.js`
- **Goal**: Isolate all API interactions out of the UI components.
- **Implementation**:
  1. Create `src/services/catalogService.js`.
  2. Extract all endpoints related to Course Catalogs (e.g., fetching catalogs, generating, deleting, saving) into standard async functions using the existing Axios setup.
  3. Write basic unit tests for `catalogService.js` using MSW or Vitest mocks.
- **Acceptance Criteria**: A clean service file exists with 100% of the catalog-related fetch logic abstracted.

### Task 3: Extract `useCatalog.js` Hook
- **Goal**: Move UI-agnostic state and orchestration logic into a custom hook.
- **Implementation**:
  1. Create `src/hooks/useCatalog.js`.
  2. Move all `useState` (loading, error, data) and `useEffect` blocks related to catalog management from `CourseCatalogDrawer.jsx` into this hook.
  3. Expose a clean interface: `{ catalogs, loading, error, fetchCatalogs, generateCatalog, ... }`.
- **Acceptance Criteria**: The custom hook correctly manages the lifecycle and delegates API calls to `catalogService`.

### Task 4: Decompose `CourseCatalogDrawer.jsx` UI
- **Goal**: Break the 1300-line monolith into smaller presentational components.
- **Implementation**:
  1. Create a new directory: `src/components/admin/catalog/`.
  2. Extract inner components like `CatalogList`, `CatalogGenerationForm`, `CatalogDetailModal` into separate files.
  3. Refactor the main `CourseCatalogDrawer.jsx` to act as a Container that purely consumes `useCatalog` and passes props to the extracted presentational components.
- **Acceptance Criteria**: `CourseCatalogDrawer.jsx` is significantly reduced in size (< 300 lines) and contains strictly structural UI logic. Tests still pass.
