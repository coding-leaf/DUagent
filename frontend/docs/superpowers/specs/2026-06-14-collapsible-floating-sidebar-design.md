# AI Chat Sidebar Collapsible & Responsive Floating Design Spec

## 1. Background & Goals
Currently, the AI chat assistant page (`AIChat.jsx`) features hardcoded sidebars on both the left (conversation history) and right (recommended learning resources). These panels take up fixed widths on large screens and are entirely hidden (`hidden`) on smaller mobile and tablet viewports without any toggle mechanism or sliding drawer, making key features inaccessible on mobile.

The goals of this redesign are:
1. **Desktop Collapsing**: Allow users on large viewports to collapse/expand sidebars via small arrow toggle buttons. When collapsed, sidebars smoothly contract to `w-0` and the central chat area expands to occupy the available screen width.
2. **Mobile Floating Drawers**: Provide toggles in the top context bar on smaller viewports to slide the sidebars in as fixed-position overlay drawers (with backdrop filters).
3. **Persistency / Initial State**: By default, sidebars are expanded when loading the page. No local storage persistence is needed as per user preference ("默认展开").

---

## 2. UI / UX Design

### Desktop Collapsible Sidebar
- **Left Sidebar (History)**: Width transitions between `w-64` (expanded) and `w-0` (collapsed).
- **Right Sidebar (Resources)**: Width transitions between `w-72` (expanded) and `w-0` (collapsed).
- **Toggle Handles**: 
  - Rounded toggle circular buttons (size `w-6 h-6`) positioned vertically centered on the divider line of each sidebar (`absolute top-1/2 -translate-y-1/2`).
  - Displays Material Symbol icons (`chevron_left` and `chevron_right`) based on collapse state.
  - Hovering transitions background and text colors to cyan themes.
  - Even when a sidebar is collapsed to `w-0`, the toggle handle remains visible and hoverable at the viewport's edge so the user can easily expand it again.

### Mobile overlay Drawers
- **Left Sidebar**: Moves to `fixed left-0 top-0 h-full w-64 z-50 shadow-2xl bg-white transition-transform duration-300` when viewport width `< 1024px`. Drawer is active when `leftDrawerOpen` is true (`translate-x-0`), and hidden offscreen otherwise (`-translate-x-full`).
- **Right Sidebar**: Moves to `fixed right-0 top-0 h-full w-72 z-50 shadow-2xl bg-white transition-transform duration-300` when viewport width `< 1280px`. Drawer is active when `rightDrawerOpen` is true (`translate-x-0`), and hidden offscreen otherwise (`translate-x-full`).
- **Overlay Backdrop**: A full-viewport semi-transparent overlay (`fixed inset-0 bg-slate-900/30 backdrop-blur-xs z-40`) is displayed if either mobile drawer is open. Clicking the overlay immediately closes both drawers.
- **Top Bar Triggers**:
  - **Left menu toggle**: A hamburger icon button `menu` on the left of the Top Context Bar (hidden on `lg:flex`).
  - **Right resource toggle**: A book icon button `menu_book` on the right of the Top Context Bar (hidden on `xl:flex`).

---

## 3. Implementation details (AIChat.jsx)

### React States
```javascript
const [leftCollapsed, setLeftCollapsed] = useState(false);  // Desktop left panel collapse state
const [rightCollapsed, setRightCollapsed] = useState(false); // Desktop right panel collapse state
const [leftDrawerOpen, setLeftDrawerOpen] = useState(false);  // Mobile left drawer open state
const [rightDrawerOpen, setRightDrawerOpen] = useState(false);// Mobile right drawer open state
```

