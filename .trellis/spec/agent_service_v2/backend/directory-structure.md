# Directory Structure (`agent_service_v2`)

> Module layout for `agent_service_v2/src/agent_service_v2/`.

---

## Layout

```
agent_service_v2/
├── pyproject.toml              # uv project definition (AgentScope 2.x, FastAPI, SSE)
├── tests/                      # Pytest suite for agents, tools, middleware
└── src/agent_service_v2/
    ├── agents/                 # Specialized agent definitions (roles, system prompts)
    ├── api/                    # FastAPI routers (workbench, knowledge, evaluation, personalized)
    ├── artifacts/              # Generated files, manifests, artifact scanner
    ├── generators/             # Content generation pipelines
    ├── observability/          # Middleware logging, token tracking, traces
    ├── runtime/                # Agent runtime loop, execution context
    ├── safety/                 # Content review, internal disclosure policy
    ├── schemas/                # Pydantic v2 schemas for agent input/output
    ├── session/                # Session store and history management
    ├── team/                   # Multi-agent collaboration teams / topologies
    ├── tools/                  # Tool implementations, MCP clients (e.g. web_search_mcp)
    ├── workspaces/             # Local workspace persistence
    ├── main.py                 # FastAPI application & lifespan management
    └── team_app.py             # Team runtime application integration
```

---

## Conventions

- **Agents (`agents/`)**: Declare AgentScope agent instances or factory classes. Keep prompts explicit and role boundaries clear.
- **Tools (`tools/`)**: Callable tools exposed to agents. Must validate inputs strictly and handle tool execution exceptions gracefully.
- **API (`api/`)**: Handle external caller requests (FastAPI endpoints); push real-time agent output through SSE events.
- **Runtime (`runtime/`)**: Manages agent loop execution, timeout, cancellation, and context injection.
- **Safety (`safety/`)**: Enforce disclosure filtering and policy inspection on agent inputs and outputs.
