# Canvas Card Close & Restore Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a close (✕) button to tabs in the Agent Workspace, manage hidden tabs in ChatContext, and provide a "找回已关闭" dropdown to restore them, while ensuring correct fallback/dynamic card titles and icons from both frontend and backend.

**Architecture:** Extend `ChatContext` with a state `hiddenArtifactIds` and toggle handlers. Update `AgentWorkspace` to filter tabs. Modify `WorkspaceTabs` to render the close buttons, the recovery dropdown, and correct icons. Align backend artifact schema to serialize `title` in SSE.

**Tech Stack:** React, FastAPI, AgentScope 2.x, Vitest, pytest.

---

### Task 1: Backend Artifact Title Serialization

**Files:**
- Modify: `agent_service_v2/src/agent_service_v2/artifacts/schemas.py:46-53`
- Modify: `agent_service_v2/tests/test_protocol_adapter.py:198-204`

- [ ] **Step 1: Write/Update the test verifying title serialization**
  In `agent_service_v2/tests/test_protocol_adapter.py`, update `test_protocol_adapter_emits_artifact_after_artifact_tool_success` to verify `title` is in the event's `payload["artifact"]`.
  ```python
  # In agent_service_v2/tests/test_protocol_adapter.py
  # Modify lines 198-204:
  assert events[0].type == EduEventType.ARTIFACT_CREATED
  assert events[0].payload == {
      "artifact": {
          "id": "artifact_001_functions",
          "type": "CodeSandboxCard",
          "title": "C语言函数核心概念",
          "props": {
              "problem_id": "prob_1",
              "language": "c"
          }
      }
  }
  ```

- [ ] **Step 2: Run tests to verify it fails**
  Run: `cd agent_service_v2 && ./.venv/bin/pytest tests/test_protocol_adapter.py -k test_protocol_adapter_emits_artifact_after_artifact_tool_success`
  Expected: FAIL (assertion error showing missing 'title')

- [ ] **Step 3: Modify backend schemas.py to serialize title**
  Update `PublishedArtifact.to_event_payload` in `agent_service_v2/src/agent_service_v2/artifacts/schemas.py`.
  ```python
  # In agent_service_v2/src/agent_service_v2/artifacts/schemas.py:46-53
  def to_event_payload(self) -> dict[str, Any]:
      return {
          "artifact": {
              "id": self.id,
              "type": self.type,
              "title": self.title,
              "props": self.props,
          }
      }
  ```

- [ ] **Step 4: Run test to verify it passes**
  Run: `cd agent_service_v2 && ./.venv/bin/pytest tests/test_protocol_adapter.py`
  Expected: PASS

- [ ] **Step 5: Commit changes**
  Run:
  ```bash
  git add agent_service_v2/src/agent_service_v2/artifacts/schemas.py agent_service_v2/tests/test_protocol_adapter.py
  git commit -m "feat: backend support serializing artifact title in event payload"
  ```

---

### Task 2: Frontend Artifact Parser for Title

**Files:**
- Modify: `frontend/src/utils/chatStreamEvents.js:80-89`
- Modify: `frontend/src/context/ChatContext.jsx:34-40`

- [ ] **Step 1: Update normalizeArtifact to parse title**
  In `frontend/src/utils/chatStreamEvents.js`, update `normalizeArtifact` to extract `title` from `event.payload.artifact`.
  ```javascript
  // In frontend/src/utils/chatStreamEvents.js:80-89
  export const normalizeArtifact = (event) => {
    const artifact = event.payload?.artifact;
    if (!artifact || !artifact.type) return null;
    return {
      id: artifact.id || `artifact-${crypto.randomUUID()}`,
      type: artifact.type,
      title: artifact.title || null,
      props: artifact.props || {},
      timestamp: event.timestamp || new Date().toISOString()
    };
  };
  ```

- [ ] **Step 2: Update artifactsFromMessages to preserve title**
  In `frontend/src/context/ChatContext.jsx`, update the `artifactsFromMessages` helper to carry `title` over.
  ```javascript
  // In frontend/src/context/ChatContext.jsx:34-40
  const id = artifact.id || `artifact-${crypto.randomUUID()}`;
  artifactsMap.set(id, {
    id,
    type: artifact.type,
    title: artifact.title || null,
    props: artifact.props || {},
    timestamp: artifact.timestamp || message.timestamp || new Date().toISOString()
  });
  ```

