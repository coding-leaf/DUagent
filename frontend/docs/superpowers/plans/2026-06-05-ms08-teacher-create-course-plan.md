# MS-08 教师创建课程入口实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 暴露教师端已有 `POST /courses` 端点的 UI 入口，创建课程后展示课程码供学生加入。

**Architecture:** 4 个 task。Task 1 新建 Dialog 组件，Task 2-3 改 TeacherConsole 入口。仅 2 个文件，不碰 Backend/Agent/OpenAPI。

**Tech Stack:** React, Tailwind CSS, JavaScript

**依据 Spec：** `docs/superpowers/specs/2026-06-05-ms08-teacher-create-course-design.md`

---

### Task 1: 新建 CreateCourseDialog

**Files:**
- Create: `src/components/CreateCourseDialog.jsx`

- [ ] **Step 1: 创建文件**

```jsx
import { useState } from 'react';
import { courseService } from '../api/services/course';

export default function CreateCourseDialog({ open, onClose, onCreated }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    setSubmitting(true);
    setError('');

    try {
      const res = await courseService.createCourse({
        name: name.trim(),
        description: description.trim() || undefined
      });
      if (res.code === 201) {
        setResult(res.data);
        if (onCreated) {
          await onCreated(res.data);
        }
      } else {
        setError(res.message || '创建失败');
      }
    } catch {
      setError('网络错误，请重试');
    } finally {
      setSubmitting(false);
    }
  };

  const handleClose = () => {
    setName('');
    setDescription('');
    setError('');
    setResult(null);
    onClose();
  };

  const [copied, setCopied] = useState(false);

  const copyCode = async () => {
    if (!result?.course_code) return;
    try {
      await navigator.clipboard.writeText(result.course_code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback: select text for manual copy
      const el = document.createElement('textarea');
      el.value = result.course_code;
      document.body.appendChild(el);
      el.select();
      document.execCommand('copy');
      document.body.removeChild(el);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-xl p-6 w-full max-w-sm mx-4">
        <h2 className="text-lg font-bold text-slate-900 mb-1">创建课程</h2>
        <p className="text-sm text-slate-500 mb-4">开设一个新课程并获取课程码</p>

        {result ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-emerald-600 bg-emerald-50 rounded-lg p-3 text-sm font-medium">
              <span className="material-symbols-outlined text-lg">check_circle</span>
              课程创建成功
            </div>
            <div className="bg-slate-50 rounded-lg p-4 text-center">
              <p className="text-xs text-slate-500 mb-1">课程码</p>
              <p className="text-2xl font-bold text-cyan-700 tracking-wider font-mono">{result.course_code}</p>
              <p className="text-sm text-slate-600 mt-1">{result.name}</p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={copyCode}
                className="flex-1 px-4 py-2 text-sm font-semibold text-cyan-600 bg-cyan-50 hover:bg-cyan-100 rounded-lg transition-colors"
              >
                {copied ? '已复制' : '复制课程码'}
              </button>
              <button
                onClick={handleClose}
                className="flex-1 px-4 py-2 text-sm font-semibold text-white bg-cyan-600 hover:bg-cyan-700 rounded-lg transition-colors"
              >
                完成
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <div className="space-y-3">
              <input
                autoFocus
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="课程名称，如 数据结构2026春"
                disabled={submitting}
                className="w-full px-4 py-2.5 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-cyan-500/20 focus:border-cyan-500 outline-none transition-all disabled:opacity-50"
              />
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="课程描述（可选）"
                disabled={submitting}
                className="w-full px-4 py-2.5 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-cyan-500/20 focus:border-cyan-500 outline-none transition-all disabled:opacity-50"
              />
            </div>
            {error && (
              <p className="mt-2 text-xs text-red-500">{error}</p>
            )}
            <div className="flex justify-end gap-2 mt-4">
              <button
                type="button"
                onClick={handleClose}
                disabled={submitting}
                className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg transition-colors disabled:opacity-50"
              >
                取消
              </button>
              <button
                type="submit"
                disabled={submitting || !name.trim()}
                className="px-4 py-2 text-sm font-semibold text-white bg-cyan-600 hover:bg-cyan-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {submitting ? '创建中...' : '创建'}
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
git add frontend/src/components/CreateCourseDialog.jsx
git commit -m "新增 CreateCourseDialog 创建课程弹窗组件"
```

---

### Task 2: TeacherConsole 加创建课程按钮

**Files:**
- Modify: `src/pages/TeacherConsole.jsx`

- [ ] **Step 1: 追加 import 和 state**

追加 import：
```javascript
import CreateCourseDialog from '../components/CreateCourseDialog';
```

追加 state：
```javascript
const [showCreateDialog, setShowCreateDialog] = useState(false);
```

- [ ] **Step 2: 在顶部导航区加按钮**

在 TeacherConsole 顶部导航行（身份展示块右侧）追加：

