# StudentProfile 真实字段接线实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 StudentProfile.jsx 从幽灵字段模型切回真实契约 — 5 张卡片重接真实数据，修复无课程无限 loading bug，清理全部 effectsData 残留。

**Architecture:** 纯前端单文件改动。引入 useAuth() 取姓名，useCourse() 已有。GET /profile 提供 5 卡片全部数据。GET /evaluation 在确认不再消费后移除调用。Backend/OpenAPI/Agent 零改动。

**Tech Stack:** React 19 + Tailwind CSS 4.3 + Vite 8, no new dependencies

---

### Task 1：基础设施：修复 loading 逻辑、加 imports、清理 effectsData

**Files:**
- Modify: `src/pages/StudentProfile.jsx`（全文）

- [ ] **Step 1：添加 useAuth import**

在 `src/pages/StudentProfile.jsx` import 区追加 `useAuth`：

```jsx
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Sidebar from '../components/Sidebar';
import { profileService } from '../api/services/profile';
import { useCourse } from '../context/CourseContext';
import Navbar from '../components/Navbar';
```

改为：

```jsx
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Sidebar from '../components/Sidebar';
import { profileService } from '../api/services/profile';
import { useCourse } from '../context/CourseContext';
import { useAuth } from '../context/AuthContext';
import Navbar from '../components/Navbar';
```

- [ ] **Step 2：在组件顶部获取 useAuth 并解构 courses**

在第 10 行 `const { activeCourseId } = useCourse();` 之后追加：

```jsx
const { activeCourseId, courses } = useCourse();
const { user } = useAuth();
```

（同时将原来的 `const { activeCourseId } = useCourse();` 改为 `const { activeCourseId, courses } = useCourse();`）

- [ ] **Step 3：删除 effectsData 相关 state**

当前 `const [effectsData, setEffectsData] = useState(null);` — **删除整行。**

state 区改为：

```jsx
const [profileData, setProfileData] = useState(null);
const [loading, setLoading] = useState(true);
```

- [ ] **Step 4：修复 useEffect — 无课程时停止 loading，移除 Promise.all 和 evaluation 调用**

当前 useEffect 替换为：

```jsx
useEffect(() => {
  const fetchProfile = async () => {
    if (!activeCourseId) {
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const res = await profileService.getStudentProfile(activeCourseId);
      if (res.code === 200) setProfileData(res.data);
    } catch (error) {
      console.error("Failed to fetch profile data:", error);
    } finally {
      setLoading(false);
    }
  };
  fetchProfile();
}, [activeCourseId]);
```

**关键变化：**
- 移除 `Promise.all`（不再调用 evaluation）
- `!activeCourseId` 时显式 `setLoading(false)` 后 return
- 只发一个 GET /profile 请求

- [ ] **Step 5：渲染顺序 — 无课程 → loading → 正常**

当前 loading 检查和 return 之后的部分替换为以下渲染顺序：

```jsx
if (!activeCourseId) {
  return (
    <div className="bg-background text-on-background font-body-md antialiased min-h-screen">
      <Navbar />
      <Sidebar />
      <main className="ml-0 lg:ml-64 pt-16">
        <div className="max-w-[1280px] mx-auto px-6 py-8 flex flex-col items-center justify-center min-h-[60vh] text-center">
          <span className="material-symbols-outlined text-6xl text-slate-300 mb-6">person_search</span>
          <h2 className="font-h1 text-2xl text-on-surface mb-3">还没有可查看的课程画像</h2>
          <p className="text-body-md text-secondary max-w-md mb-8">
            加入一门课程后，这里会展示你的模态偏好、引导粒度、知识坐标和学习状态。
          </p>
          <button
            onClick={() => navigate('/dashboard')}
            className="px-6 py-2.5 bg-cyan-600 text-white rounded-xl font-bold hover:bg-cyan-700 transition-colors cursor-pointer"
          >
            去课程页
          </button>
        </div>
      </main>
    </div>
  );
}

if (loading) {
  return (
    <div className="bg-background min-h-screen flex items-center justify-center">
      <span className="material-symbols-outlined animate-spin text-4xl text-cyan-500">progress_activity</span>
    </div>
  );
}
```

