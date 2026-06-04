# 阶段一验收缺陷修复 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复阶段一验收中发现的 7 个前端缺陷（CORS 阻断、声明不实、组件未接入、E2E 覆盖不足、永久 Loading、硬编码回退、文档不实），使 E2E 3/3 通过、构建通过、lint 通过。

**Architecture:** 三轮实施：第一轮修复页面状态（FeedbackStatus 清理 + Dashboard/TeacherConsole/TeacherStudentReport/Quiz 接入），第二轮修复 E2E 基础设施（CORS + Playwright 依赖纳入 + 用例重写 + .gitignore），第三轮根据实际验证结果更新 WORKFLOW.md。每轮独立验证并 commit。

**Tech Stack:** React 19, Vite 8, Tailwind CSS 4, Playwright 1.60, Node.js

---

### Task 1: FeedbackStatus.jsx — 移除 prop-types 依赖

**Files:**
- Modify: `/home/yezisama/workspace/workflow/EDUagent/frontend/src/components/FeedbackStatus.jsx`

- [ ] **Step 1: 删除 prop-types 导入**

删除第 1 行：
```
import PropTypes from 'prop-types';
```

- [ ] **Step 2: 删除 propTypes 声明**

删除第 52-57 行：
```
FeedbackStatus.propTypes = {
  status: PropTypes.oneOf(['loading', 'empty', 'error']).isRequired,
  title: PropTypes.string,
  description: PropTypes.string,
  onRetry: PropTypes.func,
};
```

- [ ] **Step 3: 验证构建**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run build
```

Expected: 构建通过（含 chunk 大小警告，可接受）。

- [ ] **Step 4: 验证 lint**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint
```

Expected: 0 errors, 0 warnings.

---

### Task 2: Dashboard.jsx — 接入 FeedbackStatus + 修复 Loading + 添加 data-testid

**Files:**
- Modify: `/home/yezisama/workspace/workflow/EDUagent/frontend/src/pages/Dashboard.jsx`

- [ ] **Step 1: 提取 fetchResources 到组件作用域并新增 error 状态**

在第 2 行 `import { useState, useEffect } from 'react';` 改为：
```jsx
import { useState, useEffect, useCallback } from 'react';
```

在第 37 行 `const [loading, setLoading] = useState(true);` 之后添加：
```jsx
const [error, setError] = useState(false);
```

将第 39-55 行（整个 useEffect）替换为：
```jsx
const fetchResources = useCallback(async () => {
  if (!activeCourseId) return;
  try {
    setLoading(true);
    setError(false);
    const res = await learningService.getResources({ course_id: activeCourseId, page: 1, page_size: 50 });
    if (res.code === 200 && res.data) {
      setAllResources(res.data.resources || []);
    }
  } catch (err) {
    console.error("Failed to fetch resources:", err);
    setError(true);
  } finally {
    setLoading(false);
  }
}, [activeCourseId]);

useEffect(() => {
  fetchResources();
}, [fetchResources]);
```

- [ ] **Step 2: 导入 FeedbackStatus 和解构 courseLoading**

在第 6 行 `import { useCourse } from '../context/CourseContext';` 下方添加：
```jsx
import FeedbackStatus from '../components/FeedbackStatus';
```

将第 32 行 `const { activeCourseId } = useCourse();` 改为：
```jsx
const { activeCourseId, loading: courseLoading } = useCourse();
```

- [ ] **Step 3: 在 return 前添加课程加载中和无课程状态判断**

在第 66 行 `return (` 之前插入：
```jsx
if (courseLoading) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <FeedbackStatus status="loading" title="加载课程中..." />
    </div>
  );
}

if (!activeCourseId) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <FeedbackStatus status="empty" title="暂无课程" description="请先加入一门课程" />
    </div>
  );
}
```

- [ ] **Step 4: 替换资源 loading 状态**

将第 166-169 行（当前文件中的位置，以 `{loading ?` 开头的三元表达式第一部分）：
```jsx
{loading ? (
  <div className="py-12 flex justify-center">
    <span className="material-symbols-outlined animate-spin text-4xl text-primary">progress_activity</span>
  </div>
) : filteredResources.length > 0 ? (
```

