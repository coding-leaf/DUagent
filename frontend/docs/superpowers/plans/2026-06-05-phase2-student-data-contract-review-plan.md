# Phase 2 Student Data Contract Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a student-side data contract review matrix that separates supported fields, unsupported page assumptions, backend aggregation gaps, Agent dependencies, and teacher-side projection needs.

**Architecture:** This is a documentation and audit task. It reads the formal Client API contract, frontend pages/services, Backend routes, and Agent schemas, then writes one review document without modifying OpenAPI or runtime code.

**Tech Stack:** Markdown, OpenAPI JSON, React/JavaScript source review, FastAPI route/schema review, Agent Service schema review.

**Spec:** `docs/superpowers/specs/2026-06-05-phase2-student-data-contract-review-design.md`

---

## File Structure

**Create:**

- `docs/superpowers/specs/2026-06-05-phase2-student-data-contract-review.md`  
  The actual review output. It will contain the evidence matrix, page-by-page findings, teacher projection notes, priority summary, and OpenAPI update candidates.

**Read only:**

- `docs/superpowers/specs/2026-06-05-phase2-student-data-contract-review-design.md`
- `../docs/10-client-api/Client-API.openapi.json`
- `../docs/10-client-api/API_前端接口规范.md`
- `src/api/services/*.js`
- `src/pages/StudentProfile.jsx`
- `src/pages/Dashboard.jsx`
- `src/pages/ResourceDetail.jsx`
- `src/pages/LearningPath.jsx`
- `src/pages/Quiz.jsx`
- `src/pages/PracticeResult.jsx`
- `src/pages/AIChat.jsx`
- `src/pages/TeacherConsole.jsx`
- `src/pages/TeacherStudentReport.jsx`
- `../backend/app/api/v1/*.py`
- `../agent_service/schemas/*.py`
- `../agent_service/api/v1/*.py`

**Do not modify in this plan:**

- `../docs/10-client-api/*`
- `src/`
- `../backend/`
- `../agent_service/`

---

### Task 1: Create Review Document Skeleton

**Files:**
- Create: `docs/superpowers/specs/2026-06-05-phase2-student-data-contract-review.md`

- [ ] **Step 1: Read the approved design**

Run:
```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend
sed -n '1,280p' docs/superpowers/specs/2026-06-05-phase2-student-data-contract-review-design.md
```

Expected: The design states that this review covers student-side pages, marks teacher projection dependencies, and does not update OpenAPI or runtime code.

- [ ] **Step 2: Create the review document with fixed sections**

Create `docs/superpowers/specs/2026-06-05-phase2-student-data-contract-review.md` with:

```markdown
# 阶段二学生端数据契约审查

> 状态：审查中
> 日期：2026-06-05
> 依据：`docs/superpowers/specs/2026-06-05-phase2-student-data-contract-review-design.md`

## 1. 审查结论摘要

本文件用于记录学生端页面字段、正式 Client API、Backend 实现、Agent 来源和教师端投影之间的对齐情况。本轮不修改 OpenAPI，不修改前端或后端代码。

## 2. 固定决策

- 认知成长曲线：删除，不设计历史快照表。
- 建议学习时长：删除。
- 学习动力指数：删除。
- 班级覆盖率：删除。
- 重点关注学生：删除。
- 排名类指标：删除。
- 累计学习时长：待定，可基于资源、练习、AIChat 等真实行为统计。
- 资源详情正文：限定为文字类资源的正文前几段预览。

## 3. 审查矩阵

| 能力名称 | 涉及页面 | 当前前端来源 | OpenAPI 状态 | Backend 状态 | Agent 来源 | 真实数据可用性 | 假展示风险 | 教师端投影 | 建议处理 | 优先级 | 待确认问题 |
|----------|----------|--------------|--------------|--------------|------------|----------------|------------|------------|----------|--------|------------|

## 4. 页面审查

### 4.1 StudentProfile

### 4.2 Dashboard / ResourceDetail

### 4.3 LearningPath

### 4.4 Quiz / PracticeResult

### 4.5 AIChat

## 5. 教师端投影依赖

## 6. OpenAPI 更新候选

## 7. Backend / Agent 实现候选

## 8. 前端删除或降级候选

## 9. 暂缓或删除能力

## 10. 下一步建议
```