- [ ] **Step 6：验证 — lint + build + effectsData 残留检查**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint && npm run build
```

预期：lint 零错误，build 通过。

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && grep -n 'effectsData\|getLearningEffects\|Promise.all' src/pages/StudentProfile.jsx | head
```

预期：无匹配。

- [ ] **Step 7：commit**

```bash
cd /home/yezisama/workspace/workflow/EDUagent && git add frontend/src/pages/StudentProfile.jsx && git commit -m "refactor: StudentProfile 基础设施 — 修复无课程 loading、移除 effectsData、添加 useAuth"
```

---

### Task 2：卡片 1 — 个人信息重接

**Files:**
- Modify: `src/pages/StudentProfile.jsx`（卡片 1 区域 + 解构替换）

- [ ] **Step 1：替换幽灵字段解构 — 从 profile 取真实字段**

当前 `profileData` 和 `effectsData` 解构替换为从 `profile` 取真实字段，同时计算 displayName 和 currentCourseName：

```jsx
const profile = profileData || {};
const {
  modal_preference = {},
  guidance_level = { current: 'L2', updated_at: '' },
  knowledge_coordinates = [],
  cognitive_blindspots = [],
  drive_intent = { type: 'casual', intensity: 30 },
  discipline_badge = { subject: '', level: '', streak_days: 0 },
} = profile;

// 姓名优先级：real_name → username → 兜底
const displayName = user?.real_name || user?.username || '学生';
const displayInitial = (user?.real_name || user?.username || '学').charAt(0);

// 当前课程名：从 CourseContext 按 activeCourseId 查找
const currentCourseName = courses.find(c => c.id === activeCourseId)?.name || '未选择';
```

删除旧的两行解构：
```jsx
const { name, level, title, current_course, system_suggestion } = profileData || {};
const { weekly_max_accuracy, total_duration_hours, knowledge_nodes } = effectsData || {};
```

- [ ] **Step 2：重写卡片 1 个人信息 JSX**

替换当前 Profile Card（原第 57-76 行）：

```jsx
{/* 卡片 1：个人信息 */}
<div className="relative overflow-hidden bg-white p-8 rounded-2xl shadow-sm border border-gray-100 flex items-center gap-8 mb-8">
  <div className="absolute top-0 right-0 w-64 h-64 -mr-20 -mt-20 opacity-5">
    <span className="material-symbols-outlined text-9xl">school</span>
  </div>
  <div className="relative">
    <div className="relative w-32 h-32 rounded-full border-4 border-slate-100 overflow-hidden bg-cyan-500/10">
      <div className="w-full h-full rounded-full bg-cyan-500/20 text-cyan-600 flex items-center justify-center font-bold text-xl">
        {displayInitial}
      </div>
    </div>
  </div>
  <div className="flex-1">
    <div className="flex items-center gap-4 mb-2">
      <h1 className="font-h1 text-3xl text-on-surface">{displayName}</h1>
      {discipline_badge.level && discipline_badge.subject ? (
        <span className="bg-amber-50 text-amber-700 text-xs px-4 py-1 rounded-full font-bold uppercase tracking-wider border border-amber-200">
          学科勋章：{discipline_badge.subject} · {discipline_badge.level}
        </span>
      ) : (
        <span className="bg-slate-100 text-slate-400 text-xs px-4 py-1 rounded-full">学科勋章：—</span>
      )}
    </div>
    <p className="text-body-md text-secondary">当前进修课程：<span className="text-primary font-bold">{currentCourseName}</span></p>
  </div>
</div>
```

**语义限定：** 勋章标签文案固定为"学科勋章：{subject} · {level}"，不使用"Lvl X"或通用等级用语。无数据时显示"学科勋章：—"。

