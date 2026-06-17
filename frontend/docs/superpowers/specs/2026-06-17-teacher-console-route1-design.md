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
- **Problem**: `StudentMonitoringSection` has hardcoded UI for search and pagination (e.g., "42名学生中展示 14名") which does nothing.
- **Solution**: 
  - Since the backend API (`getClassStudents`) returns the full list of students without pagination parameters, we will perform data manipulation in the frontend container.
  - **State in `TeacherConsole`**:
    - `studentSearchQuery` (string, default `""`)
    - `studentCurrentPage` (number, default `1`)
  - **Derived Data**:
    - `filteredStudents`: Filter the raw `students` array by matching `studentSearchQuery` against `username`, `english_name`, and `student_id` (case-insensitive).
    - `totalPages`: `Math.ceil(filteredStudents.length / PAGE_SIZE)` (PAGE_SIZE = 14).
    - `paginatedStudents`: `filteredStudents.slice((studentCurrentPage - 1) * PAGE_SIZE, studentCurrentPage * PAGE_SIZE)`.
  - **Effects**:
    - Reset `studentCurrentPage` to 1 whenever `studentSearchQuery` changes or `activeClass` changes.
  - **Component Interface (`StudentMonitoringSection`)**:
    - Replace `students` prop with `paginatedStudents`.
    - Add props: `totalStudents` (length of `filteredStudents`), `currentPage`, `totalPages`, `onPageChange`, `searchQuery`, `onSearchChange`.
    - Replace hardcoded text with dynamic text: `共 {totalStudents} 名学生，当前第 {currentPage}/{totalPages} 页`.
    - Bind search `<input>` to `searchQuery` and `onChange={(e) => onSearchChange(e.target.value)}`.
    - Bind pagination buttons to `onPageChange`.

## 4. Error Handling
- Invalid page transitions (e.g., clicking "Prev" on page 1) will be prevented by disabling the buttons when `currentPage <= 1` or `currentPage >= totalPages`.
- If no students match the search, the UI should gracefully display the existing `<FeedbackStatus status="empty" title="该班级暂无学生" />` (update the text to "没有找到匹配的学生" if `searchQuery` is not empty).

## 5. Testing Strategy
- Ensure `npm run lint` and `npm run build` pass after modifications.
- Verify search logic does not crash if fields like `english_name` are undefined.
