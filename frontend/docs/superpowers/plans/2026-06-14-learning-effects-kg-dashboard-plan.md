# Learning Effects KG Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `/learning-effects` hard-coded content with a KG-node-centered learning effects dashboard backed by real evaluation data.

**Architecture:** Backend evaluation aggregation will build node-level progress rows from active KG/LearningPath fallback, quiz questions, and quiz attempts. The first implementation will store those rows in `Evaluation.progress_table.rows` to avoid a database migration, while OpenAPI and frontend code document and consume the stable row shape. The frontend will render overview metrics, summary, node table, mastery distribution, and evaluation refresh polling from real API responses only.

**Tech Stack:** FastAPI, SQLAlchemy async, MySQL-compatible JSON fields, React 19, Vite, Playwright, OpenAPI JSON/Markdown.

---

## File Structure

- Modify `../backend/app/api/v1/evaluation.py`
  - Add pure helper functions to resolve KG nodes and build evaluation node progress rows.
  - Include node progress rows in empty and stored evaluation responses.
  - Save rule-generated node progress rows during `/evaluation/refresh`.
- Modify `../backend/tests/test_refresh_async.py`
  - Extend existing evaluation refresh coverage for `unassessed_default_pass`, `pending_practice`, and scored rows.
- Modify `../docs/10-client-api/Client-API.openapi.json`
  - Document `EvaluationNodeProgress` and `EvaluationData.node_progress`.
- Modify `../docs/10-client-api/API_前端接口规范.md`
  - Document the node progress row fields and status rules.
- Modify `src/api/services/learning.js`
  - Make `refreshEvaluation(courseId)` send `{ course_id: courseId }`.
- Modify `src/pages/LearningEffects.jsx`
  - Remove hard-coded report, path table, fake resource distribution, and inert buttons.
  - Render `node_progress` or fallback `progress_table.rows`.
  - Poll `taskService.getTaskStatus()` after refresh.
- Modify `e2e/specs.spec.js`
  - Add a route-driven test for node progress states and refresh polling.
- Modify `WORKFLOW.md`
  - Record implementation, verification, contract status, commit.
- Modify `docs/feature-ledger.md`
  - Update `/learning-effects` row from “累计时长/趋势等仍是阶段二缺口” to the new KG-node dashboard status.

## Task 1: Backend Node Progress Aggregation

**Files:**
- Modify: `../backend/app/api/v1/evaluation.py`
- Test: `../backend/tests/test_refresh_async.py`

- [ ] **Step 1: Write failing backend assertions**

Add an evaluation-specific test after the existing evaluation refresh success case in `../backend/tests/test_refresh_async.py`. Seed a KG with three nodes, two quiz questions, and one submitted quiz session:

```python
from app.models.others import CourseKnowledgeGraph
from app.models.quiz import QuizAnswer, QuizQuestion, QuizSession
```

Use rows:

```python
kg = CourseKnowledgeGraph(
    course_id=course_id,
    version=1,
    is_active=True,
    source_type="test",
    generation_strategy="test",
    nodes=[
        {"id": "node_pointer", "name": "指针基础", "chapter": "指针"},
        {"id": "node_array", "name": "数组", "chapter": "数组"},
        {"id": "node_malloc", "name": "动态内存", "chapter": "动态内存"},
    ],
    edges=[],
)
question_pointer = QuizQuestion(
    course_id=course_id,
    chapter="指针",
    knowledge_point="指针基础",
    type="single_choice",
    source="baseline",
    content="指针题",
    options=[{"key": "A", "text": "正确"}],
    correct_answer="A",
)
question_array = QuizQuestion(
    course_id=course_id,
    chapter="数组",
    knowledge_point="数组",
    type="single_choice",
    source="baseline",
    content="数组题",
    options=[{"key": "A", "text": "正确"}],
    correct_answer="A",
)
session = QuizSession(
    user_id=user_id,
    course_id=course_id,
    chapter="指针",
    score=100,
    correct_count=1,
    total_count=1,
    time_spent=180,
)
answer = QuizAnswer(
    quiz_id=session.id,
    question_id=question_pointer.id,
    user_answer="A",
    is_correct=True,
    correct_answer="A",
)
```

After `GET /api/v1/evaluation`, assert:

```python
rows = body["data"]["node_progress"]
by_id = {row["node_id"]: row for row in rows}
assert by_id["node_pointer"]["assessment_state"] == "scored"
assert by_id["node_pointer"]["mastery_score"] == 100
assert by_id["node_pointer"]["mastery_label"] == "A"
assert by_id["node_pointer"]["study_duration_seconds"] == 180
assert by_id["node_array"]["assessment_state"] == "pending_practice"
assert by_id["node_array"]["mastery_score"] is None
assert by_id["node_malloc"]["assessment_state"] == "unassessed_default_pass"
assert by_id["node_malloc"]["mastery_label"] == "未测评/默认通过"
```

- [ ] **Step 2: Run the backend test and verify failure**

Run:

```bash
cd ../backend
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/evaluation_node_progress_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_refresh_async.py -q -p no:cacheprovider
```

Expected: FAIL because `node_progress` is missing.

- [ ] **Step 3: Add node aggregation helpers**

In `../backend/app/api/v1/evaluation.py`, import:

```python
from collections import defaultdict
from app.models.catalog import CourseCatalog, CourseOffering
from app.models.others import CourseKnowledgeGraph
from app.models.quiz import QuizAnswer, QuizQuestion, QuizSession
from app.services.course_knowledge_graphs import get_active_knowledge_graph
```

Add helpers:

```python
def _mastery_label(score: float | None) -> str:
    if score is None:
        return ""
    if score >= 90:
        return "A"
    if score >= 75:
        return "B"
    if score >= 60:
        return "C"
    return "需复习"


async def _resolve_evaluation_kg(db: AsyncSession, course_id: str) -> CourseKnowledgeGraph | None:
    kg = await get_active_knowledge_graph(db, course_id)
    if kg is not None:
        return kg
    offering_result = await db.execute(
        select(CourseOffering).where(
            CourseOffering.id == course_id,
            CourseOffering.is_deleted == False,
        )
    )
    offering = offering_result.scalar_one_or_none()
    if offering is None:
        return None
    catalog_result = await db.execute(
        select(CourseCatalog).where(
            CourseCatalog.id == offering.catalog_id,
            CourseCatalog.is_deleted == False,
        )
    )
    catalog = catalog_result.scalar_one_or_none()
    if catalog is None or not catalog.kg_host_course_id:
        return None
    return await get_active_knowledge_graph(db, catalog.kg_host_course_id)


async def _build_node_progress_rows(user_id: str, course_id: str, db: AsyncSession) -> list[dict]:
    kg = await _resolve_evaluation_kg(db, course_id)
    nodes = kg.nodes if kg and isinstance(kg.nodes, list) else []
    if not nodes:
        return []

    names = [str(node.get("name") or node.get("id") or "").strip() for node in nodes if isinstance(node, dict)]
    names = [name for name in names if name]

    questions_result = await db.execute(
        select(QuizQuestion).where(
            QuizQuestion.course_id == course_id,
            QuizQuestion.knowledge_point.in_(names),
            QuizQuestion.is_deleted == False,
        )
    )
    questions = questions_result.scalars().all()
    question_counts: dict[str, int] = defaultdict(int)
    question_to_kp: dict[str, str] = {}
    for question in questions:
        kp = question.knowledge_point or ""
        question_counts[kp] += 1
        question_to_kp[question.id] = kp

    session_result = await db.execute(
        select(QuizSession).where(
            QuizSession.user_id == user_id,
            QuizSession.course_id == course_id,
            QuizSession.is_deleted == False,
        )
    )
    sessions = session_result.scalars().all()
    session_by_id = {session.id: session for session in sessions}

    attempts: dict[str, dict] = defaultdict(lambda: {"correct": 0, "total": 0, "duration": 0, "sessions": set()})
    if session_by_id:
        answer_result = await db.execute(
            select(QuizAnswer).where(
                QuizAnswer.quiz_id.in_(list(session_by_id.keys())),
                QuizAnswer.question_id.in_(list(question_to_kp.keys())),
                QuizAnswer.is_deleted == False,
            )
        )
        for answer in answer_result.scalars().all():
            kp = question_to_kp.get(answer.question_id)
            session = session_by_id.get(answer.quiz_id)
            if not kp or not session:
                continue
            stats = attempts[kp]
            stats["total"] += 1
            stats["correct"] += 1 if answer.is_correct else 0
            stats["sessions"].add(session.id)
        for kp, stats in attempts.items():
            stats["duration"] = sum(session_by_id[sid].time_spent or 0 for sid in stats["sessions"])

    rows: list[dict] = []
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id") or node.get("node_id") or f"node_{index}")
        node_name = str(node.get("name") or node_id)
        question_count = question_counts.get(node_name, 0)
        attempt_stats = attempts.get(node_name)
        attempt_count = int(attempt_stats["total"]) if attempt_stats else 0
        score = round((attempt_stats["correct"] / attempt_stats["total"]) * 100, 1) if attempt_stats and attempt_stats["total"] else None

        if score is not None:
            assessment_state = "scored"
            status = "已掌握" if score >= 75 else "已练习"
            mastery_label = _mastery_label(score)
        elif question_count > 0:
            assessment_state = "pending_practice"
            status = "待练习"
            mastery_label = "待练习"
        else:
            assessment_state = "unassessed_default_pass"
            status = "未测评/默认通过"
            mastery_label = "未测评/默认通过"

        rows.append({
            "node_id": node_id,
            "node_name": node_name,
            "status": status,
            "study_duration_seconds": int(attempt_stats["duration"]) if attempt_stats and attempt_stats["duration"] else None,
            "mastery_score": score,
            "mastery_label": mastery_label,
            "assessment_state": assessment_state,
            "question_count": question_count,
            "attempt_count": attempt_count,
            "resource_visit_count": None,
            "last_activity_at": None,
        })
    return rows
```