- [ ] **Step 3：验证**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint && npm run build
```

- [ ] **Step 4：commit**

```bash
cd /home/yezisama/workspace/workflow/EDUagent && git add frontend/src/pages/StudentProfile.jsx && git commit -m "feat: StudentProfile 卡片1 — 个人信息重接 useAuth + CourseContext + discipline_badge"
```

---

### Task 3：卡片 2 + 3 — 模态偏好 + 引导粒度

**Files:**
- Modify: `src/pages/StudentProfile.jsx`（卡片 2 + 3 区域）

- [ ] **Step 1：重写卡片 2 模态偏好 — 5 条进度条**

替换当前 Modality Card（原第 78-90 行）：

```jsx
{/* 卡片 2：模态偏好 */}
<div className="lg:col-span-4 bg-white p-6 rounded-2xl border border-gray-100 shadow-sm">
  <h3 className="font-h3 text-xl mb-6 flex items-center gap-2 text-on-surface">
    <span className="material-symbols-outlined text-cyan-500">pie_chart</span> 模态偏好
  </h3>
  <div className="flex flex-col gap-4">
    {[
      { key: 'video_animation', label: '视频动画' },
      { key: 'chart_logic', label: '图表逻辑' },
      { key: 'text_analysis', label: '文本分析' },
      { key: 'code_practice', label: '代码实操' },
      { key: 'formula_derivation', label: '公式推导' },
    ].map(({ key, label }) => {
      const value = modal_preference[key] ?? 0;
      const colorClass = value >= 70 ? 'bg-cyan-600' : value >= 40 ? 'bg-cyan-400' : 'bg-slate-300';
      return (
        <div key={key}>
          <div className="flex justify-between mb-1">
            <span className="text-xs text-secondary font-bold">{label}</span>
            <span className="text-xs text-cyan-700 font-bold">{value}%</span>
          </div>
          <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
            <div className={`h-full ${colorClass} rounded-full transition-all`} style={{ width: `${value}%` }}></div>
          </div>
        </div>
      );
    })}
  </div>
</div>
```

- [ ] **Step 2：卡片 3 — 进度条动态计算**

将第 102 行硬编码 `style={{ width: '50%' }}` 替换为：

```jsx
style={{ width: `${
  guidance_level.current === 'L1' ? '33%' :
  guidance_level.current === 'L3' ? '100%' : '66%'
}` }}
```

- [ ] **Step 3：卡片 3 — L1/L2/L3 刻度点动态高亮**

L1 刻度点 `className` 改为条件渲染：
```jsx
className={`w-6 h-6 rounded-full border-4 shadow-sm z-10 ${
  guidance_level.current === 'L1'
    ? 'bg-cyan-500 border-white shadow-cyan-200'
    : 'bg-white border-slate-200'
}`}
```

L1 文案 className 改为：
```jsx
className={`text-label-sm font-bold ${guidance_level.current === 'L1' ? 'text-cyan-600' : 'text-slate-400'}`}
```

L2、L3 同理替换 — L2 条件 `=== 'L2'`，L3 条件 `=== 'L3'`。

- [ ] **Step 4：卡片 3 — 添加更新时间**

在系统建议块之前追加：

```jsx
{guidance_level.updated_at && (
  <p className="text-xs text-slate-400 mt-4 text-center">
    更新于 {(() => {
      const diff = Date.now() - new Date(guidance_level.updated_at).getTime();
      const days = Math.floor(diff / 86400000);
      return days === 0 ? '今天' : `${days} 天前`;
    })()}
  </p>
)}
```

- [ ] **Step 5：卡片 3 — 删除系统建议块**

删除现有的"系统建议"区块（`bg-cyan-50` + `system_suggestion` 引用）。

- [ ] **Step 6：验证**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint && npm run build
```

- [ ] **Step 7：commit**

```bash
cd /home/yezisama/workspace/workflow/EDUagent && git add frontend/src/pages/StudentProfile.jsx && git commit -m "feat: StudentProfile 卡片2+3 — 模态偏好进度条 + 引导粒度动态数据"
```

---

### Task 4：卡片 4 — 知识坐标 + 认知盲区（合并双色列表）

**Files:**
- Modify: `src/pages/StudentProfile.jsx`（卡片 4 区域）

- [ ] **Step 1：重写卡片 4 整体 JSX — 双色知识坐标列表 + 盲区严重度列表**

替换当前 Knowledge Map 卡片（原第 136-169 行）：

