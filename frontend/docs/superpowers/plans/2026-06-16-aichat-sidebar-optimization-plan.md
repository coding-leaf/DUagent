# AIChat Sidebar Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Modify the AIChat sidebars to collapse into a 64px mini-sidebar to prevent width animation layout jank and keep expand toggle buttons visible.

**Architecture:** Use CSS classes to transition the `w-0` to `w-16` instead, and wrap inner contents in fixed-width containers `w-64`/`w-72` with `overflow-hidden` to avoid reflows. Add icons to the history list for the mini-view.

**Tech Stack:** React, TailwindCSS

---

### Task 1: Update Left Sidebar

**Files:**
- Modify: `frontend/src/pages/AIChat.jsx`

- [ ] **Step 1: Modify the Left Sidebar `aside` and wrapper classes**

Update the classes in `frontend/src/pages/AIChat.jsx` around line 580.
Change the desktop collapse style from `lg:w-0 lg:opacity-0 lg:border-transparent` to `lg:w-16 lg:border-r lg:border-slate-200`.
Change the wrapper from `w-full` and `min-w-[256px]` to `w-64`.

```jsx
        {/* Left Sidebar - History */}
        <aside className={`
          bg-white flex flex-col z-30 transition-all duration-300 ease-in-out relative flex-shrink-0
          /* Mobile Drawer Style */
          fixed top-0 left-0 h-full w-64 shadow-2xl lg:shadow-none lg:static lg:h-full
          ${leftDrawerOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
          /* Desktop Collapse Style */
          ${leftCollapsed ? 'lg:w-16 lg:border-r lg:border-slate-200' : 'lg:w-64 lg:border-r lg:border-slate-200'}
        `}>
          {/* Wrapper to handle overflow clipping during width transitions without hiding absolute handle */}
          <div className="w-64 h-full overflow-hidden flex flex-col">
            <div className="flex-1 flex flex-col w-64 h-full">
```

- [ ] **Step 2: Add icons to the history list items**

Update the session mapping (around line 611) to add a chat bubble icon and a `title` attribute.

```jsx
                {sessions.map(session => (
                  <div key={session.id} className="group/session flex items-center">
                    <div
                      onClick={() => {
                        if (abortControllerRef.current) {
                          abortControllerRef.current();
                          abortControllerRef.current = null;
                        }
                        setActiveSession(session.id);
                        setLeftDrawerOpen(false);
                      }}
                      className={`flex-1 px-3 py-2 rounded-lg cursor-pointer text-[13px] transition-colors flex items-center gap-2 ${
                        activeSession === session.id
                          ? 'bg-slate-100 text-slate-800 font-semibold'
                          : 'text-slate-500 hover:bg-slate-50'
                      }`}
                      title={session.title}
                    >
                      <Icon name="chat_bubble_outline" className="material-symbols-outlined text-[16px] flex-shrink-0"/>
                      <span className="truncate">{session.title}</span>
                    </div>
```

- [ ] **Step 3: Run linter and build to verify changes**

Run: `npm run lint && npm run build`
Expected: PASS without errors.

- [ ] **Step 4: Commit**

```bash
git add src/pages/AIChat.jsx
git commit -m "feat(ui): optimize left sidebar collapse animation and add mini mode"
```

### Task 2: Update Right Sidebar

**Files:**
- Modify: `frontend/src/pages/AIChat.jsx`

- [ ] **Step 1: Modify the Right Sidebar `aside` and wrapper classes**

Update the classes around line 849.
Change the desktop collapse style from `xl:w-0 xl:opacity-0 xl:border-transparent` to `xl:w-16 xl:border-l xl:border-slate-200`.
Change the wrapper from `w-full` and `min-w-[288px]` to `w-72`.

```jsx
        {/* Right Sidebar - Resources (Competition Ready) */}
        <aside className={`
          bg-white flex flex-col z-30 transition-all duration-300 ease-in-out relative flex-shrink-0
          /* Mobile Drawer Style */
          fixed top-0 right-0 h-full w-72 shadow-2xl xl:shadow-none xl:static xl:h-full
          ${rightDrawerOpen ? 'translate-x-0' : 'translate-x-full xl:translate-x-0'}
          /* Desktop Collapse Style */
          ${rightCollapsed ? 'xl:w-16 xl:border-l xl:border-slate-200' : 'xl:w-72 xl:border-l xl:border-slate-200'}
        `}>
          {/* Wrapper to handle overflow clipping during width transitions without hiding absolute handle */}
          <div className="w-72 h-full overflow-hidden flex flex-col">
            <div className="flex-1 flex flex-col w-72 h-full">
```

- [ ] **Step 2: Run linter and build to verify changes**

Run: `npm run lint && npm run build`
Expected: PASS without errors.

- [ ] **Step 3: Commit**

```bash
git add src/pages/AIChat.jsx
git commit -m "feat(ui): optimize right sidebar collapse animation to mini mode"
```