### Component Structure
```jsx
<div className="font-body-md text-slate-800 bg-slate-50 min-h-screen flex flex-col">
  <Navbar />

  <div className="flex-1 flex overflow-hidden pt-16 relative">
    
    {/* Left Sidebar - History */}
    <aside className={`
      bg-white flex flex-col z-30 transition-all duration-300 ease-in-out relative
      /* Mobile Drawer Style */
      fixed top-0 left-0 h-full w-64 shadow-2xl lg:shadow-none lg:static lg:h-auto
      \${leftDrawerOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
      /* Desktop Collapse Style */
      \${leftCollapsed ? 'lg:w-0 lg:opacity-0 lg:overflow-hidden lg:border-transparent' : 'lg:w-64 lg:opacity-100 lg:border-r lg:border-slate-200'}
    `}>
      {/* Sidebar Content */}
      <div className="flex-1 flex flex-col min-w-[256px]">
        {/* We wrap sidebar contents in a fixed min-width div so shrinking the parent container doesn't reflow/squish texts */}
        ...
      </div>

      {/* Desktop Collapse Handle (Hidden on mobile) */}
      <button 
        onClick={() => setLeftCollapsed(!leftCollapsed)}
        className="hidden lg:flex absolute right-[-12px] top-1/2 -translate-y-1/2 w-6 h-6 rounded-full border border-slate-200 bg-white items-center justify-center shadow-md cursor-pointer hover:bg-slate-50 hover:text-cyan-600 transition-all z-40 active:scale-90"
      >
        <span className="material-symbols-outlined text-[16px]">
          {leftCollapsed ? 'chevron_right' : 'chevron_left'}
        </span>
      </button>
    </aside>

    {/* Backdrop Overlay (Mobile only) */}
    {(leftDrawerOpen || rightDrawerOpen) && (
      <div 
        onClick={() => { setLeftDrawerOpen(false); setRightDrawerOpen(false); }}
        className="fixed inset-0 bg-slate-900/30 backdrop-blur-xs z-40 lg:hidden"
      />
    )}

    {/* Center Column - Main Chat */}
    <main className="flex-1 flex flex-col relative bg-slate-50 z-10">
      
      {/* Top Context Bar */}
      <div className="h-14 border-b border-slate-200 bg-white/80 backdrop-blur-md flex items-center justify-between px-6 z-10">
        <div className="flex items-center gap-1.5 min-w-0">
          {/* Mobile Left Drawer Trigger */}
          <button 
            onClick={() => setLeftDrawerOpen(true)}
            className="lg:hidden text-slate-500 hover:bg-slate-100 p-1.5 rounded-lg transition-colors cursor-pointer mr-1"
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
          className="xl:hidden text-slate-500 hover:bg-slate-100 p-1.5 rounded-lg transition-colors cursor-pointer"
        >
          <span className="material-symbols-outlined text-[20px]">menu_book</span>
        </button>
      </div>

      {/* Messages Scroll Area */}
      ...
    </main>

    {/* Right Sidebar - Resources */}
    <aside className={`
      bg-white flex flex-col z-30 transition-all duration-300 ease-in-out relative
      /* Mobile Drawer Style */
      fixed top-0 right-0 h-full w-72 shadow-2xl xl:shadow-none xl:static xl:h-auto
      \${rightDrawerOpen ? 'translate-x-0' : 'translate-x-full xl:translate-x-0'}
      /* Desktop Collapse Style */
      \${rightCollapsed ? 'xl:w-0 xl:opacity-0 xl:overflow-hidden xl:border-transparent' : 'xl:w-72 xl:opacity-100 xl:border-l xl:border-slate-200'}
    `}>
      {/* Sidebar Content wrapper */}
      <div className="flex-1 flex flex-col min-w-[288px]">
        ...
      </div>

      {/* Desktop Collapse Handle (Hidden on mobile) */}
      <button 
        onClick={() => setRightCollapsed(!rightCollapsed)}
        className="hidden xl:flex absolute left-[-12px] top-1/2 -translate-y-1/2 w-6 h-6 rounded-full border border-slate-200 bg-white items-center justify-center shadow-md cursor-pointer hover:bg-slate-50 hover:text-cyan-600 transition-all z-40 active:scale-90"
      >
        <span className="material-symbols-outlined text-[16px]">
          {rightCollapsed ? 'chevron_left' : 'chevron_right'}
        </span>
      </button>
    </aside>

  </div>
</div>
```

### Mobile Selection Interlock
- When mobile users tap on a session in the left history drawer, or tap the "+" new session button, we trigger the session change and immediately set `leftDrawerOpen(false)` so the sidebar slides out of view seamlessly.

---

## 4. Test Plan
- **Lint Check**: Run `npm run lint` to verify syntax and formatting.
- **Responsiveness Check**: Verify responsive viewports:
  - Desktop ($> 1280px$): Verify left and right panels are visible by default and can be collapsed using arrow handles. Verify center chat stretches to fill space.
  - Tablet ($1024px - 1280px$): Verify right panel is hidden by default but can be toggled via the `menu_book` button on the top right context bar.
  - Mobile ($< 1024px$): Verify both panels are hidden by default, and triggers `menu` and `menu_book` correctly slide the drawers in and out. Click backdrop to close.