```jsx
{/* 卡片 4：知识坐标 + 认知盲区 */}
<div className="lg:col-span-7 bg-white p-8 rounded-2xl border border-gray-100 shadow-sm">
  <h3 className="font-h3 text-xl mb-8 flex items-center gap-2 text-on-surface">
    <span className="material-symbols-outlined text-cyan-500">grid_view</span> 知识坐标 &amp; 认知盲区
  </h3>

  {/* 上半：知识坐标 */}
  <div className="mb-6">
    <p className="text-xs text-slate-400 uppercase font-bold tracking-wider mb-3">知识坐标</p>
    {knowledge_coordinates.length > 0 ? (
      <div className="flex flex-wrap gap-3">
        {knowledge_coordinates.map((node, i) => {
          const isMastered = node.status === 'mastered';
          return (
            <span
              key={i}
              className={`px-4 py-2 rounded-lg border text-sm font-bold flex items-center gap-2 transition-all hover:scale-105 ${
                isMastered
                  ? 'bg-green-50 text-green-700 border-green-100'
                  : 'bg-amber-50 text-amber-700 border-amber-100'
              }`}
            >
              <span className="material-symbols-outlined text-base" style={{ fontVariationSettings: '"FILL" 1' }}>
                {isMastered ? 'check_circle' : 'sync'}
              </span>
              {node.name}
              {isMastered && node.mastered_at && (
                <span className="text-green-400 text-xs font-normal ml-1">
                  · {(() => {
                    const diff = Date.now() - new Date(node.mastered_at).getTime();
                    const days = Math.floor(diff / 86400000);
                    return days === 0 ? '今天掌握' : `${days} 天前掌握`;
                  })()}
                </span>
              )}
            </span>
          );
        })}
      </div>
    ) : (
      <p className="text-sm text-slate-400 py-8 text-center">暂无知识坐标数据</p>
    )}
  </div>

  {/* 下半：认知盲区 */}
  <div className="border-t border-slate-100 pt-6">
    <p className="text-xs text-slate-400 uppercase font-bold tracking-wider mb-3">认知盲区</p>
    {cognitive_blindspots.length > 0 ? (
      <div className="space-y-2">
        {cognitive_blindspots.map((item, i) => {
          const severityColors = {
            high: 'bg-red-50 text-red-700 border-red-100',
            medium: 'bg-amber-50 text-amber-700 border-amber-100',
            low: 'bg-slate-100 text-slate-500 border-slate-200',
          };
          const severityLabels = { high: '高', medium: '中', low: '低' };
          const colorClass = severityColors[item.severity] || severityColors.low;
          const label = severityLabels[item.severity] || item.severity;
          return (
            <div key={i} className="flex items-center gap-3">
              <span className={`px-2 py-0.5 rounded text-xs font-bold ${colorClass} border`}>
                {label}
              </span>
              <span className="text-sm text-on-surface">{item.name}</span>
              <span className="text-xs text-slate-400">· 错误 {item.error_count} 次</span>
            </div>
          );
        })}
      </div>
    ) : (
      <p className="text-sm text-slate-400 py-4 text-center">暂无认知盲区记录</p>
    )}
  </div>
</div>
```

