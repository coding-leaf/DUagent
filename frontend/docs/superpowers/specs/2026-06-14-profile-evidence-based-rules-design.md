# Evidence-Based Student Profile Rules Design

## Context

`/profile` and `/learning-effects` are already connected to real APIs, but several student profile fields are not yet explainable enough:

- `guidance_level` can be manually changed by the user, while profile refresh may currently overwrite course profile guidance.
- `modal_preference` and `resource_preference` are partly derived from available course resource counts, which does not prove student preference.
- `knowledge_coordinates` and `cognitive_blindspots` can be empty because they depend on quiz chapter history rather than the course KG node range.
- `drive_intent` exists as a profile field, but its source must be explicit if core profile fields move to Backend rules.
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
- Do not introduce a full KG node table migration in the first implementation unless the string-match bridge proves unusable. The initial design works with the current JSON KG storage and documents its limits.

## Current Data Model Constraints

The implementation must account for the current storage model before changing profile rules:

1. KG nodes are stored as JSON, not table rows.
   - `course_knowledge_graphs.nodes` contains node objects such as `{id, name, chapter}`.
   - There is no `kg_nodes` table and no FK target for quiz questions.
   - Current evaluation code resolves the active KG, reads `nodes`, then matches quiz evidence by node name.

2. Quiz evidence is not directly node-bound.
   - `quiz_questions` has `knowledge_point`, but no `node_id`.
   - `quiz_answers` links to `quiz_questions` through `question_id`.
   - The current practical bridge is:

```text
QuizAnswer.question_id
  -> QuizQuestion.knowledge_point
  -> KG node.name
```

3. Learning activity is node-aware but loosely constrained.
   - `learning_activities.node_id` exists and is indexed.
   - It is a string field without FK enforcement against KG JSON nodes.

4. Profile refresh currently soft-deletes old `user_profiles` rows and inserts a new row, while `schema.sql` declares `UNIQUE INDEX uk_user_course (user_id, course_id)`.
   - If the live MySQL schema still has that non-filtered unique index, a second refresh can violate the unique key even when the old row is marked `is_deleted = 1`.
   - Fixing this write model is a blocking prerequisite before expanding profile refresh writes.

The first implementation should keep the current JSON KG model and make the bridge explicit. A normalized KG node table is a later migration candidate, not a hidden assumption of this design.

## Blocking Prerequisites

1. Fix `user_profiles` write semantics.
   - Preferred short-term fix: update existing active profile rows in place for each `(user_id, course_id)` instead of soft-delete plus insert.
   - Alternative: change the schema to support only one active row, for example with an active-row uniqueness strategy compatible with MySQL.
   - The implementation plan must verify the live schema before changing refresh behavior.

2. Extract the KG node progress aggregation into a shared Backend helper.
   - Start from the existing `_build_node_progress_rows()` logic.
   - Make it explicit that quiz evidence currently maps by `QuizQuestion.knowledge_point == KG node.name`.
   - Keep activity evidence mapped by `LearningActivity.node_id == KG node.id`.
   - Add tests around this bridge before profile uses the same output.

3. Decide the first-stage node identity policy.
   - First-stage policy: KG node `id` is authoritative for learning activity; KG node `name` is the compatibility key for quiz evidence.
   - If a KG node is renamed, historical quiz evidence may no longer match. This is accepted as a known limitation until quiz questions store a stable `node_id`.
   - A future schema migration may add `quiz_questions.node_id` and backfill from active KG names.

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
   - quiz sessions and answers mapped to KG nodes through the current compatibility bridge
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

API placement:

- `modal_preference` remains the canonical numeric five-dimensional score object consumed by the existing dedicated modal preference UI.
- `profile_dimensions.resource_preference` is a human-readable summary derived from the same duration evidence, not a separate model.
- Do not introduce a second independent `resource_preference` score field in v1.

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

`profile_dimensions.resource_preference` shows the top 3 modal labels by effective study duration. Its source is `activity`, with documentation that this means effective study duration.

## Knowledge Progress, Coordinates, And Blindspots

KG defines the full learning scope. Quiz and evaluation evidence determine mastery and weakness.

Data sources:

- Active KG nodes for the current course catalog.
- Quiz attempts and answer correctness mapped through `QuizQuestion.knowledge_point == KG node.name`.
- Node-bound learning activity duration mapped through `LearningActivity.node_id == KG node.id`.
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
- Minimum evidence for mastery is at least 3 answered questions for that KG node, unless fewer than 3 questions exist for the node; in that case all available questions must be answered.
- A node is `mastered` when cumulative correctness is at least `80%` and minimum evidence is met.
- A node is `weak` when cumulative correctness is below `70%`, or the latest node practice score is below `60%`.
- Intermediate scored nodes are `learning`.
- Nodes without questions cannot be marked `mastered`.
- Nodes without questions but with learning activity are `learning`.
- Nodes without questions and without learning activity are `unstarted`.

