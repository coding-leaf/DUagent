# 阶段二学生端数据契约审查

> 状态：审查中
> 日期：2026-06-05
> 依据：`docs/superpowers/specs/2026-06-05-phase2-student-data-contract-review-design.md`

## 1. 审查结论摘要

本文件用于记录学生端页面字段、正式 Client API、Backend 实现、Agent 来源和教师端投影之间的对齐情况。本轮不修改 OpenAPI，不修改前端或后端代码。

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

### 4.3 LearningPath

#### 证据

- 前端调用 `learningService.getLearningPath(activeCourseId)` -> `GET /learning-path`。
- `learningService` 未封装 `GET /learning-path/nodes/{node_id}/resources`。
- 页面中"欠缺知识点推荐""关键缺失""智能体提示""配套习题""推荐资源卡"存在静态内容。

#### 矩阵条目

| 能力名称 | 涉及页面 | 当前前端来源 | OpenAPI 状态 | Backend 状态 | Agent 来源 | 真实数据可用性 | 假展示风险 | 教师端投影 | 建议处理 | 优先级 | 待确认问题 |
|----------|----------|--------------|--------------|--------------|------------|----------------|------------|------------|----------|--------|------------|
| 学习路径基础节点 | LearningPath | `GET /learning-path` | 已声明 | 已实现 | LearningPath Agent 可生成 | 可用性需验证 | 无 | 可投影为学习进度 | 保留 | P1 | 节点 status/mastery 语义是否稳定 |
| 节点资源 | LearningPath | 当前未调用正式端点 | `/learning-path/nodes/{node_id}/resources` 已声明 | 已实现 | 资源/题目来源混合 | 未接入 | 静态内容 | 可投影为个体诊断资源 | 补前端消费 | P1 | 节点展开还是跳转时加载 |
| 智能体提示 | LearningPath | 静态文案 | 未声明 | 未实现 | 可能需要 Agent | 不可用 | 静态内容 | 不投影 | 前端降级 | P2 | 是否保留为通用说明而非个性化提示 |
| 推荐资源卡 | LearningPath | 静态卡片 | 已有节点资源端点可替代 | 已实现端点 | 不需要新增 | 未接入 | 静态内容 | 可投影 | 补前端消费 | P1 | 使用 NodeResources 哪些数组展示 |

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

## 5. 教师端投影依赖

### 5.1 已投影数据（教师端真实路径已验证的投影）

| 学生端来源字段 | 教师端学生报告展示 | 数据流状态 | 备注 |
|---------------|-------------------|-----------|------|
| `/profile.knowledge_coordinates` (status 字段) | `profile_summary.knowledge_mastered` / `knowledge_weak` | 后端从 profile 聚合为整数计数，前端消费 | 已可用，但仅展示计数，不展示具体知识点名称 |
| `/profile.modal_preference` | `profile_summary.modal_preference` → 模态偏好标签列表 | backend 从 profile 提取 key 列表，前端展示标签 | 已可用 |
| `/learning-path.nodes` (status/completed) | `path_progress.current_node` / `completed_nodes` / `total_nodes` | backend 从 learning_path 聚合，前端展示进度条和数字 | 已可用 |
| `/evaluation` (综合评分) | `evaluation_summary.overall_score` | backend 从 evaluation 表取值，前端展示分数 | 已可用 |
| `/quiz/sessions` (数据库表) | `quiz_stats.total_attempts` / `avg_score` / `avg_time_spent` | backend 从 quiz_session 表统计，前端展示三指标卡片 | 已可用 |

### 5.2 待聚合投影（OpenAPI 已声明，后端返回空数组）

| 学生端来源 | 教师端字段 | 当前状态 | 建议 |
|-----------|-----------|---------|------|
| Profile Agent 或 Quiz diagnosis | `StudentLearning.weak_points` | 后端返回 `[]`，前端展示"正式接口暂未提供" | 需确定聚合来源：从 `/profile.knowledge_coordinates` 中 status!=mastered 提取，还是从 quiz diagnosis 提取 |
| 资源访问 / quiz 提交 / AIChat | `StudentLearning.recent_activity` | 后端返回 `[]`，前端展示"正式接口暂未提供" | 需先确定行为采集方案（类型、title、时间戳来源），再聚合 |

### 5.3 仅 Mock 路径展示的投影（非正式数据路径）

