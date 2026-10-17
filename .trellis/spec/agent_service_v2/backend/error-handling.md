# Error Handling (`agent_service_v2`)

> Agent runtime and streaming exception handling.

---

## Conventions

1. **SSE Error Propagation**: When streaming agent thoughts or tokens, send structured SSE error events (e.g., `event: error\ndata: {"error": "..."}`) rather than crashing the HTTP stream abruptly.
2. **Tool Call Failures**: Agent tools must catch tool-internal exceptions and return an informative error message string to the agent model rather than throwing unhandled exceptions that abort the entire workflow.
3. **Safety & Policy Violations**: If content triggers `safety/` disclosure filters, return sanitized messages or specific policy error signals.
4. **Resilience**: Ensure network timeouts to external LLMs or MCP servers are caught and retried or failed cleanly.
