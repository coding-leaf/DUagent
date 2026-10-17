# Quality Guidelines (`agent_service_v2`)

> Quality, testing, and development standards.

---

## Conventions

1. **Test-Driven Verifications**: Unit and integration tests reside in `agent_service_v2/tests/`. Run them using `uv run pytest`.
2. **Tool and Middleware Testing**: Whenever a tool or middleware is added/modified, add unit tests verifying both happy paths and edge cases (e.g., timeouts, malformed inputs, policy violations).
3. **Simplicity First**: Agent prompts and workflow chains should remain as simple as possible to achieve the task. Avoid multi-turn over-complex deliberation when a single agent call suffices.
4. **Code is Truth**: Reference existing tested components in `agent_service_v2/` as the primary standard.
