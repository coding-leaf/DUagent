# CourseCatalog Ready Gate Baseline

## Purpose

This document rebuilds the current facts for the next Phase B design:

```text
CourseCatalog ingestion -> CourseOffering binding -> resource generation / Quiz generation ready gate
```

The facts below use current code as the source of truth. Older progress notes and draft plans are treated only as historical context.

## Current Data Model

### CourseCatalog

Current ORM: `../backend/app/models/catalog.py`.

`course_catalogs` is the administrator-owned shared course content asset.

Important fields:

- `id`
- `title`
- `description`
- `status`
- `knowledge_status`
- `material_count`
- `last_ingestion_task_id`
- `last_ingestion_status`
- `chunk_count`
- `last_error`
- `is_deleted`

`status` currently controls whether a catalog can be bound to a teacher class.

`knowledge_status` currently tracks knowledge base freshness and ingestion quality.

Observed `CourseCatalog.status` values in current code/tests:

- `draft`
- `ingesting`
- `ready`
- `failed`

Observed `CourseCatalog.knowledge_status` values in current code/tests:

- `draft`
- `dirty`
- `ingesting`
- `ready`
- `partial`
- `failed`

### CourseCatalogMaterial

`course_catalog_materials` stores original uploaded or registered materials for a catalog.

Important fields:

- `id`
- `catalog_id`
- `filename`
- `source_type`
- `storage_uri`
- `file_size`
- `chunk_count`
- `last_error`
- `ingested_at`
- `status`
- `is_deleted`

Observed material statuses:

- `uploaded`
- `ingesting`
- `ingested`
- `failed`

The upload endpoint accepts `.txt`, `.md`, and `.pdf` files and writes them under the configured CourseCatalog storage root. Backend responses do not expose absolute server paths.

### CourseOffering

`course_offerings` binds teacher-owned teaching classes to shared catalogs.

Important fields:

- `id`
- `name`
- `description`
- `catalog_id`
- `teacher_id`
- `class_code`
- `is_deleted`

Current class creation behavior in `../backend/app/api/v1/courses.py`:

- If `catalog_id` is present, Backend loads the catalog.
- Missing catalog returns 404.
- `catalog.status != "ready"` returns 409.
- `knowledge_status` is not checked during class creation.
- The created `CourseOffering.id` is the same as the legacy `courses.id`, preserving current course list and enrollment compatibility.

## Current Ingestion Chain

Current API: `../backend/app/api/v1/catalogs.py`.

Admin-facing endpoints:

- `GET /api/v1/admin/course-catalogs`
- `POST /api/v1/admin/course-catalogs`
- `GET /api/v1/admin/course-catalogs/{catalog_id}`
- `POST /api/v1/admin/course-catalogs/{catalog_id}/materials/upload`
- `POST /api/v1/admin/course-catalogs/{catalog_id}/materials`
- `GET /api/v1/admin/course-catalogs/{catalog_id}/materials`
- `GET /api/v1/admin/course-catalogs/{catalog_id}/knowledge-status`
- `POST /api/v1/admin/course-catalogs/{catalog_id}/ingestions`

Teacher/user-facing catalog endpoint:

- `GET /api/v1/course-catalogs?status=ready`

Current ingestion flow:

```text
Admin uploads or registers material
-> Backend creates CourseCatalogMaterial(status=uploaded)
-> ready catalog becomes status=ready, knowledge_status=dirty
-> non-ready catalog remains status=draft, knowledge_status=draft
-> Admin starts ingestion
-> Backend selects material.status in uploaded/failed
-> Backend creates AsyncTask(task_type=course_catalog_ingestion)
-> Backend background task calls Agent /agent/v1/knowledge/ingestions
-> Agent returns material results and chunk count
-> Backend updates material/catalog/task status
```

Current status outcomes:

- First ingestion all success: `status=ready`, `knowledge_status=ready`, task `completed`.
- First ingestion partial success: `status=ready`, `knowledge_status=partial`, task `failed`.
- First ingestion all failure: `status=failed`, `knowledge_status=failed`, task `failed`.
- Incremental upload to ready catalog: `status=ready`, `knowledge_status=dirty`.
- Incremental ingestion success: `status=ready`, `knowledge_status=ready`, task `completed`.
- Incremental ingestion failure or partial failure: `status=ready`, `knowledge_status=partial`, task `failed`.
- Ingestion in progress: `knowledge_status=ingesting`; `status=ingesting` only for first ingestion, otherwise `status=ready`.