```jsx
            <button
              onClick={() => setShowCreateDialog(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-cyan-600 bg-cyan-50 hover:bg-cyan-100 rounded-lg transition-colors"
            >
              <span className="material-symbols-outlined text-sm">add</span>
              创建课程
            </button>
```

- [ ] **Step 3: 将班级获取逻辑提为 refreshClasses callback**

当前 TeacherConsole 在 `useEffect` 内调用 `teachingService.getClasses()`。需将获取逻辑抽成可回调的 `refreshClasses`。

在组件体内（`useEffect` 之前）添加：
```javascript
  const refreshClasses = useCallback(async () => {
    setClassesLoading(true);
    try {
      const res = await teachingService.getClasses();
      if (res.code === 200) {
        setClasses(res.data || []);
        if (res.data?.length > 0 && !activeClass) {
          setActiveClass(res.data[0].id);
        }
      }
    } catch (e) {
      console.error(e);
    } finally {
      setClassesLoading(false);
    }
  }, []);
```
注意：`useCallback` 需在现有 import `{ useState, useEffect }` 后追加。替换现有 `useEffect` 中的 fetch 逻辑为 `useEffect(() => { refreshClasses(); }, [refreshClasses])`。

- [ ] **Step 4: 在 return 之前追加 Dialog（onCreated 调用 refreshClasses）**

```jsx
      <CreateCourseDialog
        open={showCreateDialog}
        onClose={() => setShowCreateDialog(false)}
        onCreated={async () => {
          await refreshClasses();
        }}
      />
```

- [ ] **Step 5: 验证 lint + build**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint && npm run build
```
Expected: PASS

- [ ] **Step 6: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/src/pages/TeacherConsole.jsx
git commit -m "TeacherConsole 加创建课程按钮和 refreshClasses 回调"
```

---

### Task 3: TeacherConsole 无班级空状态加创建入口

**Files:**
- Modify: `src/pages/TeacherConsole.jsx`

- [ ] **Step 1: 确认 showCreateDialog state 在 early return 之前定义**

Task 2 已追加 `const [showCreateDialog, setShowCreateDialog] = useState(false);`，需确保它在无班级的 `if (!classes || classes.length === 0)` early return 之前。React hooks 必须顶层调用，这点自然满足。

- [ ] **Step 2: 用 Fragment 包裹无班级 early return 并追加按钮 + Dialog**

TeacherConsole 无班级时的 early return 大致结构：
```jsx
  if (!classesLoading && classes.length === 0) {
    return (
      <div className="min-h-screen ...">
        <空状态内容 />
      </div>
    );
  }
```

改为 Fragment 包裹，同时加入创建按钮和 Dialog：
```jsx
  if (!classesLoading && classes.length === 0) {
    return (
      <>
        <div className="min-h-screen ...">
          <空状态内容 />
          <button
            onClick={() => setShowCreateDialog(true)}
            className="px-5 py-2.5 text-sm font-semibold text-white bg-cyan-600 hover:bg-cyan-700 rounded-full transition-colors mt-4"
          >
            创建第一门课程
          </button>
        </div>
        <CreateCourseDialog
          open={showCreateDialog}
          onClose={() => setShowCreateDialog(false)}
          onCreated={async () => {
            await refreshClasses();
          }}
        />
      </>
    );
  }
```

**关键：** Dialog 必须放在 Fragment 内（与空状态 div 平级），否则在 early return 路径内 Dialog 不会渲染。`showCreateDialog` state 在 early return 上方已定义，两个分支均可访问。

- [ ] **Step 3: 验证 lint + build**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint && npm run build
```
Expected: PASS

- [ ] **Step 4: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/src/pages/TeacherConsole.jsx
git commit -m "TeacherConsole 无班级空状态加创建课程入口"
```

---

### Task 4: 全量验证 + WORKFLOW 收口

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
- 2026-06-05：MS-08 教师创建课程入口完成：
  - 新增 `CreateCourseDialog`：输入课程名称 → `POST /courses` → 展示课程码 + 一键复制
  - TeacherConsole 顶部加"创建课程"按钮，无班级空状态加创建入口
  - `npm run lint` / `npm run build` 通过。无 OpenAPI/契约漂移。
```

- [ ] **Step 3: 提交**

```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/WORKFLOW.md
git commit -m "记录 MS-08 教师创建课程入口完成"
```

---

## 自审清单

**1. Spec 覆盖：** ✅ Task 1-3 覆盖 Dialog + 按钮 + 空状态。Task 4 收口。

**2. 无占位符：** ✅ 所有步骤含完整代码。

## 验证

| 方式 | 内容 |
|------|------|
| `npm run lint` | 每个 Task |
| `npm run build` | Task 2-3 |
| 手工：教师 | "创建课程" → 输入名称 → 成功 → 展示课程码 → 复制 → 关闭 |
| 手工：学生 | 用课程码通过 Navbar "+" 加入课程 → 成功 |
| E2E | 可选 |