| 字段 | 所在页面 | 问题 |
|------|---------|------|
| `student.overall_mastery`、`student.current_path_node` | TeacherConsole | 仅 Mock 条件分支下展示，真实接口不返回。`overall_mastery` 在 OpenAPI 班级学生列表无此字段 |
| `insights.special_students`、`insights.avg_duration`、`insights.coverage_rate` | TeacherConsole AI Insights 面板 | 仅 Mock 条件分支下展示，真实接口 `getConsoleInsights` 未在 OpenAPI 中找到契约 |
| `report.username`、`report.level`、`report.major`、`report.score`、`report.total_duration_hours`、`report.rank`、`report.motivation_index` | TeacherStudentReport | 仅 Mock 条件分支下展示，真实接口 StudentLearning 不包含这些字段 |
| `report.cognitive_growth` 认知成长曲线图表 | TeacherStudentReport | 仅 Mock 分支渲染，使用静态 SVG 模拟数据 |

### 5.4 前端代码中不准确的注释

- `TeacherStudentReport.jsx` 第 537 行注释 `weak_points — 不在正式 StudentLearning 契约中` 不准确：`weak_points` 已在 OpenAPI `StudentLearning.schema` 中声明，只是后端当前返回空数组。
- `TeacherStudentReport.jsx` 第 561 行注释 `recent_activity — 不在正式 StudentLearning 契约中` 同样不准确：`recent_activity` 已在 OpenAPI `StudentLearning.schema` 中声明（items 含 type/title/created_at），后端当前返回空数组。

## 6. OpenAPI 更新候选

| 候选 | 理由 | 前置条件 |
|------|------|----------|
| 文字资源正文预览字段或详情端点 | `ResourceDetail` 需要文字类资源前几段 | 明确正文来源是资源表字段还是文件解析结果 |
| 累计学习时长字段 | 可基于资源、练习、AIChat 行为计算 | 明确行为采集来源和统计周期 |

## 7. Backend / Agent 实现候选

| 候选 | 层次 | 说明 |
|------|------|------|
| `StudentLearning.weak_points` 聚合 | Backend | OpenAPI 已声明，后端当前为空数组 `[]`。可从 profile 的 `knowledge_coordinates` 中提取 status 非 masterd 的知识点名称，或从 quiz `diagnosis.weak_points` 聚合 |
| `StudentLearning.recent_activity` 聚合 | Backend | OpenAPI 已声明，后端当前为空数组 `[]`。需要定义活动来源（resource/view、quiz/submit、tutoring 等），按 created_at 倒序取最近 N 条 |
| Quiz diagnosis 前端可用性验证 | Backend + Frontend | `diagnosis.summary`、`weak_points`、`suggestions` 已在 OpenAPI 声明。优先验证真实返回结构，再补充前端 PracticeResult / TeacherStudentReport 消费 |
| 班级学生列表 mock 隐藏字段对齐 | Backend | 当前 `GET /teaching/classes/{class_id}/students` 返回的字段（`major`、`grade`）与 Mock 路径的 `overall_mastery`、`current_path_node` 不一致。需确认学生列表是否聚合展示 mastery 和 path 状态 |

## 8. 前端删除或降级候选

### P0 — 确认删除（契约未声明，真实数据不可用）

| 页面 | 字段/能力 | 代码位置 | 原因 |
|------|-----------|---------|------|
| TeacherStudentReport | `report.total_duration_hours` | mock 分支 lines 135, 293 | 已确认删除 |
| TeacherStudentReport | `report.rank` / 排位名次 | mock 分支 line 139 | 已确认删除，排名类指标 |
| TeacherStudentReport | `report.motivation_index` / 学习动力指数 | mock 分支 line 151 | 已确认删除 |
| TeacherStudentReport | `report.level` / 等级 | mock 分支 line 121 | mock 专属字段 |
| TeacherStudentReport | `report.major` / 专业 | mock 分支 line 123 | mock 专属字段 |
| TeacherStudentReport | `report.score` / 综合评分（mock 版本） | mock 分支 line 131 | mock 字段，真实路径使用 `evaluation_summary.overall_score` |
| TeacherStudentReport | 认知成长曲线图表 | mock 分支 lines 301-335 | 已确认删除 |
| TeacherStudentReport | `report.class_name` / 班级名 | mock 分支 line 126 | mock 专属字段 |
| TeacherStudentReport | `report.status` / 状态 | mock 分支 line 125 | mock 专属字段 |
| TeacherConsole | `student.overall_mastery` / 掌握度进度条 | mock 分支 lines 213-216 | mock 专属字段 |
| TeacherConsole | `student.current_path_node` / 当前节点标签 | mock 分支 line 209 | mock 专属字段 |
| TeacherConsole | `insights.special_students` / 重点关注学生 | mock 分支 lines 288-307 | 已确认删除 |
| TeacherConsole | `insights.avg_duration` / 平均活跃时间 | mock 分支 line 275 | 已确认删除 |
| TeacherConsole | `insights.coverage_rate` / 知识点覆盖率 | mock 分支 line 279 | 已确认删除 |
| TeacherConsole | `cls.students` / 班级学生人数 | all branches line 157 | 在 OpenAPI 班级列表 schema 中无此字段 |

