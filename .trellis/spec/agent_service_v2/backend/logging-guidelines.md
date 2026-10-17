# Logging & Observability Guidelines (`agent_service_v2`)

> Agent logging and trace tracking conventions.

---

## Conventions

1. **Observability Middleware**: Use modules under `observability/` (e.g., `agent_logging_middleware.py`) to intercept and record agent runs, token counts, and execution latency.
2. **Tool Invocations**: Log tool names and summary arguments at `INFO` level. Avoid dumping massive raw payloads (like multi-megabyte search documents) directly into stdout.
3. **Sensitive Scrubbing**: Ensure system prompts, user private tokens, or proprietary agent instructions are not leaked into public log sinks.
4. **KISS**: Favor clear, grep-friendly structured logs over overcomplicated distributed tracing libraries unless required.
