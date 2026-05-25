# Tools And MCP

Official pages:

- Basic tool concept: https://docs.agentscope.io/basic-concepts/tool.md
- Tool capabilities: https://docs.agentscope.io/building-blocks/tool-capabilities.md
- Sandbox and Tool: https://docs.agentscope.io/deploy-and-serve/sandbox-and-tool.md

## Tool Categories

AgentScope documents three tool categories:

- Native Python functions registered through `Toolkit`
- MCP server tools
- AgentScope skills

Tool invocation is delegated to model provider APIs. AgentScope provides the interface for defining and integrating tools.

## EDUagent Tool Boundary

Use `tools/` for:

- diagram generation
- code execution
- external APIs
- document processing helpers
- future MCP wrappers

Do not register arbitrary project functions as tools without considering:

- input schema
- idempotency
- timeout
- side effects
- user data exposure
- fallback behavior

## Suggested Tool Candidates

- `retrieve_course_knowledge`
- `retrieve_user_memory`
- `generate_diagram`
- `run_safe_code_snippet`
- `search_resource_catalog`

Start with deterministic Python function tools before MCP unless the external system already exposes MCP.

## Safety Rules

- Tool functions must have typed inputs and explicit return shapes.
- Tools that touch files or external services must log failures and degrade gracefully when used in live request paths.
- Do not let tools write Backend SQL from Agent Service.
- Do not expose local filesystem traversal to model-controlled arguments without strict path allowlists.