- [ ] **Step 3: Verify skeleton exists**

Run:
```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend
sed -n '1,220p' docs/superpowers/specs/2026-06-05-phase2-student-data-contract-review.md
```

Expected: The file exists and contains all ten sections.

- [ ] **Step 4: Commit skeleton**

Run:
```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/docs/superpowers/specs/2026-06-05-phase2-student-data-contract-review.md
git commit -m "新增学生端数据契约审查文档骨架"
```

Expected: Commit succeeds and only the new review document is included.

---

### Task 2: Collect Contract Evidence

**Files:**
- Modify: `docs/superpowers/specs/2026-06-05-phase2-student-data-contract-review.md`

- [ ] **Step 1: Extract OpenAPI paths**

Run:
```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend
jq -r '.paths | to_entries[] | .key as $p | .value | keys[] | "\(.|ascii_upcase) \($p)"' ../docs/10-client-api/Client-API.openapi.json
```

Expected: Output includes `/profile`, `/evaluation`, `/resources`, `/learning-path`, `/learning-path/nodes/{node_id}/resources`, `/quiz/questions`, `/quiz/submit`, `/quiz/result`, `/tutoring/chat`, `/tutoring/conversations`, and teaching endpoints.

- [ ] **Step 2: Extract relevant schemas**

Run:
```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend
jq '.components.schemas.ProfileData, .components.schemas.EvaluationData, .components.schemas.ResourceItem, .components.schemas.LearningPathData, .components.schemas.NodeResources, .components.schemas.QuizSubmitResult, .components.schemas.QuizDiagnosis, .components.schemas.StudentLearning' ../docs/10-client-api/Client-API.openapi.json
```

Expected: Output shows official field names for the student-facing data and teacher projection target.

- [ ] **Step 3: Extract frontend service calls**

Run:
```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend
rg -n "apiClient|client\\.|Service|getStudentProfile|getLearningEffects|getResources|getLearningPath|getQuestions|submitQuiz|getResult|getSessions|getHistory|streamChat" src/api/services src/pages
```

Expected: Output lists the real frontend API usage and highlights any service methods that are not used by pages.

- [ ] **Step 4: Add evidence summary to review document**

Append this structure under `## 1. 审查结论摘要` and fill it from the command outputs:

```markdown
### 契约证据摘要

- 正式学生端数据路径：
  - `GET /profile`
  - `GET /evaluation`
  - `GET /resources`
  - `GET /learning-path`
  - `GET /learning-path/nodes/{node_id}/resources`
  - `GET /quiz/questions`
  - `POST /quiz/submit`
  - `GET /quiz/result`
  - `POST /tutoring/chat`
  - `GET /tutoring/conversations`
  - `GET /tutoring/conversations/{id}`
- 教师端投影目标：
  - `GET /teaching/classes/{class_id}/students`
  - `GET /teaching/classes/{class_id}/students/{student_id}/learning`
- 已确认删除能力：
  - 认知成长曲线、建议学习时长、学习动力指数、班级覆盖率、重点关注学生、排名类指标。
```

- [ ] **Step 5: Commit evidence summary**

Run:
```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/docs/superpowers/specs/2026-06-05-phase2-student-data-contract-review.md
git commit -m "补充学生端契约证据摘要"
```

Expected: Commit succeeds.

---

### Task 3: Review StudentProfile

**Files:**
- Modify: `docs/superpowers/specs/2026-06-05-phase2-student-data-contract-review.md`

- [ ] **Step 1: Read source files**