- [ ] **Step 2：验证**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint && npm run build
```

- [ ] **Step 3：commit**

```bash
cd /home/yezisama/workspace/workflow/EDUagent && git add frontend/src/pages/StudentProfile.jsx && git commit -m "feat: StudentProfile 卡片4 — 知识坐标双色列表 + 认知盲区"
```

---

### Task 5：卡片 5 — 驱动力 + 学科勋章（替换旧卡片）+ 全量清理

**Files:**
- Modify: `src/pages/StudentProfile.jsx`（旧 Heat 卡片 → 新卡片 5）

- [ ] **Step 1：删除旧"学习热度与准度"卡片 + 替换为新卡片 5**

删除当前 Heat Card（原第 171-210 行），替换为：

```jsx
{/* 卡片 5：驱动力 + 学科勋章 */}
<div className="lg:col-span-5 bg-white p-8 rounded-2xl border border-gray-100 shadow-sm">
  <h3 className="font-h3 text-xl mb-6 flex items-center gap-2 text-on-surface">
    <span className="material-symbols-outlined text-cyan-500">psychology</span> 学习状态
  </h3>

  {/* 驱动力 */}
  <div className="mb-6">
    <p className="text-xs text-slate-400 uppercase font-bold tracking-wider mb-3">驱动力</p>
    <div className="flex items-center gap-4">
      <span className="px-3 py-1.5 bg-cyan-50 text-cyan-700 rounded-lg text-sm font-bold border border-cyan-100">
        {{
          exam_sprint: '备考冲刺',
          daily_homework: '日常作业',
          casual: '兴趣驱动',
        }[drive_intent.type] || drive_intent.type}
      </span>
      <div className="flex-1">
        <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
          <div className="h-full bg-cyan-500 rounded-full" style={{ width: `${drive_intent.intensity}%` }}></div>
        </div>
      </div>
      <span className="text-xs text-slate-500 font-bold w-8 text-right">{drive_intent.intensity}%</span>
    </div>
  </div>

  {/* 学科勋章 */}
  <div className="border-t border-slate-100 pt-6">
    <p className="text-xs text-slate-400 uppercase font-bold tracking-wider mb-3">学科勋章</p>
    {discipline_badge.subject && discipline_badge.level ? (
      <div className="flex items-center gap-4">
        <div className="w-16 h-16 rounded-full bg-amber-100 flex items-center justify-center border-4 border-amber-200">
          <span className="material-symbols-outlined text-2xl text-amber-600" style={{ fontVariationSettings: '"FILL" 1' }}>
            verified
          </span>
        </div>
        <div>
          <p className="font-bold text-on-surface">
            学科勋章：{discipline_badge.subject} · {discipline_badge.level}
          </p>
          <p className="text-sm text-slate-500 mt-1">
            连续打卡 <span className="text-amber-600 font-bold">{discipline_badge.streak_days}</span> 天
          </p>
        </div>
      </div>
    ) : (
      <p className="text-sm text-slate-400 py-4 text-center">暂无学科勋章</p>
    )}
  </div>
</div>
```

**语义一致性：** 勋章区文案同样使用"学科勋章：{subject} · {level}"，与卡片 1 完全一致。不出现"Lvl"、"等级"等通用等级体系用语。

- [ ] **Step 2：全量清理验证 — 确认 effectsData 和幽灵字段无残留**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && grep -n 'effectsData\|weekly_max_accuracy\|total_duration_hours\|knowledge_nodes\|system_suggestion\|getLearningEffects\|Promise.all' src/pages/StudentProfile.jsx
```

预期：无匹配（`Promise.all` 可能被匹配到其他位置，手工确认 StudentProfile.jsx 中已全部移除）。

- [ ] **Step 3：最终验证 — lint + build**

```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend && npm run lint && npm run build
```

预期：lint 零错误，build 通过。

- [ ] **Step 4：commit**

```bash
cd /home/yezisama/workspace/workflow/EDUagent && git add frontend/src/pages/StudentProfile.jsx && git commit -m "feat: StudentProfile 卡片5 — 驱动力 + 学科勋章替换旧热度卡片，全量清理 effectsData"
```

---

## 任务依赖

```
Task 1（基础设施）→ Task 2（卡片1）→ Task 3（卡片2+3，可与4并行）
                                      → Task 4（卡片4，可与3并行）
                                      → Task 5（卡片5+清理，依赖2/3/4完成）
```

Task 3 和 Task 4 修改同一文件的不同区域，可顺序执行以确保无冲突。Task 5 必须在 Task 2/3/4 之后（需要 Task 2 定义的 profile 解构字段）。

## 自审

1. **Spec coverage：** 每项 spec 需求对应 Task
   - 无课程空态 → Task 1 Step 4-5 ✓
   - 姓名优先级 `real_name || username` → Task 2 Step 1 ✓
   - 5 张卡片接线 → Task 2-5 ✓
   - 删除幽灵字段 → Task 2 Step 1 + Task 5 Step 2 ✓
   - discipline_badge 语义一致 → Task 2 Step 2 + Task 5 Step 1 ✓（两处均为"学科勋章：{subject} · {level}"）
   - effectsData 全量清理（state、请求、分支，不只看 JSX）→ Task 1 Step 3,6 + Task 5 Step 2 ✓
   - evaluation 判定 → Task 5 Step 2 通过 grep 验证不再消费 ✓
2. **Placeholder scan：** 无 TBD/TODO ✓
3. **Type consistency：** `user.real_name`、`user.username` 来自 GET /users/me；`modal_preference`、`guidance_level` 等来自 GET /profile ✓
