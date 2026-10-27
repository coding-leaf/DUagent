# Error Handling (`agent_service_v2`)

> Agent runtime and streaming exception handling.

---

## Conventions

1. **SSE Error Propagation**: When streaming agent thoughts or tokens, send structured SSE error events (e.g., `event: error\ndata: {"error": "..."}`) rather than crashing the HTTP stream abruptly.
2. **Tool Call Failures**: Agent tools must catch tool-internal exceptions and return an informative error message string to the agent model rather than throwing unhandled exceptions that abort the entire workflow.
3. **Safety & Policy Violations**: If content triggers `safety/` disclosure filters, return sanitized messages or specific policy error signals.
4. **Resilience**: Ensure network timeouts to external LLMs or MCP servers are caught and retried or failed cleanly.
5. **Stream Termination**: Every run that emits `workflow_started` must end with exactly one `workflow_completed` or `workflow_failed`, then the event bus must be closed so the SSE response finishes. Background pipelines wrap their whole body in `try/except Exception` and convert the error into `workflow_failed`; they never re-raise into the stream.
6. **No In-Process HTTP**: Do not call the service's own endpoints over HTTP from inside a handler. Compose the target code in-process — the removed `/agent/v2/team-runtime` mount and its `httpx.ASGITransport` loopback are the anti-pattern to avoid.
7. **Protocol Adapter Event Classification & Defensiveness**: `EDUProtocolAdapter` maps framework events to streaming protocol. Only explicit terminal framework errors (e.g. `ExceedMaxItersEvent`) emit `workflow_failed`. Benign lifecycle/hint events (`HintBlockEvent`, `DataBlockStartEvent`, `DataBlockEndEvent`, etc.) and unknown framework extension events must be safely absorbed/dropped with `logger.debug` rather than terminating the workflow.
