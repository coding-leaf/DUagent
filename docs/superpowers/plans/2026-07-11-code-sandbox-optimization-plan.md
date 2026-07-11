# Code Sandbox Design & Prompt Optimization Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Modify the backend system prompt template and refactor the frontend `CodeSandboxCard` component to render markdown descriptions, show clean public test case grids, support dropdown language selectors for free sandbox mode, and verify all changes through Unit Tests.

---

### Task 1: Backend System Prompt Update

**Files:**
- Modify: `agent_service_v2/src/agent_service_v2/agents/prompts.py`

- [ ] **Step 1: Modify WORKBENCH_SYSTEM_PROMPT in prompts.py**
  Add strict instruction formatting rules for the `statement` field of `create_validated_personal_code_problem` tool calling.

- [ ] **Step 2: Run pytest to ensure backend tests still pass**
  Run: `cd agent_service_v2 && ./.venv/bin/pytest tests`
  Expected: PASS

- [ ] **Step 3: Commit changes**
  Run: `git add agent_service_v2/src/agent_service_v2/agents/prompts.py && git commit -m "feat: enforce structured statement markdown format in agent system prompt"`

---

### Task 2: Frontend Refactor for CodeSandboxCard

**Files:**
- Modify: `frontend/src/components/workspace/plugins/codeSandbox/CodeSandboxCard.jsx`
- Modify: `frontend/src/components/workspace/plugins/CodeSandboxCard.test.jsx`

- [ ] **Step 1: Write/Update unit test in CodeSandboxCard.test.jsx**
  Update the tests to render with the new card and check that the language selector works, and the markdown content renders properly.

- [ ] **Step 2: Run tests to verify they fail**
  Run: `cd frontend && npm run test:unit -- src/components/workspace/plugins/CodeSandboxCard.test.jsx`
  Expected: FAIL

- [ ] **Step 3: Refactor CodeSandboxCard.jsx**
  - Import `MarkdownViewer` from `../../../common/MarkdownViewer`
  - Render `questionText` inside `MarkdownViewer`
  - Implement `LanguageSelector` dropdown component for free sandboxes
  - Implement `PublicTestCases` grid card rendering component
  - Limit rendering function lines to comply with `AGENTS.md` (no single function > 50 lines)

- [ ] **Step 4: Run tests to verify they pass**
  Run: `cd frontend && npm run test:unit -- src/components/workspace/plugins/CodeSandboxCard.test.jsx`
  Expected: PASS

- [ ] **Step 5: Run full frontend test and build check**
  Run: `cd frontend && npm run test:unit && npm run build`
  Expected: PASS

- [ ] **Step 6: Commit changes**
  Run: `git add frontend/src/components/workspace/plugins/codeSandbox/CodeSandboxCard.jsx frontend/src/components/workspace/plugins/CodeSandboxCard.test.jsx && git commit -m "feat: refactor CodeSandboxCard with Markdown description, test cases grid and language selection dropdown"`
