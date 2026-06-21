# Progress Journal - Frontend ResourceDetail & Catalogs Refactoring

Last visited: 2026-06-21T09:26:09+08:00

## Refactoring Steps
- [ ] Task 1: Create Custom Hook `useResourceDetail`
  - [ ] Step 1.1: Locate `learningService.getResourceDetail` and investigate its parameters and return type
  - [ ] Step 1.2: Implement `frontend/src/hooks/useResourceDetail.js` using SWR
- [ ] Task 2: Refactor `ResourceDetail.jsx`
  - [ ] Step 2.1: Analyze `frontend/src/pages/ResourceDetail.jsx` data fetching and state
  - [ ] Step 2.2: Refactor `ResourceDetail.jsx` to use `useResourceDetail` hook and eliminate manual fetching/loading/error state
- [ ] Task 3: Refactor `useCatalog.js` and Catalogs Components
  - [ ] Step 3.1: Analyze `frontend/src/hooks/useCatalog.js` and how components use it
  - [ ] Step 3.2: Simplify manual polling, setTimeout, and sequence refs using SWR conditional polling and revalidation/mutation
- [ ] Task 4: Run build, lint, and tests
  - [ ] Step 4.1: Run `npm run lint` and fix any issues
  - [ ] Step 4.2: Run `npm run test:unit` and verify all tests pass
  - [ ] Step 4.3: Run `npm run build` and ensure clean build
