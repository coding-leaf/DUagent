# AIChat AgentScope-native Workbench v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build AIChat as an AgentScope 2.0.3 native workbench, centered on Workspace, Agent, Plan tools, Mem0Middleware, ContextConfig, RAG boundary, placeholder Toolkit, and AgentEvent-to-EDU-SSE adaptation.

**Architecture:** Frontend still calls Backend only. Backend proxies AIChat turns to `agent_service_v2` `/agent/v2/workbench/chat`. `agent_service_v2` creates an isolated AgentScope workspace per user/course/conversation, constructs an AgentScope Agent with Plan tools, memory middleware, context config, RAG adapter boundary, and placeholder AIChat tools, then maps AgentScope stream events into EDU SSE v2. Old `agent_service/` stays in the repo but is ignored by this chain.

**Tech Stack:** AgentScope 2.0.3, Python 3.12, FastAPI, SSE, Pydantic v2, pytest, React, Vitest.

---

## File Structure

### Agent Service v2

- Create: `agent_service_v2/src/agent_service_v2/main.py`  
  FastAPI app entrypoint.
- Create: `agent_service_v2/src/agent_service_v2/api/workbench.py`  
  Thin `/agent/v2/workbench/chat` route.
- Create: `agent_service_v2/src/agent_service_v2/schemas/workbench.py`  
  Request, workspace, event, and placeholder observation schemas.
- Create: `agent_service_v2/src/agent_service_v2/workspaces/manager.py`  
  Creates safe `LocalWorkspace` instances from user/course/conversation identity.
- Create: `agent_service_v2/src/agent_service_v2/agents/workbench_factory.py`  
  Builds the AgentScope Agent from workspace, model, toolkit, middleware, and configs.
- Create: `agent_service_v2/src/agent_service_v2/agents/prompts.py`  
  AIChat workbench system prompt.
- Create: `agent_service_v2/src/agent_service_v2/tools/planning.py`  
  Builds AgentScope Plan tools.
- Create: `agent_service_v2/src/agent_service_v2/tools/memory.py`  
  Builds optional Mem0Middleware and exposes memory tools.
- Create: `agent_service_v2/src/agent_service_v2/tools/rag.py`  
  AgentScope RAG service adapter boundary and placeholder retrieval tool.
- Create: `agent_service_v2/src/agent_service_v2/tools/workbench_placeholders.py`  
  Placeholder tools for learning state, artifact draft, and grounding review.
- Create: `agent_service_v2/src/agent_service_v2/runtime/events.py`  
  EDU event schema helpers and sequence counter.
- Create: `agent_service_v2/src/agent_service_v2/runtime/agent_event_adapter.py`  
  Maps AgentScope events and tool observations to EDU SSE v2 events.
- Create: `agent_service_v2/src/agent_service_v2/runtime/sse.py`  
  Serializes EDU events to SSE.

### Agent Service v2 Tests

- Create: `agent_service_v2/tests/test_workspace_manager.py`
- Create: `agent_service_v2/tests/test_workbench_factory.py`
- Create: `agent_service_v2/tests/test_plan_toolkit.py`
- Create: `agent_service_v2/tests/test_agent_event_adapter.py`
- Create: `agent_service_v2/tests/test_workbench_api.py`

### Later Backend / Frontend

- Modify later: `backend/app/api/v1/tutoring.py`
- Modify later: `backend/app/services/agent_client.py`
- Modify later: `backend/app/services/tutoring_stream_adapter.py`
- Modify later: `frontend/src/context/ChatContext.jsx`
- Modify later: `frontend/src/api/services/chat.js`

---

## Phase 0: Design Approval

- [ ] **Step 1: Review AgentScope-native design**

Review:

```text
docs/superpowers/specs/2026-06-30-aichat-workbench-v2-design.md
```

Expected approval:

```text
AgentScope Workspace / Agent / Plan / Mem0 / Context / RAG / Toolkit / Event Adapter are the core architecture.
```

- [ ] **Step 2: Confirm Toolkit scope**

Confirm:

```text
First implementation creates placeholder tools only. It does not port old agent_service business logic.
```

- [ ] **Step 3: Confirm old service boundary**

Confirm:

```text
Old agent_service/ remains on disk but is ignored by AIChat v2.
```

---

## Phase 1: Workspace Boundary

**Goal:** Every AIChat v2 request gets an isolated AgentScope `LocalWorkspace`.

**Files:**

- Create: `agent_service_v2/src/agent_service_v2/workspaces/manager.py`
- Create: `agent_service_v2/tests/test_workspace_manager.py`

- [ ] **Step 1: Write failing workspace tests**

Cover:

```text
workspace_id includes user_id, course_id/global, conversation_id.
unsafe path characters are sanitized.
different conversations produce different workspaces.
workspace manager returns LocalWorkspace.
```

Run:

```bash
cd agent_service_v2 && ./.venv/bin/pytest tests/test_workspace_manager.py -q
```

Expected:

```text
FAIL because workspace manager does not exist.
```

- [ ] **Step 2: Implement workspace manager**