Run:
```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend
sed -n '1,340p' src/pages/StudentProfile.jsx
sed -n '1,120p' src/api/services/profile.js
jq '.components.schemas.ProfileData, .components.schemas.EvaluationData' ../docs/10-client-api/Client-API.openapi.json
```

Expected: Identify real fields from `/profile` and `/evaluation`, and frontend fields that are static or contract-external.

- [ ] **Step 2: Fill StudentProfile section**

Under `### 4.1 StudentProfile`, add:

```markdown
### 4.1 StudentProfile

#### 证据

- 前端调用：
  - `profileService.getStudentProfile(activeCourseId)` -> `GET /profile`
  - `profileService.getLearningEffects(activeCourseId)` -> `GET /evaluation`
- 正式契约：
  - `/profile` 支持 `modal_preference`、`guidance_level`、`knowledge_coordinates`、`cognitive_blindspots`、`drive_intent`、`discipline_badge`、`generated_at`。
  - `/evaluation` 支持 `progress_table`、`mastery_table`、`resource_usage_table`、`summary_text`、`generated_at`。
- 明确删除：
  - `learning_motivation`
  - `motivation_percentile`
  - `cognitive_growth`
  - 认知成长曲线
- 待定：
  - `total_duration_hours`，后续需明确行为采集来源。

#### 矩阵条目

| 能力名称 | 涉及页面 | 当前前端来源 | OpenAPI 状态 | Backend 状态 | Agent 来源 | 真实数据可用性 | 假展示风险 | 教师端投影 | 建议处理 | 优先级 | 待确认问题 |
|----------|----------|--------------|--------------|--------------|------------|----------------|------------|------------|----------|--------|------------|
| 模态偏好雷达图 | StudentProfile | 当前 UI 使用静态数组 | `/profile.modal_preference` 已声明 | 需核实真实返回 | Profile Agent 可生成 | 未验证 | 静态内容 | 可投影为学生画像摘要 | 补前端消费 | P1 | 需确认 modal_preference 对象如何映射雷达图维度 |
| 引导粒度 | StudentProfile | 当前 UI 多为静态展示 | `/profile.guidance_level` 已声明 | 需核实真实返回 | Profile Agent 可生成 | 未验证 | 静态内容 | 可投影 | 补前端消费 | P1 | L1/L2/L3 文案是否沿用当前 UI |
| 知识坐标/认知盲区 | StudentProfile | 当前读取 `knowledge_nodes`，非正式字段 | `/profile.knowledge_coordinates`、`cognitive_blindspots` 已声明 | 需核实真实返回 | Profile Agent 可生成 | 未验证 | 契约外字段 | 可投影为教师端薄弱点 | 补前端消费 | P1 | 需确认 status 到 UI 样式的映射 |
| 认知成长曲线 | StudentProfile | `cognitive_growth` 契约外字段 | 未声明 | 无需实现 | 不需要 | 不可用 | 契约外字段 | 不投影 | 前端删除 | P0 | 已确认删除 |
| 学习动力指数 | StudentProfile | 默认值兜底 | 未声明 | 无需实现 | 不需要 | 不可用 | 默认值兜底 | 不投影 | 前端删除 | P0 | 已确认删除 |
| 累计学习时长 | StudentProfile | `total_duration_hours` 契约外字段 | 未声明 | 待定 | 不需要或聚合 | 待定 | 默认值兜底 | 待定 | 延期讨论 | P2 | 需确认行为采集方案 |
```

- [ ] **Step 3: Commit StudentProfile review**

Run:
```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/docs/superpowers/specs/2026-06-05-phase2-student-data-contract-review.md
git commit -m "补充 StudentProfile 契约审查"
```

Expected: Commit succeeds.

---

### Task 4: Review Dashboard and ResourceDetail

**Files:**
- Modify: `docs/superpowers/specs/2026-06-05-phase2-student-data-contract-review.md`

