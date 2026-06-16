# AI Chat Collapsible & Floating Sidebars Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement desktop collapsible sidebars and mobile sliding drawers for the history panel (left) and recommended learning resources (right) on the `AIChat.jsx` page, resolving mobile display blindspots and expanding desktop screen control.

**Architecture:** Use React state variables to track collapsing/drawer opening, conditionally render Tailwind CSS classes for animations/width adjustments, mount toggle handles, and intercept mobile selection to auto-close drawers.

**Tech Stack:** React 19, Tailwind CSS v4, Lucide/Material Symbols, Playwright E2E testing framework.

---

### Task 1: Add State Variables and Mobile Toggle Triggers to Header

**Files:**
- Modify: `src/pages/AIChat.jsx:51-118`
- Modify: `src/pages/AIChat.jsx:300-370`

- [ ] **Step 1: Declare left/right collapse and mobile drawer React states**

Modify `src/pages/AIChat.jsx` at the top of the `AIChat` component (around line 51) to declare these state variables.

```jsx
export default function AIChat() {
  const { activeCourseId, courses } = useCourse();
  const [sessions, setSessions] = useState([]);
  const [activeSession, setActiveSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isSending, setIsSending] = useState(false);
  
  // Collapse & Drawer States
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [leftDrawerOpen, setLeftDrawerOpen] = useState(false);
  const [rightDrawerOpen, setRightDrawerOpen] = useState(false);
```

- [ ] **Step 2: Add Mobile Toggle Buttons to the Header Context Bar**

Modify `src/pages/AIChat.jsx` around line 304 (in the Top Context Bar) to include hamburger button on the left and menu book button on the right.

```jsx
          {/* Top Context Bar */}
          <div className="h-14 border-b border-slate-200 bg-white/80 backdrop-blur-md flex items-center justify-between px-6 z-10">
            <div className="flex items-center gap-1.5 min-w-0">
              {/* Mobile Left Drawer Trigger */}
              <button 
                onClick={() => setLeftDrawerOpen(true)}
                className="lg:hidden text-slate-500 hover:bg-slate-100 p-1.5 rounded-lg transition-colors cursor-pointer mr-1 flex items-center justify-center"
              >
                <span className="material-symbols-outlined text-[20px]">menu</span>
              </button>
              
              <div className="text-sm text-slate-700 font-medium truncate">
                {activeSession ? sessions.find(s => s.id === activeSession)?.title || '对话中' : '新对话'}
              </div>
            </div>

            {/* Mobile Right Drawer Trigger */}
            <button 
              onClick={() => setRightDrawerOpen(true)}
              className="xl:hidden text-slate-500 hover:bg-slate-100 p-1.5 rounded-lg transition-colors cursor-pointer flex items-center justify-center"
            >
              <span className="material-symbols-outlined text-[20px]">menu_book</span>
            </button>
          </div>
```

- [ ] **Step 3: Run ESLint to verify syntax**

Run: `npm run lint`
Expected: PASS (No errors relating to the newly added hooks or components)

- [ ] **Step 4: Commit changes**

```bash
git add src/pages/AIChat.jsx
git commit -m "feat: add sidebar state variables and mobile toggle buttons"
```

---

### Task 2: Implement Collapsible and Sliding History Sidebar (Left Sidebar)

**Files:**
- Modify: `src/pages/AIChat.jsx:258-299`

- [ ] **Step 1: Replace left sidebar element with responsive collapsible wrapper**

Modify the left `<aside>` container in `src/pages/AIChat.jsx` (around line 258) to dynamically apply Tailwind classes and inject the desktop hover collapse handle. Wrap internal content in a fixed width wrapper to prevent reflow.

