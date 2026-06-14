# Evidence-Based Student Profile Rules Design

## Context

`/profile` and `/learning-effects` are already connected to real APIs, but several student profile fields are not yet explainable enough:

- `guidance_level` can be manually changed by the user, while profile refresh may currently overwrite course profile guidance.
- `modal_preference` and `resource_preference` are partly derived from available course resource counts, which does not prove student preference.
- `knowledge_coordinates` and `cognitive_blindspots` can be empty because they depend on quiz chapter history rather than the course KG node range.
- `discipline_badge` currently behaves like a rough score label, not a transparent achievement.
- Agent-generated profile fields make the source of truth hard to verify and hard to explain.

The new design makes Backend rule computation the authority for core profile fields. Agents may generate explanations or suggestions, but may not overwrite authoritative profile values.

## Goals

1. Make every visible profile field traceable to a clear data source and calculation rule.
2. Guarantee that user-selected `L1 / L2 / L3` is the effective tutoring guidance level.
3. Derive profile and learning-effect fields from MySQL data, KG nodes, quiz results, and learning activity events.
4. Keep Agent use limited to non-authoritative explanation or recommendation text.
5. Keep `/profile` and `/learning-effects` consistent for KG node mastery and weak-point state.

## Non-Goals

- Do not infer modal preference from AIChat intent classification.
- Do not infer profile fields from long-term memory.
- Do not let Agent output directly replace core profile fields.
- Do not use mock data or course resource availability as a substitute for student behavior.
- Do not introduce a complex recommendation model.

## Authoritative Data Flow

Frontend keeps the existing user-facing flow:

- `GET /profile?course_id=...` renders the student profile.
- `POST /profile/refresh` refreshes the profile.
- `PUT /users/me` updates the manually selected guidance level.
- `GET /evaluation?course_id=...` renders learning effects.

Backend changes profile refresh from Agent-generated core fields to rule-computed core fields:

1. Read user learning context:
   - `users.major`
   - `users.grade`
   - `users.guidance_level`
2. Read course context:
   - teaching class / course offering
   - course name or direction
   - active KG nodes for the bound catalog
3. Read learning behavior:
   - `learning_activities.activity_type`
   - `learning_activities.duration_seconds`
   - `learning_activities.node_id`
   - `learning_activities.resource_id`
   - `learning_activities.occurred_at`
4. Read quiz and evaluation evidence:
   - quiz sessions and node-bound answers
   - node-level score, correctness, attempt counts, latest attempt
   - existing `evaluation.node_progress`, if already aligned to the same aggregation rules
5. Compute profile fields with deterministic rules.
6. Persist the resulting `user_profiles` record.

Agent boundaries:

- AIChat Agent receives only de-identified learning context:
  - `major`
  - `grade`
  - `guidance_level`
  - course name or course direction
  - active KG nodes
  - rule-computed `user_profile`
- AIChat Agent must not receive `real_name`, `username`, `email`, or `student_id`.
- `user_id` may remain in Agent API payloads for internal correlation if technically required, but must not be used as user-facing prompt content.
- Profile Agent, if retained, may only generate non-authoritative text such as `profile_summary_text`, `explanation`, or `recommendation`.

## Guidance Level

`User.guidance_level` is the sole authoritative source for `L1 / L2 / L3`.

Rules:

- The `/profile` UI labels this as the student's manual tutoring preference.
- Updating L1/L2/L3 calls `PUT /users/me`.
- `GET /profile` returns `guidance_level.current` equal to `users.guidance_level`.
- `POST /profile/refresh` must not overwrite `users.guidance_level`.
- `POST /profile/refresh` must not let Agent overwrite the effective guidance level.
- If a system recommendation is useful, return it as a separate non-authoritative field:
  - `guidance_level_suggestion.recommended`
  - `guidance_level_suggestion.reason`
- Backend AIChat payload assembly must set `user_profile.guidance_level = current_user.guidance_level`.
- Existing `user_profiles.guidance_level_current` values are compatibility data only. Responses should prefer `users.guidance_level`, and new profile records should mirror that value for compatibility.

This guarantees that once a student chooses L1/L2/L3, tutoring Agents use that value.

## Resource Preference And Modal Preference

Resource preference and modal preference are the same concept for the current product stage.

