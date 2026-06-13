# Student Profile Learning Record Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the personal profile image summary from system-oriented fields into a student-facing learning record.

**Architecture:** Keep Backend, Agent, OpenAPI, and profile data unchanged. Add front-end presentation mappings in `StudentProfile.jsx` and use `profile_dimensions[].key` as the stable semantic key for labels, values, source chips, and object formatting.

**Tech Stack:** React, Vite, existing `profileService`, existing `taskService`, Tailwind utility classes.

---

## File Structure

- Modify: `src/pages/StudentProfile.jsx`
  - Owns the personal profile page UI.
  - Add learning-record display label mappings.
  - Reuse current API calls and task polling.
- Modify: `WORKFLOW.md`
  - Add one dated implementation record after verification.

## Task 1: Update Learning Record Labels And Value Formatting

**Files:**
- Modify: `src/pages/StudentProfile.jsx`

- [ ] **Step 1: Replace profile value label mappings**

Update the existing `PROFILE_VALUE_LABELS` object so learning direction and guidance values are student-facing:

```jsx
const PROFILE_VALUE_LABELS = {
  exam_sprint: '备考冲刺',
  daily_homework: '课后巩固',
  casual: '兴趣拓展',
  video_animation: '视频动画',
  chart_logic: '图表逻辑',
  text_analysis: '文本解析',
  code_practice: '代码实操',
  formula_derivation: '公式推导',
  L1: '启发点拨',
  L2: '分步伴学',
  L3: '详细讲解',
  starter: '入门起步',
  active: '稳定学习',
  focused: '高频投入',
};
```

- [ ] **Step 2: Add dimension display label mappings**

Add this object near `PROFILE_EMPTY_TEXT`:

```jsx
const PROFILE_DIMENSION_LABELS = {
  learning_goal: '当前学习方向',
  weak_points: '待提升内容',
  resource_preference: '学习资料偏好',
  guidance_level: '辅导方式',
  knowledge_progress: '掌握进度',
  discipline: '学习习惯',
};
```

- [ ] **Step 3: Replace source label mappings**

Update `sourceLabel` to use learning-record language:

```jsx
const sourceLabel = (source) => ({
  profile_dialogue: '个人补充',
  system_profile: '系统分析',
  resource_usage: '学习行为',
  evaluation: '评测结果',
  activity: '学习记录',
  system_pending: '数据不足',
}[source] || source || '未知来源');
```

- [ ] **Step 4: Use dimension key for card title**

Change the dimension card title from backend label to the display label:

```jsx
<p className="text-xs text-slate-400 font-bold uppercase tracking-wider">
  {PROFILE_DIMENSION_LABELS[dimension.key] || dimension.label}
</p>
```

- [ ] **Step 5: Update learning record section title**

Change the section title and description:

```jsx
<span className="material-symbols-outlined text-cyan-500">badge</span> 学习档案
```

```jsx
<p className="text-sm text-secondary mt-1">根据学习行为、评测结果和个人补充生成的课程学习档案。</p>
```

- [ ] **Step 6: Run lint**

Run:

```bash
npm run lint
```

Expected: exits 0.

## Task 2: Verify Build And Record Progress

**Files:**
- Modify: `WORKFLOW.md`

- [ ] **Step 1: Run production build**

Run:

```bash
npm run build
```

Expected: exits 0. Existing Vite chunk size warning is acceptable.

- [ ] **Step 2: Add workflow record**

Append a dated section to `WORKFLOW.md`:

```markdown
## 2026-06-13 学生画像学习档案命名优化

- **问题**: 个人资料页画像摘要仍使用偏系统的字段名和值，例如“学习目标：每日作业”和 `L1`，学生侧理解成本较高。
- **方案**: 只在前端展示层将画像摘要调整为“学习档案”口径，不改接口、不改后端数据。
- **改动**:
  - `src/pages/StudentProfile.jsx`: 将六维画像展示名改为“当前学习方向 / 待提升内容 / 学习资料偏好 / 辅导方式 / 掌握进度 / 学习习惯”；将来源标签和枚举值改为学生可读文案。
- **验证**: `npm run lint` 通过；`npm run build` 通过，仍有既有 Vite chunk size warning。
- **契约**: 无 OpenAPI 变更；只修改前端渲染文案。
```

- [ ] **Step 3: Review diff**

Run:

```bash
git diff -- src/pages/StudentProfile.jsx WORKFLOW.md
```

Expected: diff only contains the learning-record display changes and workflow note.

- [ ] **Step 4: Commit**

Run:

```bash
git add src/pages/StudentProfile.jsx WORKFLOW.md
git commit -m "优化学生画像学习档案命名"
```

Expected: commit succeeds with exactly those two files.

## Self-Review

- Spec coverage: Covers display names, enum values, source labels, hidden raw course ID behavior from the existing implementation, testing, and non-goals.
- Placeholder scan: No placeholders, no TODO markers, no deferred design decisions.
- Type consistency: Uses existing React component, existing `dimension.key`, existing `dimension.label`, and existing local helper pattern.
