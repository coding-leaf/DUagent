# AIChat Artifact Workbench UI V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a frontend-only AIChat mock that shows conversation history, an Agent artifact workspace, AI chat, visible tool progress, and generated learning artifacts without changing backend contracts.

**Architecture:** Reuse the existing `ChatContext.workspaceArtifacts`, `sendMockArtifact`, `components/workspace/AgentWorkspace`, and plugin registry. `AIChat.jsx` owns the three-column shell; `ChatArea.jsx` owns chat input, assistant action controls, and frontend-only mock tool/artifact triggers.

**Tech Stack:** React, Tailwind CSS classes, Vitest, Testing Library, existing workspace plugin components.

---

### Task 1: Characterize Current Workspace Behavior

**Files:**
- Modify: `frontend/src/components/workspace/AgentWorkspace.test.jsx`

- [ ] Add assertions that the workspace title and empty state are visible when no artifacts exist.
- [ ] Run `cd frontend && npm run test:unit -- src/components/workspace/AgentWorkspace.test.jsx`
- [ ] Expected initial result before implementation: existing tests pass, but AIChat does not yet place this workspace into the page shell.

### Task 2: Refactor AIChat Page Shell

**Files:**
- Modify: `frontend/src/pages/AIChat.jsx`

- [ ] Import `AgentWorkspace` from `frontend/src/components/workspace/AgentWorkspace.jsx`.
- [ ] Replace the old center `ChatArea` + right `SidebarResources` layout with left `SidebarHistory`, center `AgentWorkspace`, right `ChatArea`.
- [ ] Keep `Navbar` and current drawer behavior for the left history panel.
- [ ] Remove the right resource sidebar from this page only; existing resource pages remain unchanged.

### Task 3: Add Frontend-Only Tool Demo Controls

**Files:**
- Modify: `frontend/src/components/chat/ChatArea.jsx`
- Modify: `frontend/src/components/chat/ChatMessage.jsx`
- Modify: `frontend/src/components/chat/ToolCallCard.jsx`

- [ ] Add lightweight quick action buttons below the chat input for: `补弱计划`, `推荐资源`, `讲解页`, `练习预览`.
- [ ] When a quick action is clicked, append a mock user message, an assistant message with completed tool calls, and one workspace artifact through `sendMockArtifact`.
- [ ] Render retry/regenerate/copy actions below the assistant message, not inside `ToolCallCard`.
- [ ] Keep `ToolCallCard` display-only: status, title, description, output summary.

### Task 4: Verify and Record

**Files:**
- Modify: `WorkLine.md`

- [ ] Run targeted unit tests for workspace and chat components where available.
- [ ] Run `cd frontend && npm run build`.
- [ ] Append WorkLine entry describing frontend-only UI mock, tests, and no interface drift.