- [ ] **Step 1: Read source files**

Run:
```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend
sed -n '1,260p' src/pages/Dashboard.jsx
sed -n '1,260p' src/pages/ResourceDetail.jsx
sed -n '1,80p' src/api/services/learning.js
jq '.components.schemas.ResourceItem, .paths["/resources"]' ../docs/10-client-api/Client-API.openapi.json
```

Expected: Confirm `Dashboard` uses `/resources`, while `ResourceDetail` is static.

- [ ] **Step 2: Fill Dashboard / ResourceDetail section**

Under `### 4.2 Dashboard / ResourceDetail`, add:

```markdown
### 4.2 Dashboard / ResourceDetail

#### 证据

- `Dashboard` 调用 `learningService.getResources({ course_id, page, page_size })` -> `GET /resources`。
- `ResourceDetail` 当前没有 API 调用，正文、阅读进度、当前阅读时长、建议用时、关键词、路径图均为静态展示。
- 正式 `ResourceItem` 支持 `id`、`title`、`type`、`description`、`tags`、`chapter`、`knowledge_point`、`view_count`、`created_at`。

#### 矩阵条目

| 能力名称 | 涉及页面 | 当前前端来源 | OpenAPI 状态 | Backend 状态 | Agent 来源 | 真实数据可用性 | 假展示风险 | 教师端投影 | 建议处理 | 优先级 | 待确认问题 |
|----------|----------|--------------|--------------|--------------|------------|----------------|------------|------------|----------|--------|------------|
| 资源列表 | Dashboard | `GET /resources` | 已声明 | 已实现 | 资源生成 Agent 只参与生成 | 可用 | 无 | 可投影为资源访问基础 | 保留 | P1 | 需确认空列表展示 |
| 文字资源正文预览 | ResourceDetail | 当前静态正文 | 未声明独立详情端点 | 未确认 | 不默认需要 | 不可用 | 静态内容 | 可作为资源阅读活动基础 | 补 Client API 字段 | P1 | 正文前几段来自资源表字段还是文件解析结果 |
| 阅读进度 | ResourceDetail | 当前静态 65% | 未声明 | 未实现 | 不需要 | 不可用 | 静态内容 | 可投影为学习活动 | 延期讨论 | P2 | 是否需要行为记录表 |
| 累计学习时长 | ResourceDetail / StudentProfile | 当前静态/默认值 | 未声明 | 未实现 | 不需要 | 待定 | 默认值兜底 | 待定 | 延期讨论 | P2 | 是否基于资源访问、练习、AIChat 统一计算 |
| 建议学习时长 | ResourceDetail | 当前静态 25m | 未声明 | 无需实现 | 不需要 | 不可用 | 静态内容 | 不投影 | 前端删除 | P0 | 已确认删除 |
```

- [ ] **Step 3: Commit Dashboard / ResourceDetail review**

Run:
```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/docs/superpowers/specs/2026-06-05-phase2-student-data-contract-review.md
git commit -m "补充资源页契约审查"
```

Expected: Commit succeeds.

---

### Task 5: Review LearningPath

**Files:**
- Modify: `docs/superpowers/specs/2026-06-05-phase2-student-data-contract-review.md`

- [ ] **Step 1: Read source files**

Run:
```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend
sed -n '1,320p' src/pages/LearningPath.jsx
sed -n '1,80p' src/api/services/learning.js
jq '.components.schemas.LearningPathData, .components.schemas.PathNode, .components.schemas.NodeResources, .paths["/learning-path"], .paths["/learning-path/nodes/{node_id}/resources"]' ../docs/10-client-api/Client-API.openapi.json
```

Expected: Confirm base path endpoint is used, node resources endpoint is declared but not used.

- [ ] **Step 2: Fill LearningPath section**

Under `### 4.3 LearningPath`, add:

```markdown
### 4.3 LearningPath

#### 证据

- 前端调用 `learningService.getLearningPath(activeCourseId)` -> `GET /learning-path`。
- `learningService` 未封装 `GET /learning-path/nodes/{node_id}/resources`。
- 页面中“欠缺知识点推荐”“关键缺失”“智能体提示”“配套习题”“推荐资源卡”存在静态内容。

#### 矩阵条目

| 能力名称 | 涉及页面 | 当前前端来源 | OpenAPI 状态 | Backend 状态 | Agent 来源 | 真实数据可用性 | 假展示风险 | 教师端投影 | 建议处理 | 优先级 | 待确认问题 |
|----------|----------|--------------|--------------|--------------|------------|----------------|------------|------------|----------|--------|------------|
| 学习路径基础节点 | LearningPath | `GET /learning-path` | 已声明 | 已实现 | LearningPath Agent 可生成 | 可用性需验证 | 无 | 可投影为学习进度 | 保留 | P1 | 节点 status/mastery 语义是否稳定 |
| 节点资源 | LearningPath | 当前未调用正式端点 | `/learning-path/nodes/{node_id}/resources` 已声明 | 已实现 | 资源/题目来源混合 | 未接入 | 静态内容 | 可投影为个体诊断资源 | 补前端消费 | P1 | 节点展开还是跳转时加载 |
| 智能体提示 | LearningPath | 静态文案 | 未声明 | 未实现 | 可能需要 Agent | 不可用 | 静态内容 | 不投影 | 前端降级 | P2 | 是否保留为通用说明而非个性化提示 |
| 推荐资源卡 | LearningPath | 静态卡片 | 已有节点资源端点可替代 | 已实现端点 | 不需要新增 | 未接入 | 静态内容 | 可投影 | 补前端消费 | P1 | 使用 NodeResources 哪些数组展示 |
```

- [ ] **Step 3: Commit LearningPath review**

Run:
```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/docs/superpowers/specs/2026-06-05-phase2-student-data-contract-review.md
git commit -m "补充学习路径契约审查"
```

Expected: Commit succeeds.

---

### Task 6: Review Quiz and PracticeResult

**Files:**
- Modify: `docs/superpowers/specs/2026-06-05-phase2-student-data-contract-review.md`

- [ ] **Step 1: Read source files**

Run:
```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend
sed -n '1,220p' src/pages/Quiz.jsx
sed -n '1,240p' src/pages/PracticeResult.jsx
sed -n '1,80p' src/api/services/quiz.js
jq '.components.schemas.QuizQuestions, .components.schemas.QuizSubmitResult, .components.schemas.QuizDiagnosis, .paths["/quiz/questions"], .paths["/quiz/submit"], .paths["/quiz/result"]' ../docs/10-client-api/Client-API.openapi.json
```

Expected: Confirm submit result supports per-question results, while refreshed result uses latest quiz and diagnosis.

- [ ] **Step 2: Fill Quiz / PracticeResult section**

Under `### 4.4 Quiz / PracticeResult`, add:

