# Backend Catalogs & Resources Refactoring Plan

This plan follows the Layered Architecture: `Router -> Service -> DB` pattern to thin the routes in `catalogs.py` and `resources.py` and encapsulate domain logic into `ResourceService`, `CatalogMaterialService`, and `CatalogService`.

## Proposed Changes

### 1. Create `backend/app/services/resource_service.py`
- Define `ResourceService` class taking `db: AsyncSession` in constructor.
- Implement `list_resources` method.
- Implement `get_resource_detail` method.
- Implement `generate_resources` method.

### 2. Refactor `backend/app/api/v1/resources.py`
- Import `ResourceService`.
- Instatiate `ResourceService` using the injected `db` session dependency.
- Refactor the three endpoints to delegate requests to the service.
- Keep the router thin, handling only input/output DTOs/JSONResponses.

### 3. Refactor `backend/app/services/catalog_material_service.py`
- Implement `save_uploaded_material(self, catalog: CourseCatalog, file: UploadFile) -> CourseCatalogMaterial` to encapsulate file chunking, writes, and database update/rollback transactions.
- Implement `get_material_counts(self, catalog_id: str) -> dict[str, int]` to encapsulate material count queries.
- Add `await self.db.commit()` inside `delete_material`.

### 4. Refactor `backend/app/api/v1/catalogs.py`
- Delegate material uploads to `CatalogMaterialService.save_uploaded_material`.
- Delegate material counts queries to `CatalogMaterialService.get_material_counts`.
- Clean up transactions and file I/O operations from the router.

## Verification Checklist
- Run python compile check on modified files.
- Run tests: `pytest tests/test_course_catalogs.py tests/test_resource_detail.py tests/test_resources_async.py tests/test_catalog_material_service.py tests/test_catalog_service.py`
