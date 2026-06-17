# Frontend Phase 2 Refactoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `TeacherConsole.jsx` and `StudentProfile.jsx` by extracting their data fetching and polling logic into Custom Hooks using SWR, and clean up scattered `try-catch` network handling.

**Architecture:** Container/Presentational Pattern + Custom Hook Pattern (Separation of Concerns). `swr` will be used to replace manual `useEffect` data fetching and long-polling.

**Tech Stack:** React, Vite, SWR, Axios

---

### Task 1: Install and Configure SWR

**Files:**
- Modify: `package.json`

- [ ] **Step 1: Install SWR**

Run: `npm install swr`
Expected: PASS (Successfully added to package.json dependencies)

- [ ] **Step 2: Commit**

```bash
git add package.json package-lock.json
git commit -m "build: add swr for data fetching and polling"
```

---

### Task 2: Extract `useTeacherConsoleData` Hook

**Files:**
- Create: `src/hooks/useTeacherConsoleData.js`

- [ ] **Step 1: Create the Hook file**

Create `src/hooks/useTeacherConsoleData.js`:

```javascript
import useSWR from 'swr';
import { teachingService } from '../api/services/teaching';
import { learningService } from '../api/services/learning';

const fetcherWrapper = async (promise) => {
  const res = await promise;
  if (res.code !== 200) {
    throw new Error(res.message || '请求失败');
  }
  return res;
};

export function useTeacherConsoleData(activeClass) {
  // Fetch classes
  const { data: classesRes, error: classesError, mutate: refreshClasses, isLoading: classesLoading } = useSWR(
    ['teachingClasses'],
    () => fetcherWrapper(teachingService.getClasses())
  );
  
  const classes = classesRes?.data || [];

  // Fetch students for active class
  const { data: studentsRes, error: studentsError, isLoading: studentsLoading } = useSWR(
    activeClass ? ['classStudents', activeClass] : null,
    () => fetcherWrapper(teachingService.getClassStudents(activeClass))
  );

  const students = studentsRes?.data || [];

  // Fetch insights
  const { data: insightsRes, error: insightsError, isLoading: insightsLoading } = useSWR(
    activeClass ? ['classInsights', activeClass] : null,
    () => fetcherWrapper(teachingService.getConsoleInsights(activeClass))
  );

  const insights = insightsRes?.data || null;

  // Fetch resources
  const { data: resourcesRes, error: resourcesError, isLoading: resourcesLoading } = useSWR(
    activeClass ? ['classResources', activeClass] : null,
    () => fetcherWrapper(learningService.getResources({ course_id: activeClass, page: 1, page_size: 50 }))
  );

  const resources = resourcesRes?.data?.resources || [];

  return {
    classes,
    classesLoading,
    classesError: classesError ? '教学班加载失败' : null,
    refreshClasses,
    students,
    studentsLoading,
    studentsError: studentsError ? '学生列表加载失败' : null,
    insights,
    insightsLoading,
    insightsError: insightsError ? '班级统计加载失败' : null,
    resources,
    resourcesLoading,
    resourcesError: resourcesError ? '学习资源加载失败' : null,
  };
}
```

- [ ] **Step 2: Test imports (Dry Run)**

Run: `npm run lint`
Expected: PASS or warning about unused exports.

- [ ] **Step 3: Commit**

```bash
git add src/hooks/useTeacherConsoleData.js
git commit -m "feat(hooks): extract useTeacherConsoleData hook with SWR"
```

---

### Task 3: Refactor `TeacherConsole.jsx` to use Hook

**Files:**
- Modify: `src/pages/TeacherConsole.jsx`

- [ ] **Step 1: Replace manual state and effects with the Hook**

In `src/pages/TeacherConsole.jsx`:
1. Import the hook: `import { useTeacherConsoleData } from '../hooks/useTeacherConsoleData';`
2. Remove the local state variables: `classes`, `students`, `insights`, `classesLoading`, `studentsLoading`, `studentsError`, `insightsLoading`, `insightsError`, `resources`, `resourcesLoading`, `resourcesError`.
3. Remove the `refreshClasses` useCallback and both `useEffect` hooks that manage data fetching.
4. Add the hook invocation right after `const [activeClass, setActiveClass] = useState(null);`:

```javascript
  const {
    classes, classesLoading, refreshClasses,
    students, studentsLoading, studentsError,
    insights, insightsLoading, insightsError,
    resources, resourcesLoading, resourcesError
  } = useTeacherConsoleData(activeClass);

  // Auto-select first class if none active
  useEffect(() => {
    if (classes.length > 0 && !activeClass) {
      if (pendingCreatedClassId && classes.some(c => c.id === pendingCreatedClassId)) {
        setActiveClass(pendingCreatedClassId);
        setPendingCreatedClassId(null);
      } else {
        setActiveClass(classes[0].id);
      }
    }
  }, [classes, activeClass, pendingCreatedClassId]);
```

- [ ] **Step 2: Run linter and builder**

Run: `npm run lint && npm run build`
Expected: PASS (No undefined variables, builds successfully)

- [ ] **Step 3: Commit**

