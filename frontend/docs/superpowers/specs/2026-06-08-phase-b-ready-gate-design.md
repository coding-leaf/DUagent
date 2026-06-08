# Phase B Ready Gate Design

## Background

Baseline facts are recorded in:

`docs/superpowers/specs/2026-06-08-course-catalog-ready-gate-baseline.md`

Current state:

- Admin can create CourseCatalogs, upload materials, trigger ingestion, and observe `knowledge_status`.
- Teachers create classes by binding `CourseCatalog.status=ready`.
- `POST /resources/generate` and `POST /quiz/generate` still use the teaching class `course_id` directly and do not check the bound CourseCatalog.
- Agent retrieval uses the payload `course_id`, while CourseCatalog ingestion writes Qdrant chunks using `CourseCatalog.id`.

Phase B makes generation consumers respect the CourseCatalog knowledge base.

## Goals

Implement a shared ready gate for:

- `POST /api/v1/resources/generate`
- `POST /api/v1/quiz/generate`

The gate must:

- Resolve the teaching class `course_id` to its bound `CourseOffering.catalog_id`.
- Load the bound `CourseCatalog`.
- Reject generation when the catalog has no usable knowledge base.
- Pass the CourseCatalog id to Agent as the knowledge lookup id.
- Keep the Client API request shape stable.
- Update OpenAPI, Backend, Frontend services, and tests together.

## Non-Goals

This phase does not implement:

- LearningPath / KG ready gate.
- KG generation from CourseCatalog materials.
- `source_refs` persistence or ResourceDetail source display.
- New TeacherConsole resource generation UI.
- New Quiz generation UI.
- Resource learning behavior, reading progress, or activity tables.
- Agent API schema expansion beyond using the existing `course_id` field as the knowledge lookup id.

LearningPath remains P0/P1 but is deferred because it depends on KG readiness, not only Qdrant readiness. It needs a separate design for KG source, KG status, and node matching.

## Ready Semantics

CourseCatalog has two separate state axes:

- `status`: bindability of the catalog to a teaching class.
- `knowledge_status`: quality and freshness of the knowledge base.

Phase B ready gate uses both:

| `status` | `knowledge_status` | Generation allowed | Reason |
| --- | --- | --- | --- |
| `ready` | `ready` | Yes | Fully synchronized knowledge base. |
| `ready` | `partial` | Yes, degraded | Existing knowledge base has at least some usable chunks; incremental or partial material failures should not fully break teaching classes. |
| `ready` | `dirty` | No | New uploaded material is pending ingestion, so generation would ignore current source materials. |
| `ready` | `ingesting` | No | Knowledge base is changing. |
| `ready` | `draft` | No | No completed ingestion evidence. |
| `ready` | `failed` | No | Last known knowledge base state is unusable. |
| not `ready` | any | No | Catalog is not bindable and should not power generation. |

Additional chunk guard:

- `ready/ready` and `ready/partial` require `CourseCatalog.chunk_count > 0`.
- If `chunk_count <= 0`, reject with `knowledge_base_empty`.

This makes `partial` usable only when the database proves that at least one chunk exists.

## Error Codes

Use consistent business error codes for both endpoints.

| HTTP | `detail.code` | `detail.message` | When |
| --- | --- | --- | --- |
| 404 | `course_catalog_missing` | `课程未绑定可用资源库` | No `CourseOffering`, no catalog, deleted catalog, or legacy course without catalog binding. |
| 409 | `course_material_missing` | `课程资料尚未完成入库` | Catalog exists but `status/knowledge_status` is not usable. |
| 409 | `knowledge_base_empty` | `课程知识库为空` | Catalog is otherwise usable but `chunk_count <= 0`. |

These are string `detail.code` values, not numeric legacy codes, because `TaskStatus.error_code` and Agent error codes already use string identifiers. OpenAPI should document the shape without weakening existing numeric errors elsewhere.

Generation is rejected before task creation. A request that never enters Agent should not create an `AsyncTask`.

## Backend Architecture

Create a shared helper:

`../backend/app/services/course_catalog_gate.py`

Responsibilities:

- `resolve_generation_catalog(db, course_id) -> GenerationCatalogContext`
- Find `CourseOffering` by `id == course_id`.
- Find non-deleted `CourseCatalog` by `CourseOffering.catalog_id`.
- Enforce the ready semantics above.
- Return:
  - `class_course_id`
  - `catalog_id`
  - `catalog_title`
  - `knowledge_status`
  - `degraded: bool`
  - `chunk_count`

Recommended data class:

```python
class GenerationCatalogContext(BaseModel):
    class_course_id: str
    catalog_id: str
    catalog_title: str
    knowledge_status: str
    degraded: bool
    chunk_count: int
```

The helper should raise `HTTPException` with the error shapes above.

### Resource Generation

In `../backend/app/api/v1/resources.py`:

1. Resolve the catalog before creating `AsyncTask`.
2. Keep `AsyncTask.course_id = req.course_id` so task ownership remains tied to the teaching class.
3. Store catalog context in `task.result` with this shape:

```json
{
  "class_course_id": "course123",
  "catalog_id": "catalog123",
  "knowledge_status": "partial",
  "degraded": true
}
```

4. Send Agent payload with:

```json
{
  "course_id": "catalog123"
}
```

