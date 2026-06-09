# CourseCatalog Resource Consumption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Express the first-version CourseCatalog resource consumption loop in the frontend: Admin-generated resources are consumed by teachers and students through class-level `course_id`.

**Architecture:** Keep all reads on the existing class-scoped resource API, `GET /resources?course_id=...`, and reuse the existing `/resource/:id` detail route. Make only frontend product-surface changes: student empty copy, teacher catalog/resource visibility, and E2E regression coverage. No new backend API, no mock data in production code, no catalog-level resource model.

**Tech Stack:** React 19 + Vite, React Router, existing `learningService`, existing `teachingService`, Playwright, ESLint, Vite build.

---

## Pre-Modification Review Required By AGENTS.md

### 1. Problem Analysis

The current frontend already supports these contract facts:

- Student Dashboard reads class-scoped resources through `learningService.getResources({ course_id: activeCourseId, page: 1, page_size: 50 })`.
- `Dashboard.jsx` has a separate no-course branch and course-with-no-resources branch.
- TeacherConsole reads classes from `/courses`; `teachingService.getClasses()` preserves `catalog_id` and `catalog_title`.
- TeacherConsole currently shows `catalog_title` on class cards, but does not fetch or display the selected class resources.
- `/resource/:id` is already accessible to teacher and student roles through `ProtectedRoute`.
- `ResourceDetail.jsx` does not have explicit 404/403 handling; this implementation will not claim or change that behavior.

The missing first-version consumption surface is:

- Student course-with-empty-resources copy still says "暂无资源 / 当前课程暂无学习资源" instead of "课程资源正在准备中 / 请稍后查看".
- TeacherConsole cannot confirm "this class is bound to this catalog and these learning resources are visible to students".
- Existing E2E only checks TeacherConsole does not expose generation. It does not assert teacher resource list/detail entry or the new student empty copy.

### 2. Planned File Changes

- Modify `src/pages/Dashboard.jsx`
  - Change only the resources-empty copy in the branch with `data-testid="resources-empty"`.
  - Do not change the no-course branch copy.
- Modify `src/pages/TeacherConsole.jsx`
  - Import `learningService`.
  - Track selected-class resources, loading, and error state.
  - Fetch `GET /resources` with `{ course_id: activeClass, page: 1, page_size: 50 }` when `activeClass` changes.
  - Add a read-only "本班学习资源" section with catalog binding status, class-scoped resource cards, empty state, and detail navigation.
  - Do not add generate/upload/delete controls.
- Modify `e2e/specs.spec.js`
  - Add a student Dashboard empty-state regression.
  - Extend the teacher regression to verify catalog status, resource list, detail navigation, and no deprecated generation calls.

### 3. Modification Approach

- Use the current `learningService.getResources()` instead of creating new service methods.
- Put TeacherConsole resource fetching in the same `activeClass` effect as students/insights so class changes refresh all class-specific panels together.
- Use small local helpers inside `TeacherConsole.jsx` for resource type labels and cards only if needed.
- Make the teacher resource section read-only. Clicking a resource card navigates to `/resource/${resource.id}`.
- Preserve existing route and API contracts.

### 4. Possibly Affected Features

- Student Dashboard resource empty state.
- Student Dashboard resource list filtering if the empty branch is accidentally changed; tests should prevent this.
- TeacherConsole class-switching behavior and loading state.
- TeacherConsole student monitor and insights fetch timing, because resource fetch will run in the same selected-class lifecycle.
- ResourceDetail teacher access through existing route.

### 5. Planned Test Commands

- Focused E2E:
  - `npm run test:e2e -- e2e/specs.spec.js -g "Student dashboard shows preparation copy|Teacher console shows catalog-bound class resources"`
- Existing Admin/Teacher regression:
  - `npm run test:e2e -- e2e/specs.spec.js -g "Admin course catalog resource generation|Teacher console does not expose"`
- Frontend checks:
  - `npm run lint`
  - `npm run build`

No backend pytest is required because this plan does not change backend API, schemas, persistence, or OpenAPI.

## Scope

In scope:

- Student no-resource copy for the class-scoped resources branch.
- Teacher read-only visibility into selected class catalog binding and class-scoped learning resources.
- Teacher resource detail navigation using existing `/resource/:id`.
- E2E coverage for student empty copy and teacher consumption surface.
- `WORKFLOW.md` update after implementation.
- One concise Chinese commit after each completed modification batch.

