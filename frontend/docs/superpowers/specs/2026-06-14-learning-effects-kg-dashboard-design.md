# Learning Effects KG Dashboard Design

Date: 2026-06-14
Status: Draft approved for planning

## Background

`/learning-effects` is currently only partly backed by real data. The page calls `GET /evaluation?course_id=...`, and the practice mastery card can derive rows from `knowledge_nodes` or `mastery_table.rows`. Several visible sections are still hard-coded:

- AI insight text.
- Learning path progress table.
- Resource feedback distribution chart.
- Report export action.
- Re-evaluation button behavior.

The current Client API contract already defines `EvaluationData` with:

- `progress_table`
- `mastery_table`
- `resource_usage_table`
- `summary_text`
- `generated_at`

It also defines `POST /evaluation/refresh` as an async task trigger. The contract does not define reliable fields for resource preference percentages, trend curves, or cumulative study time. Those must not be invented in the frontend.

## Goal

Replace the hard-coded `/learning-effects` page with a KG-node-centered learning effects dashboard that is driven by real course data.

The dashboard should answer:

1. Which KG nodes are in the current learning scope.
2. Which nodes the student has interacted with.
3. Which nodes have quiz evidence.
4. Which nodes are not measured because they have no available questions.
5. What the student should do next.

## Non-Goals

- Do not keep fake resource preference distribution such as "dynamic demo 60%".
- Do not fabricate study duration when no activity record exists.
- Do not treat missing quiz data as a real high score.
- Do not make the frontend call Agent Service directly.
- Do not revive deprecated frontend entries for `/resources/generate` or `/quiz/generate`.
- Do not modify `../docs/10-client-api/*` until the implementation plan confirms the exact contract delta.

## Product Decisions

### Missing Questions

If a KG node has no available quiz questions, show:

```text
未测评/默认通过
```

This state is not counted as a real mastery score. It means the system has no quiz evidence for the node, but the node should not block progress.

If a KG node has questions but the student has not answered them, show:

```text
待练习
```

### Study Duration

Study duration means time spent in content related to a KG node. It can come from resource detail visits, node practice sessions, or future heartbeat events.

If no reliable duration source exists yet, the UI must show `暂无记录` instead of a fake hour value.

### Report Text

The page should use the neutral label "学习效果总结", not "实时分析报告".

The summary source is:

1. `summary_text` from the latest evaluation, if available.
2. A rule-based empty state if no evaluation has been generated.
3. Optional Agent-generated prose in a later phase, but only after the structured data is stable.

## Page Design

### 1. Overview

Show compact course-level metrics:

- KG 节点总数
- 已练习节点数
- 待练习节点数
- 未测评/默认通过节点数
- 最近评估时间

These metrics should be derived from the same node rows used by the table.

### 2. Learning Summary

Replace the current hard-coded AI paragraph with:

- `summary_text`, when present.
- Empty state text when no summary exists.
- Refresh status when a refresh task is running or failed.

No unsupported claims such as "过去 7 天提升 32%" should appear unless the backend provides explicit evidence.

### 3. KG Node Progress Table

The main table should be the page's source of truth.

Columns:

- 节点名称
- 学习状态
- 学习耗时
- 掌握评分
- 证据来源
- 操作

Learning status values:

- `未开始`
- `学习中`
- `已练习`
- `已掌握`
- `待练习`
- `未测评/默认通过`

Mastery score rules:

- If quiz attempts exist, show the latest or aggregated quiz score.
- If questions exist but no attempt exists, show `待练习`.
- If no questions exist, show `未测评/默认通过`.
- If the backend cannot determine the node mapping, show `暂无数据`.

Actions:

- `查看资源`: navigate to the node resources or related resources.
- `进入练习`: navigate to `/quiz?course_id=...&node_id=...` when questions are available.

### 4. Mastery Distribution

Replace the current resource feedback donut with a mastery distribution built from real node states:

- A / 高掌握
- B / 基本掌握
- C / 需复习
- 待练习
- 未测评/默认通过

The distribution must not include preference categories unless a real behavior-tracking contract exists.

## Data Model Direction

### Evaluation Node Row

The backend should eventually expose node-level rows in `progress_table.rows` or a new explicit field. The implementation plan must choose the least disruptive option after checking backend code.

Recommended row shape:

```json
{
  "node_id": "kg-node-id",
  "node_name": "指针基础",
  "status": "practiced",
  "study_duration_seconds": 420,
  "mastery_score": 86,
  "mastery_label": "B",
  "assessment_state": "scored",
  "question_count": 7,
  "attempt_count": 2,
  "resource_visit_count": 3,
  "last_activity_at": "2026-06-14T10:00:00Z"
}
```

Assessment states:

- `scored`: quiz evidence exists.
- `pending_practice`: questions exist but no attempt exists.
- `unassessed_default_pass`: no questions exist.
- `unknown`: mapping or source data is incomplete.

### Source Data

The evaluation aggregation should use:

- Active KG / LearningPath fallback for node scope.
- Node resources and resource metadata for node-content mapping.
- Quiz questions and attempts for mastery evidence.
- Learning activity events for duration, when available.

If activity events are not available yet, the first implementation may expose `study_duration_seconds: null` and show `暂无记录`.

## Refresh Flow

The "重新评估" button should call:

```text
POST /evaluation/refresh
GET /tasks/{task_id}
GET /evaluation
```

Terminal task states should include `completed`, `failed`, and `partial` if the backend already uses `partial` for async tasks.

On success, reload the latest evaluation. On failure or partial completion, keep the last visible evaluation and show a non-blocking status message.

## Frontend Behavior

- Load state: show skeletons or compact loading status.
- No active course: show "请先加入或选择课程".
- No evaluation generated: show empty state and a refresh action.
- No KG nodes: show "课程知识图谱尚未准备好".
- No study duration: show `暂无记录`.
- No questions for node: show `未测评/默认通过`.
- Questions but no attempts: show `待练习`.

The page should not render hard-coded course topics such as "线性表与栈", "散列表(Hash)", or "红黑树进阶".

## Contract Impact

The recommended contract path is adding an explicit `node_progress` array to `EvaluationData`. The frontend needs stable typed fields rather than table-column inference, and the existing table fields are too loose for node-level status, duration, and assessment state.

The existing `progress_table`, `mastery_table`, and `resource_usage_table` can remain for compatibility, but the redesigned `/learning-effects` page should prefer `node_progress` when present.

Any chosen path must update:

- Backend schema/DTO.
- Backend aggregation service.
- Client API OpenAPI.
- API markdown spec.
- Frontend service usage.
- `/learning-effects` page.
- Tests.

## Testing Strategy

Frontend:

- Rendering with scored nodes.
- Rendering with `unassessed_default_pass` nodes.
- Rendering with questions but no attempts.
- Empty course / empty evaluation states.
- Refresh task success and failure states.

Backend:

- Aggregates active KG fallback nodes.
- Maps quiz attempts to KG nodes.
- Returns default-pass state for nodes with no questions.
- Does not count default-pass nodes as scored mastery.
- Keeps last evaluation visible when refresh fails.

Contract:

- OpenAPI schema check.
- Frontend contract fixture aligned with the schema.

## Planning Defaults

1. Add `node_progress` to `EvaluationData`.
2. Treat duration as nullable until a real learning activity source is confirmed.
3. Use existing `summary_text` when available; otherwise use a rule-based empty state in phase one.
4. Remove or disable report export in the first implementation unless a real export contract already exists.
