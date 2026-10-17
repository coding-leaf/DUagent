# Database Guidelines (`backend`)

> SQLAlchemy 2.0 Async conventions.

---

## Conventions

1. **Async Only**: Use `AsyncSession` provided via FastAPI dependency `get_db()`.
2. **SQLAlchemy 2.0 Syntax**: Use `select(...)` and `execute(...)` instead of legacy 1.x query syntax (`session.query(...)` is forbidden).
3. **Transactions**: Commit via session context or service-level transaction boundaries. Always handle rollback on failure.
4. **Relationship Loading**: Explicitly use `selectinload` or `joinedload` when traversing relationships to avoid async N+1 and lazy-loading errors.
5. **KISS**: Do not invent custom ORM abstractions. Use standard SQLAlchemy constructs directly.