Out of scope:

- AI Chat, Quiz, LearningPath, KG ready gate, or Agent retrieval changes.
- Admin source material visibility for students or teachers.
- Teacher generation, upload, delete, regenerate, or request-generation controls.
- Catalog-level resource APIs or backfill behavior.
- ResourceDetail 404/403 UX changes.
- Backend, Agent Service, OpenAPI, or `../docs/` changes.

## Contract Facts To Preserve

- Student and teacher consumption reads `Resource.course_id` through class-level `course_id`.
- `CourseOffering.id == Course.id` only applies to catalog-bound courses created through the current backend binding branch; legacy courses may have no catalog binding.
- Late-created classes do not get historical resources unless they were in the generation task fan-out snapshot.
- TeacherConsole must not call deprecated `POST /resources/generate`.
- No production mock data or fake resource fallback.

## File Structure

Frontend:

- Modify `src/pages/Dashboard.jsx`
  - Responsible for student course resource list and empty states.
- Modify `src/pages/TeacherConsole.jsx`
  - Responsible for teacher selected-class overview, roster, insights, and new read-only learning resource confirmation panel.
- Modify `e2e/specs.spec.js`
  - Responsible for browser-level regression coverage.

Docs:

- Modify `WORKFLOW.md`
  - Record implementation, verification commands, OpenAPI non-drift, commit hash/message, and residual risk.

---

## Task 1: Student Dashboard Empty Copy

**Files:**
- Modify: `e2e/specs.spec.js`
- Modify: `src/pages/Dashboard.jsx`

- [ ] **Step 1: Add failing E2E coverage for course-with-no-resources copy**

Append this test inside `test.describe('Vite Multi-Agent Learning System E2E Suite', () => { ... })` in `e2e/specs.spec.js`, near the existing student Dashboard tests:

```js
  test('Student dashboard shows preparation copy when active course has no resources', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'e2e-student-token');
      localStorage.setItem('course_id', 'course-empty-e2e');
    });

    await page.route('**/api/v1/users/me', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          id: 'student-empty-e2e',
          email: 'student@example.com',
          username: 'Student E2E',
          role: 'student',
        },
      }));
    });

    await page.route('**/api/v1/courses**', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          courses: [{
            id: 'course-empty-e2e',
            name: '空资源教学班',
            description: '有课程但暂无学习资源',
          }],
        },
      }));
    });

    await page.route(/\/api\/v1\/resources(\?.*)?$/, async (route) => {
      expect(route.request().method()).toBe('GET');
      const url = new URL(route.request().url());
      expect(url.searchParams.get('course_id')).toBe('course-empty-e2e');
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          resources: [],
          total: 0,
          page: 1,
          page_size: 50,
        },
      }));
    });

    await page.goto('/dashboard');

    await expect(page.getByText('暂无课程')).toHaveCount(0);
    await expect(page.getByTestId('resources-empty')).toBeVisible();
    await expect(page.getByTestId('resources-empty').getByText('课程资源正在准备中')).toBeVisible();
    await expect(page.getByTestId('resources-empty').getByText('请稍后查看')).toBeVisible();
  });
```

- [ ] **Step 2: Run the focused E2E and verify it fails**

Run:

```bash
npm run test:e2e -- e2e/specs.spec.js -g "Student dashboard shows preparation copy"
```

Expected: FAIL because `resources-empty` still renders "暂无资源 / 当前课程暂无学习资源".

- [ ] **Step 3: Change only the resources-empty copy**

In `src/pages/Dashboard.jsx`, replace the existing course-with-no-resources empty branch:

```jsx
              <div data-testid="resources-empty">
                <FeedbackStatus status="empty" title="暂无资源" description="当前课程暂无学习资源" />
              </div>
```

with:

```jsx
              <div data-testid="resources-empty">
                <FeedbackStatus status="empty" title="课程资源正在准备中" description="请稍后查看" />
              </div>
```

Do not edit this no-course branch:

```jsx
          <FeedbackStatus status="empty" title="暂无课程" description="请先加入一门课程" />
```

- [ ] **Step 4: Run the focused E2E and verify it passes**

