# AI Chat UI Fine-Tuning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fine-tune the AI Chat layout width, fix collapse button alignment, add missing icon mappings, clean up mock event listeners, and implement high-fidelity cards (StudyPlan, WeakPoints, PathRecommendation) with a Popover mock selector.

**Architecture:** Extend `PluginRegistry` with the new business components, remove window event listeners in favor of direct context calls, create custom Tailwind UI plugins, and adjust desktop column sizes.

**Tech Stack:** React 19, TailwindCSS, Lucide Icons, SWR.

---

### Task 1: Clean Up Window Event Listener & Map Missing Icons

**Files:**
- Modify: `frontend/src/components/Icon.jsx`
- Modify: `frontend/src/components/chat/ChatArea.jsx`

- [ ] **Step 1: Map data_object icon**

Modify `frontend/src/components/Icon.jsx` to map `'data_object'` to `'Braces'`.

- [ ] **Step 2: Clean up window event listener in ChatArea.jsx**

Remove the `window` event listener (`mock-artifact` custom event) inside `ChatArea.jsx` `useEffect`. Call the context method `sendMockArtifact` directly inside the mock handler.

- [ ] **Step 3: Run lint & build check**

Run: `cd frontend && npm run lint && npm run build`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/Icon.jsx frontend/src/components/chat/ChatArea.jsx
git commit -m "refactor(ui): register braces icon and clean up window mock event listener"
```

---

### Task 2: Implement StudyPlanCard, WeakPointsCard, and PathRecommendationCard

**Files:**
- Create: `frontend/src/components/workspace/plugins/StudyPlanCard.jsx`
- Create: `frontend/src/components/workspace/plugins/WeakPointsCard.jsx`
- Create: `frontend/src/components/workspace/plugins/PathRecommendationCard.jsx`

- [ ] **Step 1: Implement StudyPlanCard.jsx**

Create `frontend/src/components/workspace/plugins/StudyPlanCard.jsx`. It should render a list of 4 items with a green badge, total duration, and a "开始练习" button.

```jsx
import Icon from '../../Icon';

