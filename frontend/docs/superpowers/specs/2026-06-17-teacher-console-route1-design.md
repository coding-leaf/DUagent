# Teacher Console Post-Refactor Fixes (Route 1) Design Spec

## 1. Objective
Address the residual architectural and UI issues identified during Phase 2 UI Splitting code review (HIGH-3 and HIGH-4). Specifically, implement real frontend pagination and filtering for the student monitoring table, and remove routing dependencies from pure presentational components.

## 2. Scope
This design is strictly scoped to:
- `src/pages/TeacherConsole.jsx`
- `src/components/teacher/StudentMonitoringSection.jsx`
- `src/components/teacher/TeacherResourceSection.jsx`

## 3. Architecture & Data Flow
`TeacherConsole` will act as the single source of truth for routing and list manipulation logic.

### 3.1 Resolving HIGH-4: Decoupling Routing
- **Problem**: `TeacherConsole.jsx` currently passes the `navigate` hook directly as a prop to `StudentMonitoringSection` and `TeacherResourceSection`. Presentational components should not know about React Router.
- **Solution**:
  - `TeacherConsole` will define two handler functions:
    - `handleStudentClick = (studentId) => navigate('/teacher/report?course_id=...&student_id=...')`
    - `handleResourceClick = (resourceId) => navigate('/resource/...')`
  - These will be passed as `onStudentClick` and `onResourceClick` props to the respective child components.
  - The child components will invoke these callbacks with the appropriate IDs.

### 3.2 Resolving HIGH-3: Frontend Pagination & Searching
- **Problem**: `StudentMonitoringSection` has hardcoded UI for search and pagination (e.g., "42名学生中展示 14名") which does nothing. It also has a non-functional refresh button.
- **Solution**: 
  - **Constants**: Define `STUDENT_PAGE_SIZE = 14` outside the component lifecycle (at the top of the file or in `src/constants/`).
  - **State in `TeacherConsole`**:
    - `studentSearchQuery` (string, default `""`)
    - `studentCurrentPage` (number, default `1`)
  - **Derived Data (with Null-Safety)**:
    - `filteredStudents`: Filter the raw `students` array using safe fallback to prevent NPEs.
      ```javascript
      const q = studentSearchQuery.toLowerCase();
      const filteredStudents = students.filter(s =>
        (s.username ?? '').toLowerCase().includes(q) ||
        (s.english_name ?? '').toLowerCase().includes(q) ||
        (s.student_id ?? '').toLowerCase().includes(q)
      );
      ```
    - `totalPages`: `Math.ceil(filteredStudents.length / STUDENT_PAGE_SIZE)`.
    - `paginatedStudents`: `filteredStudents.slice((studentCurrentPage - 1) * STUDENT_PAGE_SIZE, studentCurrentPage * STUDENT_PAGE_SIZE)`.
  - **Effects**:
    - Use a `useEffect` dependent *only* on `activeClass` to reset `studentCurrentPage` to 1. This cleanly isolates class-switching logic.
    - Use a separate `useEffect` dependent on `studentSearchQuery` to reset `studentCurrentPage` to 1.
  - **Component Interface (`StudentMonitoringSection`)**:
    - Replace `students` prop with `paginatedStudents`.
    - Add props: `totalStudents` (length of `filteredStudents`), `currentPage`, `totalPages`, `onPageChange`, `searchQuery`, `onSearchChange`, and `onRefresh` (bound to `refreshStudents` from `useTeacherConsoleData`).
    - Replace hardcoded text with dynamic text: `共 {totalStudents} 名学生，当前第 {currentPage}/{totalPages} 页`.
    - Simplify the pagination UI: Render only "上一页" (Prev) and "下一页" (Next) buttons along with the text indicator, avoiding hardcoded page numbers.
    - Bind search `<input>` to `searchQuery` and `onChange={(e) => onSearchChange(e.target.value)}`.
    - Bind the refresh `<button>` to `onRefresh`.

## 4. Error Handling
- Invalid page transitions will be prevented by disabling the Prev/Next buttons when `currentPage <= 1` or `currentPage >= totalPages`.
- If no students match the search, the UI will display `<FeedbackStatus status="empty" title="没有找到匹配的学生" />`.

## 5. Testing Strategy
- Ensure `npm run lint` and `npm run build` pass after modifications.
- Verify `studentCurrentPage` resets correctly when changing classes or typing in the search box.
