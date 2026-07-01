---
name: agentscope-framework-audit
description: Audit EDUagent AgentScope 2.x implementations for pseudo-framework usage, fake integration, hand-written agent runtimes disguised as AgentScope, copied 1.x patterns, missing Agent/tool/middleware/workspace/session usage, unsafe product protocol leakage, and untested agent_service_v2 entrypoints.
---

# AgentScope Framework Audit

Use this skill to verify that an AgentScope 2.x implementation genuinely uses framework primitives instead of only naming them in docs or wrapping hand-written orchestration.

## Audit Goal

Prove one of these outcomes with file and line evidence:

- **Framework-native**: AgentScope owns the reasoning/acting loop and lifecycle boundaries.
- **Partially framework-native**: AgentScope is used, but important lifecycle pieces are still custom.
- **Pseudo-framework**: code mostly hand-rolls runtime, workflow, state, tools, streaming, or memory while using AgentScope names superficially.

Do not rely on intent, architecture prose, or imports alone. Inspect the code path that actually runs.

## Evidence To Collect First

Run local checks before judging. Use the target environment's Python executable when the repo has a venv.

```bash
python -c "import agentscope; print(getattr(agentscope, '__version__', 'unknown')); print(agentscope.__file__)"
python -c "import agentscope, pkgutil; print(sorted(m.name for m in pkgutil.iter_modules(agentscope.__path__)))"
python -c "import agentscope.agent as a; print([x for x in dir(a) if not x.startswith('_')])"
python -c "import agentscope.tool as t; print([x for x in dir(t) if not x.startswith('_')])"
python -c "import importlib.util; mods=['agentscope.middleware','agentscope.workspace','agentscope.service']; print({m: bool(importlib.util.find_spec(m)) for m in mods})"
rg "Agent\(|reply_stream|Toolkit|ToolGroup|FunctionTool|Middleware|RAGMiddleware|Mem0Middleware|Workspace|create_app|AgentEvent|Protocol" .
rg "while .*tool|for .*step|workflow|planner|manual|event_stream|StreamingResponse|data:" .
```

For repo audits, inspect tests and the actual app entrypoint. A framework-looking helper that is never called does not count.

## False Positives To Avoid

- `async for event in agent.reply_stream(...)` is expected streaming consumption, not hand-written orchestration.
- `json.loads()` is acceptable for trusted JSON from config, tests, persisted state, non-LLM APIs, or tool payloads. Flag only LLM free-text protocols built with regex/XML/string slicing/brace balancing.
- Normal filesystem reads/writes are acceptable for source files, migrations, static templates, and tests. Runtime user/session artifacts need workspace isolation.
- Project-specific RAG tools are acceptable when EDU-specific ACLs, KG filters, or source metadata justify them and they are registered as AgentScope tools with structured observations.
- Do not demand full Agent Service adoption when the design intentionally uses AgentScope building blocks behind an EDUagent service facade.

## Hard Red Flags

Treat these as likely pseudo-framework until disproven:

- A custom loop chooses tools, updates steps, calls LLM, and retries without verified AgentScope reply/reply_stream lifecycle usage.
- Tool calls are represented by project-specific dicts but not registered through verified AgentScope tool primitives or a project builder that registers them.
- Product SSE is generated from hand-written status strings instead of adapting AgentScope/runtime events.
- Workspace paths exist, but runtime artifacts bypass workspace/session isolation.
- Memory or RAG silently falls back to old custom code without evaluating AgentScope middleware or documenting EDU-specific reasons.
- AgentScope 1.x patterns such as old `ReActAgent` or pipeline code are copied into a 2.x implementation without verified compatibility.
- Public APIs expose raw AgentScope internals instead of a stable EDU protocol adapter.
- Tests assert only that an import exists, not that framework lifecycle objects drive the run.

## Required Architecture Checks

### 1. Runtime Ownership

Find the execution core. Prefer a version-verified shape like:

```python
agent = Agent(..., toolkit=toolkit, middlewares=middlewares)
async for event in agent.reply_stream(inputs):
    ...
```

Flag if the primary path uses a custom workflow runner that calls tools and LLMs directly.

### 2. Tooling

Verify tools are registered through AgentScope primitives available in the installed version, such as toolkit/tool base/function tool/tool group equivalents.

Placeholder tools are acceptable only if they are still shaped as framework tools or clearly isolated behind a builder that will register them as tools.

### 3. Planning

For planning behavior, verify planning tools or task-context equivalents are available to the agent in the installed version.

Flag frontend buttons, backend routes, or fixed workflow branches that select the plan for the agent. UI controls may provide natural-language hints; the agent should choose the route inside guardrails.

### 4. Memory And RAG

Prefer framework boundaries where they fit:

- AgentScope memory middleware or documented memory tools.
- AgentScope RAG middleware/service or documented RAG tools.
- Explicit disabled status when configuration is missing.

Project-specific EDU retrieval is valid when it preserves tool boundaries, ACLs, KG filters, source metadata, event visibility, and tests.

Flag silent fallback to old custom memory/RAG code.

### 5. Workspace And Session Boundary

Verify workspace/session separation:

- Workspace manager or project facade derives workspace from server-trusted user/course/session ids.
- Runtime artifacts and offloaded context are workspace/session scoped.
- Workspace stores files/offload/artifacts, not authoritative business records.
- Backend or product DB remains the authority for business entities unless a migration explicitly says otherwise.

### 6. Event And Protocol Boundary

Verify AgentScope/runtime events are adapted, not leaked or replaced:

- Input: verified AgentScope event/message/tool lifecycle objects or normalized runtime events derived from them.
- Adapter output: EDU events such as `workflow_started`, `tool_started`, `tool_completed`, `plan_updated`, `text_delta`, `workflow_completed`, and `workflow_failed`.
- Public API should not expose raw AgentScope objects.

### 7. Bounded Autonomy

Verify guardrails exist:

- max iterations, max steps, or verified equivalent
- tool allowlist / groups
- timeout or failure events
- permission / confirmation boundary for unsafe external actions
- tests for stop/failure behavior

## Severity Rubric

- **Critical**: main runtime is custom LLM/tool orchestration; AgentScope is cosmetic.
- **High**: AgentScope Agent is used, but tools, events, memory, workspace, or permissions bypass framework/project primitives on the main path.
- **Medium**: framework primitives are used, but boundaries are weak, untested, or not wired to the actual entrypoint.
- **Low**: naming, docs, or tests are unclear but main path is framework-native.

## Output Format

Report findings first:

```text
Verdict: Framework-native / Partially framework-native / Pseudo-framework

Findings:
- [Severity] file:line - issue. Evidence: exact code behavior. Why it matters. Required fix.

Positive evidence:
- file:line - framework primitive is correctly used on the actual run path.

Missing evidence:
- What could not be proven and what command/file would prove it.

Recommended next fixes:
1. Highest-impact change first.
2. Keep EDU product protocol and AgentScope internals separated.
```

## Review Discipline

- Cite concrete files and lines.
- Distinguish docs claims from executable code.
- Confirm tests exercise the real entrypoint.
- Do not call an implementation framework-native because it imports AgentScope.
- Do not demand full Agent Service adoption if the design intentionally uses AgentScope building blocks or an Agent Service-inspired facade.
- When API names are uncertain, verify via installed package introspection before calling them missing.
