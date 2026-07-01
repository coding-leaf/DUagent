# AIChat Draft Conversation And Tool Events Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix AIChat new-conversation draft behavior and remove frontend-manufactured quick-action tool results.

**Architecture:** `ChatContext` remains the single source of chat session, message, and workspace artifact state. Quick actions become prompt shortcuts that use the existing streaming path, while `ChatContext` continues to reduce only backend-returned native EDU v2 events.

**Tech Stack:** React 19, SWR, Vitest, Testing Library.

---

## File Structure

- Modify `frontend/src/context/ChatContext.jsx`: add draft conversation state and remove mock artifact/demo helpers from the public context.
- Modify `frontend/src/context/ChatContext.test.jsx`: add regression coverage for draft mode and keep native event reducer coverage.
- Modify `frontend/src/components/chat/ChatArea.jsx`: replace mock quick-action calls with prompt shortcut calls.
- Create `frontend/src/components/chat/ChatArea.test.jsx`: verify quick action prompt behavior.
- Delete `frontend/src/components/chat/mockToolDemos.js`: remove hard-coded frontend tool results once no production code imports it.
- Modify `WorkLine.md`: record the completed change and verification.

## Task 1: Draft Conversation State

- [ ] **Step 1: Write failing test**

Add a test in `frontend/src/context/ChatContext.test.jsx` with a consumer that waits for `activeSession` to become `conv-existing`, calls `resetConversation()`, and asserts `activeSession` remains blank after the session auto-selection effect has had a chance to run.

- [ ] **Step 2: Run RED**

Run:

```bash
cd frontend && npm run test:unit -- src/context/ChatContext.test.jsx -t "keeps a user-created draft conversation active"
```

Expected: FAIL because `activeSession` becomes `conv-existing` again.

- [ ] **Step 3: Implement minimal fix**

Add `isDraftConversation` in `ChatContext`. Set it to true in `resetConversation()`, set it to false when selecting a historical session or sending a message, and gate the auto-selection effect with `!isDraftConversation`.

- [ ] **Step 4: Run GREEN**

Run the same focused test and expect PASS.

## Task 2: Quick Actions Use Real Stream Path

- [ ] **Step 1: Write failing test**

Create `frontend/src/components/chat/ChatArea.test.jsx`. Mock `useChat` and `useCourse`, render `ChatArea`, click the `补弱计划` quick action, and assert `sendMessage('帮我根据当前薄弱点生成补弱学习计划。')` was called while `runMockToolDemo` was not called.

- [ ] **Step 2: Run RED**

Run:

```bash
cd frontend && npm run test:unit -- src/components/chat/ChatArea.test.jsx -t "submits quick action prompts through sendMessage"
```

Expected: FAIL because the component currently calls `runMockToolDemo`.

- [ ] **Step 3: Implement minimal fix**

Replace `QUICK_ACTIONS` entries with prompt strings and update the click handler to call `handleSendMessage(action.prompt)`. Remove `runMockToolDemo` from `ChatArea`.

- [ ] **Step 4: Remove production mock helpers**

Remove `MOCK_TOOL_DEMOS`, `sendMockArtifact`, and `runMockToolDemo` from `ChatContext`. Delete `frontend/src/components/chat/mockToolDemos.js` after confirming there are no production imports.

- [ ] **Step 5: Run GREEN**

Run the focused `ChatArea` test and the existing `ChatContext` test.

## Task 3: Verification And Commit

- [ ] **Step 1: Run frontend checks**

Run:

```bash
cd frontend && npm run test:unit -- src/context/ChatContext.test.jsx src/components/chat/ChatArea.test.jsx
cd frontend && npm run lint
cd frontend && npm run build
```

- [ ] **Step 2: Update WorkLine**

Append a 2026-07-01 entry noting the AIChat draft fix, quick-action mock removal, test commands, and no interface drift.

- [ ] **Step 3: Commit**

Commit only the files touched for this task, leaving unrelated `TODO.md` untouched:

```bash
git add docs/superpowers/specs/2026-07-01-aichat-draft-and-tool-events-design.md docs/superpowers/plans/2026-07-01-aichat-draft-and-tool-events.md frontend/src/context/ChatContext.jsx frontend/src/context/ChatContext.test.jsx frontend/src/components/chat/ChatArea.jsx frontend/src/components/chat/ChatArea.test.jsx frontend/src/components/chat/mockToolDemos.js WorkLine.md
git commit -m "修复AIChat新对话与工具事件链路"
```