改为：
```jsx
{loading ? (
  <FeedbackStatus status="loading" title="加载资源中..." />
) : error ? (
  <FeedbackStatus status="error" title="加载失败" description="请检查网络连接或稍后重试" onRetry={fetchResources} />
) : filteredResources.length > 0 ? (
```

- [ ] **Step 5: 替换资源为空状态**

将资源为空时的 div（原约第 217-219 行）：
```jsx
<div className="text-center py-12 text-gray-400 text-sm bg-white rounded-xl border border-outline-variant">
  暂无匹配的专题资源
</div>
```

改为：
```jsx
<div data-testid="resources-empty">
  <FeedbackStatus status="empty" title="暂无资源" description="当前课程暂无学习资源" />
</div>
```

- [ ] **Step 6: 为资源卡片添加 data-testid**

在资源卡片 div 上添加属性（原约第 175 行）：
```jsx
<div key={resource.id} data-testid="resource-card" className="bg-white rounded-xl border border-outline-variant p-6 shadow-sm ...">
```

- [ ] **Step 7: 验证构建和 lint**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run build && npm run lint
```

Expected: 构建通过，0 errors, 0 warnings.

---

### Task 3: TeacherConsole.jsx — 接入 FeedbackStatus + 分离 Loading + 硬编码改为 — + data-testid

**Files:**
- Modify: `/home/yezisama/workspace/workflow/EDUagent/frontend/src/pages/TeacherConsole.jsx`

- [ ] **Step 1: 导入 FeedbackStatus**

在第 3 行 `import { teachingService } from '../api/services/teaching';` 下方添加：
```jsx
import FeedbackStatus from '../components/FeedbackStatus';
```

- [ ] **Step 2: 分离 classesLoading 和 studentsLoading**

将第 13 行：
```jsx
const [loading, setLoading] = useState(true);
```

替换为：
```jsx
const [classesLoading, setClassesLoading] = useState(true);
const [studentsLoading, setStudentsLoading] = useState(false);
```

- [ ] **Step 3: 修复班级列表请求 — 添加 finally**

将第 16-23 行：
```jsx
useEffect(() => {
  teachingService.getClasses().then(res => {
    if (res.code === 200 && res.data.length > 0) {
      setClasses(res.data);
      setActiveClass(res.data[0].id);
    }
  }).catch(console.error);
}, []);
```

改为：
```jsx
useEffect(() => {
  teachingService.getClasses().then(res => {
    if (res.code === 200 && res.data.length > 0) {
      setClasses(res.data);
      setActiveClass(res.data[0].id);
    }
  }).catch(console.error).finally(() => setClassesLoading(false));
}, []);
```

- [ ] **Step 4: 修复学生列表请求 — 添加 studentsLoading 管理**

将第 26-37 行：
```jsx
useEffect(() => {
  if (activeClass) {
    setTimeout(() => setLoading(true), 0);
    Promise.all([
      teachingService.getClassStudents(activeClass),
      teachingService.getConsoleInsights(activeClass)
    ]).then(([studentsRes, insightsRes]) => {
      if (studentsRes.code === 200) setStudents(studentsRes.data);
      if (insightsRes.code === 200) setInsights(insightsRes.data);
    }).catch(console.error).finally(() => setLoading(false));
  }
}, [activeClass]);
```

改为：
```jsx
useEffect(() => {
  if (activeClass) {
    setStudentsLoading(true);
    Promise.all([
      teachingService.getClassStudents(activeClass),
      teachingService.getConsoleInsights(activeClass)
    ]).then(([studentsRes, insightsRes]) => {
      if (studentsRes.code === 200) setStudents(studentsRes.data);
      if (insightsRes.code === 200) setInsights(insightsRes.data);
    }).catch(console.error).finally(() => setStudentsLoading(false));
  }
}, [activeClass]);
```

- [ ] **Step 5: 在 return 前添加班级无数据状态判断**

在第 39 行 `return (` 之前插入：
```jsx
if (classesLoading) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <FeedbackStatus status="loading" title="加载班级列表..." />
    </div>
  );
}