Use AgentScope 2.0.3 `LocalWorkspace`:

```python
from agentscope.workspace import LocalWorkspace
```

Create workspaces under:

```text
agent_service_v2/workspaces/ai-chat/<safe_user>/<safe_course>/<safe_conversation>
```

- [ ] **Step 3: Verify workspace tests**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/pytest tests/test_workspace_manager.py -q
```

Expected:

```text
PASS
```

---

## Phase 2: Agent Factory With Context And Plan

**Goal:** Build an AgentScope `Agent` with workspace offloader, `ContextConfig`, `ReActConfig`, and Plan tools in the Toolkit.

**Files:**

- Create: `agent_service_v2/src/agent_service_v2/agents/workbench_factory.py`
- Create: `agent_service_v2/src/agent_service_v2/agents/prompts.py`
- Create: `agent_service_v2/src/agent_service_v2/tools/planning.py`
- Create: `agent_service_v2/tests/test_workbench_factory.py`
- Create: `agent_service_v2/tests/test_plan_toolkit.py`

- [ ] **Step 1: Write failing plan toolkit test**

Assert toolkit construction includes:

```text
TaskCreate
TaskGet
TaskList
TaskUpdate
```

Run:

```bash
cd agent_service_v2 && ./.venv/bin/pytest tests/test_plan_toolkit.py -q
```

Expected:

```text
FAIL because planning toolkit builder does not exist.
```

- [ ] **Step 2: Implement planning toolkit builder**

Use AgentScope classes:

```python
from agentscope.tool import TaskCreate, TaskGet, TaskList, TaskUpdate, Toolkit
```

Return a `Toolkit` containing the plan tools.

- [ ] **Step 3: Write failing agent factory test**

Assert:

```text
factory receives LocalWorkspace.
factory creates AgentScope Agent.
agent is configured with ContextConfig.
agent is configured with ReActConfig(max_iters bounded).
agent uses workspace as offloader.
agent toolkit contains plan tools.
```

- [ ] **Step 4: Implement agent factory**

Use introspection-confirmed AgentScope 2.0.3 API:

```python
from agentscope.agent import Agent, ContextConfig, ReActConfig
```

Model construction is isolated behind a provider function. If no model is configured, factory returns a clear configuration error rather than silently using the old service.

- [ ] **Step 5: Verify phase 2 tests**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/pytest tests/test_plan_toolkit.py tests/test_workbench_factory.py -q
```

Expected:

```text
PASS
```

---

## Phase 3: Memory And RAG Boundaries

**Goal:** Add AgentScope-native memory and RAG boundaries without copying old agent code.

**Files:**

- Create: `agent_service_v2/src/agent_service_v2/tools/memory.py`
- Create: `agent_service_v2/src/agent_service_v2/tools/rag.py`
- Create: `agent_service_v2/tests/test_memory_boundary.py`
- Create: `agent_service_v2/tests/test_rag_boundary.py`

- [ ] **Step 1: Write memory boundary tests**

Cover:

```text
Mem0Middleware builder accepts user_id.
When config is available, middleware is returned.
When config is missing, disabled status is returned explicitly.
No old agent_service memory module is imported.
```

- [ ] **Step 2: Implement memory boundary**

Use AgentScope:

```python
from agentscope.middleware import Mem0Middleware
```

The builder returns:

```text
MemoryBoundary(enabled=True, middleware=Mem0Middleware(...))
```

or:

```text
MemoryBoundary(enabled=False, reason="mem0_not_configured")
```

- [ ] **Step 3: Write RAG boundary tests**

Cover:

```text
RAG adapter exposes retrieve_course_context placeholder.
RAG adapter records backend mode as agentscope_rag.
RAG adapter does not import old agent_service retrieval modules.
```

- [ ] **Step 4: Implement RAG boundary**

Create `RagServiceAdapter` with a placeholder `retrieve_course_context` tool. It returns structured observation:

```json
{
  "query": "...",
  "course_id": "...",
  "source_refs": [],
  "status": "placeholder"
}
```

- [ ] **Step 5: Verify phase 3 tests**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/pytest tests/test_memory_boundary.py tests/test_rag_boundary.py -q
```

Expected:

```text
PASS
```

---

## Phase 4: Placeholder Toolkit

**Goal:** Provide stable tool names and observation schemas while leaving business logic as placeholders.

**Files:**

- Create: `agent_service_v2/src/agent_service_v2/tools/workbench_placeholders.py`
- Create: `agent_service_v2/tests/test_workbench_placeholder_tools.py`

- [ ] **Step 1: Write placeholder tool tests**

Cover tools:

```text
read_learning_state
draft_study_artifact
review_grounding
```

Expected observations:

```text
Each tool returns status="placeholder".
Each tool returns structured dict output.
No tool returns UI-only prose.
```

- [ ] **Step 2: Implement placeholder tools**

Implement placeholder functions and register them through AgentScope `FunctionTool` if constructor signature is verified. If `FunctionTool` constructor details are unclear, wrap the functions behind a toolkit builder and add introspection notes before implementation.

- [ ] **Step 3: Merge Toolkit parts**

Final Toolkit contains:

```text
Plan tools
Memory tools when enabled
RAG placeholder tool
Workbench placeholder tools
```

- [ ] **Step 4: Verify phase 4 tests**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/pytest tests/test_workbench_placeholder_tools.py tests/test_plan_toolkit.py -q
```