```markdown
### 4.4 Quiz / PracticeResult

#### 证据

- `Quiz` 调用 `GET /quiz/questions` 和 `POST /quiz/submit`。
- `PracticeResult` 优先使用 `location.state.result`，刷新时调用 `GET /quiz/result`。
- 刷新路径当前手动构造 `total_count: 10`、`correct_count` 和空 `per_question_results`。
- 页面未完整消费 `diagnosis.summary`、`diagnosis.weak_points`、`diagnosis.suggestions`。

#### 矩阵条目

| 能力名称 | 涉及页面 | 当前前端来源 | OpenAPI 状态 | Backend 状态 | Agent 来源 | 真实数据可用性 | 假展示风险 | 教师端投影 | 建议处理 | 优先级 | 待确认问题 |
|----------|----------|--------------|--------------|--------------|------------|----------------|------------|------------|----------|--------|------------|
| 取题 | Quiz | `GET /quiz/questions` | 已声明 | 已实现 | Assessment Agent 可生成题目 | 可用 | 无 | 不直接投影 | 保留 | P1 | chapter 参数是否固定为 tree |
| 提交结果逐题复盘 | Quiz / PracticeResult | `POST /quiz/submit` state | `per_question_results` 已声明 | 已实现 | Assessment Agent 诊断异步参与 | 可用性需验证 | 无 | 可投影为薄弱点来源 | 保留 | P1 | 刷新后是否还能拿到逐题结果 |
| 刷新后的结果页 | PracticeResult | `GET /quiz/result` 后手动构造 | `diagnosis` 已声明 | 已实现 | Assessment Agent suggestions | 部分可用 | 手动构造字段 | 补前端消费 | P1 | 是否需要后端补 latest_quiz 的题数/正确数 |
| AI 诊断建议 | PracticeResult | 当前文案基于 accuracy 静态判断 | `diagnosis.summary/suggestions/weak_points` 已声明 | 已实现 | Assessment Agent | 可用性需验证 | 静态内容 | 可投影为教师端行动建议 | 补前端消费 | P1 | suggestions 展示位置 |
| 历史击败/新纪录/排名 | PracticeResult | 静态展示 | 未声明 | 无需实现 | 不需要 | 不可用 | 静态内容 | 不投影 | 前端删除 | P0 | 已确认删除 |
```

- [ ] **Step 3: Commit Quiz review**

Run:
```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/docs/superpowers/specs/2026-06-05-phase2-student-data-contract-review.md
git commit -m "补充测验结果契约审查"
```

Expected: Commit succeeds.

---

### Task 7: Review AIChat

**Files:**
- Modify: `docs/superpowers/specs/2026-06-05-phase2-student-data-contract-review.md`

- [ ] **Step 1: Read source files**

Run:
```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend
sed -n '1,260p' src/pages/AIChat.jsx
sed -n '1,220p' src/api/services/chat.js
jq '.components.schemas.ChatRequest, .components.schemas.ConversationBrief, .components.schemas.ConversationDetail, .paths["/tutoring/chat"], .paths["/tutoring/conversations"], .paths["/tutoring/conversations/{id}"]' ../docs/10-client-api/Client-API.openapi.json
```

Expected: Confirm SSE chat and conversation history endpoints are declared and used.

- [ ] **Step 2: Fill AIChat section**

Under `### 4.5 AIChat`, add:

```markdown
### 4.5 AIChat

#### 证据

- 前端调用 `GET /tutoring/conversations`、`GET /tutoring/conversations/{id}` 和 `POST /tutoring/chat`。
- `chatService.streamChat` 使用 `fetch` 解析 SSE。
- Mock 分支由 `VITE_USE_MOCK` 控制，属于开发辅助，不是正式路径。
- `WORKFLOW.md` 已记录真实 SSE 流 smoke 验证通过。

#### 矩阵条目

| 能力名称 | 涉及页面 | 当前前端来源 | OpenAPI 状态 | Backend 状态 | Agent 来源 | 真实数据可用性 | 假展示风险 | 教师端投影 | 建议处理 | 优先级 | 待确认问题 |
|----------|----------|--------------|--------------|--------------|------------|----------------|------------|------------|----------|--------|------------|
| SSE 答疑 | AIChat | `POST /tutoring/chat` fetch stream | 已声明 | 已实现 | Tutoring Agent | 已 smoke 验证 | Mock 开发辅助 | 不投影完整内容 | 保留 | P1 | token 过期/网络中断错误处理 |
| 会话列表 | AIChat | `GET /tutoring/conversations` | 已声明 | 已实现 | Backend 存储 | 需验证 | 无 | 可聚合为最近活动 | 保留 | P1 | 最近活动是否只显示摘要 |
| 会话详情 | AIChat | `GET /tutoring/conversations/{id}` | 已声明 | 已实现 | Backend 存储 | 需验证 | 无 | 不投影完整内容 | 保留 | P1 | 隐私边界 |
| AIChat 活动摘要 | TeacherStudentReport | 当前未实现 | 未声明为教师投影字段 | 未实现聚合 | 不需要 Agent 原文 | 不可用 | 无 | 可投影摘要 | 延期讨论 | P2 | 只统计次数/时间，不展示聊天内容 |
```