if (!classesLoading && classes.length === 0) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <FeedbackStatus status="empty" title="暂无班级" description="您目前没有管理任何班级" />
    </div>
  );
}
```

- [ ] **Step 6: 替换学生列表 loading**

将第 122-124 行（`{loading ?` 的三元表达式）：
```jsx
{loading ? (
  <div className="col-span-1 lg:col-span-2 py-8 flex justify-center"><span className="material-symbols-outlined animate-spin text-4xl text-primary">progress_activity</span></div>
) : (
```

改为：
```jsx
{studentsLoading ? (
  <div className="col-span-1 lg:col-span-2 py-8 flex justify-center">
    <FeedbackStatus status="loading" title="加载学生列表..." />
  </div>
) : (
```

- [ ] **Step 7: 替换学生列表为空状态**

将第 171-173 行：
```jsx
{!loading && students.length === 0 && (
   <div className="col-span-1 lg:col-span-2 py-8 text-center text-outline">暂无学生数据</div>
)}
```

改为：
```jsx
{!studentsLoading && students.length === 0 && (
   <div className="col-span-1 lg:col-span-2 py-8">
     <FeedbackStatus status="empty" title="暂无学生" description="当前班级暂无学生数据" />
   </div>
)}
```

- [ ] **Step 8: 硬编码回退改为 —**

第 158 行：
```jsx
{student.major || '计算机科学'}
```
改为：
```jsx
{student.major || '—'}
```

第 163 行：
```jsx
{student.grade || '2026级'}
```
改为：
```jsx
{student.grade || '—'}
```

- [ ] **Step 9: 为学生卡片添加 data-testid**

在学生卡片 div（约第 126-129 行）上添加属性：
```jsx
<div
  key={student.user_id}
  data-testid="student-card"
  onClick={() => navigate(`/teacher/report?course_id=${activeClass}&student_id=${student.user_id}`)}
  className="flex items-center gap-6 p-4 rounded-xl border border-outline-variant hover:bg-surface-container-low transition-colors cursor-pointer"
>
```

- [ ] **Step 10: 验证构建和 lint**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run build && npm run lint
```

Expected: 构建通过，0 errors, 0 warnings.

---

### Task 4: TeacherStudentReport.jsx — URL Query 深链 + 参数缺失错误 + 动态标题

**Files:**
- Modify: `/home/yezisama/workspace/workflow/EDUagent/frontend/src/pages/TeacherStudentReport.jsx`

- [ ] **Step 1: 导入 FeedbackStatus**

在第 3 行 `import { teachingService } from '../api/services/teaching';` 下方添加：
```jsx
import FeedbackStatus from '../components/FeedbackStatus';
```

- [ ] **Step 2: 仅从 URL Query 获取参数，移除所有回退**

将第 12-14 行：
```jsx
const queryParams = new URLSearchParams(location.search);
const classId = queryParams.get('course_id') || location.state?.class_id || localStorage.getItem('course_id') || 'default_course';
const studentId = queryParams.get('student_id') || location.state?.student_id || 'u_01';
```

改为：
```jsx
const queryParams = new URLSearchParams(location.search);
const classId = queryParams.get('course_id');
const studentId = queryParams.get('student_id');
```

- [ ] **Step 3: useEffect 中参数缺失时直接返回**

将第 19-26 行：
```jsx
useEffect(() => {
  setTimeout(() => setLoading(true), 0);
  teachingService.getStudentReport(classId, studentId).then(res => {
    if (res.code === 200) {
      setReport(res.data);
    }
  }).catch(console.error).finally(() => setLoading(false));
}, [classId, studentId]);
```

改为：
```jsx
useEffect(() => {
  if (!classId || !studentId) {
    setLoading(false);
    return;
  }
  setLoading(true);
  teachingService.getStudentReport(classId, studentId).then(res => {
    if (res.code === 200) {
      setReport(res.data);
    }
  }).catch(console.error).finally(() => setLoading(false));
}, [classId, studentId]);
```

- [ ] **Step 4: loading 和参数缺失状态替换为 FeedbackStatus**

将第 28-34 行：
```jsx
if (loading) {
  return <div className="min-h-screen flex items-center justify-center bg-background"><span className="material-symbols-outlined animate-spin text-4xl text-primary">progress_activity</span></div>;
}

if (!report) {
  return <div className="min-h-screen flex items-center justify-center bg-background">未找到报告数据</div>;
}
```

改为：
```jsx
if (loading) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <FeedbackStatus status="loading" title="加载报告数据..." />
    </div>
  );
}

if (!classId || !studentId) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <FeedbackStatus status="error" title="参数缺失" description="请从学生列表页面进入" />
    </div>
  );
}

if (!report) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <FeedbackStatus status="error" title="未找到报告数据" description="请检查课程和学生信息是否正确" />
    </div>
  );
}
```

- [ ] **Step 5: 标题改为动态数据**

将第 73 行：
```jsx
<h1 className="font-h1 text-h1 text-on-background">学情详尽报告 <span className="text-primary-container">· 李华</span></h1>
```

改为：
```jsx
<h1 className="font-h1 text-h1 text-on-background">学情详尽报告 <span className="text-primary-container">· {report.student?.real_name || report.username || '学生报告'}</span></h1>
```

- [ ] **Step 6: 验证构建和 lint**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run build && npm run lint
```

Expected: 构建通过，0 errors, 0 warnings.

---

### Task 5: Quiz.jsx — 添加 data-testid

**Files:**
- Modify: `/home/yezisama/workspace/workflow/EDUagent/frontend/src/pages/Quiz.jsx`

- [ ] **Step 1: 为空题目状态容器添加 data-testid**

第 89-95 行，在空题目 div 上添加属性：
```jsx
<div data-testid="quiz-empty" className="bg-surface min-h-screen flex items-center justify-center flex-col gap-4">
```

- [ ] **Step 2: 为题目区域添加 data-testid**

第 201 行，在题目 section 上添加属性：
```jsx
<section data-testid="quiz-question" className="bg-white rounded-2xl p-8 border border-slate-200 ...">
```

- [ ] **Step 3: 验证构建**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run build
```

Expected: 构建通过。

---

### Task 6: Round 1 Commit — 页面状态修复

- [ ] **Step 1: 全量验证**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint && npm run build
```

Expected: lint 0/0, 构建通过。

- [ ] **Step 2: 提交第一轮**

```bash
cd /home/yezisama/workspace/workflow/EDUagent && git add \
  frontend/src/components/FeedbackStatus.jsx \
  frontend/src/pages/Dashboard.jsx \
  frontend/src/pages/TeacherConsole.jsx \
  frontend/src/pages/TeacherStudentReport.jsx \
  frontend/src/pages/Quiz.jsx && \
  git diff --check && \
  git commit -m "fix(frontend): integrate FeedbackStatus, fix infinite loading, remove hardcoded fallbacks"
```

---

### Task 7: playwright.config.js — CORS 修复

**Files:**
- Modify: `/home/yezisama/workspace/workflow/EDUagent/frontend/playwright.config.js`

- [ ] **Step 1: 替换两处 127.0.0.1 为 localhost**

第 16 行：
```
baseURL: 'http://127.0.0.1:5173',
```
→
```
baseURL: 'http://localhost:5173',
```

第 29 行：
```
url: 'http://127.0.0.1:5173',
```
→
```
url: 'http://localhost:5173',
```

---

### Task 8: package.json — 确认 Playwright 依赖纳入提交

**Files:**
- Modify: `/home/yezisama/workspace/workflow/EDUagent/frontend/package.json`（确认工作区已有修改）
- Modify: `/home/yezisama/workspace/workflow/EDUagent/frontend/package-lock.json`（确认工作区已有修改）

> 当前工作区中这两个文件已被修改（`git status` 显示 `M`），包含 `@playwright/test` 依赖和 `test:e2e` script。本任务将这些修改纳入提交。

- [ ] **Step 1: 确认依赖和 script 已存在**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && node -e "const p=require('./package.json'); console.log('test:e2e:', p.scripts['test:e2e']); console.log('@playwright/test:', p.devDependencies['@playwright/test'])"
```

Expected: 输出 `test:e2e: playwright test` 和 `@playwright/test: ^1.60.0`。

若缺失则运行：
```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm install --save-dev @playwright/test@^1.60.0
```
并确保 `package.json` 的 `scripts` 中有 `"test:e2e": "playwright test"`。

---

### Task 9: e2e/specs.spec.js — E2E 用例修复

**Files:**
- Modify: `/home/yezisama/workspace/workflow/EDUagent/frontend/e2e/specs.spec.js`

- [ ] **Step 1: UseCase 1 — 追加资源和空状态断言**

将第 42-47 行替换为：

```js
// 3. Assert active course loads resource cards or empty status
const selectEl = page.locator('select');
await expect(selectEl).toBeVisible();

const h1El = page.locator('h1:has-text("资源库")');
await expect(h1El).toBeVisible();

// 验证资源卡片或空状态可见
const resourceCard = page.locator('[data-testid="resource-card"]').first();
const resourcesEmpty = page.locator('[data-testid="resources-empty"]');
await expect(resourceCard.or(resourcesEmpty).first()).toBeVisible();
```

- [ ] **Step 2: UseCase 2 — 课程数量断言（≥2）**

将第 58-61 行替换为：

```js
const optionCount = await selectEl.locator('option').count();
expect(optionCount).toBeGreaterThanOrEqual(2);
await selectEl.selectOption({ index: 1 });
await page.waitForSelector('[data-testid="resource-card"], [data-testid="resources-empty"]');
```

- [ ] **Step 3: UseCase 2 — Quiz 页面数据断言**

将第 69-72 行替换为：

```js
// 4. Go to online testing
await page.goto('/quiz');
await page.waitForURL('**/quiz');
await expect(page).toHaveURL(/.*quiz/);

// 验证题目或空状态可见
const quizQuestion = page.locator('[data-testid="quiz-question"]');
const quizEmpty = page.locator('[data-testid="quiz-empty"]');
await expect(quizQuestion.or(quizEmpty).first()).toBeVisible();
```

- [ ] **Step 4: UseCase 3 — 修复学生卡片选择器**

将第 90-93 行替换为：

```js
// 4. Click a student card from the monitor roster to open the report
const studentCard = page.locator('[data-testid="student-card"]').first();
await expect(studentCard).toBeVisible();
await studentCard.click();
```

- [ ] **Step 5: 移除 waitForTimeout — UseCase 3 班级切换**

将第 85-88 行替换为：

```js
const classButtons = page.locator('button:has-text("班")');
if (await classButtons.count() > 1) {
  await classButtons.nth(1).click();
  await page.waitForSelector('[data-testid="student-card"]');
}
```

---

### Task 10: .gitignore — 添加 test-results/

**Files:**
- Modify: `/home/yezisama/workspace/workflow/EDUagent/frontend/.gitignore`

- [ ] **Step 1: 在文件末尾追加**

```
test-results/
```

- [ ] **Step 2: 确认不再追踪**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && git status test-results/
```

若 test-results/ 当时已被追踪，需先 `git rm --cached -r test-results/`。

---

### Task 11: Round 2 Commit — E2E 修复

- [ ] **Step 1: 提交第二轮**

```bash
cd /home/yezisama/workspace/workflow/EDUagent && git add \
  frontend/playwright.config.js \
  frontend/package.json \
  frontend/package-lock.json \
  frontend/e2e/specs.spec.js \
  frontend/.gitignore && \
  git diff --check && \
  git commit -m "fix(frontend): fix CORS in playwright config, rewrite E2E specs with data-testid, add test-results to gitignore"
```

---

### Task 12: 运行 E2E 测试验证

- [ ] **Step 1: 启动前端开发服务器（确保后端也已启动）**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run dev &
```

- [ ] **Step 2: 运行 E2E 测试**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run test:e2e
```

Expected: 3/3 passed。

- [ ] **Step 3: 若 E2E 失败**

常见原因排查：
- 后端未启动 → 启动 Backend（`python -m uvicorn app.main:app --host 127.0.0.1 --port 8001`）
- 测试账号不存在 → 确认 `s@t.com` / `t@t.com` 已注册
- 验证码服务不可用 → 启动 Agent Service（`uvicorn agent_service.main:app --host 127.0.0.1 --port 8002`）

---

### Task 13: WORKFLOW.md — 根据实际验证结果更新

**Files:**
- Modify: `/home/yezisama/workspace/workflow/EDUagent/backend/WORKFLOW.md`

- [ ] **Step 1: 替换第 140 行标题**

根据 E2E 实际结果，将：
```
- `2026-06-05` `前端阶段一联调全面修复与 E2E 完备验收通过`
```

改为（二选一）：

E2E 全通过：
```
- `2026-06-05` `前端阶段一验收缺陷修复完成（E2E 3/3 通过）`
```

E2E 仍有失败：
```
- `2026-06-05` `前端阶段一验收缺陷修复（E2E N/3 通过，待进一步修复）`
```

- [ ] **Step 2: 修正第 146 行资源生成声明**

将：
```
- **状态组件与E2E用例**：新增通用状态组件 [FeedbackStatus.jsx]...编写 3 条覆盖完整学生资源/路径/测试/教师报告的主流程测试用例。
```

改为：
```
- **状态组件与E2E用例**：FeedbackStatus 已接入 Dashboard、TeacherConsole、TeacherStudentReport（loading/empty/error 三态）。保留 `triggerResourceGeneration()` 和 `getTaskStatus()` API 服务函数（前端页面未接入，待后续阶段实现）。E2E 用例已修复 CORS 和选择器，覆盖率已补强。
```

- [ ] **Step 3: 修正第 148 行警告描述**

将：
```
- **代码规范**：消除所有 trailing whitespace（`git diff --check` 成功），编译打包与 linter 达到 **0 errors, 0 warnings** 标准。
```

改为：
```
- **代码规范**：`git diff --check` 通过，`npm run lint` 为 0 errors 0 warnings，`npm run build` 通过（含 chunk 大小警告）。
```

- [ ] **Step 4: 在条目末尾追加实际验证结果**

```markdown
- **验证结果**：
  - `npm run lint`：[填写实际结果]
  - `npm run build`：[填写实际结果]
  - `npm run test:e2e`：[填写实际结果]
  - `git diff --check`：[填写实际结果]
  - Client API 契约漂移：否
  - Agent API 契约漂移：否
```

- [ ] **Step 5: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent && git add backend/WORKFLOW.md && git commit -m "docs: update WORKFLOW.md with actual stage 1 fix verification results"
```

---

### Task 14: 最终验证

- [ ] **Step 1: 全量检查**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run build
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run test:e2e
cd /home/yezisama/workspace/workflow/EDUagent && git diff --check
```

- [ ] **Step 2: 确认工作区卫生**

```bash
cd /home/yezisama/workspace/workflow/EDUagent && git status
```

确认：`AGENTS.md`、`frontend/.gitkeep` 的变更未纳入提交。`test-results/` 不在追踪列表。

- [ ] **Step 3: 最终验证清单**

  - [ ] `npm run lint` 通过（0 errors, 0 warnings）
  - [ ] `npm run build` 通过
  - [ ] `npm run test:e2e` 3/3 通过
  - [ ] `git diff --check` 通过
  - [ ] 无课程 Dashboard 显示 Empty 而非永久 Loading（人工验证）
  - [ ] 无班级 TeacherConsole 显示 Empty 而非永久 Loading（人工验证）
  - [ ] TeacherStudentReport 缺少参数时显示错误而非假数据
  - [ ] WORKFLOW.md 记录实际验证结果
