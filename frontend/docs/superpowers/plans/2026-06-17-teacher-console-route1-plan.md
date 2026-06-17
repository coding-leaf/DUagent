# Teacher Console Route 1 Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement real frontend pagination, searching, and decouple routing from presentational components in TeacherConsole.

**Architecture:** Moving state (search, pagination) and routing (`navigate`) up to the `TeacherConsole` container. Presentational components (`StudentMonitoringSection`, `TeacherResourceSection`) become pure stateless consumers of callbacks.

**Tech Stack:** React, SWR

---

### Task 1: Update `TeacherResourceSection.jsx` to decouple routing

**Files:**
- Modify: `src/components/teacher/TeacherResourceSection.jsx`

- [ ] **Step 1: Replace `navigate` with `onResourceClick` callback**

```javascript
// Change props from:
export default function TeacherResourceSection({
  ...
  copiedCourseCode,
  navigate
}) {

// To:
export default function TeacherResourceSection({
  ...
  copiedCourseCode,
  onResourceClick
}) {
```

- [ ] **Step 2: Update `onClick` usage**

Find:
```javascript
onClick={() => navigate(`/resource/${resource.id}`)}
```
Replace with:
```javascript
onClick={() => onResourceClick(resource.id)}
```

- [ ] **Step 3: Run linter**

Run: `npm run lint`
Expected: PASS or warning about unused `navigate`.

- [ ] **Step 4: Commit**

```bash
git add src/components/teacher/TeacherResourceSection.jsx
git commit -m "refactor(teacher): decouple routing from TeacherResourceSection"
```

---

### Task 2: Update `StudentMonitoringSection.jsx` to use dynamic props

**Files:**
- Modify: `src/components/teacher/StudentMonitoringSection.jsx`

- [ ] **Step 1: Update props**

```javascript
// Change props to include new pagination and callback props
export default function StudentMonitoringSection({
  activeClassInfo,
  activeClass,
  studentsLoading,
  studentsError,
  students, // Note: this will now receive paginatedStudents
  isMockMode,
  totalStudents,
  currentPage,
  totalPages,
  onPageChange,
  searchQuery,
  onSearchChange,
  onRefresh,
  onStudentClick
}) {
```

- [ ] **Step 2: Update routing**

Find:
```javascript
onClick={() => navigate(`/teacher/report?course_id=${activeClass}&student_id=${student.user_id}`)}
```
Replace with:
```javascript
onClick={() => onStudentClick(student.user_id)}
```

- [ ] **Step 3: Update Search & Refresh Header**

Find:
```javascript
            <div className="flex items-center bg-surface-container-low rounded-lg px-3 py-1.5 border border-outline-variant">
              <Icon name="search" className="material-symbols-outlined text-outline text-sm mr-2"/>
              <input className="bg-transparent border-none focus:ring-0 text-sm w-32 outline-none" placeholder="搜索学生..." type="text" />
            </div>
            <button className="p-2 rounded-lg hover:bg-surface-container transition-colors">
              <Icon name="refresh" className="material-symbols-outlined text-outline"/>
            </button>
```
Replace with:
```javascript
            <div className="flex items-center bg-surface-container-low rounded-lg px-3 py-1.5 border border-outline-variant">
              <Icon name="search" className="material-symbols-outlined text-outline text-sm mr-2"/>
              <input 
                className="bg-transparent border-none focus:ring-0 text-sm w-32 outline-none" 
                placeholder="搜索学生..." 
                type="text" 
                value={searchQuery}
                onChange={(e) => onSearchChange(e.target.value)}
              />
            </div>
            <button 
              onClick={onRefresh}
              className="p-2 rounded-lg hover:bg-surface-container transition-colors"
            >
              <Icon name="refresh" className="material-symbols-outlined text-outline"/>
            </button>
```

- [ ] **Step 4: Update Pagination Footer**

Find:
```javascript
        {/* Pagination */}
        <div className="px-md py-4 bg-surface-container-low border-t border-outline-variant flex justify-between items-center">
          <span className="text-xs font-medium text-outline">当前显示 {activeClassInfo?.name || activeClass} (42名学生中展示 14名)</span>
          <div className="flex gap-1">
            <button className="px-3 py-1 bg-white border border-outline-variant rounded-lg text-xs font-bold hover:bg-surface-container transition-colors">上一页</button>
            <button className="px-3 py-1 bg-primary text-white border border-primary rounded-lg text-xs font-bold">1</button>
            <button className="px-3 py-1 bg-white border border-outline-variant rounded-lg text-xs font-bold hover:bg-surface-container transition-colors">2</button>
            <button className="px-3 py-1 bg-white border border-outline-variant rounded-lg text-xs font-bold hover:bg-surface-container transition-colors">下一页</button>
          </div>
        </div>
```
Replace with:
```javascript
        {/* Pagination */}
        <div className="px-md py-4 bg-surface-container-low border-t border-outline-variant flex justify-between items-center">
          <span className="text-xs font-medium text-outline">
            当前显示 {activeClassInfo?.name || activeClass} (共 {totalStudents} 名学生，当前第 {currentPage}/{totalPages} 页)
          </span>
          <div className="flex gap-1">
            <button 
              onClick={() => onPageChange(currentPage - 1)}
              disabled={currentPage <= 1}
              className="px-3 py-1 bg-white border border-outline-variant rounded-lg text-xs font-bold hover:bg-surface-container transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              上一页
            </button>
            <button 
              onClick={() => onPageChange(currentPage + 1)}
              disabled={currentPage >= totalPages}
              className="px-3 py-1 bg-white border border-outline-variant rounded-lg text-xs font-bold hover:bg-surface-container transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              下一页
            </button>
          </div>
        </div>
```

