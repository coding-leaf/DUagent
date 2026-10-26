# Quality Guidelines (`backend`)

> Engineering quality and testing standards.

---

## Conventions

1. **Simplicity First**: Write code that is easy to delete or replace. Never build speculative abstractions for future features.
2. **Testing**: Run tests with `pytest`. When writing or refactoring services, add unit/integration tests for critical business logic under `backend/tests/`.
3. **Async Cleanliness**: Avoid blocking synchronous calls (e.g., synchronous file I/O, `time.sleep()`, synchronous `requests.get`) inside async endpoint handlers or services. Use async counterparts (`asyncio.sleep`, `httpx.AsyncClient`).
4. **Code is Truth**: If existing patterns in `backend/app/` work well and are tested, align with them rather than inventing new patterns.

---

## Static Analysis — Ruff

`backend` and `agent_service_v2` share a **single repo-root `ruff.toml`**. Ruff is a
Rust-native scanner (≈0.05 s for the whole backend) and replaces flake8/pylint.

```bash
# From the repo root — scans both Python packages
uv tool run ruff==0.13.0 check backend/app/

# Auto-fix import order / unused imports / whitespace
uv tool run ruff==0.13.0 check --fix backend/app/
```

Use `uv tool run ruff==0.13.0` (or the version pinned as `RUFF_VERSION` in
`check_all.py`) rather than a bare `ruff`. The repo root has no
`pyproject.toml`, so `uv run ruff` resolves nothing and falls back to the
caller's `PATH` — a machine that never installed ruff would fail with
`Failed to spawn: 'ruff'`. `uv tool run` fetches the pinned version on demand
and caches it, so the gate behaves the same everywhere.

### Rule set

| Setting | Value | Rationale |
| :-- | :-- | :-- |
| `target-version` | `py312` | Matches both services' `requires-python`. |
| `line-length` | `120` | Wide enough for prompt literals and SQLAlchemy chains. |
| `select` | `E`, `F`, `W`, `I` | pycodestyle, pyflakes, warnings, import sorting. |
| `ignore` | `E712`, `E501` | See below — both are load-bearing. |

### Why `E712` is ignored

SQLAlchemy 2.0 filters must stay SQL expressions:

```python
# ✅ Emits `WHERE is_deleted = 0`
query = select(User).where(User.is_deleted == False)

# ❌ Evaluates Python truthiness on the column; the filter silently disappears
query = select(User).where(not User.is_deleted)
```

`E712` would demand the second form, so it is globally disabled. Never "fix" an
`E712` warning by hand.

### Why `E501` is ignored

Line length is the formatter's job. Long URLs, Chinese prompt strings, and
`TableColumn(...)` rows must not block static scanning.

### Zero-warning policy

`uv tool run ruff==0.13.0 check backend/app/` must print `All checks passed!`
before review.
Don't add `# noqa` to silence a real finding — fix it. The only sanctioned `noqa`
is `# noqa: F401` on an import kept purely for its side effect or as a documented
test patch seam, and it must carry an explanatory comment.

### Architecture guardrails

Rules Ruff cannot express (no direct LLM calls, no cross-layer imports, no swallowed
exceptions, `# arch-allow:` escape hatches) live in
[architecture-guardrails.md](./architecture-guardrails.md). Read it before touching
`app/services/` or `app/api/`.

---

## Local Verification

```bash
# Backend only
cd backend && uv tool run ruff==0.13.0 check app/ && ./.venv/Scripts/python.exe -m pytest tests/ -q

# Whole repo (frontend lint+build+tests, both Python packages, both test suites)
python check_all.py
```
