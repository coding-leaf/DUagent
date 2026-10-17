# Quality Guidelines (`backend`)

> Engineering quality and testing standards.

---

## Conventions

1. **Simplicity First**: Write code that is easy to delete or replace. Never build speculative abstractions for future features.
2. **Testing**: Run tests with `pytest`. When writing or refactoring services, add unit/integration tests for critical business logic under `backend/tests/`.
3. **Async Cleanliness**: Avoid blocking synchronous calls (e.g., synchronous file I/O, `time.sleep()`, synchronous `requests.get`) inside async endpoint handlers or services. Use async counterparts (`asyncio.sleep`, `httpx.AsyncClient`).
4. **Code is Truth**: If existing patterns in `backend/app/` work well and are tested, align with them rather than inventing new patterns.