They are derived from effective learning duration, not resource counts and not AIChat intent.

Data source:

- `learning_activities`
- current user
- current course
- events with real study duration

Counted activity types:

- `resource_study`
- `node_practice_submit`, when it represents practice time

Excluded activity types:

- `resource_view`
- `node_view`
- any event without meaningful `duration_seconds`

Resource type to modal mapping:

| Resource type | Modal field |
| --- | --- |
| `video` | `video_animation` |
| `mindmap` or diagram-like resource | `chart_logic` |
| `document` / `reading` | `text_analysis` |
| `code` | `code_practice` |
| explicitly formula-like resource metadata | `formula_derivation` |

If formula-like metadata is not stable, `formula_derivation` remains `0`.

Scoring:

- Aggregate `duration_seconds` per modal.
- If total effective duration is `0`, all modal scores are `0`, and the UI shows an empty state.
- If there is duration evidence, normalize each modal against the max-duration modal:

```text
modal_score = modal_duration / max_modal_duration * 100
```

`profile_dimensions.resource_preference` shows the top 3 modal labels by effective study duration. Its source is `activity` or `resource_usage`, with documentation that this means effective study duration.

## Knowledge Progress, Coordinates, And Blindspots

KG defines the full learning scope. Quiz and evaluation evidence determine mastery and weakness.

Data sources:

- Active KG nodes for the current course catalog.
- Node-bound quiz attempts and answer correctness.
- Node-bound learning activity duration.
- `evaluation.node_progress`, if aligned to this same aggregation.

Node states:

| State | Meaning |
| --- | --- |
| `unstarted` | KG node exists, no learning activity and no quiz evidence |
| `learning` | node has learning activity but insufficient quiz evidence |
| `pending_practice` | node has questions but no completed practice |
| `weak` | quiz evidence shows weak understanding |
| `mastered` | quiz evidence reaches mastery threshold |

Mastery rules:

- Nodes with questions are judged primarily by quiz evidence.
- A node is `mastered` when cumulative correctness is at least `80%` and minimum evidence is met.
- A node is `weak` when cumulative correctness is below `70%`, or the latest node practice score is below `60%`.
- Intermediate scored nodes are `learning`.
- Nodes without questions cannot be marked `mastered`.
- Nodes without questions but with learning activity are `learning` or `studied`.
- Nodes without questions and without learning activity are `unstarted`.

Weak-point rules:

- Weak points must be selected from KG nodes. Agent may not invent course-external weak points.
- A KG node is weak when:
  - cumulative correctness is below `70%` with quiz evidence, or
  - latest node practice score is below `60%`.
- Severity:
  - `high`: cumulative correctness below `50%`, latest score below `40%`, or high error count.
  - `medium`: cumulative correctness from `50%` to below `70%`, or latest score from `40%` to below `60%`.
  - `low`: slightly below threshold with low error count.
- `cognitive_blindspots` returns top N weak nodes, sorted by severity, error count, and recency.

Knowledge coordinates:

`knowledge_coordinates` projects the full KG scope into student state. Each item should include:

- `node_id`
- `name`
- `status`
- `mastery_score`
- `evidence`: `quiz`, `activity`, or `none`

Profile progress summary:

`profile_dimensions.knowledge_progress` should become a structured summary rather than a raw count:

```json
{
  "total_nodes": 20,
  "mastered_nodes": 3,
  "learning_nodes": 5,
  "weak_nodes": 2,
  "pending_nodes": 8,
  "mastery_rate": 15
}
```

Frontend can render this as "已掌握 3/20，薄弱 2 个，待练习 8 个".

## Learning Habits

Learning habit is a weighted score based on regularity and effort.

Input fields:

- `active_days_7d`
- `active_days_30d`
- `streak_days`
- `study_duration_7d`
- `study_duration_30d`
- `practice_count_7d`
- `last_activity_at`

Score weights:

| Dimension | Weight | Inputs |
| --- | ---: | --- |
| Continuity | 35% | `streak_days`, `active_days_7d` |
| Effort | 35% | `study_duration_7d`, `study_duration_30d` |
| Practice participation | 20% | `practice_count_7d` |
| Recency | 10% | `last_activity_at` |

Output labels:

| Label | Meaning |
| --- | --- |
| `stable` | regular learning and meaningful effort |
| `sprint` | high recent effort but weaker continuity |
| `casual` | some activity but unstable |
| `inactive` | little or no recent learning behavior |
| `new` | insufficient data |

`profile_dimensions.discipline` returns structured evidence:

```json
{
  "label": "stable",
  "score": 76,
  "streak_days": 4,
  "active_days_7d": 5,
  "study_duration_7d": 7200,
  "last_activity_at": "2026-06-14T10:00:00Z"
}
```

## Discipline Badge

The discipline badge is a composite achievement based on learning habit and knowledge progress.

Inputs:

- Learning habit score: 40%
- Knowledge mastery/progress score: 50%
- Weak-point penalty: 10%

Levels:

| Level | Meaning |
| --- | --- |
| `starter` | new or score below 40 |
| `steady` | score from 40 to 69 |
| `advanced` | score from 70 to 84 |
| `excellent` | score at least 85 |

Badge output:

- `subject`: course name or course direction, not an opaque course id.
- `level`: one of the levels above.
- `score`: composite score.
- `streak_days`: copied from learning habit evidence.
- `reasons`: short evidence list, for example:
  - `近 7 天活跃 5 天`
  - `已掌握 8/20 个知识点`
  - `仍有 2 个薄弱点`

## API Contract

Reuse existing endpoints where possible:

- `GET /profile`
- `POST /profile/refresh`
- `GET /evaluation`
- `POST /evaluation/refresh`
- `GET /tasks/{task_id}`
- `PUT /users/me`

The profile response may add fields, but must not remove existing fields:

- `modal_preference`
- `guidance_level`
- `knowledge_coordinates`
- `cognitive_blindspots`
- `drive_intent`
- `discipline_badge`
- `profile_dimensions`

Potential additive fields:

- `learning_habits`
- `guidance_level_suggestion`
- `profile_summary_text`

Because this changes formal data meaning and may add response fields, update both:

- `../docs/10-client-api/Client-API.openapi.json`
- `../docs/10-client-api/API_前端接口规范.md`

## Frontend Display

`/profile` should make sources understandable:

- Manual tutoring preference for L1/L2/L3.
- Effective study duration for resource/modal preference.
- KG + quiz evidence for knowledge progress, coordinates, and blindspots.
- Learning activities for learning habit.
- Rule-based composite evidence for discipline badge.

Empty states:

- No learning activity: show "暂无有效学习时长".
- No quiz evidence: show "尚未完成练习，无法判断掌握".
- Missing KG: show "课程知识图谱尚未准备好".
- No weak points: show "暂无薄弱点证据".

`/learning-effects` and `/profile` must share the same KG node aggregation so they do not disagree about mastered or weak nodes.

## Testing

Backend tests should cover:

1. Updating `User.guidance_level` changes the AIChat Agent payload guidance level.
2. Profile refresh does not overwrite `User.guidance_level`.
3. Profile response mirrors `User.guidance_level` as `guidance_level.current`.
4. Resource/modal preference uses `learning_activities.duration_seconds`, not course resource counts.
5. No learning activity yields zero/empty preference.
6. KG nodes plus quiz results generate `mastered`, `weak`, `learning`, `pending_practice`, and `unstarted`.
7. Weak threshold works for cumulative correctness below `70%`.
8. Weak threshold works for latest score below `60%`.
9. Learning habit weighted score and label are deterministic.
10. Discipline badge level and reasons are deterministic.

Frontend verification:

- `npm run lint`
- `npm run build`
- Manual or E2E path covering:
  - select L1/L2/L3
  - refresh profile
  - complete a node quiz
  - view `/learning-effects`
  - view `/profile`

## Implementation Assumptions

1. Quiz evidence must be node-bound before weak-point and mastery rules are changed. If quiz answer records do not already expose stable `node_id`, the implementation must first align quiz submission records to KG nodes and test that alignment.
2. Formula-like preference is only computed from stable resource metadata. If no stable metadata exists, `formula_derivation` remains `0` and the UI treats it as no evidence rather than inferred preference.
3. `evaluation.node_progress` should become the shared KG node aggregation output consumed by both `/evaluation` and `/profile`. If an implementation finds the existing function unsuitable, it should extract a shared backend aggregation helper before changing either endpoint.