export default function StudyPlanCard({ planDate, tasks }) {
  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
      <div className="flex items-center justify-between mb-5 border-b border-slate-100 pb-3">
        <div className="flex items-center gap-2 text-slate-800 font-bold">
          <Icon name="calendar_today" className="text-cyan-600 text-[18px]" />
          <span>今日学习计划</span>
        </div>
        <span className="text-xs text-slate-400 font-mono">{planDate || '今日'}</span>
      </div>

      <div className="space-y-3">
        {tasks?.map((task, idx) => (
          <div key={idx} className="flex items-center justify-between p-3 rounded-xl bg-slate-50 border border-slate-100 hover:border-slate-200 transition-colors">
            <div className="flex items-center gap-3">
              <span className="w-6 h-6 rounded-full bg-emerald-500 text-white font-semibold text-xs flex items-center justify-center flex-shrink-0">
                {idx + 1}
              </span>
              <span className="text-sm font-semibold text-slate-700">{task.name}</span>
            </div>
            <span className="text-xs text-slate-400 font-medium font-mono">{task.duration} 分钟</span>
          </div>
        ))}
      </div>

      <div className="mt-5 flex justify-end">
        <button className="px-5 py-2.5 bg-emerald-500 hover:bg-emerald-600 active:scale-95 text-white text-xs font-bold rounded-xl transition-all shadow-sm cursor-pointer flex items-center gap-1.5">
          <Icon name="play_arrow" className="text-white text-[16px]" />
          开始练习
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Implement WeakPointsCard.jsx**

Create `frontend/src/components/workspace/plugins/WeakPointsCard.jsx`. It should render horizontal progress bars in green, orange, or red indicating weak points.

```jsx
import Icon from '../../Icon';

export default function WeakPointsCard({ title, points }) {
  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
      <div className="flex items-center justify-between mb-5 border-b border-slate-100 pb-3">
        <div className="flex items-center gap-2 text-slate-800 font-bold">
          <Icon name="broken_image" className="text-amber-500 text-[18px]" />
          <span>{title || '薄弱点分析'}</span>
        </div>
      </div>

      <div className="space-y-4">
        {points?.map((item, idx) => {
          let barColor = 'bg-emerald-500';
          let textColor = 'text-emerald-700 bg-emerald-50 border-emerald-100';
          let impactText = '低';

          if (item.mastery < 40) {
            barColor = 'bg-red-500';
            textColor = 'text-red-700 bg-red-50 border-red-100';
            impactText = '高';
          } else if (item.mastery < 70) {
            barColor = 'bg-amber-500';
            textColor = 'text-amber-700 bg-amber-50 border-amber-100';
            impactText = '中';
          }

          return (
            <div key={idx} className="space-y-1.5">
              <div className="flex justify-between items-center text-xs">
                <span className="font-semibold text-slate-700">{item.name}</span>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-slate-400">掌握度: {item.mastery}%</span>
                  <span className={`px-1.5 py-0.5 rounded text-[10px] border font-bold ${textColor}`}>
                    影响: {impactText}
                  </span>
                </div>
              </div>
              <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                <div className={`${barColor} h-full rounded-full transition-all duration-500`} style={{ width: `${item.mastery}%` }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Implement PathRecommendationCard.jsx**

Create `frontend/src/components/workspace/plugins/PathRecommendationCard.jsx`. It should render a horizontal sequence of steps.

```jsx
import Icon from '../../Icon';

export default function PathRecommendationCard({ strategy, duration, target, steps }) {
  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
      <div className="flex items-center justify-between mb-5 border-b border-slate-100 pb-3">
        <div className="flex items-center gap-2 text-slate-800 font-bold">
          <Icon name="route" className="text-blue-500 text-[18px]" />
          <span>个性化路径推荐</span>
        </div>
        <span className="px-2 py-0.5 text-[10px] font-bold text-blue-600 bg-blue-50 border border-blue-100 rounded">
          {strategy || '补强优先'}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-6 bg-slate-50 p-4 rounded-xl border border-slate-100 text-xs">
        <div>
          <span className="text-slate-400 block mb-0.5">预计时长</span>
          <span className="font-bold text-slate-700 font-mono">{duration || '15 天'}</span>
        </div>
        <div>
          <span className="text-slate-400 block mb-0.5">核心目标</span>
          <span className="font-bold text-slate-700">{target || '强化薄弱概念'}</span>
        </div>
      </div>

      <div className="flex items-center justify-between overflow-x-auto py-2 px-1 gap-2 custom-scrollbar">
        {steps?.map((step, idx) => (
          <div key={idx} className="flex items-center gap-2 flex-shrink-0">
            <div className="flex flex-col items-center">
              <span className={`w-8 h-8 rounded-full font-bold text-xs flex items-center justify-center border shadow-sm ${
                idx === 1 
                  ? 'bg-blue-500 text-white border-blue-500' 
                  : 'bg-white text-slate-400 border-slate-200'
              }`}>
                {idx + 1}
              </span>
              <span className="text-[10px] font-semibold mt-1.5 text-slate-600">{step.name}</span>
            </div>
            {idx < steps.length - 1 && (
              <span className="text-slate-300 font-bold select-none text-[16px]">→</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run build check**

Run: `cd frontend && npm run build`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/workspace/plugins/
git commit -m "feat(plugins): add high-fidelity StudyPlan, WeakPoints, and PathRecommendation components"
```

---

### Task 3: Register Custom Components in PluginRegistry & Verify

**Files:**
- Modify: `frontend/src/components/workspace/PluginRegistry.js`
- Modify: `frontend/src/components/workspace/PluginRegistry.test.js`

- [ ] **Step 1: Register in PluginRegistry.js**

Import and add `StudyPlan`, `WeakPoints`, and `PathRecommendation` mapping in `frontend/src/components/workspace/PluginRegistry.js`.

- [ ] **Step 2: Update unit test**

Modify `frontend/src/components/workspace/PluginRegistry.test.js` to assert that `StudyPlan`, `WeakPoints`, and `PathRecommendation` map to defined components.

- [ ] **Step 3: Run unit tests**

Run: `cd frontend && npm run test:unit -- src/components/workspace/PluginRegistry.test.js`
Expected: PASS (6 test cases passing)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/workspace/PluginRegistry.js frontend/src/components/workspace/PluginRegistry.test.js
git commit -m "test(workspace): map and verify new high-fidelity plugin components"
```

---

### Task 4: Build Mock Controller Popover in ChatArea

**Files:**
- Modify: `frontend/src/components/chat/ChatArea.jsx`

- [ ] **Step 1: Implement Popover selector in ChatArea.jsx**

Modify `ChatArea.jsx` to render a Mock trigger list on click of the Braces (`data_object`) icon.
Store a state `showMockMenu` (boolean) to toggle the menu dropdown right above the composer.
Provide mock actions inside the dropdown targeting:
- `+ QuizCard`: Single choice question.
- `+ Mermaid`: Node graph flowchart.
- `+ Markdown`: GFM markdown note document.
- `+ StudyPlan`: 4 steps 二叉树 plan (60 mins, 45 mins, etc.).
- `+ WeakPoints`: 二叉树遍历 (28%), 递归实现 (46%), 平衡二叉树 (58%).
- `+ PathRecommendation`: Route roadmap 1->2->3->4->5 nodes.

```jsx
// Popover UI template to render inside compose area (under ChatArea input area):
{showMockMenu && (
  <div className="absolute bottom-16 left-8 bg-white border border-slate-200 rounded-xl shadow-lg p-3 grid grid-cols-2 gap-2 z-50 animate-fadeIn text-xs w-64">
    <div className="col-span-2 font-bold text-slate-500 mb-1 border-b pb-1">触发模拟 Artifact</div>
    <button onClick={() => { sendMockArtifact({ type: 'QuizCard', props: { question: '数据结构中，以下哪个是线性结构？', choices: ['二叉树', '图', '队列', '网'], correctAnswer: 2 } }); setShowMockMenu(false); }} className="p-2 hover:bg-slate-50 border border-slate-100 rounded text-left font-semibold text-slate-700 cursor-pointer">+ 测验卡片</button>
    <button onClick={() => { sendMockArtifact({ type: 'Mermaid', props: { chart: 'graph TD\nA[二叉树] --> B(二叉搜索树)\nA --> C(平衡二叉树)\nC --> D(AVL 树)' } }); setShowMockMenu(false); }} className="p-2 hover:bg-slate-50 border border-slate-100 rounded text-left font-semibold text-slate-700 cursor-pointer">+ 流程图</button>
    <button onClick={() => { sendMockArtifact({ type: 'Markdown', props: { content: '# 二叉树遍历详解\n\n1. **前序遍历** (根 -> 左 -> 右)\n2. **中序遍历** (左 -> 根 -> 右)\n3. **后序遍历** (左 -> 右 -> 根)' } }); setShowMockMenu(false); }} className="p-2 hover:bg-slate-50 border border-slate-100 rounded text-left font-semibold text-slate-700 cursor-pointer">+ Markdown 课件</button>
    <button onClick={() => { sendMockArtifact({ type: 'StudyPlan', props: { planDate: '2026-06-26', tasks: [{ name: '二叉树遍历 (重点突破)', duration: 60 }, { name: '递归思想强化训练', duration: 45 }, { name: '树的层序遍历与应用', duration: 45 }, { name: '今日小结与错题回顾', duration: 20 }] } }); setShowMockMenu(false); }} className="p-2 hover:bg-slate-50 border border-slate-100 rounded text-left font-semibold text-slate-700 cursor-pointer">+ 学习计划</button>
    <button onClick={() => { sendMockArtifact({ type: 'WeakPoints', props: { title: '薄弱点分析', points: [{ name: '二叉树遍历', mastery: 28 }, { name: '递归实现', mastery: 46 }, { name: '平衡二叉树 (AVL)', mastery: 58 }, { name: '图的最短路径', mastery: 72 }, { name: '哈希冲突处理', mastery: 80 }] } }); setShowMockMenu(false); }} className="p-2 hover:bg-slate-50 border border-slate-100 rounded text-left font-semibold text-slate-700 cursor-pointer">+ 薄弱点分析</button>
    <button onClick={() => { sendMockArtifact({ type: 'PathRecommendation', props: { strategy: '补强优先', duration: '18 天', target: '掌握树、图、哈希表等核心结构', steps: [{ name: '基础回顾' }, { name: '弱点突破' }, { name: '综合提升' }, { name: '专题拓展' }, { name: '项目实战' }] } }); setShowMockMenu(false); }} className="p-2 hover:bg-slate-50 border border-slate-100 rounded text-left font-semibold text-slate-700 cursor-pointer">+ 推荐路径</button>
  </div>
)}
```

- [ ] **Step 2: Run lint and build**

Run: `cd frontend && npm run lint && npm run build`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/chat/ChatArea.jsx
git commit -m "feat(ui): add Mock menu popover and support six artifact payloads"
```

---

### Task 5: Refine Sizing & Sidebar Collapse Button Positioning

**Files:**
- Modify: `frontend/src/components/chat/ChatArea.jsx`
- Modify: `frontend/src/components/chat/SidebarHistory.jsx`

- [ ] **Step 1: Increase ChatArea desktop width**

In `ChatArea.jsx` (line 54 wrapper class):
Change `w-full lg:w-[380px]` to `w-full lg:w-[450px]`.

- [ ] **Step 2: Refine SidebarHistory collapse button styling**

Modify the collapse handle button classes in `SidebarHistory.jsx` (around line 77-83):
Change wrapper class to:
`hidden lg:flex absolute right-[-12px] top-1/2 -translate-y-1/2 w-6 h-6 rounded-full border border-slate-200 bg-white items-center justify-center shadow-md cursor-pointer hover:bg-slate-50 hover:text-cyan-600 transition-all z-40 active:scale-90` (specifically ensure `z-40` is present, and add a background color so it stands out cleanly on top of the border line).

- [ ] **Step 3: Run full verification suite**

Run:
1. `cd frontend && npm run lint` (ESlint check)
2. `cd frontend && npm run build` (Production compilation)
3. `cd frontend && npm run test:unit` (89 Vitest unit tests pass)

Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/chat/ChatArea.jsx frontend/src/components/chat/SidebarHistory.jsx
git commit -m "style(ui): enlarge ChatArea desktop width and fix history collapse handle alignment"
```