Mastery score:

- `mastery_score` is the cumulative correctness percentage for answered quiz questions mapped to the KG node.
- If a node has quiz evidence but has not met the minimum evidence threshold, `mastery_score` is still returned as the current cumulative correctness percentage, and `evidence_status = insufficient_quiz_evidence` may be included for UI explanation.
- If a node has questions but no answered quiz evidence, `mastery_score = null`.
- If a node has no quiz questions, `mastery_score = null`; learning activity alone never creates a mastery score.
- `mastery_label` may still use presentation buckets such as A/B/C, but those labels are derived from `mastery_score` and are not the authoritative score.

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
- `evidence_status`, optional
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

Current bridge limitations:

- This design does not claim referential integrity between quiz questions and KG nodes in the current schema.
- The first implementation must document and test the string-match bridge.
- If tests show unacceptable mismatch rates on real data, the plan should stop and introduce a `quiz_questions.node_id` migration instead of guessing.

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

Normalization:

| Input | Score function |
| --- | --- |
| `streak_days` | `min(streak_days / 7, 1) * 100` |
| `active_days_7d` | `active_days_7d / 7 * 100` |
| `study_duration_7d` | `min(study_duration_7d / 7200, 1) * 100`; 7200 seconds means 2 hours in 7 days |
| `study_duration_30d` | `min(study_duration_30d / 28800, 1) * 100`; 28800 seconds means 8 hours in 30 days |
| `practice_count_7d` | `min(practice_count_7d / 5, 1) * 100` |
| `last_activity_at` | 100 if within 24h, 70 if within 3 days, 40 if within 7 days, otherwise 0 |

Dimension scores:

```text
continuity_score = average(streak_days_score, active_days_7d_score)
effort_score = average(study_duration_7d_score, study_duration_30d_score)
practice_score = practice_count_7d_score
recency_score = last_activity_score

learning_habit_score =
  continuity_score * 0.35 +
  effort_score * 0.35 +
  practice_score * 0.20 +
  recency_score * 0.10
```

Output labels:

Labels are assigned by ordered rules, not only by one score range:

| Label | Rule | Meaning |
| --- | --- | --- |
| `new` | total effective activity events `< 2` and no quiz evidence | insufficient data |
| `inactive` | no `last_activity_at`, or latest activity is older than 7 days, or `learning_habit_score < 20` | little or no recent learning behavior |
| `sprint` | `effort_score >= 70` and `continuity_score < 40` | high recent effort but weaker continuity |
| `stable` | `learning_habit_score >= 60` and latest activity is within 7 days | regular learning and meaningful effort |
| `casual` | otherwise, when there is some activity evidence | some activity but unstable |

The rule order matters: `new` and `inactive` are checked before `sprint`, then `stable`, then `casual`.

`learning_habits` returns structured evidence:

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

The discipline badge is a composite achievement based on `learning_habits` and knowledge progress.

Inputs:

- `learning_habits.score`: 40%
- Knowledge mastery/progress score: 50%
- Weak-point penalty: 10%

Knowledge progress score:

```text
knowledge_progress_score =
  mastered_nodes / total_nodes * 100
```

If `total_nodes` is `0`, knowledge progress score is `0` and badge level should be `starter` with a reason that KG is unavailable.

Weak-point penalty:

```text
weak_penalty_score = min(weak_nodes / max(total_nodes, 1), 1) * 100

badge_score =
  learning_habit_score * 0.40 +
  knowledge_progress_score * 0.50 -
  weak_penalty_score * 0.10
```

Clamp `badge_score` to `0..100`.

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

## Profile Dimensions Shape

`profile_dimensions` remains the main summary array rendered by `StudentProfile.jsx`.

The response should keep the existing keys and make their values more structured where needed:

| Key | Value shape | Source | Display intent |
| --- | --- | --- | --- |
| `learning_goal` | string | `profile_dialogue`, `activity`, or `system_pending` | Student's stated or activity-derived learning direction |
| `weak_points` | array of weak node names | `quiz` | Top weak KG nodes from answer evidence |
| `resource_preference` | string or array of top modal labels | `activity` | Top modal/resource forms by effective study duration |
| `guidance_level` | `L1` / `L2` / `L3` | `manual` | User-selected tutoring preference |
| `knowledge_progress` | structured summary object | `kg_quiz_activity` | KG node progress summary |
| `learning_habits` | structured learning habit object | `activity` | Learning regularity and effort |

