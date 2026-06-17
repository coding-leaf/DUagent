# Teacher Student Report Refactoring Spec

## 1. Context & Motivation
`TeacherStudentReport.jsx` is currently a monolithic file (~350 lines, 20KB) containing complex UI logic, chart rendering, and an anti-pattern data fetching mechanism (`requestSeq.current`) to handle race conditions. Additionally, it uses a hardcoded Google Image URL as a placeholder avatar which needs to be removed.

## 2. Software Engineering & Architecture Guidelines

According to `AGENTS.md` **Reuse-First Principle**:
> "状态管理与数据获取：轮询、缓存、乐观更新、请求去重——优先考虑 SWR / React Query，而非手写 useEffect"

Our `package.json` already includes `swr` (v2.4.1). Therefore, we will strictly follow the software engineering best practice of utilizing **SWR** for data fetching instead of inventing custom `AbortController` or sequence-tracking logic. SWR natively handles race conditions, caching, and deduplication.

## 3. Design Implementation

### 3.1 Data Fetching Layer (SWR)
We will extract the fetching logic into a custom hook `useStudentReport.js`:
- Use `useSWR` to fetch `teachingService.getStudentReport(classId, studentId)`.
- SWR key: `['studentReport', classId, studentId]`.
- Return `{ reportData, isLoading, error }` directly to the container.

### 3.2 Avatar Placeholder Resolution
Remove the hardcoded `<img>` tag pointing to `lh3.googleusercontent.com`.
Implement an Initials Avatar similar to the Teacher header:
```jsx
<div className="w-20 h-20 rounded-full bg-cyan-500/10 text-cyan-600 flex items-center justify-center border border-cyan-500/30 font-bold text-3xl">
  {(report.student?.real_name || report.student?.student_id || '学').charAt(0)}
</div>
```

### 3.3 UI Component Extraction (Presentational)
Create the following pure UI components inside `src/components/report/`:
1. `ReportHeader.jsx`: The top sticky header containing the teacher info and course name.
2. `ProfileBanner.jsx`: The student's basic info, newly implemented CSS Avatar, and the AI summary box.
3. `QuizStatsMetrics.jsx`: The "Online Quiz Stats" card.
4. `PathProgressCard.jsx`: The "Path Progress" card.
5. `ModalityPreferenceCard.jsx`: The "Modal Preference" card.
6. `KnowledgeGrid.jsx`: The details section containing "Knowledge Coordinates", "Mastery Breakdown", "Weak Points", and "Recent Activity".

### 3.4 Thin Container Refactoring
`TeacherStudentReport.jsx` will be stripped of all logic and inline JSX. It will:
1. Parse URL params.
2. Call `useStudentReport(classId, studentId)`.
3. Render Error/Loading states using existing `<FeedbackStatus>`.
4. Compose the extracted UI components into the dashboard layout.
