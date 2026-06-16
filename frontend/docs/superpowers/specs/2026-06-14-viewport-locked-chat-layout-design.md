# AI Chat Viewport-Locked Chat Layout Design Spec

## 1. Background & Goals
During long conversations in the AI Chat assistant (`AIChat.jsx`), the page wrapper's height would expand dynamically (using `min-h-screen` and auto heights on sidebars), causing the entire web page to develop a scrollbar. As the user scrolled down to read new messages, the left sidebar (containing the "+ 新对话" reset button) and the right sidebar (containing the learning context and recommended resources) would scroll up and disappear from the viewport. 

The goal of this redesign is to lock the layout height to the viewport height (`h-screen overflow-hidden` on the page wrapper) so that:
1. The Navbar, top context bar, and sidebars (left & right) remain strictly pinned to the screen at all times.
2. Only the middle messages scroll container scrolls internally.
3. The user never needs to scroll up to click "+ 新对话" or view recommended resources.

---

## 2. Layout & CSS Architecture

### Outer Page Wrapper
- **Current**: `<div className="font-body-md text-slate-800 bg-slate-50 min-h-screen flex flex-col">`
- **Target**: `<div className="font-body-md text-slate-800 bg-slate-50 h-screen flex flex-col overflow-hidden">`
- *Rationale*: Locks the outer page container to exactly 100vh and prevents any browser-level/body scrolling.

### Inner Content Container
- **Current**: `<div className="flex-1 flex overflow-hidden pt-16">`
- **Target**: `<div className="flex-1 flex overflow-hidden pt-16">` (Unchanged, already utilizes flexbox fill and overflows hidden, but will now be constrained by the parent's fixed height).

### Left History Sidebar
- **Current**:
  ```jsx
  <aside className={`
    bg-white flex flex-col z-30 transition-all duration-300 ease-in-out relative flex-shrink-0
    /* Mobile Drawer Style */
    fixed top-0 left-0 h-full w-64 shadow-2xl lg:shadow-none lg:static lg:h-auto
    ...
  `}>
  ```
- **Target**:
  ```jsx
  <aside className={`
    bg-white flex flex-col z-30 transition-all duration-300 ease-in-out relative flex-shrink-0
    /* Mobile Drawer Style */
    fixed top-0 left-0 h-full w-64 shadow-2xl lg:shadow-none lg:static lg:h-full
    ...
  `}>
  ```
- *Rationale*: Replaces `lg:h-auto` with `lg:h-full` so the sidebar matches the height of the parent container on desktop viewports.

### Right Resources Sidebar
- **Current**:
  ```jsx
  <aside className={`
    bg-white flex flex-col z-30 transition-all duration-300 ease-in-out relative flex-shrink-0
    /* Mobile Drawer Style */
    fixed top-0 right-0 h-full w-72 shadow-2xl xl:shadow-none xl:static xl:h-auto
    ...
  `}>
  ```
- **Target**:
  ```jsx
  <aside className={`
    bg-white flex flex-col z-30 transition-all duration-300 ease-in-out relative flex-shrink-0
    /* Mobile Drawer Style */
    fixed top-0 right-0 h-full w-72 shadow-2xl xl:shadow-none xl:static xl:h-full
    ...
  `}>
  ```
- *Rationale*: Replaces `xl:h-auto` with `xl:h-full` so the recommended resources panel fills the screen height and maintains internal scroll capabilities on desktop.

---

## 3. Test & Verification Plan
1. **Body Scroll Lock**: Simulate many chat messages, verify that the browser window scrollbar never appears.
2. **Sidebar Sticky Verification**:
   - Ensure the "+ 新对话" button remains visible and clickable at all times in the left sidebar.
   - Ensure "当前学习上下文" and "相关资源推荐" remain fixed and visible at all times in the right sidebar.
3. **Internal Scrolling**: Verify the message stream and the sidebar history stream scroll independently inside their respective wrappers.