Allowed source labels:

| Source | Meaning |
| --- | --- |
| `manual` | User selected or edited this value |
| `profile_dialogue` | Student supplied it through profile dialogue |
| `activity` | Computed from learning activity duration or recency |
| `quiz` | Computed from quiz answers |
| `kg_quiz_activity` | Computed from KG nodes plus quiz and activity evidence |
| `system_profile` | Rule fallback when explicit evidence is missing |
| `system_pending` | Not enough evidence yet |

Frontend may continue using the generic dimension grid, but it must render structured `knowledge_progress` and `learning_habits` values explicitly rather than dumping object keys.

Compatibility:

- If legacy `profile_dimensions` still contains key `discipline`, frontend may map it to the new learning habits display during migration.
- New refresh output should use `learning_habits` for the habit dimension.
- `discipline_badge` remains the separate top-level composite achievement field.

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

## Drive Intent

`drive_intent` remains a top-level profile field, but it is also rule-computed by Backend.

Inputs:

- `learning_goal` from profile dialogue, when present.
- `study_duration_7d`.
- `practice_count_7d`.
- `active_days_7d`.

Rules:

- If the student explicitly provides a learning goal through profile dialogue, preserve it as `drive_intent.learning_goal` and set `source = profile_dialogue`.
- `intensity` is computed from recent activity:

```text
duration_score = min(study_duration_7d / 7200, 1) * 60
practice_score = min(practice_count_7d / 5, 1) * 25
active_day_score = active_days_7d / 7 * 15
intensity = duration_score + practice_score + active_day_score
```

- `type` is derived from activity pattern unless profile dialogue provides a more specific goal:
  - `exam_sprint`: `intensity >= 75` or high recent effort with short continuity.
  - `daily_homework`: `intensity >= 35` and recurring activity exists.
  - `casual`: otherwise.
- `source = activity` when type/intensity are computed from learning behavior.
- `source = system_pending` when there is no dialogue and no recent activity.

`profile_dimensions.learning_goal` uses:

1. `drive_intent.learning_goal` with `source = profile_dialogue`, if present.
2. `drive_intent.type` with `source = activity`, if activity exists.
3. `待补充` with `source = system_pending`, if no evidence exists.

## API Field Compatibility

- `knowledge_mastered` and `knowledge_weak` columns may be populated with `mastered_nodes` and `weak_nodes` for legacy summaries, but they are not the authoritative profile API shape.
- Do not remove these columns in this implementation.
- `knowledge_coordinates` and `cognitive_blindspots` should remain JSON fields in `user_profiles`, filled from the shared KG aggregation output.

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
- `profile_dimensions.source` labels must be translated using the source table above.

Empty states:

- No learning activity: show "暂无有效学习时长".
- No quiz evidence: show "尚未完成练习，无法判断掌握".
- Missing KG: show "课程知识图谱尚未准备好".
- No weak points: show "暂无薄弱点证据".

`/learning-effects` and `/profile` must share the same KG node aggregation so they do not disagree about mastered or weak nodes.

No dedicated `resource_preference` UI is required in v1. The existing modal preference card displays the numeric five-dimensional scores, and the existing profile dimension grid displays the top preference summary.

## Evaluation Contract Alignment

`/evaluation` remains the detailed KG node progress view.

The shared aggregation should feed:

- `GET /evaluation` `node_progress`
- `Evaluation.progress_table.rows` when refresh persists a snapshot
- `/profile` `knowledge_coordinates`
- `/profile` `cognitive_blindspots`
- `/profile` `profile_dimensions.knowledge_progress`

`Evaluation.mastery_table` and `Evaluation.resource_usage_table` should not remain Agent-only if they are shown or reused for rule profile fields:

- `mastery_table` should either be regenerated from the shared KG aggregation or treated as legacy snapshot data.
- `resource_usage_table` should either be regenerated from `learning_activities.duration_seconds` by resource/modal type or treated as legacy snapshot data.
- Agent may still generate `summary_text`, but the numeric tables must be rule-derived if they feed UI decisions.

## Migration And Backward Compatibility

Existing profile rows may contain Agent-generated fields. The migration behavior is:

