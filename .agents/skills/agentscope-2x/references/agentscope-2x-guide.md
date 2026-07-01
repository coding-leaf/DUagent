# AgentScope 2.x Guide

## Scope

This reference is for AgentScope 2.x design work in EDUagent. AgentScope 2.x is a breaking-change line from 1.x, so verify the installed version and current docs before writing imports or method calls.

API names in this guide are candidate primitives from AgentScope 2.x docs or prior local usage. Treat them as version-verified only after checking the installed package or official docs for the target environment.

## Current Docs And Introspection

Before writing AgentScope 2.x code, look up current official docs for the exact version being used. Prefer local package introspection when implementing against an installed environment.

Useful introspection pattern:

```python
import inspect
import importlib.util
import agentscope
import agentscope.agent as agent
import agentscope.tool as tool

print(getattr(agentscope, "__version__", "unknown"))
print(agentscope.__file__)
print([name for name in dir(agent) if not name.startswith("_")])
print([name for name in dir(tool) if not name.startswith("_")])
print({m: bool(importlib.util.find_spec(m)) for m in [
    "agentscope.middleware",
    "agentscope.workspace",
    "agentscope.service",
]})

# For candidate APIs:
print(inspect.signature(agent.Agent))
```

Check these documentation areas when available:

- Agent building block: Agent, streaming replies, events, context, state.
- Tool building block: Python tools, MCP tools, tool groups, permission, external execution.
- Middleware building block: model calls, acting, tool lists, context compression, prompt hooks.
- Agent Service: sessions, SSE streams, replay, background tasks, workspaces, protocol adaptation.
- Agent Team: leader/worker agents, team creation, inter-agent coordination.
- Tracing and observability.

If docs are unreachable, use local package introspection and mark unverified API details as assumptions. Do not turn remembered examples into code.

## Core Mental Model

Use AgentScope as the agent runtime, not just an LLM wrapper.

The EDU product owns:

- public HTTP/SSE/API contracts
- domain tool implementations
- persistence and authorization
- UI event mapping
- guardrail policy

AgentScope owns or should strongly influence:

- reasoning/acting loop
- tool invocation lifecycle
- model calls
- event stream
- tracing/middleware hooks
- agent/team coordination

State boundary:

- `Agent` is the reasoning/acting engine.
- In service deployments, sessions are the unit of runtime state.
- Agents are reusable identity/runtime templates unless the verified version documents a different lifecycle.
- Sessions own context, transcript, in-flight reply, permission context, and model binding.

## Capability Map

### Agent

Use Agent as the unit that receives a user message, reasons over context, selects tools, observes tool results, and produces final output. Prefer framework streaming APIs for interactive products.

Candidate core interfaces to verify:

- `reply(inputs)`: run the loop and return the final message.
- `reply_stream(inputs)`: yield event objects as they are produced.
- `observe(msgs)`: add messages to context without triggering reasoning.
- `compress_context(context_config)`: compress context when needed.

Design checklist:

- system prompt / instruction source
- model configuration
- allowed tools/tool groups
- context and memory inputs
- max iterations or equivalent stopping constraints
- output mode: text, structured output, events, artifacts
- failure behavior

### Tools

Represent every external or domain capability as a typed tool:

- retrieve course knowledge
- retrieve user memory
- read learner profile
- analyze weak points
- recommend resources
- draft study plan
- generate quiz preview
- generate lesson artifact
- create Mermaid/diagram artifact
- run critic or grounding check

Tool rules:

- One capability per tool.
- Inputs and outputs should be schema-like and stable.
- Return observations, not UI strings.
- Keep side effects explicit.
- Wrap unsafe tools with permission or policy checks.

Candidate tool primitives to verify before use:

- `ToolBase` for custom tools.
- `FunctionTool` for wrapping Python functions.
- Built-in tools such as `Bash`, `Read`, `Write`, `Edit`, `Grep`, and `Glob` where the installed package provides them and permissions allow them.
- `Toolkit` for assembling tools, MCP clients, skills, and tool groups.
- `ToolGroup` and tool-reset mechanisms where supported.
- `TaskCreate`, `TaskGet`, `TaskList`, and `TaskUpdate` for planning where supported.
- `ToolMiddlewareBase` for per-tool logging, metrics, retry, and other execution-local concerns.

### MCP

Use MCP when a capability is external, reusable, or tool-server-shaped. Do not use MCP just to call local helper functions.

Good MCP candidates:

- file/workspace tools in a sandbox
- browser/search tools
- remote code execution tools
- shared institutional knowledge tools

### Middleware

Use middleware to observe or modify agent lifecycle behavior without mixing tracing into business tools.

Typical uses:

- emit product trace events
- collect model-call metadata
- enforce prompt/policy additions
- filter or annotate tools
- compress context
- measure latency/cost
- inject guardrail checks

Candidate agent-level middleware hook positions to verify:

- `on_reply`
- `on_reasoning`
- `on_acting`
- `on_model_call`
- `on_compress_context`
- `on_system_prompt`
- `list_tools`

Candidate built-in middleware to evaluate before hand-rolling equivalent behavior:

- tracing middleware
- reply-budget middleware
- RAG middleware
- memory middleware such as Mem0 integration
- TTS or multimodal middleware where relevant

### Tracing

Use tracing for debugging and audit. Do not treat logs as the product protocol. Convert trace/runtime events into stable product events when the UI depends on them.

### Sessions And Workspace

Use session/workspace patterns when a product needs long-lived sessions, replayable event streams, background tasks, or workspace state.

For AI Workbench:

- session maps to conversation/workbench run
- workspace stores artifacts and intermediate files
- event stream maps to frontend SSE
- replay supports history inspection

If EDUagent does not adopt the full Agent Service resource model, still borrow the session-stream shape and isolate product protocol conversion in an adapter.

Candidate workspace implementations to verify:

- local workspace
- Docker workspace
- E2B workspace
- workspace manager or service facade for multi-tenant mapping

Runtime user/session artifacts must be workspace-isolated. Ordinary source files, migrations, static templates, and test fixtures may use normal filesystem APIs.

### Agent Team

Use teams only when roles add real value:

- planner
- researcher/retriever
- tutor/explainer
- resource recommender
- quiz drafter
- critic/grounding reviewer
- artifact composer

Avoid making a team when a single Agent with tools is enough.

Candidate team primitives to verify:

- leader/user-facing agent session
- worker sessions with separate state and workspace binding
- team coordination tools such as `TeamCreate`, `AgentCreate`, `TeamSay`, and `TeamDelete`
- sub-agent templates where worker roles need different prompts, permissions, context config, or seeded task context

## Event Adapter Pattern

Do not expose raw AgentScope events directly to frontend or backend contracts. Add an adapter layer:

```text
AgentScope event
  -> RuntimeEvent(normalized)
  -> EDU SSE event
```

EDU SSE event vocabulary includes:

- `workflow_started`
- `step_started`
- `step_completed`
- `tool_started`
- `tool_completed`
- `tool_failed`
- `source_refs`
- `artifact_created`
- `critic_completed`
- `plan_updated`
- `text_delta`
- `workflow_completed`
- `workflow_failed`

Each event should include the stable fields required by the current EDU v2 protocol, such as run/session ids, sequence, timestamp, type, and payload.

Candidate AgentScope events to map from, after verification:

- reply start/end events -> run/workflow start and completion
- text block start/delta/end events -> text streaming
- tool call start/delta/end events -> requested tool call construction
- tool result start/delta/end events -> tool observation/result streaming
- model call start/end events -> trace data
- max-iteration events -> bounded-autonomy stop/failure
- user-confirmation events -> permission or human-in-the-loop state
- external-execution events -> pause/resume for external tools