- [ ] **Step 4: Return node progress from GET and refresh**

In `get_evaluation`, include:

```python
node_progress = await _build_node_progress_rows(current_user.id, course_id, db)
```

For empty response, add `"node_progress": node_progress`.

For stored response, prefer stored rows if present:

```python
progress_table = ev.progress_table or _empty_table
stored_node_progress = progress_table.get("rows") if isinstance(progress_table, dict) else None
"node_progress": stored_node_progress if isinstance(stored_node_progress, list) and stored_node_progress else node_progress
```

In `_run_evaluation_refresh_background`, before creating `Evaluation`, call:

```python
node_progress = await _build_node_progress_rows(user_id, course_id, db)
progress_table = data.get("progress_table", _empty_table)
if not isinstance(progress_table, dict):
    progress_table = _empty_table
progress_table = {
    "columns": progress_table.get("columns") or [],
    "rows": node_progress,
}
```

Save `progress_table=progress_table`.

- [ ] **Step 5: Run backend test and commit**

Run:

```bash
cd ../backend
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/evaluation_node_progress_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_refresh_async.py -q -p no:cacheprovider
```

Expected: PASS.

Commit:

```bash
git add ../backend/app/api/v1/evaluation.py ../backend/tests/test_refresh_async.py
git commit -m "实现学习效果节点进度聚合"
```

## Task 2: Client API Contract Update

**Files:**
- Modify: `../docs/10-client-api/Client-API.openapi.json`
- Modify: `../docs/10-client-api/API_前端接口规范.md`

- [ ] **Step 1: Update OpenAPI schema**

Add `node_progress` to `EvaluationData` and define `EvaluationNodeProgress`:

```json
"node_progress": {
  "type": "array",
  "description": "按 KG 节点聚合的学习效果进度；无题节点使用 unassessed_default_pass。",
  "items": {
    "$ref": "#/components/schemas/EvaluationNodeProgress"
  }
}
```

Schema:

```json
"EvaluationNodeProgress": {
  "type": "object",
  "properties": {
    "node_id": { "type": "string" },
    "node_name": { "type": "string" },
    "status": { "type": "string", "description": "未开始 / 学习中 / 已练习 / 已掌握 / 待练习 / 未测评/默认通过" },
    "study_duration_seconds": { "type": "integer", "nullable": true },
    "mastery_score": { "type": "number", "nullable": true },
    "mastery_label": { "type": "string" },
    "assessment_state": { "type": "string", "enum": ["scored", "pending_practice", "unassessed_default_pass", "unknown"] },
    "question_count": { "type": "integer" },
    "attempt_count": { "type": "integer" },
    "resource_visit_count": { "type": "integer", "nullable": true },
    "last_activity_at": { "type": "string", "format": "date-time", "nullable": true }
  }
}
```

- [ ] **Step 2: Update Markdown API spec**

In section `六、学习效果评估`, add rows for `node_progress` and a short rule table:

```markdown
| node_progress | array | 按 KG 节点聚合的学习效果进度 |
| node_progress[].assessment_state | string | scored / pending_practice / unassessed_default_pass / unknown |
| node_progress[].study_duration_seconds | integer/null | 有真实耗时记录时返回秒数，否则为 null |
```

Add:

```markdown
- 有答题记录：`assessment_state=scored`，返回真实 `mastery_score`。
- 有题但未答：`assessment_state=pending_practice`，前端展示“待练习”。
- 无题：`assessment_state=unassessed_default_pass`，前端展示“未测评/默认通过”，不计入真实均分。
```

