---
name: agentscope-2x
description: Build, review, or refactor EDUagent AgentScope 2.x agent runtimes, agent teams, streaming agents, tools, middleware, tracing, workspaces, and agent_service_v2 deployments. Use when designing AgentScope 2.x architecture, migrating hand-written workflows, mapping AgentScope events to EDU SSE/API protocols, or deciding how to use Agent, tools, middleware, sessions, workspaces, RAG, memory, permissions, and tracing.
---

# AgentScope 2.x

Use this skill to design or implement EDUagent AgentScope 2.x systems without falling back to hand-written pseudo-agent orchestration.

## Mandatory Checks

1. Verify the target AgentScope version before designing code.
   - For an installed environment, run Python introspection against that environment.
   - For a new or upgraded dependency, check current official AgentScope docs first.
   - If docs and installed package disagree, treat the installed package as implementation truth and document the mismatch.
2. Treat AgentScope 2.x as a breaking-change line from 1.x. Do not copy 1.x `ReActAgent` or pipeline patterns into 2.x work unless current docs or package introspection confirms compatibility.
3. Prefer framework primitives over hand-written agent runtimes:
   - Use Agent and streaming reply APIs for reasoning/acting loops.
   - Use tools/toolkits/tool groups for capabilities where the verified version supports them.
   - Use middleware and event streams for observability.
   - Use sessions/workspaces where deployment state matters.
4. Keep business protocols outside AgentScope internals. Build adapters from AgentScope events to stable EDU SSE/API contracts.
5. Do not invent AgentScope APIs. If a method, class, import path, or constructor argument is not verified in docs or by introspection, stop and verify before using it.

## EDUagent Rules

- Use `agent_service_v2/` as the AgentScope v2 runtime boundary; do not rewrite old `agent_service/` in place.
- Use `/agent/v2/...` contracts for v2 work. Do not preserve `/agent/v1/...` event shapes unless the user explicitly reverses that decision.
- Treat AI Workbench / Agent Chat as the first sample chain.
- Let the agent dynamically decide the route within a bounded toolset. Frontend controls may send natural-language hints, but must not hard-code workflow branches.
- Map AgentScope runtime events to EDU SSE v2 events through an adapter. Do not stream raw AgentScope objects to Backend or Frontend.
- Keep old `agent_service/` runnable until the v2 chain is verified.

## False Positives To Avoid

- Do not reject `async for event in agent.reply_stream(...)`; that is the expected streaming consumption pattern.
- Do not reject `json.loads()` when parsing trusted config, tests, persisted state, non-LLM API responses, or tool payloads. Reject only LLM free-text protocols built with regex/XML/string slicing/brace balancing.
- Do not reject normal filesystem APIs for source files, migrations, static templates, or test fixtures. Runtime user/session artifacts must use workspace isolation.
- Do not require full Agent Service adoption when a design intentionally uses AgentScope building blocks behind an EDUagent service facade.

## Workflow

1. Identify the work type:
   - runtime architecture
   - single agent
   - multi-agent/team
   - tool/MCP integration
   - middleware/tracing
   - streaming/SSE adapter
   - migration from hand-written workflow
2. Run the version check and read `references/agentscope-2x-guide.md` for architecture/migration decisions.
3. For project-specific code, inspect the installed package with `dir()` and `inspect.signature()` before using candidate APIs.
4. Design the boundary first:
   - external request schema
   - AgentScope runtime objects
   - tool schemas
   - event-to-SSE/API adapter
   - persistence and replay boundary
5. Only then implement or plan code.

## Design Rules

- Do not make frontend buttons choose fixed agent workflows when the product goal is autonomous agent behavior. Buttons may provide user intent hints; the agent still routes within allowed tools and guardrails.
- Do not expose AgentScope internal objects directly through public APIs. Emit stable EDU events such as `workflow_started`, `tool_started`, `tool_completed`, `artifact_created`, `critic_completed`, `text_delta`, `plan_updated`, `workflow_completed`, and `workflow_failed`.
- Keep API layers thin. API endpoints should translate HTTP/SSE to runtime calls and stream events back.
- Keep tools small and typed. Each tool should have one business capability and return structured observations, not UI strings.
- Make autonomy bounded: max steps, timeout, tool allowlist, permission checks, guardrails, and fallback events.
- Treat `Agent` as the reasoning/acting engine. In service deployments, sessions own runtime state; agents are reusable templates/configurations unless the verified version documents otherwise.

## Quick Introspection Snippets

Use these in the target environment when docs or memory may be stale:

```bash
python -c "import agentscope; print(getattr(agentscope, '__version__', 'unknown')); print(agentscope.__file__)"
python -c "import agentscope, pkgutil; print(sorted(m.name for m in pkgutil.iter_modules(agentscope.__path__)))"
python -c "import agentscope.agent as a; print([x for x in dir(a) if not x.startswith('_')])"
python -c "import agentscope.tool as t; print([x for x in dir(t) if not x.startswith('_')])"
```

Probe optional modules defensively:

```bash
python -c "import importlib.util; mods=['agentscope.middleware','agentscope.workspace','agentscope.service']; print({m: bool(importlib.util.find_spec(m)) for m in mods})"
```

## Reference

Read `references/agentscope-2x-guide.md` for the AgentScope 2.x capability map, architecture patterns, migration guidance, event-adapter pattern, and EDUagent v2 structure.
