# Backend Guidelines (Package: `backend`)

> Baseline conventions for the monolithic FastAPI business backend.

---

## Core Tenets

1. **Code is Truth**: Existing codebase (`backend/app/`) is the authoritative source. Documentation is auxiliary.
2. **Fixed Tech Stack**: FastAPI + SQLAlchemy 2.0 (async with aiosqlite/aiomysql) + Pydantic v2 + Uvicorn. Do not introduce new web/ORM frameworks.
3. **KISS Principle**: Keep architecture flat, direct, and straightforward. Avoid excessive abstraction layers, superfluous wrappers, or premature generic designs.
4. **Service Boundary**: `backend` handles user management, course catalogs, learning paths, quizzes, and business orchestration. AI agent execution is delegated to `agent_service_v2` over HTTP/SSE.

---

## Guidelines Index

| Guide | Description | Status |
|-------|-------------|--------|
| [Directory Structure](./directory-structure.md) | `backend/app/` layering and module layout | Baseline active |
| [Database Guidelines](./database-guidelines.md) | SQLAlchemy 2.0 async session, models, queries | Baseline active |
| [Error Handling](./error-handling.md) | `DomainException` and standard HTTP responses | Baseline active |
| [Logging Guidelines](./logging-guidelines.md) | Standard logging, avoiding noisy output | Baseline active |
| [Quality Guidelines](./quality-guidelines.md) | Code simplicity, test baselines | Baseline active |
