# Directory Structure (`backend`)

> Module layout for `backend/app/`.

---

## Layout

```
backend/
├── app/
│   ├── api/v1/         # FastAPI routers grouped by domain (auth, courses, tutoring, etc.)
│   ├── core/           # Settings (pydantic-settings), security, config
│   ├── db/             # SQLAlchemy async engine, base declarative model, session factory
│   ├── exceptions/     # DomainException and centralized FastAPI exception handlers
│   ├── infrastructure/ # External client adapters, helper utilities
│   ├── models/         # SQLAlchemy ORM model definitions
│   ├── schemas/        # Pydantic v2 request/response validation schemas
│   ├── services/       # Domain business logic (keeps routers thin)
│   ├── main.py         # App factory, middleware, router mount point
│   └── static_site.py  # Static file / frontend serving logic
├── requirements.txt    # Pinned production dependencies
└── tests/              # Pytest test cases
```

---

## Conventions

- **Routers (`api/v1/`)**: Only parse inputs via Pydantic schemas, invoke corresponding service functions, and return schemas or responses. No raw database queries or complex logic in routers.
- **Services (`services/`)**: Encapsulate business logic. Inject database session (`AsyncSession`).
- **Models (`models/`)**: SQLAlchemy 2.0 declarative models inheriting from `Base`.
- **Schemas (`schemas/`)**: Pydantic BaseModel for validation and serialization. Avoid passing ORM instances directly across boundaries without serialization.
- **Service Boundaries**: Backend services MUST NEVER directly invoke external LLM endpoints (`/chat/completions`) or maintain custom LLM prompts. Any content planning, reasoning, RAG extraction, or KG generation must delegate to Agent Service (`agent_service_v2`) via `AgentClient`.
- **KISS**: If a module has simple CRUD logic, keep service methods simple without excessive design patterns.
