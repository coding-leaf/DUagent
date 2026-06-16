# AIChat Sidebar Optimization Design

## Problem Statement
The AIChat page (`frontend/src/pages/AIChat.jsx`) suffers from two UI/UX issues:
1. **Janky animation**: Expanding and collapsing the sidebars causes stuttering because the `width` transition constantly forces browser layout recalculation of all flexible child elements.
2. **Invisible when collapsed**: The collapse state currently uses `w-0` and `opacity-0`. Because the expand/collapse toggle button is placed inside the sidebar container, it disappears entirely when collapsed, leaving a completely blank area and preventing the user from reopening it.

## Approach
Implement a "Mini Sidebar" pattern combined with "Fixed Inner Width Clipping" to eliminate layout thrashing and preserve visual context when collapsed.

### 1. Outer Container Transition
- Change the collapsed state class for the left sidebar from `lg:w-0 lg:opacity-0` to `lg:w-16` (64px width).
- Change the collapsed state class for the right sidebar from `xl:w-0 xl:opacity-0` to `xl:w-16`.
- Remove `opacity-0` and `border-transparent` on collapsed states so the background and border remain visible.

### 2. Inner Content Clipping (Performance Fix)
- Inside each `<aside>`, wrap the content in a fixed-width container:
  - Left side: `<div className="w-64 min-w-[256px] h-full flex flex-col">`
  - Right side: `<div className="w-72 min-w-[288px] h-full flex flex-col">`
- Set `overflow-hidden` on the wrapper. When the outer `<aside>` shrinks to 64px, the inner content is visually clipped without its CSS width changing, thereby skipping text reflows.

### 3. Mini Sidebar Visual Adjustments
- **Left Sidebar (History)**:
  - Add a `chat_bubble` icon before each history session title.
  - Make sure the icon is perfectly centered in the 64px collapsed view.
  - Add native `title` attribute to the history items so users can hover to read the full title when collapsed.
- **Right Sidebar (Resources)**:
  - The resource list already has icons at the start. Adjust padding so these icons sit centered within the 64px strip when collapsed.
- **Toggle Buttons**:
  - The toggle buttons (`absolute right-[-12px]`) will sit nicely on the edge of the 64px sidebar. They remain fully clickable since opacity is kept at 100%.

## Scope & Dependencies
- Target File: `frontend/src/pages/AIChat.jsx`
- No new external dependencies required.
- No changes to data models or APIs.
