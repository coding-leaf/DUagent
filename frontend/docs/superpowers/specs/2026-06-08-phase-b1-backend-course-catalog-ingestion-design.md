# Phase B1 Backend CourseCatalog Ingestion Orchestration Design

## Background

Phase A has separated shared course content assets from teacher-owned teaching classes:

- `CourseCatalog` is the administrator-managed shared course content asset.
- `CourseOffering` / class is the teacher-owned teaching organization.
- Teachers create classes by binding a `ready` CourseCatalog.

Phase B1 has already started on the Agent Service side. Agent Service now exposes a knowledge ingestion API that can receive a Backend CourseCatalog ID plus controlled storage paths, read course materials from the shared storage root, parse supported files, chunk content, embed it, and upsert it into Qdrant with `payload.course_id = CourseCatalog.id`.

The current gap is the Backend middle layer. Backend can create CourseCatalog records and register material metadata, but it does not yet:

- accept real material file uploads;
- save uploaded files into controlled shared storage;
- create a CourseCatalog ingestion task;
- call Agent Service `/agent/v1/knowledge/ingestions`;
- update CourseCatalog, CourseCatalogMaterial, and AsyncTask state from Agent results.

This design closes that Backend orchestration gap.

## Goals

Build the Backend orchestration slice for Phase B1:

```text
Admin uploads .txt/.md/.pdf
-> Backend saves file under controlled CourseCatalog storage
-> Backend records CourseCatalogMaterial
-> Admin triggers ingestion
-> Backend returns 202 + task_id immediately
-> Backend background task calls Agent Service
-> Agent ingests files into Qdrant using CourseCatalog.id
-> Backend updates material/catalog/task status
-> Admin or future frontend polls GET /tasks/{task_id} and knowledge-status
```

The endpoint should behave asynchronously from the Client API perspective while keeping the Backend background worker implementation linear: one background task calls the existing Agent HTTP API and waits for its response.

## Non-Goals

This phase does not implement:

- AdminConsole upload and ingestion UI.
- Agent webhook/callback for knowledge ingestion.
- Agent-side task model changes.
- KG generation or KG ready checks.
- Student AIChat / Quiz / LearningPath / ResourceDetail consumption of CourseCatalog.
- Teacher resource generation entry restoration.
- Deleting, replacing, or rebuilding existing materials.
- Object storage such as MinIO or S3.
- `.docx`, `.pptx`, images, video, audio, or OCR.

## Existing Constraints

Current code constraints shape the design:

- `CourseCatalog.knowledge_status` currently defaults to `draft`.
- `CourseCatalogMaterial.status` currently defaults to `uploaded`.
- Existing `admin_create_catalog_material()` resets both `CourseCatalog.status` and `knowledge_status` to `draft` when adding material. This must be corrected for `ready` catalogs so class binding remains valid.
- `AsyncTask.course_id` is a foreign key to `courses.id`; it must not store `catalog_id`.
- `catalog_id` and material IDs for ingestion tasks should be stored in `AsyncTask.result`.
- Agent ingestion result currently identifies materials by `storage_uri`, not `material_id`; Backend should map Agent results back to materials by `storage_uri` in this phase to avoid expanding Agent API.

## Architecture

```text
Admin / future AdminConsole
  -> Backend Client API
    -> CourseCatalog upload endpoint
    -> local shared storage
    -> CourseCatalogMaterial rows
    -> ingestion trigger endpoint
    -> AsyncTask row
    -> FastAPI background task
      -> Agent Service /agent/v1/knowledge/ingestions
      -> Agent parses/chunks/embeds/upserts Qdrant
      -> Backend updates SQL status
  -> GET /tasks/{task_id}
  -> GET /admin/course-catalogs/{catalog_id}/knowledge-status
```

Backend remains the authority for administrator permissions, catalog state, material state, file storage paths, and task state.

Agent Service remains the authority for parsing, chunking, embedding, and Qdrant writes.

## Backend Data Model

Extend `CourseCatalog`:

- `last_ingestion_task_id: str | None`
- `last_ingestion_status: str | None`
- `chunk_count: int`
- `last_error: str | None`

Extend `CourseCatalogMaterial`:

- `file_size: int`
- `chunk_count: int`
- `last_error: str | None`
- `ingested_at: datetime | None`

Keep existing defaults:

- `CourseCatalog.status = draft`
- `CourseCatalog.knowledge_status = draft`
- `CourseCatalogMaterial.status = uploaded`

No `catalog_id` column is added to `AsyncTask` in this phase. CourseCatalog task context is stored in `AsyncTask.result`, for example:

```json
{
  "catalog_id": "cat123",
  "material_ids": ["mat1", "mat2"],
  "storage_uris": ["course_catalogs/cat123/mat1/intro.md"]
}
```

No `storage_type` column is added in this phase. All Phase B1 materials are local files under the configured storage root; a storage type field can be introduced later when a real non-local storage backend exists.

## Storage Rules

Add Backend settings:

```text
COURSE_CATALOG_STORAGE_ROOT=storage/course_catalogs
COURSE_CATALOG_MAX_UPLOAD_BYTES=20971520
```

Supported upload suffixes:

- `.txt`
- `.md`
- `.pdf`

Files are stored under:

```text
{COURSE_CATALOG_STORAGE_ROOT}/{catalog_id}/{material_id}/{safe_filename}
```

Database `storage_uri` stores a relative path compatible with Agent Service resolution:

```text
course_catalogs/{catalog_id}/{material_id}/{safe_filename}
```

Backend responses must not expose absolute server paths.

Filename handling:

- use basename only;
- reject empty names;
- reject path traversal;
- reject unsupported suffixes;
- reject empty files;
- reject files above `COURSE_CATALOG_MAX_UPLOAD_BYTES`.

## Client API

### Upload Material

```text
POST /api/v1/admin/course-catalogs/{catalog_id}/materials/upload
Content-Type: multipart/form-data
field: file
```

Behavior:

- Requires `admin`.
- Rejects missing catalog with 404.
- Rejects upload while `catalog.status == ingesting` or `catalog.knowledge_status == ingesting` with 409.
- Saves the file to controlled local storage.
- Creates `CourseCatalogMaterial(status=uploaded)`.
- Increments `material_count`.
- Does not return `storage_uri`.

Catalog state after upload:

- If catalog was `ready`, keep `status=ready` and set `knowledge_status=dirty`.
- If catalog was not `ready`, keep or set `status=draft` and `knowledge_status=draft`.

The existing JSON material registration endpoint can remain for compatibility, but it should follow the same state rule: adding material to a `ready` catalog must not reset `status` to `draft`.

### Trigger Ingestion

```text
POST /api/v1/admin/course-catalogs/{catalog_id}/ingestions
```

Behavior:

- Requires `admin`.
- Rejects missing catalog with 404.
- Rejects concurrent ingestion with 409.
- Selects materials with `status in ("uploaded", "failed")`.
- Rejects when no selectable materials exist with 409.
- Sets selected materials to `ingesting`.
- Sets `catalog.knowledge_status = ingesting`.
- Sets `catalog.status = ingesting` only for first ingestion, meaning catalog is not already `ready`.
- Keeps `catalog.status = ready` for incremental ingestion.
- Creates `AsyncTask(task_type="course_catalog_ingestion", status="processing")`.
- Stores catalog and material context in `task.result`.
- Returns immediately:

```json
{
  "code": 202,
  "message": "accepted",
  "data": {
    "task_id": "task123",
    "catalog_id": "cat123",
    "status": "processing"
  }
}
```

The background task then calls:

```text
POST /agent/v1/knowledge/ingestions
```

with:

```json
{
  "catalog_id": "cat123",
  "materials": [
    {"storage_uri": "course_catalogs/cat123/mat1/intro.md"}
  ]
}
```

### Knowledge Status

Extend:

```text
GET /api/v1/admin/course-catalogs/{catalog_id}/knowledge-status
```

Response data should include:

- `catalog_id`
- `status`
- `knowledge_status`
- `material_count`
- `chunk_count`
- `pending_material_count`
- `failed_material_count`
- `last_ingestion_task_id`
- `last_ingestion_status`
- `last_error`

## State Machine

`CourseCatalog.status` controls whether a catalog can be bound by teacher classes.

`CourseCatalog.knowledge_status` controls knowledge base quality and synchronization.

| Scenario | catalog.status | catalog.knowledge_status | material.status | task.status |
| --- | --- | --- | --- | --- |
| Upload material, first time | `draft` | `draft` | `uploaded` | - |
| Upload material to ready catalog | `ready` | `dirty` | `uploaded` | - |
| Start first ingestion | `ingesting` | `ingesting` | `ingesting` | `processing` |
| Start incremental ingestion | `ready` | `ingesting` | `ingesting` | `processing` |
| All selected materials succeed | `ready` | `ready` | `ingested` | `completed` |
| First ingestion fails | `failed` | `failed` | `failed` | `failed` |
| Incremental ingestion partially fails | `ready` | `partial` | per item: `ingested` / `failed` | `failed` |
| Incremental ingestion all fail | `ready` | `partial` | `failed` | `failed` |

