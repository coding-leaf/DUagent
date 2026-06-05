# MS-05 + MS-06 前端小适配实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 暴露学生加入课程入口 + 修正教师顶部身份硬编码，两个不涉及新 API 的纯前端修复。

**Architecture:** 6 个独立 task，每个修改 1-2 个文件，可单独 lint/build 验证、单独提交。Task 2-4 递进依赖（Dialog → Navbar 集成 → Dashboard 辅助入口），Task 1 和 Task 5 独立。Task 6 为收口验证。

**Tech Stack:** React, Tailwind CSS, JavaScript

**依据 Spec：** `docs/superpowers/specs/2026-06-05-ms05-ms06-frontend-fixes-design.md`

---

### Task 1: Spec/WORKFLOW 收口

**Files:**
- Modify: `frontend/docs/superpowers/specs/2026-06-05-ms05-ms06-frontend-fixes-design.md`
- Modify: `frontend/WORKFLOW.md`

**背景：** Spec 残留文字已修正（`invite_code` → `course_code`，`refreshCourses` 确认已存在）。提交修正 + 在 WORKFLOW.md 记录 joinCourse 契约对齐。

- [ ] **Step 1: 提交 spec 修正 + WORKFLOW 记录**

在 WORKFLOW.md `## 最近验证` 末尾追加：

```markdown
- 2026-06-05：修正 `courseService.joinCourse` 请求体：`{ invite_code }` → `{ course_code }`，对齐 OpenAPI `JoinCourseRequest`（`1161e43`）。
```

Run:
```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/docs/superpowers/specs/2026-06-05-ms05-ms06-frontend-fixes-design.md frontend/WORKFLOW.md
git commit -m "收口 spec 勘误,记录 joinCourse 契约对齐"
```

---

### Task 2: 新增 JoinCourseDialog 组件

**Files:**
- Create: `src/components/JoinCourseDialog.jsx`

**背景：** 轻量弹窗，使用项目已有 Tailwind 类。Props: `open`, `onClose`, `onJoined`。

- [ ] **Step 1: 创建文件**

```jsx
import { useState } from 'react';
import { courseService } from '../api/services/course';

export default function JoinCourseDialog({ open, onClose, onJoined }) {
  const [courseCode, setCourseCode] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!courseCode.trim()) return;
    setSubmitting(true);
    setError('');
    setSuccess(false);

    try {
      const res = await courseService.joinCourse(courseCode.trim());
      if (res.code === 200) {
        setSuccess(true);
        if (onJoined) {
          await onJoined(res.data);
        }
        setTimeout(() => {
          onClose();
          setCourseCode('');
          setSuccess(false);
        }, 1500);
      } else {
        setError(res.message || '加入失败，请检查课程码');
      }
    } catch (err) {
      setError('网络错误，请重试');
    } finally {
      setSubmitting(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-xl p-6 w-full max-w-sm mx-4">
        <h2 className="text-lg font-bold text-slate-900 mb-1">加入课程</h2>
        <p className="text-sm text-slate-500 mb-4">输入教师提供的课程码加入课程</p>

        {success ? (
          <div className="flex items-center gap-2 text-emerald-600 bg-emerald-50 rounded-lg p-3 text-sm font-medium">
            <span className="material-symbols-outlined text-lg">check_circle</span>
            加入成功
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <input
              autoFocus
              type="text"
              value={courseCode}
              onChange={(e) => setCourseCode(e.target.value)}
              placeholder="输入课程码，如 DS2026"
              disabled={submitting}
              className="w-full px-4 py-2.5 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-cyan-500/20 focus:border-cyan-500 outline-none transition-all disabled:opacity-50"
            />
            {error && (
              <p className="mt-2 text-xs text-red-500">{error}</p>
            )}
            <div className="flex justify-end gap-2 mt-4">
              <button
                type="button"
                onClick={onClose}
                disabled={submitting}
                className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg transition-colors disabled:opacity-50"
              >
                取消
              </button>
              <button
                type="submit"
                disabled={submitting || !courseCode.trim()}
                className="px-4 py-2 text-sm font-semibold text-white bg-cyan-600 hover:bg-cyan-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {submitting ? '加入中...' : '加入'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 验证 lint**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint
```
Expected: PASS