Expected:

```text
PASS
```

---

## Phase 5: AgentEvent To EDU SSE Adapter

**Goal:** Map AgentScope stream events to EDU SSE v2 without exposing raw AgentScope internals.

**Files:**

- Create: `agent_service_v2/src/agent_service_v2/runtime/events.py`
- Create: `agent_service_v2/src/agent_service_v2/runtime/agent_event_adapter.py`
- Create: `agent_service_v2/src/agent_service_v2/runtime/sse.py`
- Create: `agent_service_v2/tests/test_agent_event_adapter.py`

- [ ] **Step 1: Write adapter tests**

Cover mappings:

```text
reply start -> workflow_started
tool call start -> tool_started
tool result end -> tool_completed
text delta -> text_delta
reply end -> workflow_completed
exception/max-iter -> workflow_failed
```

- [ ] **Step 2: Implement EDU event schema**

Event fields:

```text
type
run_id
conversation_id
seq
timestamp
agent
payload
```

- [ ] **Step 3: Implement adapter**

Adapter accepts AgentScope event objects and emits EDU event dictionaries. Event class detection must be based on local introspection or stable class names from installed AgentScope 2.0.3.

- [ ] **Step 4: Implement SSE serializer**

Output format:

```text
data: {"type":"text_delta",...}

```

- [ ] **Step 5: Verify phase 5 tests**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/pytest tests/test_agent_event_adapter.py -q
```

Expected:

```text
PASS
```

---

## Phase 6: Workbench API

**Goal:** Expose `/agent/v2/workbench/chat` as a thin route over the AgentScope-native pipeline.

**Files:**

- Create: `agent_service_v2/src/agent_service_v2/main.py`
- Create: `agent_service_v2/src/agent_service_v2/api/workbench.py`
- Create: `agent_service_v2/src/agent_service_v2/schemas/workbench.py`
- Create: `agent_service_v2/tests/test_workbench_api.py`

- [ ] **Step 1: Write API tests**

Cover:

```text
POST /agent/v2/workbench/chat returns text/event-stream.
Request creates isolated workspace.
Request builds AgentScope Agent.
Missing model config returns workflow_failed event, not old service fallback.
```

- [ ] **Step 2: Implement request schema**

Fields:

```text
user_id
conversation_id
message
scope
course_id
context
```

- [ ] **Step 3: Implement route**

Route responsibilities:

```text
validate request
create workspace
build agent
run reply_stream
adapt AgentScope events to EDU SSE
return EventSourceResponse or StreamingResponse
```

No business logic belongs in the route.

- [ ] **Step 4: Verify API tests**

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

**Goal:** After AgentScope-native v2 is verified, switch AIChat proxy and frontend reducer to v2 events.

Backend files:

- `backend/app/api/v1/tutoring.py`
- `backend/app/services/agent_client.py`
- `backend/app/services/tutoring_stream_adapter.py`

Frontend files:

- `frontend/src/api/services/chat.js`
- `frontend/src/context/ChatContext.jsx`
- `frontend/src/components/chat/ToolCallCard.jsx`
- `frontend/src/components/workspace/AgentWorkspace.jsx`

- [ ] **Step 1: Backend proxy test**

Expected:

```text
Frontend-facing /api/v1/tutoring/chat remains unchanged.
Backend internally calls /agent/v2/workbench/chat.
Old /agent/v1/tutoring/chat is not used.
```

- [ ] **Step 2: Frontend reducer test**

Expected:

```text
text_delta updates assistant message.
tool_started/tool_completed update tool trace.
artifact_created updates workspace artifacts.
workflow_failed marks message error.
```

- [ ] **Step 3: End-to-end sample**

Prompt:

```text
我今天应该学什么？
```

Expected:

```text
AIChat creates isolated workspace.
Agent uses Plan tools.
Memory boundary is enabled or explicitly disabled.
RAG boundary emits placeholder source_refs.
Placeholder toolkit emits structured observations.
Frontend renders stream and tool trace.
```

---

## Verification Checklist

- [ ] Workspace isolation exists before any Agent run.
- [ ] AgentScope `Agent` is the central runtime.
- [ ] Plan tools are in the Toolkit.
- [ ] `Mem0Middleware` boundary is implemented.
- [ ] `ContextConfig` and bounded `ReActConfig` are configured.
- [ ] RAG is represented by AgentScope RAG adapter boundary.
- [ ] Business tools are placeholders only in the first implementation.
- [ ] EDU SSE is produced by AgentScope event adapter.
- [ ] Backend does not import `agent_service_v2`.
- [ ] Frontend does not call Agent Service directly.
- [ ] Old `agent_service/` is not used by AIChat v2.