`partial` means the existing ready knowledge base can still be used, but new or retried material did not fully enter Qdrant.

## Background Task Logic

The background task is linear:

1. Load task, catalog, and selected materials.
2. Call Agent Service `/agent/v1/knowledge/ingestions`.
3. Map Agent material results back to DB materials by `storage_uri`.
4. For each successful item:
   - set material `status=ingested`;
   - set `chunk_count`;
   - set `ingested_at`;
   - clear `last_error`.
5. For each failed or missing item:
   - set material `status=failed`;
   - set `last_error`.
6. Update catalog:
   - all success: `status=ready`, `knowledge_status=ready`;
   - first ingestion full failure: `status=failed`, `knowledge_status=failed`;
   - first ingestion partial success: `status=ready`, `knowledge_status=partial`;
   - incremental failure: `status=ready`, `knowledge_status=partial`.
7. Update task:
   - all success: `completed`, progress `100`;
   - any failure: `failed`, progress `100`, `error_code`, `error_message`.

If Agent Service is unreachable or raises `AgentServiceError`, all selected materials become `failed`; first ingestion marks catalog `failed`, incremental ingestion marks catalog `partial`.
If Agent returns mixed material results, any ingested material with positive chunk count means content entered Qdrant; a first ingestion with at least one successful chunk should become `status=ready`, `knowledge_status=partial`, not `failed`.

## Error Handling

Recommended errors:

| HTTP | Code | Message | Scenario |
| --- | --- | --- | --- |
| 400 | `40020` | `文件名不合法` | unsafe filename |
| 400 | `40021` | `不支持的资料类型` | unsupported suffix |
| 400 | `40022` | `资料文件不能为空` | empty upload |
| 413 | `41320` | `资料文件过大` | file too large |
| 404 | existing | `课程资源库不存在` | missing catalog |
| 409 | `40911` | `课程资源库正在入库中` | concurrent ingestion or upload during ingestion |
| 409 | `40912` | `没有待入库资料` | trigger without uploaded/failed materials |
| 502/async task failed | `agent_ingestion_failed` | Agent failure | background task error |

For ingestion trigger, Agent failures should not change the initial `202` response. They are reflected through `GET /tasks/{task_id}` and `knowledge-status`.

## OpenAPI Contract

Update `../docs/10-client-api/Client-API.openapi.json`:

- Add upload endpoint with `multipart/form-data`.
- Add ingestion trigger endpoint with `202` response.
- Extend `CourseCatalogMaterialItem`.
- Extend `CourseCatalogKnowledgeStatus`.
- Add `CourseCatalogIngestionResponse`.
- Document error responses for 400, 409, and 413.

No Agent API documentation change is required in Client API, because frontend only talks to Backend.

## Tests

Backend focused tests should cover:

- model/config fields exist;
- upload `.md` succeeds and saves a file under the configured root;
- upload response does not expose absolute `storage_uri`;
- unsupported suffix returns 400;
- empty file returns 400;
- oversize file returns 413;
- upload during ingestion returns 409;
- adding material to a ready catalog keeps `catalog.status=ready` and sets `knowledge_status=dirty`;
- ingestion trigger returns `202 + task_id`;
- ingestion task stores `catalog_id` in `AsyncTask.result`, not `AsyncTask.course_id`;
- no uploaded/failed materials returns 409;
- successful Agent response marks catalog ready, materials ingested, task completed;
- first ingestion Agent failure marks catalog failed and task failed;
- incremental partial failure keeps catalog ready and sets knowledge_status partial;
- Agent result mapping uses `storage_uri`.

Existing `tests/test_course_catalogs.py` should continue to pass, with expectations updated only where the previous ready-catalog reset behavior was incorrect.

## Verification

Expected focused verification:

```bash
cd ../backend && pytest tests/test_course_catalog_ingestion.py tests/test_course_catalogs.py -q
python -m json.tool ../docs/10-client-api/Client-API.openapi.json >/tmp/client-api-openapi-check.json
```

If frontend is touched in a later slice:

```bash
npm run lint
npm run build
```

## Follow-On Work

After this Backend slice is complete, the next slice should add AdminConsole upload and ingestion controls using the new Backend endpoints and existing `GET /tasks/{task_id}` polling.

Later phases should then move AIChat, Quiz, LearningPath, and ResourceDetail to resolve knowledge through:

```text
class_id -> catalog_id -> CourseCatalog -> Qdrant / KG / published resources
```
