# 阶段一验收缺陷修复设计

**日期**: 2026-06-05
**状态**: 已确认，待实施
**范围**: 前端 7 个缺陷修复，不涉及后端 API 变更

## 问题总览

| # | 级别 | 问题 | 根因 |
|---|------|------|------|
| 1 | 阻断 | Playwright E2E 3/3 失败 | CORS: playwright 用 127.0.0.1，后端只允许 localhost |
| 2 | 高 | 资源生成声明不实 | triggerResourceGeneration/getTaskStatus 未被页面调用 |
| 3 | 高 | FeedbackStatus 未接入 + 缺少 prop-types | 组件未引用；prop-types 未在 package.json |
| 4 | 高 | E2E 覆盖力度不足 | 断言不完整、定位方式不可靠 |
| 5 | 中 | 无课程用户永久 Loading | activeCourseId 为空时未 setLoading(false) |
| 6 | 中 | 真实模式仍存在硬编码回退 | major/grade/course_id/student_id/标题含假数据 |
| 7 | 中 | WORKFLOW.md 写入不实验收结果 + test-results 未 ignore | 乐观描述、缺失 gitignore 条目 |

## 实施批次

### 第一轮：页面状态修复（5 个文件）

先处理 FeedbackStatus.jsx（移除 prop-types），再接入 Dashboard、TeacherConsole、TeacherStudentReport。

| 文件 | 修改内容 |
|------|---------|
| `FeedbackStatus.jsx` | 移除 prop-types 导入和 propTypes 声明 |
| `Dashboard.jsx` | 接入 FeedbackStatus、修复无课程永久 Loading、添加 data-testid、提取 fetchResources 到组件作用域 |
| `TeacherConsole.jsx` | 接入 FeedbackStatus、分离班级/学生 Loading、硬编码回退改为 —、添加 data-testid |
| `TeacherStudentReport.jsx` | 仅接受 URL Query 参数、缺失时显示错误、标题改为真实数据 |
| `Quiz.jsx` | 添加 `data-testid="quiz-question"` 和 `data-testid="quiz-empty"` |

### 第二轮：E2E 修复（5 个文件）

| 文件 | 修改内容 |
|------|---------|
| `playwright.config.js` | baseURL + webServer.url 改为 localhost |
| `package.json` | 将工作区中的 `@playwright/test` 依赖和 `test:e2e` script 纳入提交 |
| `package-lock.json` | 同步 lockfile |
| `e2e/specs.spec.js` | 补全断言、添加 data-testid 定位、移除不可靠选择器 |
| `.gitignore` | 添加 test-results/ |

### 第三轮：文档（1 个文件）

| 文件 | 修改内容 |
|------|---------|
| `WORKFLOW.md` | 修正 E2E 验收状态、chunk 警告描述、资源生成声明；根据实际验证结果记录 |

## 详细设计

### 1. CORS 修复

**文件**: `playwright.config.js`

- 第 16 行 `baseURL: 'http://127.0.0.1:5173'` → `'http://localhost:5173'`
- 第 29 行 `url: 'http://127.0.0.1:5173'` → `'http://localhost:5173'`

### 2. 资源生成声明清理

**不修改** `learning.js`（保留 API 函数以备后用）。

**修改** `WORKFLOW.md`（第三轮）:
- 将"触发 Agent 后台任务并实现完整任务状态流转展示"改为"保留 triggerResourceGeneration/getTaskStatus API 服务函数（前端页面未接入，待后续阶段实现）"
- E2E 结果按实施后实际状态记录

### 3. FeedbackStatus 接入

**FeedbackStatus.jsx**（第一轮首个修改）:
- 删除第 1 行 `import PropTypes from 'prop-types';`
- 删除第 52-57 行 `FeedbackStatus.propTypes = {...}`

**Dashboard.jsx**:
- 导入 `FeedbackStatus`
- 将 `fetchResources` 从 useEffect 内提取到组件作用域，使 JSX 可访问 `onRetry={fetchResources}`
- 新增 `error` 状态，请求失败时设置
- 使用 `useCourse()` 的 `loading` 判断课程加载状态：
  - `loading` 为 true → `<FeedbackStatus status="loading" title="加载课程中..." />`
  - 课程列表为空 + loading 完成 → `<FeedbackStatus status="empty" title="暂无课程" description="请先加入一门课程" />`
- 资源加载中 → `<FeedbackStatus status="loading" title="加载资源中..." />`
- 资源加载失败 → `<FeedbackStatus status="error" title="加载失败" description="请检查网络连接或稍后重试" onRetry={fetchResources} />`
- 资源为空 → `<FeedbackStatus status="empty" title="暂无资源" description="当前课程暂无学习资源" />`
- 为资源卡片添加 `data-testid="resource-card"`
- 为空状态容器添加 `data-testid="resources-empty"`

