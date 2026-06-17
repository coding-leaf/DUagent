# Catalog Routing Layer Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a 3-layer architecture (Router -> Service -> DB) with a global exception handler, specifically targeting the core CRUD operations of the `catalogs.py` fat router as a pilot.

**Architecture:** 
1. `app/exceptions/` will host domain-specific exceptions and a global exception handler.
2. `app/main.py` will register the domain exception handler to automatically map domain errors to HTTP responses.
3. `app/services/catalog_service.py` will encapsulate SQLAlchemy queries and business logic.
4. `app/api/v1/catalogs.py` endpoints will become thin wrappers delegating to `CatalogService`.

**Tech Stack:** FastAPI, SQLAlchemy, Python.

---

### Task 1: Setup Domain Exceptions Framework

**Files:**
- Create: `backend/app/exceptions/__init__.py`
- Create: `backend/app/exceptions/base.py`
- Create: `backend/app/exceptions/handlers.py`
- Modify: `backend/app/main.py`

- [x] **Step 1: Create Base Domain Exception**
Create `backend/app/exceptions/base.py`:
```python
class DomainException(Exception):
    def __init__(self, message: str, code: int, status_code: int = 400, data: dict | None = None):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.data = data
        super().__init__(self.message)
```

- [x] **Step 2: Create Domain Exception Handler**
Create `backend/app/exceptions/handlers.py`:
```python
from fastapi import Request
from fastapi.responses import JSONResponse
from .base import DomainException

async def domain_exception_handler(request: Request, exc: DomainException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message, "data": exc.data},
    )
```

- [x] **Step 3: Register Handler in main.py**
Modify `backend/app/main.py` around line 83 (before `global_exception_handler`):
```python
from app.exceptions.base import DomainException
from app.exceptions.handlers import domain_exception_handler

# inside main.py setup:
app.add_exception_handler(DomainException, domain_exception_handler)
```

- [x] **Step 4: Commit**
```bash
git add backend/app/exceptions/ backend/app/main.py
git commit -m "feat(backend): setup domain exception framework"
```

### Task 2: Create Catalog Domain Exceptions

**Files:**
- Create: `backend/app/exceptions/catalog_exceptions.py`

- [x] **Step 1: Define Catalog Exceptions**
Create `backend/app/exceptions/catalog_exceptions.py`:
```python
from fastapi import status
from app.exceptions.base import DomainException

class CatalogNotFoundError(DomainException):
    def __init__(self):
        super().__init__(
            message="课程资源库不存在",
            code=40400,
            status_code=status.HTTP_404_NOT_FOUND
        )
```

- [x] **Step 2: Commit**
```bash
git add backend/app/exceptions/catalog_exceptions.py
git commit -m "feat(backend): define catalog domain exceptions"
```

### Task 3: Create CatalogService with core CRUD

**Files:**
- Create: `backend/app/services/catalog_service.py`
- Test: `backend/tests/test_catalog_service.py`

- [x] **Step 1: Write the failing test**
Create `backend/tests/test_catalog_service.py`:
```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.catalog_service import CatalogService
from app.exceptions.catalog_exceptions import CatalogNotFoundError

@pytest.mark.asyncio
async def test_get_catalog_not_found(db: AsyncSession):
    service = CatalogService(db)
    with pytest.raises(CatalogNotFoundError):
        await service.get_catalog("invalid_id")
```

- [x] **Step 2: Run test to verify it fails**
Run: `pytest backend/tests/test_catalog_service.py -v`
Expected: FAIL (ModuleNotFoundError or similar)

- [x] **Step 3: Write CatalogService Implementation**
Create `backend/app/services/catalog_service.py`:
```python
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.catalog import CourseCatalog
from app.exceptions.catalog_exceptions import CatalogNotFoundError

class CatalogService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_catalog(self, catalog_id: str) -> CourseCatalog:
        result = await self.db.execute(
            select(CourseCatalog).where(
                CourseCatalog.id == catalog_id,
                CourseCatalog.is_deleted == False,
            )
        )
        catalog = result.scalar_one_or_none()
        if not catalog:
            raise CatalogNotFoundError()
        return catalog

    async def list_catalogs(self, status_filter: str | None, page: int, page_size: int) -> tuple[list[CourseCatalog], int]:
        query = select(CourseCatalog).where(CourseCatalog.is_deleted == False)
        if status_filter:
            query = query.where(CourseCatalog.status == status_filter)

        total = (await self.db.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
        result = await self.db.execute(
            query.order_by(CourseCatalog.create_time.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def create_catalog(self, title: str, description: str) -> CourseCatalog:
        catalog = CourseCatalog(
            title=title.strip(),
            description=(description or "").strip(),
            status="draft",
            knowledge_status="draft",
            material_count=0,
        )
        self.db.add(catalog)
        await self.db.flush()
        await self.db.refresh(catalog)
        return catalog
```

- [x] **Step 4: Run test to verify it passes**
Run: `pytest backend/tests/test_catalog_service.py -v`
Expected: PASS

- [x] **Step 5: Commit**
```bash
git add backend/tests/test_catalog_service.py backend/app/services/catalog_service.py
git commit -m "feat(backend): implement CatalogService core CRUD"
```

### Task 4: Refactor catalogs.py Routing Layer

**Files:**
- Modify: `backend/app/api/v1/catalogs.py`

- [x] **Step 1: Replace _get_admin_catalog_or_404**
In `backend/app/api/v1/catalogs.py`:
- Remove the `_get_admin_catalog_or_404` function completely.
- Add import at the top: `from app.services.catalog_service import CatalogService`

- [x] **Step 2: Refactor `admin_list_course_catalogs`**
Update `admin_list_course_catalogs` in `catalogs.py`:
```python
@router.get("/admin/course-catalogs")
async def admin_list_course_catalogs(
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    service = CatalogService(db)
    catalogs, total = await service.list_catalogs(status_filter, page, page_size)
    return {
        "code": 200,
        "message": "success",
        "data": {
            "catalogs": [_catalog_item(c) for c in catalogs],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }
```

- [x] **Step 3: Refactor `admin_create_course_catalog`**
Update `admin_create_course_catalog` in `catalogs.py`:
```python
@router.post("/admin/course-catalogs", status_code=201)
async def admin_create_course_catalog(
    req: CourseCatalogCreateRequest,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    service = CatalogService(db)
    catalog = await service.create_catalog(req.title, req.description)
    return {"code": 201, "message": "created", "data": _catalog_item(catalog)}
```

- [x] **Step 4: Refactor `admin_get_course_catalog`**
Update `admin_get_course_catalog` in `catalogs.py`:
```python
@router.get("/admin/course-catalogs/{catalog_id}")
async def admin_get_course_catalog(
    catalog_id: str,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    service = CatalogService(db)
    catalog = await service.get_catalog(catalog_id)
    return {"code": 200, "message": "success", "data": _catalog_item(catalog)}
```

- [x] **Step 5: Replace remaining `_get_admin_catalog_or_404` usages**
In `backend/app/api/v1/catalogs.py`, find all 10 remaining occurrences of:
`await _get_admin_catalog_or_404(db, catalog_id)`
And replace them with:
`await CatalogService(db).get_catalog(catalog_id)`

- [x] **Step 6: Run integration tests**
Run: `pytest backend/tests/ -k "catalog" -v`
Verify the refactored endpoints still behave correctly and the tests pass.

- [x] **Step 7: Commit**
```bash
git add backend/app/api/v1/catalogs.py
git commit -m "refactor(backend): migrate core catalog routes to use CatalogService"
```
