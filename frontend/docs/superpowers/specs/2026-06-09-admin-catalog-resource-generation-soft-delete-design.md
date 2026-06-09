# Admin Catalog Resource Generation And Soft Delete Design

## Background

EDUagent has already split shared course content assets from teacher teaching classes:

- Admin can create a CourseCatalog.
- Admin can upload source materials and run knowledge ingestion.
- Teacher can create a teaching class bound to a ready CourseCatalog.

This fixes the earlier problem where teachers could generate resources without a stable relationship to real course materials. The remaining product gap is that a CourseCatalog can now contain source materials and a vectorized knowledge base, but there is no current Admin-facing place to turn those materials into standard learning resources that students can read.

The existing `POST /api/v1/resources/generate` route still exists in Backend and has a CourseCatalog ready gate, but the current Client API marks it deprecated for frontend use, and TeacherConsole no longer exposes it. The new design must not simply restore the teacher generation panel.

## Goals

1. Add an Admin-owned resource generation workflow for CourseCatalog standard learning resources.
2. Keep teachers focused on binding ready CourseCatalogs to teaching classes, not generating shared content.
3. Add surface-level soft delete for generated resources.
4. Add surface-level soft delete for uploaded source materials.
5. Avoid physical deletion of files, Qdrant chunks, Agent artifacts, or database rows in the first version.
6. Keep OpenAPI as the source of truth and explicitly add missing contracts before frontend calls them.

## Non-Goals

- No physical file deletion.
- No Qdrant chunk deletion.
- No precise `chunk_count` rollback after material soft delete.
- No source reference cleanup.
- No teacher-facing resource generation entry.
- No quiz generation entry.
- No automatic generation immediately after ingestion.
- No hidden frontend-only delete behavior.
- No mock API or fake success path in real mode.

## Contract Findings

Current Client API has:

- `GET /resources`
- `GET /resources/{id}`
- deprecated `POST /resources/generate`
- `GET /admin/course-catalogs`
- `POST /admin/course-catalogs`
- `GET /admin/course-catalogs/{catalog_id}`
- `GET/POST /admin/course-catalogs/{catalog_id}/materials`
- `POST /admin/course-catalogs/{catalog_id}/materials/upload`
- `POST /admin/course-catalogs/{catalog_id}/ingestions`
- `GET /admin/course-catalogs/{catalog_id}/knowledge-status`

Current Client API does not have:

- `DELETE /resources/{id}`
- `DELETE /admin/resources/{resource_id}`
- `DELETE /admin/course-catalogs/{catalog_id}/materials/{material_id}`
- Admin/catalog-scoped resource generation endpoint.

Backend models already have:

- `Resource.is_deleted`
- `CourseCatalogMaterial.is_deleted`

Backend routes currently filter out deleted records in the relevant read paths, but deletion is not exposed as a Client API contract.

## Proposed Product Model

CourseCatalog becomes the Admin-owned content production unit:

```text
Admin creates CourseCatalog
-> Admin uploads source materials
-> Admin runs ingestion
-> Admin generates standard learning resources
-> Teacher binds ready CourseCatalog to class
-> Students consume generated resources through class context
```

Generated resources are standard catalog-backed materials, not teacher-private drafts. Teachers do not create or delete shared resources in this version.

## Resource Generation Workflow

### Entry

Add a generation section inside `CourseCatalogDrawer`.

The section is visible to Admin users when viewing a CourseCatalog. It should show:

- current catalog status;
- current knowledge status;
- chunk count;
- last generation task status if available;
- resource type options: `document`, `mindmap`, `reading`, `code`;
- optional chapter and knowledge point fields;
- a "生成学习资源" action.

The action is disabled when:

- catalog does not exist;
- catalog is not ready;
- knowledge status is not `ready` or usable `partial`;
- `chunk_count` is zero;
- ingestion is currently running;
- another generation task for the catalog is in progress, if Backend can detect it in this version.

### API Shape

Add a new Admin/catalog-scoped endpoint:

```http
POST /api/v1/admin/course-catalogs/{catalog_id}/resources/generations
```

Request body:

```json
{
  "chapter": "string",
  "knowledge_point": "string",
  "resource_types": ["document", "mindmap", "reading", "code"]
}
```

Response:

```json
{
  "code": 202,
  "message": "accepted",
  "data": {
    "task_id": "string",
    "catalog_id": "string",
    "status": "processing"
  }
}
```

The endpoint is Admin-only.

The existing deprecated teacher-oriented `POST /resources/generate` stays deprecated for frontend use. Backend may reuse implementation internals, but the frontend must call only the new Admin endpoint.

### Persistence Rule

Generated resources continue to be stored in `resources`.

Because current student reads are class-scoped by `course_id`, Backend must define how catalog-generated resources become visible to classes bound to the catalog. First version should choose one clear rule:

- On generation request, Backend accepts a `catalog_id`, resolves bound `CourseOffering` classes when persisting results, and writes generated resources for each bound class; or
- Backend stores catalog resource ownership separately and projects resources to bound classes in `GET /resources`.