- [ ] **Step 3: Commit AIChat review**

Run:
```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/docs/superpowers/specs/2026-06-05-phase2-student-data-contract-review.md
git commit -m "补充 AIChat 契约审查"
```

Expected: Commit succeeds.

---

### Task 8: Summarize Teacher Projection and Action Lists

**Files:**
- Modify: `docs/superpowers/specs/2026-06-05-phase2-student-data-contract-review.md`

- [ ] **Step 1: Read teacher pages and backend route**

Run:
```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend
sed -n '1,330p' src/pages/TeacherConsole.jsx
sed -n '1,620p' src/pages/TeacherStudentReport.jsx
sed -n '115,215p' ../backend/app/api/v1/teaching.py
jq '.components.schemas.StudentLearning, .paths["/teaching/classes/{class_id}/students/{student_id}/learning"]' ../docs/10-client-api/Client-API.openapi.json
```

Expected: Confirm teacher report can reuse student profile, path, quiz stats, weak points, and recent activity, but several fields are empty or not consumed.

- [ ] **Step 2: Fill teacher projection and action list sections**

Under sections 5-10, add:

```markdown
## 5. 教师端投影依赖

| 学生端数据 | 教师端用途 | 当前状态 | 建议 |
|------------|------------|----------|------|
| `/profile.knowledge_coordinates` / `cognitive_blindspots` | 学生薄弱点、知识坐标 | 学生端需先正确消费 | 先补学生端真实消费，再投影 |
| `/learning-path.nodes` | 学习路径进度 | 已有基础契约 | 可投影到 `StudentLearning.path_progress` |
| `/quiz/result.diagnosis` | 薄弱点和行动建议 | 前端未充分消费 | 先补学生端复盘展示，再聚合到教师端 |
| 资源访问/阅读进度 | 最近学习活动 | 行为来源待定 | 暂不生成教师端资源偏好 |
| AIChat 会话摘要 | 最近 AI 使用活动 | 会话端点已有 | 只考虑摘要，不投影聊天原文 |

## 6. OpenAPI 更新候选

| 候选 | 理由 | 前置条件 |
|------|------|----------|
| 文字资源正文预览字段或详情端点 | `ResourceDetail` 需要文字类资源前几段 | 明确正文来源是资源表还是文件解析结果 |
| 累计学习时长字段 | 用户提出可基于资源、练习、AIChat 行为计算 | 明确行为采集和统计周期 |

## 7. Backend / Agent 实现候选

| 候选 | 层次 | 说明 |
|------|------|------|
| `StudentLearning.weak_points` 聚合 | Backend | OpenAPI 已声明，后端当前可能为空数组，需要从 profile/quiz 诊断聚合 |
| `StudentLearning.recent_activity` 聚合 | Backend | OpenAPI 已声明，后端当前可能为空数组，需要定义活动来源 |
| Quiz diagnosis 前端可用性验证 | Backend + Frontend | 已有字段，优先验证真实返回和前端消费 |

## 8. 前端删除或降级候选

| 页面 | 字段/能力 | 建议 |
|------|-----------|------|
| StudentProfile | 认知成长曲线 | 删除 |
| StudentProfile | 学习动力指数 | 删除 |
| ResourceDetail | 建议学习时长 | 删除 |
| PracticeResult | 历史击败 / 新纪录 / 排名 | 删除 |
| LearningPath | 静态个性化提示 | 降级为普通说明或删除 |

## 9. 暂缓或删除能力

- 删除：认知成长曲线、建议学习时长、学习动力指数、班级覆盖率、重点关注学生、排名类指标。
- 暂缓：累计学习时长、阅读进度、AIChat 活动摘要、资源偏好分布。

## 10. 下一步建议

1. 先处理 P0 假展示删除：StudentProfile、ResourceDetail、PracticeResult。
2. 再处理 P1 已有契约消费：`/profile`、`/learning-path/nodes/{node_id}/resources`、`/quiz/result.diagnosis`。
3. 后端补聚合前，先确认 `StudentLearning.weak_points` 和 `recent_activity` 的来源规则。
4. OpenAPI 更新只针对文字资源正文预览和累计学习时长候选，不一次性扩展复杂指标。
```