- [ ] **Step 3: Run Vitest unit tests**
  Run: `cd frontend && npm run test:unit`
  Expected: All existing frontend tests pass.

- [ ] **Step 4: Commit changes**
  Run:
  ```bash
  git add frontend/src/utils/chatStreamEvents.js frontend/src/context/ChatContext.jsx
  git commit -m "feat: parse and preserve artifact title on frontend side"
  ```

---

### Task 3: ChatContext Hidden Artifact States

**Files:**
- Modify: `frontend/src/context/ChatContext.jsx`
- Modify: `frontend/src/context/ChatContext.test.jsx`

- [ ] **Step 1: Write failing tests in ChatContext.test.jsx**
  Add unit tests verifying `hiddenArtifactIds` starts empty, hides an artifact, restores it, and resets when session changes.
  ```javascript
  // In frontend/src/context/ChatContext.test.jsx
  test('handles hiding and restoring artifacts', async () => {
    getHistoryMock.mockResolvedValue({
      code: 200,
      data: {
        messages: [
          {
            role: 'assistant',
            content: '已生成补弱计划。',
            meta: {
              artifacts: [
                {
                  id: 'artifact-plan',
                  type: 'Markdown',
                  props: { title: '补弱计划', content: '# 补弱计划' }
                }
              ]
            }
          }
        ]
      }
    });

    renderWithProviders(<StreamConsumer />);

    await waitFor(() => {
      expect(screen.getByTestId('artifact-count').textContent).toBe('1');
    });
    expect(screen.getByTestId('active-artifact-id').textContent).toBe('artifact-plan');
    expect(screen.getByTestId('hidden-count').textContent).toBe('0');

    await act(async () => {
      screen.getByTestId('hide-artifact').click();
    });
    expect(screen.getByTestId('hidden-count').textContent).toBe('1');
    expect(screen.getByTestId('active-artifact-id').textContent).toBe('');

    await act(async () => {
      screen.getByTestId('restore-artifact').click();
    });
    expect(screen.getByTestId('hidden-count').textContent).toBe('0');
    expect(screen.getByTestId('active-artifact-id').textContent).toBe('artifact-plan');
  });
  ```

- [ ] **Step 2: Run tests to verify failure**
  Run: `cd frontend && npm run test:unit -- src/context/ChatContext.test.jsx`
  Expected: FAIL on the new test.

- [ ] **Step 3: Implement hidden state logic in ChatContext.jsx**
  Add `hiddenArtifactIds` state, export `hideArtifact(id)` and `restoreArtifact(id)`, and ensure they clear in course/session change `useEffect` blocks.
  ```javascript
  // In frontend/src/context/ChatContext.jsx:
  const [hiddenArtifactIds, setHiddenArtifactIds] = useState([]);

  const hideArtifact = (id) => {
    setHiddenArtifactIds(prev => [...prev, id]);
    // Auto switch activeArtifactId if we hid the active one
    setWorkspaceArtifacts(currentArtifacts => {
      const visible = currentArtifacts.filter(a => a.id !== id && !hiddenArtifactIds.includes(a.id));
      if (activeArtifactId === id) {
        setActiveArtifactId(visible.length > 0 ? visible[visible.length - 1].id : null);
      }
      return currentArtifacts;
    });
  };

  const restoreArtifact = (id) => {
    setHiddenArtifactIds(prev => prev.filter(i => i !== id));
    setActiveArtifactId(id);
  };
  ```
  Also update cleanup effects to clear `hiddenArtifactIds`.

- [ ] **Step 4: Run tests to verify they pass**
  Run: `cd frontend && npm run test:unit -- src/context/ChatContext.test.jsx`
  Expected: PASS

- [ ] **Step 5: Commit changes**
  Run:
  ```bash
  git add frontend/src/context/ChatContext.jsx frontend/src/context/ChatContext.test.jsx
  git commit -m "feat: implement hide and restore artifact states in ChatContext"
  ```

---

### Task 4: AgentWorkspace Filtering & Empty State

**Files:**
- Modify: `frontend/src/components/workspace/AgentWorkspace.jsx`
- Modify: `frontend/src/components/workspace/AgentWorkspace.test.jsx`