The implementation plan must pick one after checking current Backend constraints. The design preference is to avoid schema churn where possible, but not at the cost of unclear visibility.

## Resource Soft Delete

### API Shape

Add:

```http
DELETE /api/v1/admin/resources/{resource_id}
```

Response:

```json
{
  "code": 200,
  "message": "deleted",
  "data": {
    "id": "string",
    "deleted": true
  }
}
```

The endpoint is Admin-only.

### Behavior

Backend sets:

- `Resource.is_deleted = true`
- `Resource.update_by = current admin id`, if current model conventions support it

Backend does not:

- remove database rows;
- remove files;
- remove Qdrant chunks;
- remove Agent logs;
- remove async task results;
- recalculate analytics.

Existing `GET /resources`, `GET /resources/{id}`, LearningPath node resources, Profile, Evaluation, and Teaching queries already filter `Resource.is_deleted == False` where they read resources. The implementation must verify all user-facing resource reads continue to filter deleted resources.

## Material Soft Delete

### API Shape

Add:

```http
DELETE /api/v1/admin/course-catalogs/{catalog_id}/materials/{material_id}
```

Response:

```json
{
  "code": 200,
  "message": "deleted",
  "data": {
    "id": "string",
    "catalog_id": "string",
    "deleted": true,
    "knowledge_status": "dirty"
  }
}
```

The endpoint is Admin-only.

### Behavior

Backend sets:

- `CourseCatalogMaterial.is_deleted = true`
- `CourseCatalog.material_count` decremented to the count of non-deleted materials, or recalculated from non-deleted materials;
- `CourseCatalog.knowledge_status = "dirty"` when the catalog was previously `ready` or `partial`;
- `CourseCatalog.last_error = null`.

Backend does not:

- delete uploaded files;
- delete material directories;
- delete Qdrant chunks;
- reduce `chunk_count`;
- rewrite existing generated resources;
- invalidate bound teaching classes automatically.

### UI Meaning

After material soft delete, Admin sees the material disappear from the list and sees a warning that source materials changed and re-ingestion is recommended.

Because Qdrant chunks are not removed in this version, the warning must not claim that deleted material has been removed from the knowledge base. Suggested copy:

```text
资料列表已更新。当前版本仅隐藏资料记录，不清理历史向量切片；如需刷新知识库，请重新入库。
```

## Frontend Behavior

### CourseCatalogDrawer

Add two surface areas:

1. Resource generation panel.
2. Resource/material management actions.

For material list:

- Add a delete action per material.
- Confirm before deleting.
- On success, refresh materials and knowledge status.
- Do not claim physical cleanup.

For generated resources:

- If Backend provides a catalog resource list, show generated resources in the drawer and allow soft delete.
- If Backend only exposes class resource reads in first version, do not create a fake catalog resource list. The first implementation plan must add a real list endpoint before showing catalog resources in Admin UI.

### TeacherConsole

No resource generation action is added.

Teacher remains responsible for:

- creating teaching classes;
- binding ready CourseCatalogs;
- viewing students and class insights.

## Error Handling

Use existing API envelope style:

```json
{
  "code": 40913,
  "message": "课程资源库知识库未就绪",
  "data": null
}
```

Expected errors:

- `401`: unauthenticated.
- `403`: non-admin access.
- `404`: catalog, material, or resource not found.
- `409`: catalog ingesting, knowledge base not ready, no bound class if the chosen persistence rule requires bound classes.
- `422`: invalid resource type or empty request after validation.

## Testing Strategy

Backend tests:

- Admin can trigger catalog-scoped resource generation only when CourseCatalog is ready and has chunks.
- Non-admin cannot trigger catalog resource generation.
- Generation rejects dirty, draft, ingesting, failed, or empty catalogs.
- Resource soft delete sets `is_deleted` and hides the resource from read endpoints.
- Material soft delete sets `is_deleted`, refreshes material counts, marks catalog dirty when appropriate, and does not alter `chunk_count`.

Frontend E2E tests:

- Admin sees generation panel in CourseCatalog drawer.
- Admin can trigger generation and see task polling state.
- Admin can soft delete a material and sees the list refresh.
- Admin can soft delete a generated resource if a real Admin catalog resource list endpoint exists.
- TeacherConsole does not expose resource generation.

Contract checks:

- OpenAPI JSON remains valid.
- API markdown matches OpenAPI for new endpoints.
- Frontend services call only declared Client API endpoints.

## Documentation Updates

When implementation is completed:

- Update `../docs/10-client-api/Client-API.openapi.json`.
- Update `../docs/10-client-api/API_前端接口规范.md`.
- Update `docs/feature-ledger.md`.
- Update `docs/project-direction.md` if the recommended next step changes.
- Update `docs/project-coverage-audit.md` with evidence.
- Update `WORKFLOW.md` with commands and results.

## Open Questions For Implementation Plan

1. Whether generated resources should be physically duplicated into each bound teaching class or projected from catalog ownership at read time.
2. Whether a catalog resource list endpoint should be part of the first implementation batch.
3. Whether generation should be rejected when no class is currently bound to the catalog.

The implementation plan must resolve these before code changes.