```bash
git add src/pages/TeacherConsole.jsx
git commit -m "refactor(teacher): useTeacherConsoleData hook and cleanup try-catch"
```

---

### Task 4: Extract `useStudentProfile` Hook

**Files:**
- Create: `src/hooks/useStudentProfile.js`

- [ ] **Step 1: Create the Hook file**

Create `src/hooks/useStudentProfile.js`:

```javascript
import { useState } from 'react';
import useSWR from 'swr';
import { profileService } from '../api/services/profile';
import { taskService } from '../api/services/task';

const fetcherWrapper = async (promise) => {
  const res = await promise;
  if (res.code !== 200 && res.code !== 202) {
    throw new Error(res.message || '请求失败');
  }
  return res;
};

export function useStudentProfile(activeCourseId) {
  const [refreshTask, setRefreshTask] = useState(null);
  
  // Profile Fetching
  const { data: profileRes, error: profileError, mutate: mutateProfile, isLoading: profileLoading } = useSWR(
    activeCourseId ? ['studentProfile', activeCourseId] : null,
    () => fetcherWrapper(profileService.getStudentProfile(activeCourseId))
  );

  const profileData = profileRes?.data || null;

  // Task Polling with SWR (Only polls when refreshTask is active and processing)
  const isPolling = refreshTask?.status === 'processing';
  useSWR(
    isPolling ? ['profileTask', refreshTask.task_id] : null,
    () => fetcherWrapper(taskService.getTaskStatus(refreshTask.task_id)),
    {
      refreshInterval: (data) => {
        const status = data?.data?.status;
        return (status === 'completed' || status === 'failed' || status === 'partial') ? 0 : 2000;
      },
      onSuccess: (res) => {
        const status = res.data?.status || 'processing';
        setRefreshTask(prev => ({ ...prev, status, error_message: res.data?.error_message }));
        if (status === 'completed') {
          mutateProfile(); // Refresh profile when task completes
        }
      }
    }
  );

  const handleProfileRefresh = async () => {
    if (!activeCourseId || isPolling) return;
    try {
      setRefreshTask({ status: 'processing' });
      const res = await profileService.refreshProfile(activeCourseId);
      if (res.code === 202 && res.data?.task_id) {
        setRefreshTask({ task_id: res.data.task_id, status: 'processing' });
      } else {
        setRefreshTask({ status: 'failed', error_message: res.message || '启动失败' });
      }
    } catch (err) {
      setRefreshTask({ status: 'failed', error_message: err.response?.data?.detail?.message || '启动失败' });
    }
  };

  return {
    profileData,
    profileLoading,
    profileError: profileError ? '加载失败，请重试' : null,
    mutateProfile,
    refreshTask,
    isPolling,
    handleProfileRefresh,
    setRefreshTask
  };
}
```

- [ ] **Step 2: Test imports**

Run: `npm run lint`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/hooks/useStudentProfile.js
git commit -m "feat(hooks): extract useStudentProfile hook with SWR polling"
```

---

### Task 5: Refactor `StudentProfile.jsx` to use Hook

**Files:**
- Modify: `src/pages/StudentProfile.jsx`

- [ ] **Step 1: Replace manual state, fetching, and pollTask with the Hook**

In `src/pages/StudentProfile.jsx`:
1. Import the hook: `import { useStudentProfile } from '../hooks/useStudentProfile';`
2. Remove local states: `profileData`, `profileError`, `refreshTask`, `refreshing`, `setRefreshing`, `refreshMessage`, `refreshError`, `loading`.
3. Remove `activeCourseRef`, `fetchProfile`, and the giant `pollTask` `useEffect`.
4. Remove `handleProfileRefresh`.
5. Add the hook invocation right after `const [now, setNow] = useState(Date.now());`:

```javascript
  const {
    profileData,
    profileLoading: loading,
    profileError,
    mutateProfile,
    refreshTask,
    isPolling: refreshing,
    handleProfileRefresh
  } = useStudentProfile(activeCourseId);

  // Sync instruction when profile loads
  useEffect(() => {
    const ci = profileData?.drive_intent?.custom_instruction;
    if (typeof ci === 'string') setCustomInstruction(ci);
  }, [profileData]);

  // Map refresh statuses
  const refreshMessage = refreshTask?.status === 'completed' ? '画像已同步' : (refreshing ? '正在同步画像...' : '');
  const refreshError = refreshTask?.status === 'failed' ? (refreshTask.error_message || '同步失败') : '';
```

6. Update `handleGoalChange` to use `mutateProfile`:
```javascript
  const handleGoalChange = async (goalType) => {
    if (goalSubmitting) return;
    setGoalSubmitting(true);
    try {
      await profileService.updateLearningGoal(activeCourseId, goalType);
      mutateProfile();
    } catch (err) {
      console.error('更新学习方向失败:', err);
    } finally {
      setGoalSubmitting(false);
    }
  };
```

- [ ] **Step 2: Run linter and builder**

Run: `npm run lint && npm run build`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/pages/StudentProfile.jsx
git commit -m "refactor(profile): useStudentProfile hook, SWR polling, cleanup try-catch"
```