1. Do not rewrite all historical rows immediately.
2. On next `POST /profile/refresh`, compute and persist the new rule-based fields for that user/course.
3. Before refresh, `GET /profile` may still return legacy fields, but it must override `guidance_level.current` with `users.guidance_level`.
4. `profile_dimensions` must tolerate both old primitive values and new structured objects during the transition.
5. Frontend empty states must handle missing `learning_habits`, missing structured `knowledge_progress`, and legacy `discipline_badge`.

This avoids a broad data migration while making new refreshes deterministic.

## Performance Boundary

The first implementation may use real-time aggregation because expected course KG and quiz sizes are small enough for the current demo flow. To avoid duplicated work:

- Extract one shared helper for KG node progress aggregation.
- `/profile/refresh` should call the helper once and persist the derived profile fields.
- `GET /profile` should read persisted profile fields, not recompute the full KG aggregation on every page load.
- `GET /evaluation` may compute live `node_progress` as it does now, but the helper must keep query count bounded by grouping queries rather than per-node SQL.

If real data shows slow page loads, the next step is a materialized `node_progress` table or snapshot, but that is outside this first design.

## Agent Service Changes

Existing Agent Service profile generation already contains rule-based logic, but its rules differ from this design:

- It uses resource counts, not effective learning duration.
- It groups quiz evidence by chapter, not KG node.
- It recommends guidance level from quiz score.
- It derives badge level mostly from quiz average.

New boundary:

- Backend owns all authoritative profile rules.
- `agent_service/agents/profile.py` should no longer be treated as the source of core `modal_preference`, `knowledge_coordinates`, `cognitive_blindspots`, or `discipline_badge`.
- If `POST /agent/v1/profile/generate` remains for compatibility, it should either:
  - accept rule-computed profile data and return only text explanation fields, or
  - be bypassed by Backend profile refresh for core fields.

The implementation plan must choose one of these compatibility options before coding.

## Testing

Backend tests should cover:

1. Updating `User.guidance_level` changes the AIChat Agent payload guidance level.
2. Profile refresh does not overwrite `User.guidance_level`.
3. Profile response mirrors `User.guidance_level` as `guidance_level.current`.
4. Resource/modal preference uses `learning_activities.duration_seconds`, not course resource counts.
5. No learning activity yields zero/empty preference.
6. KG nodes plus quiz results through the `knowledge_point == node.name` bridge generate `mastered`, `weak`, `learning`, `pending_practice`, and `unstarted`.
7. Weak threshold works for cumulative correctness below `70%`.
8. Weak threshold works for latest score below `60%`.
9. Learning habit weighted score and label are deterministic.
10. Discipline badge level and reasons are deterministic.
11. Profile refresh succeeds twice for the same `(user_id, course_id)`.
12. `profile_dimensions` returns the defined key/source/value shapes.
13. Evaluation and profile share the same weak/mastered node classification for the same evidence.
14. `knowledge_coordinates.mastery_score` is cumulative correctness percentage when quiz evidence exists, and `null` when no quiz evidence exists.
15. `learning_habits.label` follows the ordered `new` / `inactive` / `sprint` / `stable` / `casual` rules.
16. `drive_intent` source is `profile_dialogue`, `activity`, or `system_pending` according to the evidence source.

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

1. Quiz evidence is node-aligned by the current string bridge first. A direct `quiz_questions.node_id` migration is desirable but not required for the first implementation.
2. Formula-like preference is only computed from stable resource metadata. If no stable metadata exists, `formula_derivation` remains `0` and the UI treats it as no evidence rather than inferred preference.
3. `evaluation.node_progress` should become the shared KG node aggregation output consumed by both `/evaluation` and `/profile`. If an implementation finds the existing function unsuitable, it should extract a shared backend aggregation helper before changing either endpoint.
4. The non-filtered `uk_user_course` unique index must be reconciled before relying on insert-new-profile refresh behavior.

## Implementation Phases

1. Phase 0: fix profile persistence and extract shared KG aggregation.
   - Verify live `user_profiles` unique index.
   - Make repeated profile refresh safe.
   - Extract and test KG node progress aggregation.

2. Phase 1: implement deterministic backend rules.
   - Guidance mirror from `users.guidance_level`.
   - Duration-based modal preference.
   - KG/quiz/activity-based coordinates and blindspots.
   - Learning habit score.
   - Composite discipline badge.

3. Phase 2: align Evaluation and Agent boundaries.
   - Use shared aggregation for evaluation/profile classifications.
   - Restrict Profile Agent to explanation text or bypass it for core fields.

4. Phase 3: update frontend rendering and contracts.
   - Update `StudentProfile.jsx` structured value rendering.
   - Update source labels and empty states.
   - Update OpenAPI and frontend interface spec.
