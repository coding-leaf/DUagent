# AIChat Refactoring Design Spec

## 1. Objective
Refactor `AIChat.jsx` (465 lines) to eliminate the "Fat Component" anti-pattern. We will split it into a pure structural Container and three specialized Presentational components, pushing business logic down to where it is used (Co-location). We will also fix the left sidebar overflow bug.

## 2. Architecture & Design Patterns

### 2.1 Pattern Selection
- **Container/Presentational Pattern**: `AIChat.jsx` acts as the Layout orchestrator, managing only structural drawer/collapse states.
- **State/Query Co-location**: Data fetching and derived state (like `activeKPs`) are pushed deep into the child components that need them.

### 2.2 File Distribution & Responsibilities

1. **`src/components/chat/SidebarHistory.jsx`**
   - **Responsibility**: Render past chat sessions and handle session switching/deletion.
   - **Bug Fix**: Add `overflow-hidden` to the top-level `<aside>` and ensure internal containers don't break flex boundaries when the parent shrinks to `w-16`. The inner content should cleanly clip or fade out.
   - **Data Access**: Internally consumes `useChat()` to get `sessions`, `activeSession`, `setActiveSession`, `deleteSession`, etc.
   - **Props**: `leftCollapsed`, `leftDrawerOpen`, `onToggleCollapse`, `onCloseDrawer`, `onNewChat`.

2. **`src/components/chat/SidebarResources.jsx`**
   - **Responsibility**: Render recommended learning resources based on chat context.
   - **Co-location (Option Y)**: Completely encapsulates the `learningService.getResources` API call. It also internally consumes `useChat()` to get `messages`, computes `activeKPs` via `useMemo`, and derives `recommendedResources`. The parent container knows **nothing** about this logic.
   - **Props**: `activeCourseName`, `rightCollapsed`, `rightDrawerOpen`, `onToggleCollapse`, `onCloseDrawer`.

3. **`src/components/chat/ChatArea.jsx`**
   - **Responsibility**: Render the message stream, auto-scroll logic, and the input composer.
   - **Data Access**: Internally consumes `useChat()` for `messages`, `isSending`, `sendMessage`, etc.
   - **Props**: `activeCourseName`, `onOpenLeftDrawer`, `onOpenRightDrawer` (for mobile triggers).

4. **`src/pages/AIChat.jsx`** (Container)
   - **Responsibility**: Orchestrates the 3-column layout.
   - **State**: Only holds layout UI state (`leftCollapsed`, `rightCollapsed`, `leftDrawerOpen`, `rightDrawerOpen`).
   - **Logic**: Calls `useCourse()` to pass down basic course metadata (`activeCourseName`) to components.

## 3. Data Flow
- **Chat Context**: `useChat` is heavily leveraged. Because it is a React Context, `SidebarHistory`, `SidebarResources`, and `ChatArea` can independently subscribe to it without passing massive props down from `AIChat.jsx`.
- **Resource Fetching**: `SidebarResources` independently issues `learningService.getResources` based on `useCourse().activeCourseId`.

## 4. Testing Strategy
- Run `npm run lint` and `npm run build` after each component extraction.
- Manually test the collapse/drawer behavior to ensure the left sidebar bug is resolved.
