# Learning Activity Tracking Design

Date: 2026-06-14
Status: Draft approved for planning

## Background

`/learning-effects` now displays KG-node learning progress from `EvaluationData.node_progress`. Mastery state and quiz-derived scores have a real source, but `study_duration_seconds` can only be populated when existing data such as `QuizSession.time_spent` is available. Resource reading time and node browsing time are not currently captured.

The project has `OperationLog`, but it is a system/admin operation log. It is not a learning behavior table and should not be reused for student activity analytics.

## Goal

Introduce event-level learning activity tracking so `/learning-effects` can explain learning duration and node activity with real data.

The first version should answer:

1. Which KG node or resource did the student enter.
2. How long the student spent in a related resource or node practice flow.
3. Which node-level activities can support `node_progress.study_duration_seconds`.

## Non-Goals

- Do not implement heartbeat-level tracking in the first version.
- Do not infer resource preference percentages such as "dynamic demo 60%".
- Do not block learning flows when activity tracking fails.
- Do not use `OperationLog` for learning behavior analytics.
- Do not directly call Agent Service from the frontend.
- Do not track idle/background browser time as reliable study time.

## Product Decision

Use event-level cumulative tracking.

The frontend reports activity when a student:

- Opens a resource detail page.
- Leaves a resource detail page or switches to another resource.
- Selects a KG node in LearningPath.
- Starts a node-scoped quiz.
- Submits a node-scoped quiz.

This avoids high-frequency heartbeat traffic while still giving the evaluation page a real duration source.

## Data Model

Create `learning_activities`.

Recommended fields:

| Field | Type | Notes |
| --- | --- | --- |
| id | string | Primary key |
| user_id | string | Current user |
| course_id | string | Teaching class / course context |
| node_id | string/null | KG node ID when known |
| node_name | string/null | KG node name when known |
| resource_id | string/null | Resource ID when known |
| activity_type | string | Event type |
| duration_seconds | integer/null | Duration for study/submit events |
| occurred_at | datetime | Client event time or server receive time |
| metadata | JSON/null | Small structured context |
| create_time/update_time/is_deleted | standard fields | Match local model style |

Indexes:

- `(user_id, course_id, node_id, is_deleted)`
- `(user_id, course_id, activity_type, occurred_at)`
- `(resource_id, is_deleted)`

## Event Types

### `resource_view`

Sent after `ResourceDetail.jsx` successfully loads a resource.

Required:

- `course_id`
- `resource_id`

Optional:

- `node_id`
- `node_name`

Duration:

- `null`

### `resource_study`

Sent when leaving a loaded resource detail page or switching resource ID.

Required:

- `course_id`
- `resource_id`
- `duration_seconds`

Optional:

- `node_id`
- `node_name`

Duration rules:

- Minimum useful duration: 5 seconds.
- Maximum accepted single event duration: 14,400 seconds (4 hours).
- Frontend does not send events under 5 seconds.
- Backend rejects negative values and values over 14,400 seconds with `422`.

### `node_view`

Sent when a student selects a KG node in LearningPath.

Required:

- `course_id`
- `node_id`
- `node_name`

Duration:

- `null`

### `node_practice_start`

Sent when `Quiz.jsx` loads node-scoped questions with `node_id`.

Required:

- `course_id`
- `node_id`

Optional:

- `node_name`
- `quiz_id`

Duration:

- `null`

### `node_practice_submit`

Sent when `Quiz.jsx` submits a node-scoped quiz.

Required:

- `course_id`
- `node_id`
- `quiz_id`
- `duration_seconds`

Optional:

- `node_name`

Duration:

- Use measured quiz page elapsed time instead of the current fixed `time_spent: 120`.

## API Contract

Add:

```text
POST /api/v1/learning-activities
```

Request:

```json
{
  "course_id": "course-id",
  "activity_type": "resource_study",
  "node_id": "node-id",
  "node_name": "指针基础",
  "resource_id": "resource-id",
  "quiz_id": "quiz-id",
  "duration_seconds": 180,
  "occurred_at": "2026-06-14T10:00:00Z",
  "metadata": {
    "source": "resource_detail"
  }
}
```

Response:

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": "activity-id"
  }
}
```

The endpoint accepts one event per request. Batch submission is out of scope for the first version.

## Backend Rules

- Require authentication.
- Verify the current user has access to `course_id`.
- For `resource_id`, verify the resource is readable within the course resource scope.
- For `node_id`, prefer resolving the active KG node name when `node_name` is missing.
- Reject unknown `activity_type`.
- Reject negative duration.
- Reject single durations over 4 hours with `422`.
- Store `occurred_at` from client only when parseable; otherwise use server time.

Tracking failures should not affect normal learning endpoints.

## Evaluation Aggregation

Update `/evaluation` node progress aggregation:

1. Resolve the current KG node scope.
2. Aggregate `LearningActivity.duration_seconds` by `(user_id, course_id, node_id)`.
3. Add the aggregated duration to `node_progress.study_duration_seconds`.
4. Keep `null` when no reliable activity record exists.

Quiz evidence remains the source of `mastery_score`. Activity duration does not imply mastery.

## Frontend Capture Points

### `ResourceDetail.jsx`

- On successful resource load, send `resource_view`.
- Start a timer after the resource loads.
- On unmount or resource ID change, send `resource_study` if elapsed time is at least 5 seconds.
- Use `navigator.sendBeacon` only if the existing API client pattern can support auth safely; otherwise use normal async API calls and accept best-effort delivery.

### `LearningPath.jsx`

- When `selectedNodeId` changes and the selected node is known, send `node_view`.
- Do not spam duplicate events for the same selected node during initial render.

### `Quiz.jsx`

- When questions load and URL has `node_id`, send `node_practice_start`.
- Track elapsed quiz time from question load to submit.
- Submit real `time_spent` to `/quiz/submit`.
- After successful or attempted submit, send `node_practice_submit`.

## Error Handling

Frontend:

- Activity tracking errors are logged with `console.warn`.
- No toast or blocking UI.
- No retry loop in the first version.

Backend:

- Validation failures return normal error responses.
- Evaluation aggregation ignores malformed/deleted activity rows.

## Privacy And Data Minimization

- Store only learning context, not raw page content.
- `metadata` should remain small and structured.
- Do not store answer text in activity metadata; quiz answers already live in quiz tables.

## Testing Strategy

Backend:

- Student can create activity for an enrolled/owned course.
- User cannot create activity for inaccessible course.
- Invalid activity type is rejected.
- Negative or excessive duration is rejected with `422`.
- `/evaluation` includes activity duration in `node_progress.study_duration_seconds`.

Frontend:

- `ResourceDetail` sends `resource_view` and `resource_study`.
- `LearningPath` sends `node_view` on node selection.
- `Quiz` submits measured `time_spent` and sends node practice events.
- Tracking failure does not block resource display, node selection, or quiz submit.

Contract:

- OpenAPI JSON parses.
- Markdown API spec documents activity request and response fields.

## Implementation Defaults

1. Add a dedicated `LearningActivity` model and migration.
2. Add `learningActivityService.trackActivity()`.
3. Implement single-event `POST /learning-activities`.
4. Use normal authenticated API calls for frontend events.
5. Reject durations over 4 hours with `422`.
6. Keep heartbeat and batch submission out of scope.
