# Frontend Refactoring Targets

Based on the Phase 2 Architecture Refactoring Master Plan, here are the top 3 prioritized refactoring targets for the frontend codebase:

## 1. Fat Component Extraction: `StudentProfile.jsx`
- **Files Involved**: `frontend/src/pages/StudentProfile.jsx`
- **File Size**: ~43 KB (909 lines)
- **Current Architectural Smell/Violation**: 
  - Violates the "Organize Directories" (整理目录) directive.
  - This component acts as a "Fat File", tightly coupling data fetching, background task polling, complex state management, and large JSX render blocks for multiple profile dimensions (Modality Preference, Knowledge Coordinates, Blindspots, Drive Intent, etc.).
- **Proposed Solution**: 
  - **MVVM / Custom Hooks**: Extract the data fetching, polling (`pollTask`), and state logic into a custom hook `useStudentProfile()`.
  - **Component Splitting**: Break the UI into modular sub-components under `src/components/profile/` (e.g., `ProfileHeader`, `ModalityPreferenceCard`, `KnowledgeCoordinatesCard`, `LearningHabitsCard`).

## 2. Global Axios Interceptors & Error/Toast Handling
- **Files Involved**: `frontend/src/api/client.js` and scattered UI files with `try-catch`.
- **File Size**: Spans across the network layer and multiple pages.
- **Current Architectural Smell/Violation**: 
  - Violates the "Extract Common Components" (提取公共组件) directive.
  - The Master Plan notes that 401 unauthorized errors do not trigger a redirect, and error handling (`try-catch`) is scattered redundantly across different pages.
- **Proposed Solution**: 
  - **Interceptor Pattern & Context**: Add response interceptors (`apiClient.interceptors.response.use`) in `client.js` to automatically handle 401 (redirect to login) and 500 errors.
  - Create a `ToastContext` or use a lightweight notification system to display global error messages, allowing us to remove redundant local error state handling (`profileError`, `studentsError`, etc.) and `try-catch` blocks from individual pages.

## 3. Fat Component Extraction: `TeacherConsole.jsx`
- **Files Involved**: `frontend/src/pages/TeacherConsole.jsx`
- **File Size**: ~30 KB (585 lines)
- **Current Architectural Smell/Violation**: 
  - Violates the "Organize Directories" (整理目录) directive.
  - Similar to `StudentProfile`, this file mixes multiple responsibilities: fetching teaching classes, students, console insights, resources, and rendering distinct heavy dashboard sections all within one component.
- **Proposed Solution**: 
  - **MVVM / Custom Hooks**: Consolidate the cascading `useEffect` data-fetching logic into a custom hook `useTeacherConsoleData()`.
  - **Component Splitting**: Extract presentational UI into separate components like `ClassSelector`, `StudentListTable`, `ClassInsightsOverview`, and `ResourceManagementPanel`.