5. Preserve `chapter`, `knowledge_point`, `resource_types`, `task_id`, `user_id`, and `webhook_url`.

This intentionally treats Agent `course_id` as the knowledge lookup id. It avoids Agent API drift while aligning retrieval with the CourseCatalog ingestion payload.

### Quiz Generation

In `../backend/app/api/v1/quiz.py` and `../backend/app/services/quiz_service.py`:

1. Resolve the catalog before creating `AsyncTask`.
2. Keep `AsyncTask.course_id = req.course_id`.
3. Assemble personalization context using the teaching class id, because evaluation/profile/quiz history are stored by class `course_id`.
4. Send Agent payload with:

```json
{
  "course_id": "catalog123",
  "class_course_id": "course123"
}
```

`class_course_id` is optional additive metadata for Agent observability. If Agent ignores it, behavior remains valid. OpenAPI does not expose this internal field.

5. Persist generated `QuizQuestion.course_id = req.course_id`, preserving frontend and result queries by teaching class id.

## OpenAPI Updates

Update `../docs/10-client-api/Client-API.openapi.json` and `../docs/10-client-api/API_前端接口规范.md`.

Required changes:

- Update `/resources/generate` description to remove the stale developer-upload wording.
- Document that generation requires the class to bind a usable CourseCatalog knowledge base.
- Add `409` error responses for `course_material_missing` and `knowledge_base_empty`.
- Add equivalent `409` error responses to `/quiz/generate`.
- Document that `partial` may be accepted in degraded mode when chunks exist.
- Document that no task is created when the ready gate rejects a request.

Do not add new request fields in Phase B.

## Frontend Scope

Current frontend has no active resource generation or Quiz generation entry.

Phase B frontend work should be minimal:

- Remove orphan `learningService.triggerResourceGeneration()` if no current page uses it after Backend gating.
- Remove orphan `learningService.getTaskStatus()` in favor of `taskService.getTaskStatus()` if no current page uses it.
- Do not add a new TeacherConsole resource generation panel in this phase.
- Do not add a new Quiz generation button in this phase.

If future UI reintroduces generation, it must consume the documented 409 errors and display:

- `course_catalog_missing`: ask teacher/admin to bind or prepare a resource library.
- `course_material_missing`: ask admin to complete ingestion.
- `knowledge_base_empty`: ask admin to check ingestion output.

## Tests

Backend tests are required before implementation code.

### Shared Gate Tests

Add focused tests for the helper:

- No CourseOffering -> 404 `course_catalog_missing`.
- Missing/deleted catalog -> 404 `course_catalog_missing`.
- `status != ready` -> 409 `course_material_missing`.
- `status=ready`, `knowledge_status=dirty` -> 409 `course_material_missing`.
- `status=ready`, `knowledge_status=ingesting` -> 409 `course_material_missing`.
- `status=ready`, `knowledge_status=failed` -> 409 `course_material_missing`.
- `status=ready`, `knowledge_status=ready`, `chunk_count=0` -> 409 `knowledge_base_empty`.
- `status=ready`, `knowledge_status=partial`, `chunk_count=0` -> 409 `knowledge_base_empty`.
- `status=ready`, `knowledge_status=ready`, `chunk_count>0` -> allowed.
- `status=ready`, `knowledge_status=partial`, `chunk_count>0` -> allowed with `degraded=True`.

### Resource Generation Tests

Add or extend `../backend/tests/test_resources_async.py`:

- Gate rejection returns 409 before creating `AsyncTask`.
- Allowed generation stores class `course_id` on task.
- Allowed generation sends `catalog_id` as Agent payload `course_id`.
- Partial generation sends catalog id and records degraded context in task result.

### Quiz Generation Tests

Add or extend quiz generation tests:

- Gate rejection returns 409 before creating `AsyncTask`.
- Personalization context still reads class-scoped evaluation/profile/wrong points.
- Agent payload `course_id` is the catalog id.
- Generated `QuizQuestion.course_id` remains the teaching class id.

### Frontend/Contract Checks

- `python -m json.tool ../docs/10-client-api/Client-API.openapi.json`
- `npm run lint`
- `npm run build`

Run backend pytest targets for the new gate and changed generation endpoints.

## Migration And Compatibility

No SQL migration is required in Phase B.

Legacy courses without CourseOffering binding cannot use `/resources/generate` or `/quiz/generate`. They should receive `course_catalog_missing`. Existing non-generation student flows can continue to read already persisted resources and questions by legacy `course_id`.

This is intentional: generation should not silently fall back to generic content when no CourseCatalog knowledge base is attached.

## Risks

- Existing tests that call generation on legacy courses must be updated to create a CourseCatalog and CourseOffering, or assert the new rejection.
- Agent logs may become confusing because Agent `course_id` will mean CourseCatalog id for generation while Backend task `course_id` remains class id.
- `partial` acceptance may generate from incomplete material. The degraded flag and status logging are required so this is visible.
- LearningPath remains disconnected from CourseCatalog because KG readiness is out of scope.

## Recommended Implementation Order

1. Add shared gate tests and helper.
2. Apply gate to `/resources/generate`.
3. Apply gate to `/quiz/generate`.
4. Update OpenAPI descriptions and 409 responses.
5. Remove orphan frontend service methods if confirmed unused.
6. Run backend targeted tests plus frontend lint/build.
7. Update `WORKFLOW.md`.