### P2 — 前端代码注释修正

| 文件 | 行号 | 当前内容 | 应修正为 |
|------|------|---------|---------|
| TeacherStudentReport.jsx | 537 | `weak_points — 不在正式 StudentLearning 契约中` | `weak_points — 已在 StudentLearning 契约中，后端返回空数组待聚合` |
| TeacherStudentReport.jsx | 561 | `recent_activity — 不在正式 StudentLearning 契约中` | `recent_activity — 已在 StudentLearning 契约中，后端返回空数组待聚合` |

## 9. 暂缓或删除能力

### 已确认删除（P0）
- 认知成长曲线（TeacherStudentReport mock 分支 认知成长曲线 图表）
- 建议学习时长（ResourceDetail）
- 学习动力指数（TeacherStudentReport mock 分支 `motivation_index`）
- 班级覆盖率（TeacherConsole mock 分支 `coverage_rate`）
- 重点关注学生（TeacherConsole mock 分支 `special_students`）
- 排名类指标（TeacherStudentReport mock 分支 `rank`、`motivation_index` 的"领先 92%"文案）

### 已确认删除（TeacherConsole mock 专属）
- `overall_mastery` 进度条
- `current_path_node` 标签
- `avg_duration` 平均活跃时间
- `class.students` 学生数字段

### 暂缓（P2 — 等待行为采集方案）
- 累计学习时长（`total_duration_hours`，在两个页面的 mock 分支中展示，需真实行为采集支持）
- 阅读进度（需要行为记录表）
- AIChat 活动摘要（`recent_activity` 后端已预留，仅统计次数/时间，不展示聊天内容）
- 资源偏好分布

## 10. 下一步建议

### 第一阶段：删除 P0 假展示（TeacherStudentReport + TeacherConsole mock 分支清理）

1. **TeacherStudentReport mock 分支**：删除 `total_duration_hours`、`rank`、`motivation_index`、`level`、`major`、`score`、`status`、`class_name`、认知成长曲线图表
2. **TeacherConsole mock 分支**：删除 `overall_mastery`、`current_path_node`、`special_students`、`avg_duration`、`coverage_rate`、`class.students`

### 第二阶段：补充已有契约的消费（P1）

3. **TeacherStudentReport 真实路径 weak_points 展示**：先修正第 537 行注释，再待后端聚合后补前端消费
4. **TeacherStudentReport 真实路径 recent_activity 展示**：先修正第 561 行注释，再待后端聚合后补前端消费
5. **Quiz / PracticeResult `diagnosis` 消费**：验证 `diagnosis.summary`/`weak_points`/`suggestions` 的真实返回，补充前端展示

### 第三阶段：后端聚合补全（P1）

6. **`weak_points` 聚合**：确定来源规则（profile knowledge_coordinates 取非 mastered 项，或 quiz diagnosis），修改 `get_student_learning` 返回非空数组
7. **`recent_activity` 聚合**：定义活动类型（resource/view、quiz/submit、tutoring 等），修改 `get_student_learning` 后端实现，按时间倒序取最近记录

### 第四阶段：OpenAPI 评审（P2）

8. **文字资源正文预览**：明确资源详情端点的正文 preview 字段（资源表字段或文件解析），如有必要更新 OpenAPI
9. **累计学习时长**：待行为采集方案落地后再评估是否加入 OpenAPI

### 额外勘误

10. **修正 `TeacherStudentReport.jsx` 第 537 和 561 行的注释**：两个字段均在 StudentLearning 契约中，只是后端返回空数组。修正注释以反映真实契约状态。