Important current implication:

`status=ready` means the catalog is bindable. It does not always mean the knowledge base is fully synchronized, because `knowledge_status` can be `dirty` or `partial` while `status` stays `ready`.

## Current Frontend State

Admin UI:

- `src/pages/AdminConsole.jsx` lists and creates CourseCatalog records.
- `src/components/admin/CourseCatalogDrawer.jsx` handles material listing, upload, ingestion triggering, and task polling.
- `src/api/services/admin.js` wraps the Admin CourseCatalog endpoints.
- `src/api/services/task.js` wraps `GET /tasks/{task_id}`.

Teacher UI:

- `src/components/CreateCourseDialog.jsx` loads `courseService.getReadyCatalogs()`.
- Teacher class creation requires selecting a ready catalog.
- The dialog uses catalog `status=ready` from `GET /course-catalogs?status=ready`.
- It does not filter on `knowledge_status` client-side.

Resource generation UI:

- `TeacherConsole` currently has no resource generation panel.
- `src/api/services/learning.js` still exposes `triggerResourceGeneration(params)` and `getTaskStatus(taskId)`.
- `triggerResourceGeneration()` is currently an orphan service method: it is available but not called by any page.

## Current Resource Generation Behavior

Current backend endpoint: `../backend/app/api/v1/resources.py`.

`POST /api/v1/resources/generate` currently:

- Requires `teacher`.
- Creates `AsyncTask(task_type="resource_generation")`.
- Uses the request `course_id` directly.
- Passes `task_id`, `user_id`, `course_id`, `chapter`, `knowledge_point`, `resource_types`, and `webhook_url` to Agent `/agent/v1/resources/generate`.
- Does not load `CourseOffering`.
- Does not load `CourseCatalog`.
- Does not check `CourseCatalog.status`.
- Does not check `CourseCatalog.knowledge_status`.
- Does not check whether Qdrant has chunks for the bound catalog.

Agent resource generation uses `request.course_id` for retrieval context. Current ingestion writes Qdrant payloads with `CourseCatalog.id`. Since a teaching class uses legacy `courses.id` while its catalog id is stored separately in `CourseOffering.catalog_id`, Phase B must define how generation resolves the correct knowledge id.

## Current Quiz Generation Behavior

Current backend endpoint: `../backend/app/api/v1/quiz.py`.

`POST /api/v1/quiz/generate` currently:

- Creates `AsyncTask(task_type="quiz_generation")`.
- Calls `quiz_service.assemble_generate_payload(current_user.id, req.course_id, req, db)`.
- Passes the assembled payload to Agent `/agent/v1/assessment/generate-questions`.
- Does not load `CourseOffering`.
- Does not load `CourseCatalog`.
- Does not check `CourseCatalog.status`.
- Does not check `CourseCatalog.knowledge_status`.
- Does not check whether Qdrant has chunks for the bound catalog.

The personalization payload can include evaluation, profile, wrong points, and current path node. It still uses the request `course_id` as the Agent `course_id`.

## OpenAPI Drift And Stale Contract Notes

Current OpenAPI has CourseCatalog endpoints and schemas, including ingestion fields and `course_catalog_ingestion` task type.

Known stale or incomplete points:

- `POST /resources/generate` description still says course knowledge is uploaded and vectorized by developers during development and not through frontend interfaces. This no longer matches the current Admin CourseCatalog upload and ingestion chain.
- `POST /resources/generate` does not document CourseCatalog ready gate errors.
- `POST /quiz/generate` does not document CourseCatalog ready gate errors.
- `TaskStatus.error_code` is generic and does not yet define Phase B error codes such as `course_material_missing` or `knowledge_base_empty`.
- No current Client API field maps a teaching class `course_id` to the knowledge id that Agent should use, except the backend-side `CourseOffering.catalog_id`.

## Baseline Conclusion

The current product chain has successfully built the CourseCatalog ingestion foundation, but AI generation consumers have not been moved onto that foundation yet.

Phase B should not add more UI first. It should first add a shared backend ready gate and knowledge id resolution for both:

- `POST /resources/generate`
- `POST /quiz/generate`

The design must explicitly decide:

- which `knowledge_status` values are usable;
- whether `partial` is allowed;
- how to handle `dirty`;
- whether checks reject before task creation or create a failed task;
- how Agent receives the CourseCatalog knowledge id while preserving existing Client API shape;
- what to do with the orphan frontend `triggerResourceGeneration()` method;
- whether LearningPath/KG is included now or deferred.
