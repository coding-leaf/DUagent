# Frontend AIChat Refactoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the frontend AIChat module to adhere to SWR and MVVM directives. Extract recommendation logic into a custom hook, simplify `SidebarResources.jsx` into a pure view, and integrate SWR for chat session list management in `ChatContext.jsx`.

**Architecture:**
1. **ViewModel Hook**: Create `frontend/src/hooks/useRecommendedResources.js` encapsulating resource fetching (via SWR) and knowledge-point-based filtering logic.
2. **Resource View**: Simplify `frontend/src/components/chat/SidebarResources.jsx` to consume `useRecommendedResources`.
3. **Chat ViewModel Context**: Refactor `frontend/src/context/ChatContext.jsx` to fetch and manage chat sessions using SWR, including optimistic state updates for deletion and automatic revalidation.

---

### Task 1: Create Custom Hook `useRecommendedResources`
**Files:**
- Create: `frontend/src/hooks/useRecommendedResources.js`

- [ ] **Step 1.1: Write the custom hook**
  Write the hook code using SWR as outlined in the auditor's analysis report. Ensure that it extracts active knowledge points from assistant messages and filters the course resources accordingly.

---

### Task 2: Refactor `SidebarResources`
**Files:**
- Modify: `frontend/src/components/chat/SidebarResources.jsx`

- [ ] **Step 2.1: Implement view refactoring**
  Replace local state and `useEffect` API calls with a simple invocation of the custom hook: `const { recommendedResources, error, isLoading } = useRecommendedResources(activeCourseId, messages);`. Clean up any unneeded imports and suppress-linter tags.

---

### Task 3: Refactor `ChatContext` for SWR Sessions
**Files:**
- Modify: `frontend/src/context/ChatContext.jsx`

- [ ] **Step 3.1: Integrate SWR for session list management**
  Refactor state/fetching of `sessions` to use `useSWR`. Hook `deleteSession` to run SWR `mutate` (optimistic update), and `onDone` (on stream success) to trigger revalidation if a new session is created.

---

### Task 4: Lint, Build, and Verify
**Files:**
- Run linters and tests to verify zero regressions.

- [ ] **Step 4.1: Run frontend linter and unit tests**
  Run: `cd frontend && npm run lint && npm run test:unit`
  Expected: No linting issues, all unit tests pass.

- [ ] **Step 4.2: Build frontend**
  Run: `cd frontend && npm run build`
  Expected: Successful bundle generation without compilation errors.
