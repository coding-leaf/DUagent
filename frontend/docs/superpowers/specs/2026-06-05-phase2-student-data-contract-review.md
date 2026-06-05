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

### 4.5 AIChat

## 5. 教师端投影依赖

## 6. OpenAPI 更新候选

## 7. Backend / Agent 实现候选

## 8. 前端删除或降级候选

## 9. 暂缓或删除能力

## 10. 下一步建议