**TeacherConsole.jsx**:
- 导入 `FeedbackStatus`
- 分离两类 loading 状态：`classesLoading` 和 `studentsLoading`（初始化均为 true）
- 班级列表请求 `.finally(() => setClassesLoading(false))`
- 班级加载中 → `<FeedbackStatus status="loading" title="加载班级列表..." />`
- 班级列表为空 + 加载完成 → `<FeedbackStatus status="empty" title="暂无班级" description="您目前没有管理任何班级" />`
- 学生加载中 → `<FeedbackStatus status="loading" title="加载学生列表..." />`
- 学生列表为空 + 加载完成 → `<FeedbackStatus status="empty" title="暂无学生" description="当前班级暂无学生数据" />`
- 为学生卡片添加 `data-testid="student-card"`

**Quiz.jsx**（新增到修改范围）:
- 为题目元素添加 `data-testid="quiz-question"`
- 为空状态添加 `data-testid="quiz-empty"`

### 4. E2E 用例修复

**specs.spec.js**:
- UseCase 1（第 42-47 行）：追加断言 `page.locator('[data-testid="resource-card"]').first()` 或 `page.locator('[data-testid="resources-empty"]')` 可见
- UseCase 2（第 58-61 行）：课程数量断言改用 `const optionCount = await selectEl.locator('option').count(); expect(optionCount).toBeGreaterThanOrEqual(2);`，不使用 `test.fail()`
- UseCase 2（第 70-72 行）：追加断言 Quiz 页面存在 `[data-testid="quiz-question"]` 或 `[data-testid="quiz-empty"]`
- UseCase 3（第 91 行）：`div[onClick*="report"]` → `[data-testid="student-card"]`
- 移除所有 `page.waitForTimeout()`，改用基于断言的等待

### 5. 永久 Loading 修复

**Dashboard.jsx** `useEffect`:
```
// 当 activeCourseId 为空时也必须结束 loading
if (!activeCourseId) {
  setLoading(false);
  return;
}
```
同时消费 `CourseContext.loading` 判断课程列表是否仍在加载。

**TeacherConsole.jsx** `useEffect`（班级列表）:
```
teachingService.getClasses()
  .then(...)
  .catch(console.error)
  .finally(() => setClassesLoading(false));
```
学生列表依赖 `activeClass`，仅在 `activeClass` 存在时进入 `studentsLoading`。

### 6. 硬编码回退清理

**TeacherConsole.jsx**:
- 第 158 行: `student.major || '计算机科学'` → `student.major || '—'`
- 第 163 行: `student.grade || '2026级'` → `student.grade || '—'`

**TeacherStudentReport.jsx**:
- 仅从 `queryParams.get('course_id')` 和 `queryParams.get('student_id')` 获取参数
- 移除 `location.state`、`localStorage`、`'default_course'`、`'u_01'` 回退
- 任一参数缺失 → 不发起 API 请求，渲染 `<FeedbackStatus status="error" title="参数缺失" description="请从学生列表页面进入" />`
- 第 73 行: `· 李华` → `· {report.student?.real_name || report.username || '学生报告'}`

### 7. 文档与 gitignore

**.gitignore**（第二轮）: 追加 `test-results/`

**WORKFLOW.md**（第三轮）: 实施后根据实际验证结果更新第 140 行条目：
- 标题改为反映实际 E2E 结果
- 明确记录 `npm run lint`、`npm run build`、`npm run test:e2e`、`git diff --check` 实际结果
- 修正"0 errors, 0 warnings"为准确描述（lint: 0 errors 0 warnings; build: 通过，含 chunk 警告）

## 不修改的文件

- `AGENTS.md` — 保持现有 Source of Truth 规则不变
- `frontend/src/api/services/learning.js` — 保留 API 函数
- `frontend/.gitkeep` — 不在此轮删除

## 工作区卫生

- `AGENTS.md`、`frontend/.gitkeep` 变更不纳入提交
- `test-results/` 加入 .gitignore 后不追踪
- 每轮独立 commit，不混入无关变更

## TDD 与提交要求

每轮执行顺序：
1. **RED** — 先运行相关验证确认当前失败状态（第一轮：确认构建/页面状态缺陷；第二轮：确认 E2E 3/3 失败）
2. **GREEN** — 实施修改
3. **IMPROVE** — 运行验证确认通过
4. **COMMIT** — 独立提交本轮文件
5. 第三轮仅在全部验证通过后执行，**只记录实际结果，不预先写入乐观结论**

## 验证标准

实施完成后：
- [ ] `npm run lint` 通过（0 errors, 0 warnings）
- [ ] `npm run build` 通过
- [ ] `npm run test:e2e` 3/3 通过
- [ ] `git diff --check` 通过
- [ ] 真实模式下 Dashboard 无课程时显示 Empty 而非永久 spinner（人工验证：现有 E2E 账号均有课程，无法自动化覆盖）
- [ ] 真实模式下 TeacherConsole 无班级时显示 Empty 而非永久 spinner（人工验证：现有 E2E 账号均有班级，无法自动化覆盖）
- [ ] TeacherStudentReport 缺少参数时显示错误而非假数据
- [ ] WORKFLOW.md 记录实际验证结果（非预估）
