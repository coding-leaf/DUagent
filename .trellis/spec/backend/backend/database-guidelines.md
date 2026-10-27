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
7. **Cross-Dialect SQL Compatibility & Window Function Hygiene**: 严禁在获取分组最新记录（Top-1 per group）等业务查询中随意硬编码高版本专用窗口函数（如 `ROW_NUMBER() OVER (PARTITION BY ...)`）。此类查询必须优先使用标准 SQL 时间排序结合内存字典映射（或通用标量关联子查询），确保代码在低版本兼容环境（如 MySQL 5.7）、推荐生产环境（MySQL 8.0）以及轻量测试环境（SQLite）中均能无歧义运行。
8. **Data Contract Defensive Boundary**: 在资源发布入库（如 `PersonalizedResourceGenerationService.publish`）等涉及用户自定义输入的场景中，对有限长度字段（如 `knowledge_point varchar(100)`、`title varchar(200)`、`chapter varchar(100)`）必须执行防御性长度截断与清洗，严禁放行超长文本引发 MySQL 1406 `Data too long` 异常导致数据写入崩溃。