- [ ] **Step 5: Run linter**

Run: `npm run lint`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/components/teacher/StudentMonitoringSection.jsx
git commit -m "refactor(teacher): wire up real pagination and callbacks in StudentMonitoringSection"
```

---

### Task 3: Implement Logic in `TeacherConsole.jsx`

**Files:**
- Modify: `src/pages/TeacherConsole.jsx`

- [ ] **Step 1: Define Constants and State**

At the top of `TeacherConsole.jsx` (outside the component or just below imports):
```javascript
const STUDENT_PAGE_SIZE = 14;
```

Inside the `TeacherConsole` component, add state variables:
```javascript
  const [studentSearchQuery, setStudentSearchQuery] = useState("");
  const [studentCurrentPage, setStudentCurrentPage] = useState(1);
```

- [ ] **Step 2: Add callbacks for routing**

```javascript
  const handleStudentClick = (studentId) => {
    navigate(`/teacher/report?course_id=${activeClass}&student_id=${studentId}`);
  };

  const handleResourceClick = (resourceId) => {
    navigate(`/resource/${resourceId}`);
  };
```

- [ ] **Step 3: Implement derived data and effects**

```javascript
  // Derived state for students
  const filteredStudents = (students || []).filter((s) => {
    const q = studentSearchQuery.toLowerCase();
    return (
      (s.username ?? '').toLowerCase().includes(q) ||
      (s.english_name ?? '').toLowerCase().includes(q) ||
      (s.student_id ?? '').toLowerCase().includes(q)
    );
  });
  
  const studentTotalPages = Math.max(1, Math.ceil(filteredStudents.length / STUDENT_PAGE_SIZE));
  const paginatedStudents = filteredStudents.slice(
    (studentCurrentPage - 1) * STUDENT_PAGE_SIZE,
    studentCurrentPage * STUDENT_PAGE_SIZE
  );

  // Reset page when active class changes
  useEffect(() => {
    setStudentCurrentPage(1);
  }, [activeClass]);

  // Reset page when search query changes
  useEffect(() => {
    setStudentCurrentPage(1);
  }, [studentSearchQuery]);
```

- [ ] **Step 4: Update JSX component props**

Find `<TeacherResourceSection ... />` and update it:
```javascript
          <TeacherResourceSection
            activeClassInfo={activeClassInfo}
            resourcesLoading={resourcesLoading}
            resourcesError={resourcesError}
            resources={resources}
            groupedResources={groupedResources}
            expandedChapter={expandedChapter}
            setExpandedChapter={setExpandedChapter}
            handleCopyCourseCode={handleCopyCourseCode}
            copiedCourseCode={copiedCourseCode}
            onResourceClick={handleResourceClick}
          />
```

Find `<StudentMonitoringSection ... />` and update it:
```javascript
          <StudentMonitoringSection
            activeClassInfo={activeClassInfo}
            activeClass={activeClass}
            studentsLoading={studentsLoading}
            studentsError={studentsError}
            students={paginatedStudents}
            isMockMode={isMockMode}
            totalStudents={filteredStudents.length}
            currentPage={studentCurrentPage}
            totalPages={studentTotalPages}
            onPageChange={setStudentCurrentPage}
            searchQuery={studentSearchQuery}
            onSearchChange={setStudentSearchQuery}
            onRefresh={() => refreshStudents?.()}
            onStudentClick={handleStudentClick}
          />
```
*(Make sure to extract `refreshStudents` from `useTeacherConsoleData` if not already destructured)*

Update destructuring from `useTeacherConsoleData`:
```javascript
  const {
    classes, classesLoading, refreshClasses,
    students, studentsLoading, studentsError, refreshStudents,
    insights, insightsLoading, insightsError,
    resources, resourcesLoading, resourcesError,
    resourcesTotal, resourcesTotalPages
  } = useTeacherConsoleData(activeClass, { resourcePage: 1, resourcePageSize: 50 });
```

- [ ] **Step 5: Run linter and build**

Run: `npm run lint && npm run build`
Expected: PASS (build successful)

- [ ] **Step 6: Commit**

```bash
git add src/pages/TeacherConsole.jsx
git commit -m "feat(teacher): implement real pagination and search in console"
```
