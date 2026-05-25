# Deploy And Serve

Official pages:

- Agent as Service: https://docs.agentscope.io/deploy-and-serve/agent-as-service.md
- Sandbox and Tool: https://docs.agentscope.io/deploy-and-serve/sandbox-and-tool.md

## Current Project Boundary

EDUagent already exposes Agent Service through FastAPI. Do not add a second serving layer unless there is a clear reason.

AgentScope serving features may become relevant if:

- an AgentScope-native agent needs to be served independently
- tools need sandbox isolation
- agent lifecycle/state management exceeds current FastAPI routes

## Recommended Near-Term Approach

Keep FastAPI as the public service boundary:

```text
Backend -> FastAPI api/v1 -> agents/ adapters -> AgentScope components -> schemas/SSE response
```

Use AgentScope internals behind this boundary instead of replacing the external API.

## Sandbox Guidance

Use sandboxed tools when executing untrusted code or model-controlled operations. For deterministic document ingestion and Qdrant writes, sandboxing is usually unnecessary.

## Deployment Risks

- AgentScope dependencies may introduce optional extras such as RAG, ReMe, Redis, SQLAlchemy, or provider SDKs.
- Keep optional dependencies explicit in `pyproject.toml`.
- Avoid import-time failures in live API modules if optional AgentScope extras are missing.
- Prefer lazy imports inside adapters for optional features.