Run:

```bash
npm run test:e2e -- e2e/specs.spec.js -g "Student dashboard shows preparation copy"
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add src/pages/Dashboard.jsx e2e/specs.spec.js
git commit -m "调整学生资源空态文案"
```

Expected: commit succeeds. Do not stage unrelated dirty or untracked files.

---

## Task 2: Teacher Read-Only Class Resources

**Files:**
- Modify: `e2e/specs.spec.js`
- Modify: `src/pages/TeacherConsole.jsx`

- [ ] **Step 1: Add failing E2E coverage for teacher resource consumption**

Add this test inside `test.describe('Vite Multi-Agent Learning System E2E Suite', () => { ... })`, near the existing teacher regression tests:

```js
  test('Teacher console shows catalog-bound class resources and opens detail', async ({ page }) => {
    let deprecatedGenerateRequests = 0;

    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'e2e-teacher-token');
    });

    await page.route('**/api/v1/users/me', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          id: 'teacher-resource-e2e',
          email: 'teacher@example.com',
          username: 'Teacher Resource E2E',
          role: 'teacher',
        },
      }));
    });

    await page.route('**/api/v1/resources/generate', async (route) => {
      deprecatedGenerateRequests += 1;
      await route.fulfill(jsonResponse({
        code: 410,
        message: 'deprecated',
        data: null,
      }, 410));
    });

    await page.route('**/api/v1/courses**', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          courses: [{
            id: 'class-resource-e2e',
            name: '一班',
            description: '数据结构',
            student_count: 1,
            catalog_id: 'catalog-resource-e2e',
            catalog_title: 'E2E 资源库',
          }],
        },
      }));
    });

    await page.route('**/api/v1/teaching/classes/class-resource-e2e/students', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          students: [{
            id: 'student-resource-e2e',
            username: 'student',
            real_name: '学生',
            student_id: '20260001',
          }],
        },
      }));
    });

    await page.route('**/api/v1/teaching/classes/class-resource-e2e/insights', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          weak_points_top: [],
          path_node_progress: {
            total_nodes: 0,
            completed: 0,
            in_progress: 0,
            recommended: 0,
            pending: 0,
          },
          avg_quiz_score: null,
          total_quiz_attempts: 0,
        },
      }));
    });

    await page.route(/\/api\/v1\/resources(\?.*)?$/, async (route) => {
      expect(route.request().method()).toBe('GET');
      const url = new URL(route.request().url());
      expect(url.searchParams.get('course_id')).toBe('class-resource-e2e');
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          resources: [{
            id: 'resource-teacher-e2e',
            course_id: 'class-resource-e2e',
            title: '二叉树讲义',
            type: 'document',
            description: '面向学生展示的学习资源',
            tags: ['tree'],
            chapter: '树',
            knowledge_point: '二叉树',
            view_count: 0,
          }],
          total: 1,
          page: 1,
          page_size: 50,
        },
      }));
    });

    await page.route('**/api/v1/resources/resource-teacher-e2e', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          id: 'resource-teacher-e2e',
          course_id: 'class-resource-e2e',
          title: '二叉树讲义',
          type: 'document',
          description: '面向学生展示的学习资源',
          content: '二叉树是每个节点最多有两个子节点的树结构。',
          tags: ['tree'],
          chapter: '树',
          knowledge_point: '二叉树',
        },
      }));
    });

    await page.goto('/teacher');

    await expect(page.getByRole('heading', { name: '教学班选择' })).toBeVisible();
    await expect(page.getByTestId('teacher-resource-section')).toBeVisible();
    await expect(page.getByText('绑定资源库：E2E 资源库')).toBeVisible();
    await expect(page.getByTestId('teacher-resource-card')).toHaveCount(1);
    await expect(page.getByTestId('teacher-resource-card').getByText('二叉树讲义')).toBeVisible();
    await expect(page.getByRole('button', { name: '生成资源' })).toHaveCount(0);
    await expect(page.getByText('上传原始资料')).toHaveCount(0);
    await expect(page.getByText('删除资源')).toHaveCount(0);

    await page.getByTestId('teacher-resource-card').click();
    await page.waitForURL('**/resource/resource-teacher-e2e');
    await expect(page.getByRole('heading', { name: '二叉树讲义' })).toBeVisible();
    await expect(page.getByText('二叉树是每个节点最多有两个子节点的树结构。')).toBeVisible();
    expect(deprecatedGenerateRequests).toBe(0);
  });
```