- [ ] **Step 3: Validate and commit**

Run:

```bash
python -m json.tool ../docs/10-client-api/Client-API.openapi.json >/tmp/client-api-openapi-check.json
```

Expected: no output and exit code 0.

Commit:

```bash
git add ../docs/10-client-api/Client-API.openapi.json ../docs/10-client-api/API_前端接口规范.md
git commit -m "同步学习效果节点进度契约"
```

## Task 3: Frontend Service And Page Rendering

**Files:**
- Modify: `src/api/services/learning.js`
- Modify: `src/pages/LearningEffects.jsx`

- [ ] **Step 1: Update refresh service**

Change:

```js
refreshEvaluation() {
  return apiClient.post('/evaluation/refresh');
}
```

to:

```js
refreshEvaluation(courseId) {
  return apiClient.post('/evaluation/refresh', { course_id: courseId });
}
```

- [ ] **Step 2: Rewrite LearningEffects state**

Use these imports:

```js
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { profileService } from '../api/services/profile';
import { learningService } from '../api/services/learning';
import { taskService } from '../api/services/task';
import { useCourse } from '../context/CourseContext';
import Navbar from '../components/Navbar';
```

Add helpers:

```js
const terminalTaskStates = new Set(['completed', 'failed', 'partial']);

function formatDuration(seconds) {
  if (seconds === null || seconds === undefined) return '暂无记录';
  if (seconds < 60) return `${seconds}秒`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}分钟`;
  return `${(minutes / 60).toFixed(1)}小时`;
}