EDU-specific events such as `critic_completed`, `artifact_created`, `plan_updated`, and `source_refs` are product events. They must be produced by EDU tools, middleware, or adapters; they are not assumed to be built-in AgentScope event types.

## Migration From Hand-Written Agent Code

When replacing old hand-written flows:

1. Keep the old service runnable until the new route is verified.
2. Create a new runtime boundary instead of mutating old modules in place.
3. Define the v2 event protocol before implementing tools.
4. Port business capabilities as tools, not if/else workflow branches.
5. Use AgentScope streaming/events as the source of truth.
6. Add an adapter for EDU SSE.
7. Write tests against the product event stream, not private implementation calls.

## AI Workbench Pattern

For an AI workbench/chat product, the first-class outcome is an observable agent run:

```text
User message
  -> Agent receives goal
  -> Agent selects tools
  -> tools return observations
  -> Agent creates text and artifacts
  -> critic validates grounding/safety
  -> event adapter streams UI-ready events
```

Frontend controls should not hard-code workflow intent. They may provide natural-language prompts or hints, but the agent should decide the route within a bounded toolset.

### RAG And Memory

Evaluate official RAG/memory middleware where it fits, but do not force it when EDU-specific ACLs, course KG constraints, or source metadata require project-specific retrieval tools.

Project-specific retrieval tools are valid when they preserve AgentScope boundaries: typed tool registration, structured observations, tenant/course filters, event visibility, and tests.

### EDUagent AI Workbench v2

Expected project shape:

```text
agent_service_v2/
  api/                 # thin FastAPI/SSE shell
  runtime/             # AgentScope runtime factory, event normalization
  agents/              # workbench agents or agent team definitions
  tools/               # EDU domain tools
  middleware/          # tracing, guardrails, event capture
  schemas/             # v2 request/event schemas
  tests/               # tool, runtime, adapter, integration tests
```

External protocol:

- Use `/agent/v2/...`.
- Do not preserve `/agent/v1/...` event shapes.
- Keep Backend adaptation thin and separate from old v1 adapters.

First chain:

```text
POST /agent/v2/workbench/chat
  -> AgentScope workbench agent receives natural-language goal
  -> agent chooses tools dynamically
  -> adapter emits EDU SSE v2 events
  -> frontend AIChat renders trace, text, plans, sources, critic result, artifacts
```

Do not design a fixed frontend-intent workflow such as `intent=weak_plan`. If such a field exists for UX reasons, treat it as a hint in the user message or metadata, not as a branch selector that bypasses agent reasoning.

## Guardrails

Bound autonomy with:

- max steps or max iterations
- tool allowlist
- timeout
- structured tool inputs
- permission checks
- critic/grounding review
- fallback events
- replayable trace

Do not equate autonomy with unlimited tool access.

Use the verified permission system for tool execution boundaries. Custom tools should implement or wrap permission checks. Filesystem/workspace tools should honor read-only checks and dangerous-path protections.

## Testing Strategy

Test at four levels:

1. Tool unit tests: schema, success, failure, timeout.
2. Runtime event tests: a fake model/tool sequence emits expected normalized events.
3. SSE adapter tests: normalized events become stable product events.
4. Integration smoke: one real or mocked agent run reaches `workflow_completed` and creates expected artifacts.

Avoid tests that assert private AgentScope internals unless the project intentionally pins a specific version and API.

## Anti-Patterns

- Hand-writing a ReAct loop while using AgentScope only as an LLM wrapper.
- Exposing raw AgentScope event objects as public SSE contracts.
- Making frontend buttons choose concrete workflows and calling that an agent.
- Migrating every old Agent Service endpoint before one v2 chain works.
- Treating agent autonomy as unrestricted tools, unlimited steps, or unreviewed side effects.
- Coding against AgentScope 2.x method names that were not verified against docs or the installed package.