- [ ] **Step 2: Add failing E2E coverage for teacher no-resource fallback**

Add this second teacher test in `e2e/specs.spec.js`:

```js
  test('Teacher console shows admin contact fallback when bound class has no resources', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('access_token', 'e2e-teacher-token');
    });

    await page.route('**/api/v1/users/me', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          id: 'teacher-empty-resource-e2e',
          email: 'teacher@example.com',
          username: 'Teacher Empty Resource E2E',
          role: 'teacher',
        },
      }));
    });

    await page.route('**/api/v1/courses**', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          courses: [{
            id: 'class-empty-resource-e2e',
            name: '二班',
            description: '数据结构',
            student_count: 0,
            catalog_id: 'catalog-empty-resource-e2e',
            catalog_title: '空资源库',
          }],
        },
      }));
    });

    await page.route('**/api/v1/teaching/classes/class-empty-resource-e2e/students', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: { students: [] },
      }));
    });

    await page.route('**/api/v1/teaching/classes/class-empty-resource-e2e/insights', async (route) => {
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          weak_points_top: [],
          path_node_progress: {
            total_nodes: 0,
            completed: 0,
            in_progress: 0,
            recommended: 0,
            pending: 0,
          },
          avg_quiz_score: null,
          total_quiz_attempts: 0,
        },
      }));
    });

    await page.route(/\/api\/v1\/resources(\?.*)?$/, async (route) => {
      const url = new URL(route.request().url());
      expect(url.searchParams.get('course_id')).toBe('class-empty-resource-e2e');
      await route.fulfill(jsonResponse({
        code: 200,
        message: 'success',
        data: {
          resources: [],
          total: 0,
          page: 1,
          page_size: 50,
        },
      }));
    });

    await page.goto('/teacher');

    await expect(page.getByTestId('teacher-resource-section')).toBeVisible();
    await expect(page.getByText('绑定资源库：空资源库')).toBeVisible();
    await expect(page.getByText('本班暂无学习资源，请联系管理员生成')).toBeVisible();
  });
```

- [ ] **Step 3: Run the focused E2E and verify both teacher tests fail**

Run:

```bash
npm run test:e2e -- e2e/specs.spec.js -g "Teacher console shows catalog-bound class resources|Teacher console shows admin contact fallback"
```

Expected: FAIL because `TeacherConsole.jsx` does not render `teacher-resource-section` or fetch `/resources`.

- [ ] **Step 4: Import learningService and add resource type metadata**

At the top of `src/pages/TeacherConsole.jsx`, add:

```jsx
import { learningService } from '../api/services/learning';
```

Below the `useMock` constant, add:

```jsx
const RESOURCE_TYPE_LABELS = {
  document: '文档',
  mindmap: '思维导图',
  reading: '阅读资料',
  code: '代码',
  video: '视频',
};
```

- [ ] **Step 5: Add selected-class resource state**

Inside `TeacherConsole()`, near the existing student/insight state declarations, add:

```jsx
  const [resources, setResources] = useState([]);
  const [resourcesLoading, setResourcesLoading] = useState(false);
  const [resourcesError, setResourcesError] = useState(null);
```

- [ ] **Step 6: Fetch resources when activeClass changes**

In the existing `useEffect(() => { if (!activeClass) return; ... }, [activeClass]);`, after the insights request block and before the `return () => { cancelled = true; };`, add:

```jsx
    setResourcesLoading(true);
    setResourcesError(null);
    learningService.getResources({ course_id: activeClass, page: 1, page_size: 50 })
      .then((res) => {
        if (!cancelled && res.code === 200) {
          setResources(res.data?.resources || []);
        }
      })
      .catch((err) => {
        if (cancelled) return;
        console.error('class resources fetch error', err);
        setResources([]);
        setResourcesError('班级资源加载失败，请稍后重试。');
      })
      .finally(() => {
        if (!cancelled) setResourcesLoading(false);
      });
```

This preserves the same `activeClass` lifecycle as student and insights fetches.

- [ ] **Step 7: Insert the read-only teacher resource section**