function normalizeRows(data) {
  if (Array.isArray(data?.node_progress)) return data.node_progress;
  if (Array.isArray(data?.progress_table?.rows)) return data.progress_table.rows;
  return [];
}
```

- [ ] **Step 3: Render real overview and summary**

Compute:

```js
const nodeRows = useMemo(() => normalizeRows(effectsData), [effectsData]);
const overview = useMemo(() => ({
  total: nodeRows.length,
  practiced: nodeRows.filter(row => row.assessment_state === 'scored').length,
  pending: nodeRows.filter(row => row.assessment_state === 'pending_practice').length,
  defaultPass: nodeRows.filter(row => row.assessment_state === 'unassessed_default_pass').length,
}), [nodeRows]);
```

Replace hard-coded summary text with:

```jsx
{effectsData?.summary_text ? (
  <p className="font-body-md text-slate-600 leading-relaxed">{effectsData.summary_text}</p>
) : (
  <p className="font-body-md text-slate-500 leading-relaxed">
    暂无学习效果总结。完成节点练习或点击重新评估后，系统会基于真实学习记录生成总结。
  </p>
)}
```

- [ ] **Step 4: Render node progress table and mastery distribution**

Replace the hard-coded path table with `nodeRows.map(row => ...)`.

Use:

```jsx
<td className="py-4 font-body-md text-slate-700">{row.node_name}</td>
<td className="py-4">{row.status || '暂无数据'}</td>
<td className="py-4 font-body-md text-slate-500">{formatDuration(row.study_duration_seconds)}</td>
<td className="py-4 font-bold text-cyan-600">{row.mastery_score ?? row.mastery_label ?? '暂无数据'}</td>
```

For actions:

```jsx
{row.question_count > 0 && (
  <button onClick={() => navigate(`/quiz?course_id=${activeCourseId}&node_id=${row.node_id}`)}>
    进入练习
  </button>
)}
<Link to="/learning-path">查看资源</Link>
```

Replace the fake resource distribution chart with counts grouped by `mastery_label` and `assessment_state`.

- [ ] **Step 5: Add refresh polling**

Add handler:

```js
const handleRefresh = async () => {
  if (!activeCourseId || refreshTask?.status === 'processing') return;
  setRefreshTask({ status: 'processing', progress: 0 });
  const res = await learningService.refreshEvaluation(activeCourseId);
  if (res.code === 202 && res.data?.task_id) {
    setRefreshTask({ task_id: res.data.task_id, status: 'processing', progress: 0 });
  }
};
```

Add `useEffect` polling:

```js
useEffect(() => {
  if (!refreshTask?.task_id || terminalTaskStates.has(refreshTask.status)) return undefined;
  const timer = window.setInterval(async () => {
    const res = await taskService.getTaskStatus(refreshTask.task_id);
    if (res.code !== 200) return;
    const nextTask = res.data;
    setRefreshTask(nextTask);
    if (terminalTaskStates.has(nextTask.status)) {
      window.clearInterval(timer);
      if (nextTask.status === 'completed') {
        await loadEffects();
      }
    }
  }, 1500);
  return () => window.clearInterval(timer);
}, [refreshTask?.task_id, refreshTask?.status, loadEffects]);
```

- [ ] **Step 6: Run frontend checks and commit**

Run:

```bash
npm run lint
npm run build
```

Expected: both pass.

Commit:

```bash
git add src/api/services/learning.js src/pages/LearningEffects.jsx
git commit -m "改造学习效果节点看板页面"
```

## Task 4: E2E Coverage And Progress Docs

**Files:**
- Modify: `e2e/specs.spec.js`
- Modify: `WORKFLOW.md`
- Modify: `docs/feature-ledger.md`

- [ ] **Step 1: Add Playwright route test**

Add a test that routes:

```js
await page.route('**/api/v1/evaluation?**', route => route.fulfill({
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify({
    code: 200,
    message: 'success',
    data: {
      course_id: 'course-e2e',
      node_progress: [
        { node_id: 'n1', node_name: '指针基础', status: '已掌握', study_duration_seconds: 180, mastery_score: 100, mastery_label: 'A', assessment_state: 'scored', question_count: 1, attempt_count: 1, resource_visit_count: null, last_activity_at: null },
        { node_id: 'n2', node_name: '数组', status: '待练习', study_duration_seconds: null, mastery_score: null, mastery_label: '待练习', assessment_state: 'pending_practice', question_count: 1, attempt_count: 0, resource_visit_count: null, last_activity_at: null },
        { node_id: 'n3', node_name: '动态内存', status: '未测评/默认通过', study_duration_seconds: null, mastery_score: null, mastery_label: '未测评/默认通过', assessment_state: 'unassessed_default_pass', question_count: 0, attempt_count: 0, resource_visit_count: null, last_activity_at: null }
      ],
      progress_table: { columns: [], rows: [] },
      mastery_table: { columns: [], rows: [] },
      resource_usage_table: { columns: [], rows: [] },
      summary_text: '当前指针基础掌握较好，数组节点待练习。',
      generated_at: '2026-06-14T10:00:00Z'
    }
  })
}));
```

Assert:

```js
await expect(page.getByText('指针基础')).toBeVisible();
await expect(page.getByText('待练习')).toBeVisible();
await expect(page.getByText('未测评/默认通过')).toBeVisible();
await expect(page.getByText('动态演示 (60%)')).toHaveCount(0);
```

- [ ] **Step 2: Run e2e plus checks**

Run:

```bash
npm run test:e2e -- e2e/specs.spec.js -g "learning effects"
npm run lint
npm run build
```

Expected: all pass; Vite chunk-size warning is acceptable if build exits 0.

- [ ] **Step 3: Update progress docs**

In `WORKFLOW.md`, add a 2026-06-14 entry with:

- Current completion state.
- Modified files.
- Test results.
- OpenAPI contract status.
- Commit messages.
- Remaining risk: duration remains nullable until learning activity tracking exists.

In `docs/feature-ledger.md`, update `/learning-effects` and #25 to state:

```text
KG 节点学习效果看板，展示真实 node_progress；无题节点显示“未测评/默认通过”；学习耗时无真实采集时显示暂无记录。
```

- [ ] **Step 4: Commit docs and final verification**

Run:

```bash
git diff --check
git status --short
```

Commit:

```bash
git add e2e/specs.spec.js WORKFLOW.md docs/feature-ledger.md
git commit -m "补充学习效果看板验证与进度记录"
```

## Final Verification

Run:

```bash
cd ../backend
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/evaluation_node_progress_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_refresh_async.py -q -p no:cacheprovider
cd ../frontend
npm run lint
npm run build
npm run test:e2e -- e2e/specs.spec.js -g "learning effects"
python -m json.tool ../docs/10-client-api/Client-API.openapi.json >/tmp/client-api-openapi-check.json
git diff --check
```

Expected:

- Backend evaluation refresh tests pass.
- Frontend lint passes.
- Frontend build passes.
- Playwright learning effects test passes.
- OpenAPI JSON parses.
- No whitespace errors.

## Self-Review Notes

- Spec coverage: hard-coded report, path table, fake resource distribution, refresh action, default-pass state, and duration-null behavior are all covered.
- Contract path: implementation uses a response-level `node_progress` field and stores rows in existing `progress_table.rows` to avoid a DB migration while still documenting a typed field.
- Known limitation: true resource visit duration is not implemented in this plan; duration uses quiz session `time_spent` where available and otherwise returns `null`.
