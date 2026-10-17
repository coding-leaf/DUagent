# Agent Service v2 Guidelines (Package: `agent_service_v2`)

> Microservice for AI multi-agent orchestration and workflow execution.

---

## Core Tenets

1. **Code is Truth**: Existing implementation under `agent_service_v2/src/agent_service_v2/` is authoritative.
2. **Fixed Tech Stack**: `uv` package manager + Python 3.12+ + AgentScope 2.x + FastAPI + SSE Starlette + Pydantic v2.
3. **Decoupled Architecture**: Runs as an independent service (typically port 8001/8002). Communicates with the main `backend` via REST and SSE streaming protocols.
4. **KISS Principle**: Keep agent configurations, tool registrations, and execution flows direct. Avoid unnecessary middleware nesting or over-engineered orchestration chains.

---

## Guidelines Index

| Guide | Description | Status |
|-------|-------------|--------|
| [Directory Structure](./directory-structure.md) | AgentScope agents, runtime, tools, and endpoints layout | Baseline active |
| [Database Guidelines](./database-guidelines.md) | Workspace and session artifact persistence | Baseline active |
| [Error Handling](./error-handling.md) | SSE streaming errors and agent fallback strategies | Baseline active |
| [Logging Guidelines](./logging-guidelines.md) | Observability, tool call tracing, middleware logging | Baseline active |
| [Quality Guidelines](./quality-guidelines.md) | Testing standards under `agent_service_v2/tests/` | Baseline active |
