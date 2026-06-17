# Frontend Post-Refactor Fixes Execution Plan
Date: 2026-06-17

## Overview
This document outlines the plan to address 6 specific issues (2 High, 4 Medium) discovered during the recent refactoring of the frontend. Note that HIGH-3 and HIGH-4 are explicitly excluded from this plan.

## Issues & Fix Plan

### 1. HIGH-1: SWR Race Condition in `useStudentProfile.js`
- **Issue**: `onSuccess` and `refreshInterval` modify states concurrently, causing a race condition during polling.
- **Fix**: 
  - Remove state setting inside SWR `onSuccess` callback.
  - Derive the `isPolling` status synchronously from the SWR data/error or handle state updates cleanly inside a `useEffect` hook that watches the SWR `data`.

### 2. HIGH-2: Inconsistent SWR Key in `useTeacherConsoleData.js`
- **Issue**: `['teachingClasses']` key is too broad and missing standard formatting.
- **Fix**: 
  - Update the SWR key to be more specific or standardized (e.g., passing in auth context or structuring the key as an array like `['api', 'teaching', 'classes']`).

### 3. HIGH-5: Recreating Formatting Functions in `StudentProfile.jsx`
- **Issue**: `StudentProfile.jsx` recreates 7 formatting functions on every render and passes them as props, causing unnecessary child re-renders.
- **Fix**:
  - Move pure formatting functions (`isOpaqueId`, `labelValue`, `sourceLabel`, etc.) outside of the React component.
  - For functions requiring internal state (`daysAgoText`, `displayCourseSubject`, `formatDisciplineDimension`, `formatDimensionValue`), either wrap them in `useCallback` or decouple them so they can be defined outside the component.

### 4. MEDIUM-1: Duplicated `fetcherWrapper`
- **Issue**: `fetcherWrapper` is duplicated in both `useStudentProfile.js` and `useTeacherConsoleData.js`.
- **Fix**:
  - Extract the `fetcherWrapper` logic into a new utility file: `src/utils/fetcher.js`.
  - Export it and import it in both hooks.

### 5. MEDIUM-2: Scattered Constants in `StudentProfile.jsx`
- **Issue**: Constants like `PROFILE_VALUE_LABELS` and `PROFILE_EMPTY_TEXT` are scattered and hardcoded in page components.
- **Fix**:
  - Create a new file `src/constants/profile.js`.
  - Extract the constants into this file, export them, and import them where needed.

### 6. MEDIUM-3: Environment Logic in Presentational Component
- **Issue**: `StudentMonitoringSection.jsx` reads `import.meta.env.VITE_USE_MOCK` internally. Presentational components shouldn't contain environment logic.
- **Fix**:
  - Extract `useMock = import.meta.env.VITE_USE_MOCK === 'true'` to the parent component `TeacherConsole.jsx`.
  - Pass it down as a prop `isMockMode={useMock}` to `StudentMonitoringSection`.
  - Use the `isMockMode` prop inside `StudentMonitoringSection.jsx` instead of reading the environment variable directly.

## Execution Steps
1. Create `src/utils/fetcher.js` and extract the `fetcherWrapper`.
2. Create `src/constants/profile.js` and extract profile constants.
3. Update `useStudentProfile.js` to address HIGH-1 and use the global `fetcherWrapper`.
4. Update `useTeacherConsoleData.js` to address HIGH-2 and use the global `fetcherWrapper`.
5. Update `TeacherConsole.jsx` and `StudentMonitoringSection.jsx` to address MEDIUM-3.
6. Refactor `StudentProfile.jsx` to address HIGH-5 and use the global constants from step 2.