```jsx
        {/* Left Sidebar - History */}
        <aside className={`
          bg-white flex flex-col z-30 transition-all duration-300 ease-in-out relative flex-shrink-0
          /* Mobile Drawer Style */
          fixed top-0 left-0 h-full w-64 shadow-2xl lg:shadow-none lg:static lg:h-auto
          ${leftDrawerOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
          /* Desktop Collapse Style */
          ${leftCollapsed ? 'lg:w-0 lg:opacity-0 lg:overflow-hidden lg:border-transparent' : 'lg:w-64 lg:opacity-100 lg:border-r lg:border-slate-200'}
        `}>
          <div className="flex-1 flex flex-col min-w-[256px]">
            <div className="p-5 border-b border-slate-100 flex items-center justify-between">
              <div className="flex items-center gap-2 font-bold text-slate-800">
                <div className="w-6 h-6 bg-cyan-500 rounded text-white flex items-center justify-center text-[10px]">AI</div>
                智能学习助手
              </div>
              <button 
                onClick={handleResetConversation}
                className="text-cyan-600 hover:bg-cyan-50 p-1.5 rounded-lg transition-colors cursor-pointer"
                title="新对话"
              >
                <span className="material-symbols-outlined text-[18px]">add</span>
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-3 space-y-1 custom-scrollbar">
              <div className="px-3 py-2 text-xs font-bold text-slate-400 mb-1">历史记录</div>
              {sessions.map(session => (
                <div 
                  key={session.id} 
                  onClick={() => {
                    if (abortControllerRef.current) {
                      abortControllerRef.current();
                      abortControllerRef.current = null;
                    }
                    setActiveSession(session.id);
                  }}
                  className={`px-3 py-2 rounded-lg cursor-pointer text-[13px] truncate transition-colors ${
                    activeSession === session.id 
                      ? 'bg-slate-100 text-slate-800 font-semibold' 
                      : 'text-slate-500 hover:bg-slate-50'
                  }`}
                >
                  {session.title}
                </div>
              ))}
              {sessions.length === 0 && (
                <p className="text-xs text-slate-400 px-3 py-4">无历史对话</p>
              )}
            </div>
          </div>

          {/* Desktop Collapse Handle */}
          <button 
            onClick={() => setLeftCollapsed(!leftCollapsed)}
            className="hidden lg:flex absolute right-[-12px] top-1/2 -translate-y-1/2 w-6 h-6 rounded-full border border-slate-200 bg-white items-center justify-center shadow-md cursor-pointer hover:bg-slate-50 hover:text-cyan-600 transition-all z-40 active:scale-90"
            title={leftCollapsed ? "展开侧边栏" : "收起侧边栏"}
          >
            <span className="material-symbols-outlined text-[16px] select-none">
              {leftCollapsed ? 'chevron_right' : 'chevron_left'}
            </span>
          </button>
        </aside>
```

- [ ] **Step 2: Run ESLint to verify syntax**

Run: `npm run lint`
Expected: PASS

- [ ] **Step 3: Commit changes**

```bash
git add src/pages/AIChat.jsx
git commit -m "feat: implement responsive collapsible left history sidebar"
```

---

### Task 3: Implement Collapsible and Sliding Resource Sidebar (Right Sidebar)

**Files:**
- Modify: `src/pages/AIChat.jsx:374-400`

- [ ] **Step 1: Replace right sidebar element with responsive collapsible wrapper**

Modify the right `<aside>` container in `src/pages/AIChat.jsx` (around line 374) to dynamically apply Tailwind responsive/collapse classes and inject the desktop left collapse handle. Wrap internal content in a fixed width wrapper.

```jsx
        {/* Right Sidebar - Resources (Competition Ready) */}
        <aside className={`
          bg-white flex flex-col z-30 transition-all duration-300 ease-in-out relative flex-shrink-0
          /* Mobile Drawer Style */
          fixed top-0 right-0 h-full w-72 shadow-2xl xl:shadow-none xl:static xl:h-auto
          ${rightDrawerOpen ? 'translate-x-0' : 'translate-x-full xl:translate-x-0'}
          /* Desktop Collapse Style */
          ${rightCollapsed ? 'xl:w-0 xl:opacity-0 xl:overflow-hidden xl:border-transparent' : 'xl:w-72 xl:opacity-100 xl:border-l xl:border-slate-200'}
        `}>
          <div className="flex-1 flex flex-col min-w-[288px] h-full">
            <div className="p-5 border-b border-slate-100">
              <div className="text-[11px] font-bold text-slate-400 mb-1">当前学习上下文</div>
              <div className="text-slate-800 font-semibold text-sm truncate" title={activeCourseName}>
                {activeCourseName}
              </div>
            </div>
            
            <div className="flex-1 overflow-y-auto p-5 custom-scrollbar">
              <div className="flex justify-between items-center mb-4">
                <span className="text-[12px] font-bold text-slate-400">相关资源推荐</span>
                <span className="text-[12px] text-cyan-600 cursor-pointer hover:underline">全部</span>
              </div>
              
              {/* Empty State */}
              <div className="border border-slate-200 border-dashed rounded-xl p-4 bg-slate-50 flex flex-col items-center justify-center text-center mt-6">
                <div className="w-12 h-12 bg-slate-100 rounded-full mb-3 flex items-center justify-center text-slate-400">
                  <span className="material-symbols-outlined text-2xl">inventory_2</span>
                </div>
                <div className="text-[14px] font-semibold text-slate-700 mb-1">暂无推荐资源</div>
                <div className="text-[12px] text-slate-500 leading-relaxed px-2 mt-2">
                  完成检索能力验证后，这里会展示与本轮知识点相关的课程资源。
                </div>
              </div>
            </div>
          </div>

          {/* Desktop Collapse Handle */}
          <button 
            onClick={() => setRightCollapsed(!rightCollapsed)}
            className="hidden xl:flex absolute left-[-12px] top-1/2 -translate-y-1/2 w-6 h-6 rounded-full border border-slate-200 bg-white items-center justify-center shadow-md cursor-pointer hover:bg-slate-50 hover:text-cyan-600 transition-all z-40 active:scale-90"
            title={rightCollapsed ? "展开侧边栏" : "收起侧边栏"}
          >
            <span className="material-symbols-outlined text-[16px] select-none">
              {rightCollapsed ? 'chevron_left' : 'chevron_right'}
            </span>
          </button>
        </aside>
```

- [ ] **Step 2: Run ESLint to verify syntax**

Run: `npm run lint`
Expected: PASS

- [ ] **Step 3: Commit changes**

```bash
git add src/pages/AIChat.jsx
git commit -m "feat: implement responsive collapsible right resource sidebar"
```

---

### Task 4: Implement Backdrop Overlay and Selection Interlock

**Files:**
- Modify: `src/pages/AIChat.jsx:106-118` (handleResetConversation and session selection)
- Modify: `src/pages/AIChat.jsx:320-330` (render backdrop overlay)

- [ ] **Step 1: Add interlock to close mobile drawer when switching sessions or resetting**

Modify the click handler for sessions in history list to close the left drawer:

```jsx
              {sessions.map(session => (
                <div 
                  key={session.id} 
                  onClick={() => {
                    if (abortControllerRef.current) {
                      abortControllerRef.current();
                      abortControllerRef.current = null;
                    }
                    setActiveSession(session.id);
                    setLeftDrawerOpen(false); // Close mobile history drawer
                  }}
```

And also modify `handleResetConversation` to close the drawer:

```jsx
  const handleResetConversation = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current();
      abortControllerRef.current = null;
    }
    setActiveSession(null);
    lastMessageIdRef.current = null;
    setMessages([]);
    setIsSending(false);
    setLeftDrawerOpen(false); // Close mobile drawer
  };
```

- [ ] **Step 2: Render Backdrop Overlay**

Render the overlay backdrop directly in `AIChat.jsx` above the `<main>` element, z-indexed appropriately.

```jsx
    </aside>

    {/* Backdrop Overlay for mobile drawers */}
    {(leftDrawerOpen || rightDrawerOpen) && (
      <div 
        onClick={() => { setLeftDrawerOpen(false); setRightDrawerOpen(false); }}
        className="fixed inset-0 bg-slate-900/30 backdrop-blur-xs z-40 lg:hidden transition-opacity duration-300"
      />
    )}

    {/* Center Column - Main Chat */}
    <main className="flex-1 flex flex-col relative bg-slate-50 z-10">
```

- [ ] **Step 3: Run final checks**

Run: `npm run lint`
Expected: PASS

Run: `npm run build`
Expected: PASS (Production bundle builds successfully)

- [ ] **Step 4: Commit changes**

```bash
git add src/pages/AIChat.jsx
git commit -m "feat: implement backdrop overlay and mobile selection interlock"
```
