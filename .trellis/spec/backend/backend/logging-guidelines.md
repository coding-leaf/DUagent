# Logging Guidelines (`backend`)

> Logging conventions.

---

## Conventions

1. **Standard Logger**: Use Python's standard `logging.getLogger(__name__)`.
2. **Levels**:
   - `DEBUG`: Development tracing only.
   - `INFO`: Lifecycle milestones (app start, DB init, key user transactions).
   - `WARNING`: Recoverable degradation, fallback executions.
   - `ERROR`: Unhandled failures, external API downtime, database transaction errors (always include `exc_info=True`).
3. **No Sensitive Data**: Do not log tokens, raw passwords, or unmasked user secrets.
4. **KISS**: Avoid complex logging frameworks unless required; keep formatting structured and readable.