- [ ] **Step 3: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/src/components/JoinCourseDialog.jsx
git commit -m "新增 JoinCourseDialog 加入课程弹窗组件"
```

---

### Task 3: Navbar 接入加入课程入口

**Files:**
- Modify: `src/components/Navbar.jsx`

**背景：** Navbar 第 30-44 行仅在 `courses.length > 0` 时渲染 `<select>`。改为始终渲染课程区域。

- [ ] **Step 1: 追加 import 和 state**

在现有 import 之后追加：
```javascript
import JoinCourseDialog from './JoinCourseDialog';
```

在 `useCourse()` 解构中追加 `refreshCourses`（当前为 `const { courses, activeCourseId, changeCourse } = useCourse();`）：
```javascript
const { courses, activeCourseId, changeCourse, refreshCourses } = useCourse();
```

在组件体内追加 state（放在现有 `showDropdown` state 之后）：
```javascript
const [showJoinDialog, setShowJoinDialog] = useState(false);
```

- [ ] **Step 2: 替换课程选择器区域（第 30-44 行）**

将仅在有课程时显示的 `<select>` 区域替换为始终渲染：

```jsx
          <div className="flex items-center space-x-2">
            {courses && courses.length > 0 && (
              <div className="relative">
                <select
                  value={activeCourseId || ''}
                  onChange={(e) => changeCourse(e.target.value)}
                  className="bg-cyan-50 border border-cyan-100 text-cyan-700 font-bold px-3 py-1 rounded-full text-xs outline-none cursor-pointer focus:ring-2 focus:ring-cyan-500 max-w-[180px] transition-all hover:bg-cyan-100"
                >
                  {courses.map(c => (
                    <option key={c.id} value={c.id} className="text-on-surface bg-white font-normal">
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>
            )}
            <button
              onClick={() => setShowJoinDialog(true)}
              className={courses && courses.length > 0
                ? "w-6 h-6 flex items-center justify-center rounded-full bg-cyan-50 text-cyan-600 hover:bg-cyan-100 text-sm font-bold transition-colors"
                : "bg-cyan-50 border border-cyan-100 text-cyan-700 font-bold px-3 py-1 rounded-full text-xs hover:bg-cyan-100 transition-colors"
              }
              title="加入课程"
            >
              {courses && courses.length > 0 ? '+' : '+ 加入课程'}
            </button>
          </div>
```

- [ ] **Step 3: 在 `</nav>` 之前追加 Dialog**

```jsx
      <JoinCourseDialog
        open={showJoinDialog}
        onClose={() => setShowJoinDialog(false)}
        onJoined={async (newCourse) => {
          await refreshCourses();
          if (newCourse?.id) {
            changeCourse(newCourse.id);
          }
        }}
      />
```

- [ ] **Step 4: 验证 lint + build**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint && npm run build
```
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/src/components/Navbar.jsx
git commit -m "Navbar 接入加入课程入口,成功后自动刷新并切换课程"
```

---

### Task 4: Dashboard 无课程状态补引导入口

**Files:**
- Modify: `src/pages/Dashboard.jsx`

**背景：** Dashboard 第 83 行空状态 `<FeedbackStatus status="empty" title="暂无课程" description="请先加入一门课程" />` 无操作按钮。

- [ ] **Step 1: 追加 import 和 state**

追加导入：
```javascript
import JoinCourseDialog from '../components/JoinCourseDialog';
```

Check `useCourse` 导入，追加 `refreshCourses`：
```javascript
const { courses, activeCourseId, changeCourse, refreshCourses } = useCourse();
```

追加 state（检查 `useState` 已 import）：
```javascript
const [showJoinDialog, setShowJoinDialog] = useState(false);
```

- [ ] **Step 2: 空状态下方追加按钮**

替换：
```jsx
<FeedbackStatus status="empty" title="暂无课程" description="请先加入一门课程" />
```

为：
```jsx
<FeedbackStatus status="empty" title="暂无课程" description="请先加入一门课程" />
<div className="flex justify-center mt-4">
  <button
    onClick={() => setShowJoinDialog(true)}
    className="px-5 py-2.5 text-sm font-semibold text-white bg-cyan-600 hover:bg-cyan-700 rounded-full transition-colors"
  >
    加入课程
  </button>
</div>
```

- [ ] **Step 3: JSX 末尾追加 Dialog**

在 Dashboard 最外层 `</div>` 之前追加：
```jsx
      <JoinCourseDialog
        open={showJoinDialog}
        onClose={() => setShowJoinDialog(false)}
        onJoined={async (newCourse) => {
          await refreshCourses();
          if (newCourse?.id) {
            changeCourse(newCourse.id);
          }
        }}
      />
```

- [ ] **Step 4: 验证 lint + build**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint && npm run build
```
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/src/pages/Dashboard.jsx
git commit -m "Dashboard 无课程状态补加入课程入口"
```

---

### Task 5: TeacherConsole 教师顶部身份展示

**Files:**
- Modify: `src/pages/TeacherConsole.jsx`

**背景：** 第 67-72 行硬编码姓名/角色/头像。

- [ ] **Step 1: 追加 import + useAuth + roleLabelMap**

追加 import：
```javascript
import { useAuth } from '../context/AuthContext';
```

组件体内追加：
```javascript
const { user } = useAuth();
const roleLabelMap = { teacher: '教师', admin: '管理员' };
```

- [ ] **Step 2: 替换硬编码（第 67-72 行）**

将头像 img + 姓名 Prof. Zhang + 角色"系统管理员"替换为：

```jsx
            <div className="w-10 h-10 rounded-full bg-cyan-500/20 text-cyan-600 flex items-center justify-center border border-cyan-500/30 font-bold text-sm">
              {(user?.real_name || user?.username || '教').charAt(0)}
            </div>
            <div className="flex flex-col">
              <span className="text-sm font-bold text-on-surface">{user?.real_name || user?.username || '教师'}</span>
              <span className="text-[10px] text-outline uppercase tracking-wider">
                {roleLabelMap[user?.role] || '教师'}
              </span>
            </div>
```

- [ ] **Step 3: 验证 lint + build**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint && npm run build
```
Expected: PASS

- [ ] **Step 4: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/src/pages/TeacherConsole.jsx
git commit -m "TeacherConsole 顶部身份改为真实 useAuth 数据"
```

---

### Task 6: 全量验证 + WORKFLOW 收口

**Files:**
- Modify: `frontend/WORKFLOW.md`

- [ ] **Step 1: lint + build**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint && npm run build
```
Expected: PASS

- [ ] **Step 2: 更新 WORKFLOW.md**

在 `## 最近验证` 末尾追加：

```markdown
- 2026-06-05：MS-05/MS-06 前端适配完成：
  - MS-05：Navbar "+ 加入课程"按钮 + JoinCourseDialog；Dashboard 无课程状态辅助入口。加入成功后自动刷新课程列表并切换到新课程。
  - MS-06：TeacherConsole 顶部身份改为真实 `useAuth` 数据（姓名、角色映射、文字头像）。
  - `npm run lint` / `npm run build` 通过。
```

- [ ] **Step 3: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/WORKFLOW.md
git commit -m "记录 MS-05 MS-06 前端适配完成"
```

---

## 自审清单

**1. Spec 覆盖：** ✅ Task 1-5 覆盖 MS-05/06 全部改动。Task 6 收口验证。

**2. 无占位符：** ✅ 所有步骤含完整代码。

**3. 类型一致性：** ✅ `courseCode` 贯穿 Dialog → joinCourse；`refreshCourses`/`changeCourse` 来自同一 CourseContext。

## 验证

| 方式 | 内容 |
|------|------|
| `npm run lint` | 每个 Task 独立 |
| `npm run build` | Task 3-5 |
| 手工：学生 | Navbar "+" → Dialog → 课程码 → 加入成功 → 列表刷新切换 |
| 手工：教师 | TeacherConsole 顶部真实姓名 + "教师" + 首字头像 |
| E2E | 可选 — 现有 spec 未覆盖邀请码加入和教师顶部文案 |
