# AIChat Workbench v2 Agent Service-inspired Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build AIChat v2 with an EDU FastAPI facade and an AgentScope Agent Service-inspired internal architecture: WorkbenchSession, RunBus, WorkspaceManager, AgentFactory, ProtocolAdapter, Plan tools, Mem0/RAG boundaries, and placeholder Toolkit.

**Architecture:** Frontend continues to call Backend only. Backend proxies AIChat turns to `agent_service_v2` `/agent/v2/workbench/chat`. `agent_service_v2` does not directly host AgentScope `create_app`; instead it borrows the official Agent Service resource model while keeping EDU's API and persistence boundaries.

**Tech Stack:** AgentScope 2.0.3 full extras, FastAPI, SSE, Pydantic v2, pytest, React/Vitest later.

---

## File Structure

### Agent Service v2

- Create: `agent_service_v2/src/agent_service_v2/main.py`
- Create: `agent_service_v2/src/agent_service_v2/api/workbench.py`
- Create: `agent_service_v2/src/agent_service_v2/schemas/workbench.py`
- Create: `agent_service_v2/src/agent_service_v2/session/workbench_session.py`
- Create: `agent_service_v2/src/agent_service_v2/session/run_bus.py`
- Create: `agent_service_v2/src/agent_service_v2/workspaces/workbench_workspace_manager.py`
- Create: `agent_service_v2/src/agent_service_v2/agents/workbench_factory.py`
- Create: `agent_service_v2/src/agent_service_v2/agents/prompts.py`
- Create: `agent_service_v2/src/agent_service_v2/tools/planning.py`
- Create: `agent_service_v2/src/agent_service_v2/tools/memory.py`
- Create: `agent_service_v2/src/agent_service_v2/tools/rag.py`
- Create: `agent_service_v2/src/agent_service_v2/tools/workbench_placeholders.py`
- Create: `agent_service_v2/src/agent_service_v2/runtime/edu_events.py`
- Create: `agent_service_v2/src/agent_service_v2/runtime/protocol_adapter.py`
- Create: `agent_service_v2/src/agent_service_v2/runtime/sse.py`

### Tests

- Create: `agent_service_v2/tests/test_run_bus.py`
- Create: `agent_service_v2/tests/test_workbench_workspace_manager.py`
- Create: `agent_service_v2/tests/test_protocol_adapter.py`
- Create: `agent_service_v2/tests/test_workbench_session.py`
- Create: `agent_service_v2/tests/test_workbench_api.py`
- Create: `agent_service_v2/tests/test_workbench_factory.py`
- Create: `agent_service_v2/tests/test_workbench_toolkit.py`

---

## Phase 0: Design Approval

- [ ] **Step 1: Confirm architecture choice**

Approved architecture:

```text
Scheme A: EDU FastAPI facade + AgentScope Agent Service-inspired internal architecture.
```

- [ ] **Step 2: Confirm non-goal**

Non-goal:

```text
Do not directly host AgentScope create_app as the main service in phase 1.
```

---

## Phase 1: RunBus And EDU Events

**Goal:** Build the event stream core before Agent execution.

**Files:**

- Create: `agent_service_v2/src/agent_service_v2/session/run_bus.py`
- Create: `agent_service_v2/src/agent_service_v2/runtime/edu_events.py`
- Test: `agent_service_v2/tests/test_run_bus.py`

- [ ] **Step 1: Write failing RunBus tests**

Cover:

```text
create_run returns run_id.
publish appends ordered events.
subscribe yields already buffered events.
complete closes stream.
failed run publishes workflow_failed.
```

Run:

```bash
cd agent_service_v2 && ./.venv/bin/pytest tests/test_run_bus.py -q
```

Expected:

```text
FAIL because RunBus does not exist.
```

- [ ] **Step 2: Implement EDU event schema**

Fields:

```text
type
run_id
conversation_id
seq
timestamp
agent
payload
```

- [ ] **Step 3: Implement in-memory WorkbenchRunBus**

Use a focused in-memory implementation. Do not introduce Redis in phase 1.

- [ ] **Step 4: Verify RunBus**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/pytest tests/test_run_bus.py -q
```

Expected:

```text
PASS
```

---

## Phase 2: WorkspaceManager

**Goal:** Borrow AgentScope WorkspaceManager semantics while using EDU-specific isolation keys.

**Files:**

- Create: `agent_service_v2/src/agent_service_v2/workspaces/workbench_workspace_manager.py`
- Test: `agent_service_v2/tests/test_workbench_workspace_manager.py`

- [ ] **Step 1: Write failing workspace manager tests**

Cover:

```text
workspace key uses user_id, course_id/global, conversation_id.
unsafe characters are sanitized.
manager returns LocalWorkspace.
different conversations do not share workdir.
workspace workdir stays under agent_service_v2/workspaces.
```

- [ ] **Step 2: Implement WorkbenchWorkspaceManager**

Use:

```python
from agentscope.workspace import LocalWorkspace
```

Do not trust frontend-provided paths.

- [ ] **Step 3: Verify workspace tests**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/pytest tests/test_workbench_workspace_manager.py -q
```

Expected:

```text
PASS
```

---

## Phase 3: ProtocolAdapter

**Goal:** Borrow ProtocolMiddleware semantics and map AgentScope events to EDU SSE events.

**Files:**

- Create: `agent_service_v2/src/agent_service_v2/runtime/protocol_adapter.py`
- Create: `agent_service_v2/src/agent_service_v2/runtime/sse.py`
- Test: `agent_service_v2/tests/test_protocol_adapter.py`

- [ ] **Step 1: Write failing adapter tests**

Cover mappings:

```text
ReplyStartEvent -> workflow_started
TextBlockDeltaEvent -> text_delta
ToolCallStartEvent -> tool_started
ToolResultEndEvent -> tool_completed
ReplyEndEvent -> workflow_completed
Exception or max-iter event -> workflow_failed
```

- [ ] **Step 2: Implement adapter using installed AgentScope event classes**

Use local introspection against `agentscope.event` before relying on class names.

- [ ] **Step 3: Implement SSE serializer**

Output:

```text
data: {"type":"text_delta",...}

```

- [ ] **Step 4: Verify adapter**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/pytest tests/test_protocol_adapter.py -q
```

Expected:

```text
PASS
```

---

## Phase 4: AgentFactory And Toolkit

**Goal:** Build an AgentScope Agent with Plan ToolGroup, memory/RAG boundaries, placeholder AIChat tools, ContextConfig, ReActConfig, and workspace offloader.

**Files:**

- Create: `agent_service_v2/src/agent_service_v2/agents/workbench_factory.py`
- Create: `agent_service_v2/src/agent_service_v2/agents/prompts.py`
- Create: `agent_service_v2/src/agent_service_v2/tools/planning.py`
- Create: `agent_service_v2/src/agent_service_v2/tools/memory.py`
- Create: `agent_service_v2/src/agent_service_v2/tools/rag.py`
- Create: `agent_service_v2/src/agent_service_v2/tools/workbench_placeholders.py`
- Test: `agent_service_v2/tests/test_workbench_factory.py`
- Test: `agent_service_v2/tests/test_workbench_toolkit.py`

- [ ] **Step 1: Write toolkit tests**

Expected groups:

```text
planning
memory
rag
learning_state
artifact
review
```

Planning group must contain:

```text
TaskCreate
TaskGet
TaskList
TaskUpdate
```

- [ ] **Step 2: Implement planning ToolGroup**

Use AgentScope plan tools:

```python
from agentscope.tool import TaskCreate, TaskGet, TaskList, TaskUpdate
```

- [ ] **Step 3: Implement placeholder tools**

Tools:

```text
read_learning_state
draft_study_artifact
review_grounding
```

They return structured observations with `status="placeholder"`.

- [ ] **Step 4: Implement memory/RAG boundaries**

Use:

```python
from agentscope.middleware import Mem0Middleware, RAGMiddleware
```

If config is missing, return explicit disabled status. Do not import old `agent_service`.

- [ ] **Step 5: Implement AgentFactory**

Factory creates `Agent` with:

```text
toolkit
middlewares
ContextConfig
ReActConfig
workspace offloader
```

If model config is missing, return configuration error events through session/run handling.

- [ ] **Step 6: Verify factory/toolkit**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/pytest tests/test_workbench_factory.py tests/test_workbench_toolkit.py -q
```

Expected:

```text
PASS
```

---

## Phase 5: WorkbenchSession

**Goal:** Orchestrate one AIChat run without putting business logic in API.

**Files:**

- Create: `agent_service_v2/src/agent_service_v2/session/workbench_session.py`
- Test: `agent_service_v2/tests/test_workbench_session.py`

- [ ] **Step 1: Write session tests**

Cover:

```text
session creates run_id.
session resolves workspace.
session builds agent via factory.
session streams AgentScope events through protocol adapter.
session publishes events to RunBus.
session never imports old agent_service.
```

- [ ] **Step 2: Implement WorkbenchSession**

Responsibilities:

```text
validate request context
create run
resolve workspace
create agent
run reply_stream
adapt events
publish to run bus
```

- [ ] **Step 3: Verify session tests**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/pytest tests/test_workbench_session.py -q
```

Expected:

```text
PASS
```

---

## Phase 6: Workbench API

**Goal:** Expose `/agent/v2/workbench/chat` as EDU facade over WorkbenchSession.

**Files:**

- Create: `agent_service_v2/src/agent_service_v2/main.py`
- Create: `agent_service_v2/src/agent_service_v2/api/workbench.py`
- Create: `agent_service_v2/src/agent_service_v2/schemas/workbench.py`
- Test: `agent_service_v2/tests/test_workbench_api.py`

- [ ] **Step 1: Write API tests**

Cover:

```text
POST /agent/v2/workbench/chat returns text/event-stream.
API creates WorkbenchSession run.
API streams RunBus events.
Missing model emits workflow_failed instead of calling old service.
```

- [ ] **Step 2: Implement schemas**

Request fields:

```text
user_id
conversation_id
message
scope
course_id
context
```

- [ ] **Step 3: Implement route**

Route only:

```text
parse request
delegate to WorkbenchSession
return SSE stream
```

- [ ] **Step 4: Verify API**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/pytest tests/test_workbench_api.py -q
```

Expected:

```text
PASS
```

---

## Phase 7: Backend And Frontend Integration

Defer until Agent v2 internal architecture passes tests.

Backend later:

- `backend/app/services/agent_client.py`
- `backend/app/api/v1/tutoring.py`
- `backend/app/services/tutoring_stream_adapter.py`

Frontend later:

- `frontend/src/api/services/chat.js`
- `frontend/src/context/ChatContext.jsx`
- `frontend/src/components/chat/ToolCallCard.jsx`
- `frontend/src/components/workspace/AgentWorkspace.jsx`

---

## Verification Checklist

- [ ] No direct `create_app` host in phase 1.
- [ ] AgentScope Agent is the only execution core.
- [ ] Agent Service concepts are represented: Session, MessageBus-like RunBus, WorkspaceManager, ProtocolAdapter.
- [ ] Backend/Frontend contracts remain stable.
- [ ] Old `agent_service/` is not used.

