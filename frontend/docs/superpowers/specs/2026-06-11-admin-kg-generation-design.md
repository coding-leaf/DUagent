# Admin CourseCatalog KG Generation Design

## Background

Admin CourseCatalog upload, ingestion, catalog-level resource generation, and KG-node resource mounting have reached the first usable backend/frontend loop. The remaining product gap is that active course knowledge graphs are still created or imported through backend CLI/manual operations, while Admin users have no product entry to refresh the KG before triggering KG-node resource generation.

The current student `LearningPath` page is a consumer of an existing active KG. It must not become a KG generation surface. This design adds an Admin-owned KG generation workflow inside the existing CourseCatalog drawer.

## Goals

1. Let an Admin trigger KG generation for a CourseCatalog from the existing resource library drawer.
2. Convert the current backend KG CLI logic into a reusable backend service shared by CLI and API.
3. Persist each generated KG as a new `course_knowledge_graphs` version and optionally activate it.
4. Keep the workflow task-based so the frontend can poll `/tasks/{task_id}`.
5. Make `kg_not_ready` from resource generation actionable by guiding the Admin to generate the KG first.

## Non-Goals

- Do not add KG generation controls to the student `/learning-path` page.
- Do not trigger student personalized LearningPath refresh.
- Do not restore teacher-facing `/resources/generate`.
- Do not make the API shell out to `tools/generate_knowledge_graph.py`.
- Do not automatically extract an outline from uploaded PDF/chunk content in this first version.
- Do not add a new database table or CourseCatalog KG status columns in the first version.

## User Flow

1. Admin opens an existing CourseCatalog in `CourseCatalogDrawer`.
2. The drawer shows a "知识图谱" section with active KG status.
3. Admin chooses an input mode:
   - paste course outline text; or
   - paste/import a KG JSON object with `nodes` and `edges`.
4. Admin clicks "刷新知识图谱".
5. Backend creates a `kg_generation` async task and runs KG generation in the background.
6. The drawer polls `/tasks/{task_id}`.
7. When the task completes, the drawer refreshes KG status and shows version, node count, edge count, strategy, and update time.
8. Admin can then trigger the existing catalog resource generation. If that endpoint returns `kg_not_ready`, the drawer prompts the Admin to refresh KG first.

## API Design

### Create KG Generation Task

```http
POST /api/v1/admin/course-catalogs/{catalog_id}/knowledge-graphs/generations
```

Admin-only.

Request:

```json
{
  "source_type": "outline_text",
  "outline_text": "课程大纲文本",
  "activate": true
}
```

Alternative request:

```json
{
  "source_type": "kg_json",
  "kg_json": {
    "nodes": [
      { "id": "pointer", "name": "指针", "chapter": "第 6 章 指针" }
    ],
    "edges": []
  },
  "activate": true
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
    "course_id": "string",
    "status": "processing"
  }
}
```

Validation and errors:

- `403`: non-admin user.
- `404`: CourseCatalog does not exist.
- `409`: no non-deleted `CourseOffering` is bound to the catalog. Error code: `offering_missing`.
- `409`: another KG generation task is already processing for this catalog. Error code: `kg_task_running`.
- `422`: invalid `source_type`, empty `outline_text`, or invalid `kg_json`.

KG generation does not require `CourseCatalog.knowledge_status in {"ready", "partial"}` and does not require `chunk_count > 0` for `outline_text` or `kg_json` modes. Those checks belong to resource generation because resource generation retrieves catalog knowledge chunks. If a later Route A grounding or chunk-derived KG mode is added, that mode must define its own knowledge-base ready gate.

### Get KG Status

```http
GET /api/v1/admin/course-catalogs/{catalog_id}/knowledge-graphs
```

Admin-only.

