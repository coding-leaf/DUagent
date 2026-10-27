# Database Guidelines (`backend`)

> SQLAlchemy 2.0 Async conventions.

---

## Conventions

1. **Async Only**: Use `AsyncSession` provided via FastAPI dependency `get_db()`.
2. **SQLAlchemy 2.0 Syntax**: Use `select(...)` and `execute(...)` instead of legacy 1.x query syntax (`session.query(...)` is forbidden).
3. **Transactions**: Commit via session context or service-level transaction boundaries. Always handle rollback on failure.
4. **Relationship Loading**: Explicitly use `selectinload` or `joinedload` when traversing relationships to avoid async N+1 and lazy-loading errors.
5. **KISS**: Do not invent custom ORM abstractions. Use standard SQLAlchemy constructs directly.
6. **Test Loop Isolation**: 严禁在测试模块顶层导入阶段裸调用 `asyncio.run(init_db())` 或初始化全局连接池。测试环境必须使用 pytest-asyncio fixture（如 `@pytest_asyncio.fixture(scope="module", autouse=True)`）驱动数据库初始化并在 teardown 中安全 dispose engine，防止跨事件循环共享连接引发 `RuntimeError: Future attached to a different loop`。

