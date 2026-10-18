# Quality Guidelines (`agent_service_v2`)

> Quality, testing, and development standards.

---

## Conventions

1. **Test-Driven Verifications**: Unit and integration tests reside in `agent_service_v2/tests/`. Run them using `uv run pytest`.
2. **Tool and Middleware Testing**: Whenever a tool or middleware is added/modified, add unit tests verifying both happy paths and edge cases (e.g., timeouts, malformed inputs, policy violations).
3. **Simplicity First**: Agent prompts and workflow chains should remain as simple as possible to achieve the task. Avoid multi-turn over-complex deliberation when a single agent call suffices.
4. **Code is Truth**: Reference existing tested components in `agent_service_v2/` as the primary standard.

---

## Static Analysis — Ruff

`agent_service_v2` shares the **repo-root `ruff.toml`** with `backend`, so both
Python packages are scanned by one rule set and cannot drift apart.

```bash
# From the repo root
uv tool run ruff==0.13.0 check agent_service_v2/src/agent_service_v2/

# Auto-fix import order / unused imports / whitespace
uv tool run ruff==0.13.0 check --fix agent_service_v2/src/agent_service_v2/
```

Use `uv tool run ruff==0.13.0` (or the version pinned as `RUFF_VERSION` in
`check_all.py`), not a bare `ruff`: the repo root has no `pyproject.toml`, so
`uv run ruff` would only find whatever happens to be on the caller's `PATH`.

Rule set: `target-version = py312`, `line-length = 120`, `select = ["E","F","W","I"]`,
`ignore = ["E712","E501"]`. `E712` is ignored because SQLAlchemy boolean filters must
stay SQL expressions (`Model.is_deleted == False`, never `not Model.is_deleted`);
`E501` is ignored because the formatter owns line length. Full rationale in
[`backend/quality-guidelines.md`](../../backend/backend/quality-guidelines.md).

### Zero-warning policy

`uv tool run ruff==0.13.0 check agent_service_v2/src/agent_service_v2/` must print
`All checks passed!` before review. Fix findings rather than adding `# noqa`; the
only sanctioned `noqa` is `# noqa: F401` with an explanatory comment on a
side-effect or documented patch-seam import.

### Import placement

Module-level `import` statements must stay at the top of the file. Ruff's `E402`
catches lazily-placed imports; if an import must be deferred (heavy optional
dependency, circular import), put it inside the function body — never at module
scope below other code.

### Architecture guardrails

Rules Ruff cannot express — no hardcoded subjects in prompts, no dynamically
generated parse scripts in the sandbox, no swallowed stream errors, and the
`# arch-allow:` escape hatches — live in
[architecture-guardrails.md](./architecture-guardrails.md). Read it before touching
`agents/`, `generators/`, or `tools/`.

---

## Local Verification

```bash
# Agent service only
uv tool run ruff==0.13.0 check agent_service_v2/src/agent_service_v2/
uv run --project agent_service_v2 pytest agent_service_v2/tests/ -q

# Whole repo (frontend lint+build, both Python packages, both test suites)
python check_all.py
```