In `src/pages/TeacherConsole.jsx`, insert the following section after the class selection section and before the student monitoring table section:

```jsx
          {/* Class Learning Resources */}
          <section data-testid="teacher-resource-section" className="mb-margin">
            <div className="bg-white rounded-xl border border-outline-variant shadow-sm overflow-hidden">
              <div className="px-md py-4 border-b border-outline-variant flex flex-col gap-2 bg-surface-container-lowest md:flex-row md:items-center md:justify-between">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-primary">library_books</span>
                  <div>
                    <h3 className="font-h3 text-xl text-on-surface">本班学习资源</h3>
                    <p className="text-xs text-outline">
                      {activeClassInfo?.catalog_title
                        ? `绑定资源库：${activeClassInfo.catalog_title}`
                        : '未绑定资源库'}
                    </p>
                  </div>
                </div>
                <span className="text-xs text-outline">
                  {resourcesLoading ? '正在同步资源...' : `当前 ${resources.length} 个资源`}
                </span>
              </div>

              <div className="p-md">
                {resourcesLoading ? (
                  <div className="py-8 flex justify-center">
                    <FeedbackStatus status="loading" title="加载班级资源..." />
                  </div>
                ) : resourcesError ? (
                  <div className="py-8 flex justify-center">
                    <FeedbackStatus status="error" title={resourcesError} />
                  </div>
                ) : resources.length === 0 ? (
                  <div className="py-8 flex justify-center">
                    <FeedbackStatus status="empty" title="本班暂无学习资源，请联系管理员生成" />
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                    {resources.map((resource) => (
                      <button
                        key={resource.id}
                        type="button"
                        data-testid="teacher-resource-card"
                        onClick={() => navigate(`/resource/${resource.id}`)}
                        className="text-left rounded-xl border border-outline-variant bg-surface-container-lowest p-4 hover:border-primary/50 hover:bg-surface-container-low transition-colors"
                      >
                        <div className="flex items-center justify-between gap-2 mb-3">
                          <span className="px-2.5 py-1 rounded border border-outline-variant bg-white text-xs font-semibold text-on-surface-variant">
                            {RESOURCE_TYPE_LABELS[resource.type] || resource.type || '资源'}
                          </span>
                          {resource.chapter && (
                            <span className="text-xs text-outline truncate max-w-[120px]">
                              {resource.chapter}
                            </span>
                          )}
                        </div>
                        <h4 className="text-sm font-bold text-on-surface line-clamp-2">{resource.title || '未命名资源'}</h4>
                        <p className="mt-2 text-xs text-outline line-clamp-2">
                          {resource.description || '暂无描述'}
                        </p>
                        {resource.knowledge_point && (
                          <p className="mt-3 text-xs font-semibold text-primary line-clamp-1">
                            {resource.knowledge_point}
                          </p>
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </section>
```

- [ ] **Step 8: Run the focused teacher E2E and verify it passes**

Run:

```bash
npm run test:e2e -- e2e/specs.spec.js -g "Teacher console shows catalog-bound class resources|Teacher console shows admin contact fallback"
```

Expected: PASS.

- [ ] **Step 9: Run the existing teacher no-generation regression**

Run:

```bash
npm run test:e2e -- e2e/specs.spec.js -g "Teacher console does not expose resource generation entry"
```

Expected: PASS, and `deprecatedGenerateRequests` remains `0`.

- [ ] **Step 10: Commit Task 2**

Run:

```bash
git add src/pages/TeacherConsole.jsx e2e/specs.spec.js
git commit -m "增加教师端班级资源查看"
```

Expected: commit succeeds. Do not stage unrelated dirty or untracked files.

---

## Task 3: Regression, Build, And Progress Record

**Files:**
- Modify: `WORKFLOW.md`

- [ ] **Step 1: Run Admin/Teacher CourseCatalog E2E regression**

Run:

```bash
npm run test:e2e -- e2e/specs.spec.js -g "Admin course catalog resource generation|Teacher console does not expose"
```

Expected: PASS. This confirms Admin generation/soft-delete UI still uses Admin endpoints and TeacherConsole still does not expose generation.

- [ ] **Step 2: Run all new consumption E2E tests together**

Run:

```bash
npm run test:e2e -- e2e/specs.spec.js -g "Student dashboard shows preparation copy|Teacher console shows catalog-bound class resources|Teacher console shows admin contact fallback"
```

Expected: PASS.

- [ ] **Step 3: Run lint**

Run:

```bash
npm run lint
```

Expected: PASS. If it fails on the new code, fix only the new lint issues. If it fails on pre-existing unrelated files, record the exact failure in the final summary and `WORKFLOW.md`.

- [ ] **Step 4: Run build**

Run:

```bash
npm run build
```

Expected: PASS.

- [ ] **Step 5: Update WORKFLOW.md**

Add a dated entry to `WORKFLOW.md` with:

```markdown
### 2026-06-09 CourseCatalog 资源消费闭环前端落地

- 实现状态：学生端有课程但无资源空态改为“课程资源正在准备中 / 请稍后查看”；教师端新增本班学习资源只读查看区，按当前教学班 `course_id` 调 `GET /resources`，可跳转现有 `/resource/:id` 详情。
- 修改文件：`src/pages/Dashboard.jsx`、`src/pages/TeacherConsole.jsx`、`e2e/specs.spec.js`。
- 契约：未修改 Backend/OpenAPI；继续按班存/按班读，不恢复教师端 deprecated `/resources/generate`。
- 验证：
  - `npm run test:e2e -- e2e/specs.spec.js -g "Student dashboard shows preparation copy|Teacher console shows catalog-bound class resources|Teacher console shows admin contact fallback"`：通过。
  - `npm run test:e2e -- e2e/specs.spec.js -g "Admin course catalog resource generation|Teacher console does not expose"`：通过。
  - `npm run lint`：通过。
  - `npm run build`：通过。
- 剩余风险：`ResourceDetail.jsx` 仍无显式 404/403 错误态；本轮按 spec 不扩展。
```

If any verification command fails for an unrelated existing issue, replace "通过" with the actual observed failure summary.

- [ ] **Step 6: Commit Task 3**

Run:

```bash
git add WORKFLOW.md
git commit -m "记录资源消费闭环前端落地"
```

Expected: commit succeeds. Do not stage unrelated dirty or untracked files.

---

## Final Verification Checklist

- [ ] `src/pages/Dashboard.jsx` no-course branch still shows "暂无课程 / 请先加入一门课程".
- [ ] `src/pages/Dashboard.jsx` course-with-no-resources branch keeps `data-testid="resources-empty"` and shows "课程资源正在准备中 / 请稍后查看".
- [ ] `src/pages/TeacherConsole.jsx` fetches resources only through `learningService.getResources({ course_id: activeClass, page: 1, page_size: 50 })`.
- [ ] TeacherConsole shows catalog binding status using `activeClassInfo.catalog_title`.
- [ ] TeacherConsole empty resources fallback says "本班暂无学习资源，请联系管理员生成".
- [ ] TeacherConsole has no generate/upload/delete resource controls.
- [ ] Teacher resource cards navigate to existing `/resource/:id`.
- [ ] No Backend/OpenAPI files were changed.
- [ ] No production mock/fake resource fallback was introduced.
- [ ] All planned tests were run or any skipped/failed command is documented with reason.

## Self-Review

Spec coverage:

- Student no-course and no-resource branches are covered by Task 1.
- Teacher catalog binding status, class resource list, no-resource fallback, and detail navigation are covered by Task 2.
- No teacher generation/upload/delete controls are covered by Task 2 and the existing regression.
- Admin resource generation is not reimplemented, only regressed in Task 3.
- AI Chat, Quiz, LearningPath, KG ready gate, catalog-level resource API, and automatic backfill are intentionally out of scope.

Placeholder scan:

- No task uses disallowed placeholder wording or unspecified test instructions.
- All code-changing steps include concrete snippets.
- All verification steps include exact commands and expected outcomes.

Type and API consistency:

- `learningService.getResources(params)` already exists in `src/api/services/learning.js`.
- `teachingService.getClasses()` already returns `catalog_id` and `catalog_title`.
- Teacher resource cards use existing resource fields already consumed by Dashboard: `id`, `title`, `type`, `description`, `chapter`, `knowledge_point`.
- Detail navigation reuses the existing `/resource/:id` route allowed for teacher and student roles.
