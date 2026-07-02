# AI Chat & Workspace UI Redesign (Modern Canvas & Floating Chat)

## 1. Overview
The current AI Chat interface and Agent Workspace layout in EDUagent feels rigid and cluttered. The 3-column layout locks the chat pane to a fixed width and vertically stacks generated artifacts, wasting screen space and reducing focus. 

This design implements a "Modern Canvas & Floating Chat" paradigm. The workspace becomes a tabbed, immersive canvas dedicated to a single active artifact at a time. The AI Chat transforms into a sleek, floating sidebar overlaid or adjacent to the canvas, heavily inspired by modern AI interfaces (Apple Intelligence / ChatGPT Canvas).

## 2. Architecture & Layout Changes

### 2.1 Page Layout (`AIChat.jsx`)
- **Current**: `<SidebarHistory />` + `<AgentWorkspace />` + `<ChatArea />` flex row.
- **New**: The container becomes a relative wrapper. `<SidebarHistory />` remains on the left. `<AgentWorkspace />` expands to take up `flex-1` (the entire remaining space). `<ChatArea />` becomes a floating or beautifully integrated sidebar on the right side of the canvas.

### 2.2 Workspace Canvas (`AgentWorkspace.jsx`)
- **Vertical Stacking Removed**: Remove the `space-y-6` vertical stack.
- **Tabbed Interface**: Introduce a new tab bar at the top of the workspace. When multiple artifacts are generated in the current session, they are managed via tabs. Only one artifact is displayed at a time, allowing it to occupy the maximum available screen space.
- **Empty State**: Refine the empty state to match the new canvas aesthetic (clean, minimalist, prompting the user to chat).

### 2.3 Chat Area & Input (`ChatArea.jsx`)
- **Floating Panel**: Add a subtle `box-shadow` and `backdrop-blur` to the chat container to separate it from the main canvas.
- **Pill-shaped Input**: The input area is redesigned. The quick action pills ("计划模式", "推荐资源") are integrated elegantly above the input. The textarea itself is housed in a rounded, pill-like container that floats near the bottom, rather than a bulky rectangle spanning the full width.

### 2.4 Chat Bubbles (`ChatMessage.jsx`)
- **AI Messages (Assistant)**: Remove any boxy, rigid borders. The AI text flows naturally like a document. Update the AI avatar to a modern gradient circle instead of a flat square.
- **User Messages**: Retain the distinct colored bubble for user messages, but refine the corner radii and shadow to match the overall modern aesthetic.

## 3. Component Details & Interactions

### WorkspaceTabs (New Concept within Workspace)
- **State**: Track `activeArtifactId`.
- **UI**: A horizontal scrollable list of tabs at the top of the `AgentWorkspace`. Each tab shows the artifact type or title.
- **Behavior**: Clicking a tab switches the active artifact component.

### Responsive & Toggle Behavior
- The Chat pane can be collapsed/toggled on smaller screens to allow the canvas to take 100% of the viewport. A toggle button will be added to the canvas header or chat header.

## 4. Risks & Mitigations
- **Plugin Sizing**: Existing plugins may assume infinite vertical scroll space. We need to ensure the canvas wrapper handles overflow gracefully (`overflow-y-auto`) so tall artifacts can still be scrolled within their active tab.
- **State Management**: We must correctly sync the list of `workspaceArtifacts` from `ChatContext` with the active tab state in `AgentWorkspace`. Default behavior: when a new artifact arrives, automatically switch to its tab.