- [ ] **Step 3: Run document consistency checks**

Run:
```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend
rg -n "待补充|待定项未说明|重点关注学生.*保留|学习动力指数.*保留|建议学习时长.*保留|认知成长曲线.*保留" docs/superpowers/specs/2026-06-05-phase2-student-data-contract-review.md
git diff --check -- docs/superpowers/specs/2026-06-05-phase2-student-data-contract-review.md
```

Expected: No placeholder hits that require content; `git diff --check` passes.

- [ ] **Step 4: Commit final review**

Run:
```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/docs/superpowers/specs/2026-06-05-phase2-student-data-contract-review.md
git commit -m "完成学生端数据契约审查"
```

Expected: Commit succeeds.

---

### Task 9: Update Workflow

**Files:**
- Modify: `WORKFLOW.md`

- [ ] **Step 1: Add review completion note**

In `WORKFLOW.md`, under “最近验证” or “下一步建议”, add:

```markdown
- 2026-06-05：完成阶段二学生端数据契约审查文档：
  - 审查范围：StudentProfile、Dashboard/ResourceDetail、LearningPath、Quiz/PracticeResult、AIChat，并标注教师端投影依赖。
  - 已确认删除：认知成长曲线、建议学习时长、学习动力指数、班级覆盖率、重点关注学生、排名类指标。
  - 待定：累计学习时长、阅读进度、AIChat 活动摘要、资源偏好分布。
  - OpenAPI 未修改，无契约漂移。
  - 下一步：用户审阅审查矩阵后，再决定 OpenAPI 更新候选和实现顺序。
```

- [ ] **Step 2: Run format check**

Run:
```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend
git diff --check -- WORKFLOW.md
```

Expected: PASS.

- [ ] **Step 3: Commit workflow update**

Run:
```bash
cd /home/yezisama/workspace/workflow/EDUagent
git add frontend/WORKFLOW.md
git commit -m "更新学生端契约审查进度"
```

Expected: Commit succeeds.

---

## Final Verification

- [ ] **Step 1: Verify no runtime files changed**

Run:
```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend
git diff --name-only HEAD~9..HEAD
```

Expected: Output contains only:

```text
frontend/docs/superpowers/specs/2026-06-05-phase2-student-data-contract-review.md
frontend/WORKFLOW.md
```

- [ ] **Step 2: Verify OpenAPI unchanged**

Run:
```bash
cd /home/yezisama/workspace/workflow/EDUagent/frontend
git diff --name-only HEAD~9..HEAD -- ../docs/10-client-api
```

Expected: No output.

- [ ] **Step 3: Final summary**

Report:

```markdown
当前完成：阶段二学生端数据契约审查矩阵已完成。
修改文件：审查文档、WORKFLOW.md。
测试结果：仅文档检查，未跑构建。
OpenAPI/契约是否漂移：无。
git commit 信息：列出本计划产生的 commits。
剩余风险：累计学习时长、阅读进度、资源正文来源和教师端聚合规则仍需人工确认。
下一步建议：审阅矩阵后决定是否更新 OpenAPI。
```
