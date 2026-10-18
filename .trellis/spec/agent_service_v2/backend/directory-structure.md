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
    ├── runtime/                # Agent event adaptation, SSE broadcasting
    ├── safety/                 # Content review, internal disclosure policy
    ├── schemas/                # Pydantic v2 schemas for agent input/output
    ├── session/                # Run buses, session registries, history management
    ├── tools/                  # Tool implementations, MCP clients (e.g. web_search_mcp)
    ├── workspaces/             # Local workspace persistence
    └── main.py                 # FastAPI application & lifespan management
```

---

## Conventions

- **Agents (`agents/`)**: Declare AgentScope agent instances or factory classes. Keep prompts explicit, discipline-agnostic, and role boundaries clear (e.g. `curriculum_planner.py` for universal DAG course planning). Never hardcode specific disciplines (such as C Programming) into generic planner prompts.
- **Tools (`tools/`)**: Callable tools exposed to agents (e.g. `outline_extractor.py`). Must validate inputs strictly, return serializable JSON data, and handle tool execution exceptions gracefully without crashing the workflow.
- **API (`api/`)**: Handle external caller requests (FastAPI endpoints); push real-time agent output through SSE events. Never mount another ASGI app or call the same process over HTTP — compose in-memory instead.
- **Runtime (`runtime/`)**: Maps AgentScope events to `EduEventType` and serializes them for SSE (`event_broadcaster.py`, `protocol_adapter.py`). Must not contain business logic.
- **Session (`session/`)**: Own in-process run state only (`run_bus.py` for workbench runs, `generation_registry.py` for personalized-resource generations). Durable state belongs to the Backend.
- **Generators (`generators/`)**: Long-running pipelines (public resources, personalized resources). Each pipeline emits `EduEventType` events through an injected `emit` callback and must never raise into the SSE stream.
- **Safety (`safety/`)**: Enforce disclosure filtering and policy inspection on agent inputs and outputs.