- [ ] **Step 1: Write test in AgentWorkspace.test.jsx**
  Add a test verifying that `AgentWorkspace` filters out hidden artifacts and renders the empty state if all artifacts are hidden.
  ```javascript
  // In frontend/src/components/workspace/AgentWorkspace.test.jsx
  test('filters hidden artifacts and shows empty state if all are hidden', () => {
    useChat.mockReturnValue({
      workspaceArtifacts: [
        { id: '1', type: 'QuizCard', props: { question: 'What is React?' } },
      ],
      hiddenArtifactIds: ['1'],
    });
    render(<AgentWorkspace />);
    expect(screen.getByText(/暂无生成产物/)).toBeDefined();
  });
  ```

- [ ] **Step 2: Run tests to verify failure**
  Run: `cd frontend && npm run test:unit -- src/components/workspace/AgentWorkspace.test.jsx`
  Expected: FAIL

- [ ] **Step 3: Implement filtering in AgentWorkspace.jsx**
  Filter `workspaceArtifacts` using `hiddenArtifactIds` before determining `activeArtifact` and rendering the tabs/components.
  ```javascript
  // In frontend/src/components/workspace/AgentWorkspace.jsx
  const { workspaceArtifacts, activeArtifactId, setActiveArtifactId, hiddenArtifactIds, hideArtifact, restoreArtifact } = useChat();

  const visibleArtifacts = workspaceArtifacts.filter(a => !hiddenArtifactIds.includes(a.id));
  const activeArtifact = visibleArtifacts.find(a => a.id === activeArtifactId) || visibleArtifacts[0];
  ```

- [ ] **Step 4: Run tests to verify they pass**
  Run: `cd frontend && npm run test:unit -- src/components/workspace/AgentWorkspace.test.jsx`
  Expected: PASS

- [ ] **Step 5: Commit changes**
  Run:
  ```bash
  git add frontend/src/components/workspace/AgentWorkspace.jsx frontend/src/components/workspace/AgentWorkspace.test.jsx
  git commit -m "feat: filter out hidden artifacts in AgentWorkspace"
  ```

---

### Task 5: WorkspaceTabs Rendering & Icon fallbacks

**Files:**
- Modify: `frontend/src/components/workspace/WorkspaceTabs.jsx`
- Modify: `frontend/src/components/Icon.jsx`

- [ ] **Step 1: Register insert_drive_file in Icon.jsx**
  In `frontend/src/components/Icon.jsx`, map `'insert_drive_file'` to `'FileText'`.
  ```javascript
  // In frontend/src/components/Icon.jsx:108
  'insert_drive_file': 'FileText',
  ```

- [ ] **Step 2: Redesign WorkspaceTabs to support title mapping, close buttons and restore dropdown**
  In `frontend/src/components/workspace/WorkspaceTabs.jsx`, implement the card properties metadata lookup:
  ```javascript
  const pluginMeta = {
    QuizCard: { title: '随堂测试', icon: 'quiz' },
    Mermaid: { title: '流程拓扑图', icon: 'account_tree' },
    Markdown: { title: '讲解备忘录', icon: 'description' },
    StudyPlanCard: { title: '今日学习计划', icon: 'calendar_today' },
    WeakPointsCard: { title: '薄弱知识点', icon: 'insights' },
    PathRecommendationCard: { title: '学习路径推荐', icon: 'route' },
    CodeSandboxCard: { title: '代码实操练习', icon: 'code' }
  };
  ```
  Add a close `✕` button to each tab that calls `onClose(art.id)`. Add a "找回已关闭 (N)" button on the right side if there are hidden artifacts, which triggers a dropdown listing them.

- [ ] **Step 3: Run all frontend unit tests**
  Run: `cd frontend && npm run test:unit`
  Expected: PASS

- [ ] **Step 4: Verify frontend build**
  Run: `cd frontend && npm run build`
  Expected: Build succeeds without errors.

- [ ] **Step 5: Commit changes**
  Run:
  ```bash
  git add frontend/src/components/workspace/WorkspaceTabs.jsx frontend/src/components/Icon.jsx
  git commit -m "feat: render close buttons, fallback titles/icons and restore dropdown in WorkspaceTabs"
  ```