Response:

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "catalog_id": "string",
    "course_id": "string",
    "active_graph": {
      "id": "string",
      "version": 3,
      "node_count": 108,
      "edge_count": 100,
      "source_type": "outline_llm",
      "generation_strategy": "legacy_outline",
      "metrics": {},
      "create_time": "2026-06-11T00:00:00Z",
      "update_time": "2026-06-11T00:00:00Z"
    },
    "last_generation_task": {
      "task_id": "string",
      "status": "completed",
      "error_code": null,
      "error_message": ""
    }
  }
}
```

If no active KG exists, `active_graph` is `null`.

## Course Binding Rule

The API resolves the target course through `CourseOffering`, not through a separate TeachingClass lookup.

Selection rule:

1. Query non-deleted `CourseOffering` rows where `catalog_id = :catalog_id`.
2. Order by `create_time ASC, id ASC`.
3. Use the first row's `id` as the `course_id` for `course_knowledge_graphs.course_id`.
4. If no row exists, reject with `409 offering_missing`.

This mirrors the existing CourseCatalog-to-course mapping used by Admin catalog resource generation.

## Backend Design

### Service Extraction

Create a backend KG generation service under `app/services`, containing the reusable pieces currently embedded in `tools/generate_knowledge_graph.py`:

- generate KG JSON from outline text via LLM;
- validate and clean `nodes` and `edges`;
- load/validate existing KG JSON;
- optionally support existing grounding-prune logic through service-level functions;
- create a new `CourseKnowledgeGraph` version via `create_knowledge_graph_version`;
- return a stable result payload with `graph_id`, `version`, node count, edge count, source type, generation strategy, and metrics.

The CLI should call this service instead of owning generation logic. The Admin API should call the same service from its background task. This keeps CLI behavior available while avoiding a shell dependency in the web API.

### Async Task

Use `AsyncTask.task_type = "kg_generation"` because it fits the current `String(30)` limit.

Task `result` should include:

```json
{
  "catalog_id": "string",
  "course_id": "string",
  "source_type": "outline_text",
  "activate": true,
  "graph_id": "string",
  "version": 1,
  "node_count": 108,
  "edge_count": 100,
  "generation_strategy": "legacy_outline"
}
```

On failure, write short `error_code` values that fit the current `String(20)` column, for example:

- `offering_missing`
- `kg_task_running`
- `kg_invalid_input`
- `kg_llm_failed`
- `kg_save_failed`

### Concurrency

Only one KG generation task may process for a catalog at a time.

First version uses `AsyncTask` instead of adding CourseCatalog columns:

- before creating a new task, query for non-deleted `AsyncTask` where `task_type = "kg_generation"`, `status = "processing"`, and `result.catalog_id = :catalog_id`;
- if found, return `409 kg_task_running`;
- encapsulate the MySQL JSON predicate in one helper to avoid duplicated JSON path expressions.

This does not prevent an external CLI from writing a KG version at the same time. That is acceptable for the first version because active-version creation already deactivates other versions atomically within one database transaction. Operationally, admins should avoid running the CLI manually while a UI task is processing.

## Frontend Design

Update `CourseCatalogDrawer` only.

Add a "知识图谱" section near the existing knowledge base/resource generation sections. It should show:

- active KG status: not generated, ready, generating, or failed;
- active version;
- node count and edge count;
- source type and generation strategy;
- latest task status and error message when present.

Controls:

- segmented input mode: outline text or KG JSON;
- textarea for outline text;
- textarea or file-like paste area for KG JSON;
- activate checkbox defaulted to true;
- "刷新知识图谱" button.

State behavior:

- disable the button while a KG task is processing;
- poll `/tasks/{task_id}` using existing task service;
- after completion, refresh KG status and drawer details;
- if existing resource generation returns `kg_not_ready`, display an inline prompt in the resource generation section directing the Admin to refresh KG first.

The frontend must not synthesize fake KG metrics. Empty or missing backend fields should render as unknown/not generated.

## Contract Updates

Update both Client API documents:

- `../docs/10-client-api/Client-API.openapi.json`
- `../docs/10-client-api/API_前端接口规范.md`

Add schemas for:

- KG generation request;
- KG generation response;
- Admin KG status response;
- active KG summary;
- last KG generation task summary.

Add `kg_generation` to task type descriptions.

## Testing Plan

Backend tests:

- non-admin cannot call Admin KG endpoints;
- missing catalog returns 404;
- missing `CourseOffering` returns `409 offering_missing`;
- duplicate processing task returns `409 kg_task_running`;
- `outline_text` task creates an active KG version;
- `kg_json` task validates structure and creates an active KG version;
- invalid `kg_json` returns 422;
- failure in LLM/service marks task failed with a short error code;
- CLI still works through the extracted service.

Frontend tests:

- drawer renders KG section and empty state;
- submitting outline text calls the Admin KG generation endpoint;
- task polling updates the section on completion;
- failed task displays backend error;
- resource generation `kg_not_ready` prompts KG refresh instead of showing a generic failure.

Verification commands:

```bash
npm run lint
npm run build
npm run test:e2e -- e2e/specs.spec.js -g "Admin course catalog"
```

Backend commands should be run from `../backend` with the project venv and MySQL test database, following existing test patterns for catalog resource generation and KG versioning.

## Rollout Notes

This feature makes Admin KG generation product-visible but does not claim LearningPath ready gate completion. After Admin KG generation and KG-node resource generation are stable, the next separate design should evaluate LearningPath refresh and LearningPath-KG resource hit quality.
