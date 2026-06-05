# 阶段二接口差距分析

> 本文档是阶段二的入口材料：按能力方向与已有 mock 分支做三层对照（前端 → OpenAPI → Backend/Agent），产出一份可执行的差距台账。每一项都标注优先级与建议处理方向，作为后续拆任务和契约审查的输入。

**最后更新：** 2026-06-05

---

## 1. 目标与范围

### 目标

明确前端页面能力与现有接口契约之间的差距，为阶段二契约审查提供决策依据，而不是一次性完成字段级审计。

### 范围

- 阶段二 WORKFLOW.md 列出的能力方向（资源详情/进度、认知成长、班级洞察、教师深度诊断、admin 运行状态）
- 已有前端页面中仍保留 mock 分支、且真实端点未适配或空实现的接口
- 已有真实 API 但前端字段利用不充分或适配不完整的接口

### 不纳入

- 纯 UI/UX 调整（页面布局、组件重构）
- 性能优化、bundle 体积、chunk splitting
- 后端基础设施（数据库迁移、部署配置、日志收集）
- 尚未在前端任何页面中出现过的全新产品能力

---

## 2. 契约依据

以下文件是本次分析的契约真相源：

| 层次 | 文件 |
|------|------|
| Client API 契约 | `../docs/10-client-api/Client-API.openapi.json` |
| Backend 路由 | `../backend/app/api/v1/`（auth, users, courses, profile, evaluation, learning_path, quiz, resources, tutoring, teaching, admin, tasks, webhooks） |
| Agent 内部协议 | `../agent_service/api/v1/`（health, evaluation, profile, memory, tutoring, learning_path, resources, assessment） |
| 前端页面清单 | `src/pages/`（14 个页面） |
| 前端 service 封装 | `src/api/services/`（8 个 service 文件） |

---

## 3. 差距矩阵

列说明：
- **页面/能力** — 涉及的页面名称或能力标签
- **前端需要** — 当前页面调用的 API 路径、期望的关键字段
- **OpenAPI 状态** — 路径是否声明、核心字段是否覆盖
- **Backend 状态** — 路由是否实现、返回数据是否完整
- **Agent 状态** — Agent 是否参与、Agent 端点是否已有（不适用时填 `—`）
- **缺口类型** — `接口缺失` / `字段缺失` / `mock-only` / `空实现` / `协议适配风险` / `运行时稳定性待验证` / `前端适配缺失` / `已对齐`
- **来源类型** — `阶段二新增能力` / `阶段一遗留 mock 分支` / `已有真实 API 字段不足`
- **优先级** — `P0`（阻塞联调）/ `P1`（阶段二必须）/ `P2`（可降级或暂缓）
- **建议处理** — `补接口` / `补字段` / `改前端适配` / `清理 mock 分支` / `降级` / `暂缓` / `联调验证`

---

### 组 1：阶段二能力方向（8 条）

| # | 页面/能力 | 前端需要 | OpenAPI 状态 | Backend 状态 | Agent 状态 | 缺口类型 | 来源类型 | 优先级 | 建议处理 |
|---|----------|---------|-------------|-------------|-----------|---------|---------|--------|---------|
| 1 | ResourceDetail — 资源详情正文阅读 + 阅读进度 | **当前页面 0 个 API 调用**：`ResourceDetail.jsx` 为纯静态 Demo，不含任何 `apiClient` 或 `learningService` 调用。页面需要：正文内容、阅读进度、资源元数据。`Dashboard.jsx` 已通过 `GET /resources` 获取资源列表（含 `title`, `description`, `type`, `id`, `chapter`, `knowledge_point`, `tags[]`, `view_count`），但无正文和进度字段 | `GET /resources` 已声明，无独立 `GET /resources/{id}` | Backend 已实现 `GET /resources`（`resources.py:18`） | `—` | `前端适配缺失` + `字段缺失` | 阶段二新增能力 | P1 | 补字段：在 `GET /resources` 或新增资源详情端点中增加正文（content）和进度（progress）字段；ResourceDetail.jsx 需从静态页面改造为接入 API |
| 2 | Dashboard / StudentProfile — 累计学习时长 + 建议学习时长 | 页面已有占位展示，当前数据来源是 `GET /profile`（画像统计）和 `GET /evaluation`（评估） | `GET /profile` 已声明，`GET /evaluation` 已声明 | Backend 均已实现 | Agent：`POST /evaluation/generate`、`POST /profile/generate` | `字段缺失` | 阶段二新增能力 | P1 | 补字段：核查 `/profile` 和 `/evaluation` 响应中是否已有学习时长相关字段，若无则需补 Client API + Backend |
| 3 | LearningEffects — 认知成长曲线 + 掌握度趋势 | 当前 `profileService.getLearningEffects(activeCourseId)` → `GET /evaluation`。页面已有字段 fallback 逻辑：优先用 `knowledge_nodes[]`，否则用 `mastery_table.rows[]` | `GET /evaluation` 已声明 | Backend 已实现（`evaluation.py:46`） | Agent：`POST /evaluation/generate` | `字段缺失` | 阶段二新增能力 | P1 | 补字段：核查返回的 `mastery_table`、`progress_table` 是否足以渲染趋势图/雷达图；字段粒度不足则扩展 Agent 产出结构 |
| 4 | LearningPath — 路径节点细粒度状态 + 节点资源挂载 | 当前 `learningService.getLearningPath(courseId)` → `GET /learning-path`，返回 `nodes[]`（含 `id`, `status`, `order`, `name`, `mastery`）。**未使用**已有的 `GET /learning-path/nodes/{node_id}/resources` 端点 | `GET /learning-path/nodes/{node_id}/resources` 已声明 | Backend 已实现（`learning_path.py:305`） | Agent：`POST /learning-path/generate` | `前端适配缺失` | 阶段二新增能力 | P1 | 改前端适配：在 `learningService` 中封装节点资源端点，`LearningPath.jsx` 按节点展开时调用 |
| 5 | TeacherConsole — 班级 AI 洞察 + 覆盖率 + 排名 + 动力指数 | **关键发现：** `useMock &&` 守卫整个 Insights 区块（仅在 `useMock=true` 时渲染）。当前 `teachingService.getConsoleInsights(courseId)` 真实分支返回 `data: null`（空实现）。mock 路径 `/api/v1/course/{id}/insights` | 无专用洞察端点声明 | Backend 无对应路由 | 需新增 Agent 端点或复用 `/evaluation/generate` 按班级维度聚合 | `接口缺失` + `空实现` + `mock-only` | 阶段二新增能力 | P0 | 补接口：需在 Client API 中新增班级洞察端点、Backend 实现聚合查询、Agent 负责 AI 洞察文本。**同时必须移除 `useMock &&` 守卫**，使真实数据可渲染 Insights 区块 |
| 6 | TeacherStudentReport — 深度诊断 + 资源偏好分布 + 导出报告 | **关键发现：** 整个页面布局按 `useMock` 分叉——mock 分支用 20+ 字段渲染丰富视图，真实分支仅用 ~10 字段渲染精简视图（`evaluation_summary`, `quiz_stats`, `path_progress`, `profile_summary` 等）。mock 路径 `/api/v1/teacher/students/{id}/report`，真实路径 `GET /teaching/classes/{class_id}/students/{student_id}/learning` | `GET /teaching/classes/{class_id}/students/{student_id}/learning` 已声明 | Backend 已实现（`teaching.py:115`） | `—`（诊断数据主要由 Backend 聚合） | `字段缺失` + `前端适配缺失` | 阶段二新增能力 | P1 | 补字段：扩展真实 API 返回字段（资源偏好分布、薄弱点详情、知识点坐标）；消除 `useMock` 分叉，真实模式也渲染完整报告布局 |
| 7 | AdminConsole — 智能体日志 + 用户管控 + 系统运行状态 | `admin.js` 已封装全部真实端点：`GET/PUT/DELETE /admin/users`、`GET /admin/logs/agent`、`GET /admin/logs/operations`。`AdminConsole.jsx` 已通过 `adminService.updateUser`/`removeUser` 对接用户管控。日志端点有 mock 分支（关联 #13/#14）。系统运行状态（CPU/内存/QPS）当前无数据源 | 均已声明 | Backend 均已实现（`admin.py`） | `—` | `mock-only`（关联 #13/#14）+ `字段缺失`（系统运行状态） | 阶段二新增能力 | P1 | 清理 mock 分支（#13/#14）、系统运行状态列为不建议立即实现（见 §5） |
| 8 | 学习路径节点资源挂载 | 同 #4，已并入 | 同 #4 | 同 #4 | 同 #4 | 同 #4 | 阶段二新增能力 | P1 | 同 #4 |

---

### 组 2：阶段一遗留 mock 分支（6 条）

| # | 页面/能力 | 前端需要 | OpenAPI 状态 | Backend 状态 | Agent 状态 | 缺口类型 | 来源类型 | 优先级 | 建议处理 |
|---|----------|---------|-------------|-------------|-----------|---------|---------|--------|---------|
| 9 | teachingService.getClasses — mock `/api/v1/teacher/classes` | 真实端点 `GET /courses` 已对接，且有字段适配层（将 `courses` 映射为 `classes` 格式）。`TeacherConsole.jsx` 在 mock/real 模式下展示不同字段（mock 展示 `current_path_node`/`overall_mastery`，real 展示 `major`/`grade`） | `GET /courses` 已声明 | Backend 已实现（`courses.py:18`） | `—` | `mock-only` | 阶段一遗留 mock 分支 | P1 | 清理 mock 分支：删除 `teaching.js:8-10` 的 mock 路径，统一 mock/real 渲染逻辑 |
| 10 | teachingService.getClassStudents — mock `/api/v1/course/{id}/students` | 真实端点 `GET /teaching/classes/{courseId}/students` 已对接且有适配层 | `GET /teaching/classes/{class_id}/students` 已声明 | Backend 已实现（`teaching.py:32`） | `—` | `mock-only` | 阶段一遗留 mock 分支 | P1 | 清理 mock 分支：删除 `teaching.js:29-31` 的 mock 路径 |
| 11 | teachingService.getConsoleInsights — mock `/api/v1/course/{id}/insights` | 真实分支返回 `data: null`（空实现）。与 #5 同一问题。**`useMock &&` 守卫 Insights 区块** | 无专用洞察端点 | Backend 无此路由 | 需新增 | `接口缺失` + `空实现` + `mock-only` | 阶段一遗留 mock 分支 | P0 | 同 #5：需新增班级洞察端点。清理 mock 路径 + 移除 `useMock &&` 守卫 |
| 12 | teachingService.getStudentReport — mock `/api/v1/teacher/students/{id}/report` | 真实端点 `GET /teaching/classes/{class_id}/students/{student_id}/learning` 已对接。但整个页面按 `useMock` 分叉——mock 分支 20+ 字段 vs 真实分支 ~10 字段 | 已声明 | Backend 已实现（`teaching.py:115`） | `—` | `mock-only` + `字段缺失` | 阶段一遗留 mock 分支 | P1 | 清理 mock 分支：删除 `teaching.js:80-82` mock 路径；扩展真实 API 字段后消除 `useMock` 布局分叉（关联 #6） |
| 13 | adminService.getAgentLogs — mock `/admin/logs/agents`（复数 s） | 真实端点 `GET /admin/logs/agent`（单数）已对接 | `GET /admin/logs/agent` 已声明 | Backend 已实现（`admin.py:139`） | `—` | `mock-only` | 阶段一遗留 mock 分支 | P1 | 清理 mock 分支：删除 `admin.js:23-25` 的 mock 路径。关联 #7 |
| 14 | adminService.getSystemLogs — mock `/admin/logs/system` | 真实端点 `GET /admin/logs/operations` 已对接。注意：`AdminConsole.jsx` 发起了 `getSystemLogs` 调用但**未使用其返回数据**（`Promise.all` 中仅解构了 `agentRes`） | `GET /admin/logs/operations` 已声明 | Backend 已实现（`admin.py:187`） | `—` | `mock-only` | 阶段一遗留 mock 分支 | P1 | 清理 mock 分支：删除 `admin.js:31-33` 的 mock 路径；在 AdminConsole 中接入 `getSystemLogs` 返回数据。关联 #7 |

---

### 组 3：已有真实 API 字段/适配不足（5 条）

| # | 页面/能力 | 前端需要 | OpenAPI 状态 | Backend 状态 | Agent 状态 | 缺口类型 | 来源类型 | 优先级 | 建议处理 |
|---|----------|---------|-------------|-------------|-----------|---------|---------|--------|---------|
| 15 | StudentProfile — 学生画像知识统计展示 | Backend 已补 `knowledge_mastered`、`knowledge_weak` 两个 SQL 字段（`others.py:82-83`）。`TeacherStudentReport.jsx` 真实分支已使用 `profile_summary.knowledge_mastered`/`knowledge_weak`。`StudentProfile.jsx` 是否展示这些统计待核实 | `GET /profile` 已声明，OpenAPI 响应 schema 是否含这两个字段待核对 | Backend 模型层已有 | Agent：`POST /profile/generate` | `字段缺失` | 已有真实 API 字段不足 | P1 | 补字段：如 OpenAPI schema 未声明则补；如已声明但 StudentProfile.jsx 未展示则改前端 |
| 16 | PracticeResult — Quiz 结果复盘字段覆盖度 | 当前 `quizService.getResult(courseId)` → `GET /quiz/result`。`PracticeResult.jsx` 需展示逐题复盘、薄弱点诊断。`GET /quiz/result` 返回 `diagnosis_json`（含 `suggestions[]`） | `GET /quiz/result` 已声明 | Backend 已实现（`quiz.py:187`） | Agent：`POST /assessment/evaluate` | `字段缺失` | 已有真实 API 字段不足 | P2 | 补字段：核查 `/quiz/result` 返回的 `diagnosis_json` 是否足以支撑逐题复盘；不足则需补 Agent 产出结构 |
| 17 | AIChat — SSE 流式对话稳定性 + Agent 联调 | `chatService.streamChat` 有完整 mock 分支（`setInterval` 模拟 SSE），真实分支使用原生 `fetch` + `ReadableStream` 对接 `POST /tutoring/chat`。**mock 分支是 `VITE_USE_MOCK` 控制的开发辅助，与 admin/teaching 的路径级 mock 不同** | `POST /tutoring/chat` 已声明（但可能是 SSE 语义，需确认 OpenAPI 描述） | Backend 已实现（`tutoring.py:89`） | Agent：`POST /tutoring`（SSE 流式对话） | `协议适配风险` + `运行时稳定性待验证` | 已有真实 API 字段不足 | P0 | 联调验证：确认真实 SSE 流在网络中断、token 过期、并发消息等场景下的稳定性。mock 分支可保留为开发辅助（由 `VITE_USE_MOCK` 控制），但不应作为正式路径 |
| 18 | AdminConsole — 管理员用户管控前端对接 | **已确认**：`AdminConsole.jsx` 已通过 `adminService.updateUser(userId, { status })` 执行封禁/激活操作，通过 `adminService.removeUser(userId)` 删除用户。`adminService.getUsers({ search })` 已获取列表 | 均已声明 | Backend 均已实现（`admin.py:14,62,112`） | `—` | `已对齐` | 已有真实 API 字段不足 | P1 | 联调验证：确认封禁/删除操作在真实 Backend 下功能正确 |
| 19 | 资源生成异步任务链路 | `learningService.triggerResourceGeneration(params)` → `POST /resources/generate`，`learningService.getTaskStatus(taskId)` → `GET /tasks/{task_id}`。两个端点均已在前端 service 中封装，但**暂无页面调用这两个方法** | `POST /resources/generate`、`GET /tasks/{task_id}` 均已声明 | Backend 均已实现（`resources.py:70`、`tasks.py:12`） | Agent：`POST /resources/generate` | `字段缺失` + `前端适配缺失` | 已有真实 API 字段不足 | P1 | 补字段 + 改前端：核查任务完成后返回的结果字段；在前端页面中对接任务发起→轮询状态→展示结果的完整流程 |

---

## 4. 优先级排序

### P0 — 阻塞联调（3 条）

必须在阶段二实现前解决：

| # | 条目 | 理由 |
|---|------|------|
| 5/11 | 班级 AI 洞察接口缺失 + 空实现 + `useMock &&` 守卫 | TeacherConsole 页面 Insights 区块仅在 `useMock=true` 时渲染。真实分支返回 `data: null`。无真实数据源，页面核心功能无法验收 |
| 17 | AI Chat SSE 联调稳定性 | AIChat 为核心功能。真实 SSE 流的错误处理、重连、token 过期等场景需验证。当前有完整 mock 分支可保开发不阻塞 |

### P1 — 阶段二必须（13 条）

| # | 条目 | 理由 |
|---|------|------|
| 1 | ResourceDetail 静态页面改造 + 资源正文/进度字段 | 当前页面 0 个 API 调用，需从头对接 |
| 2 | 学习时长字段 | 新能力，数据来源待明确 |
| 3 | 认知成长趋势字段 | 趋势图需足够粒度的历史数据 |
| 4/8 | 路径节点资源端点前端封装 + 页面接入 | 端点已存在，仅需前端适配 |
| 6 | 教师深度诊断字段 + 消除 `useMock` 布局分叉 | mock 分支 20+ 字段 vs 真实分支 ~10 字段，差距大 |
| 7 | Admin 日志 mock 清理 + 系统日志数据接入 | 关联 #13/#14 |
| 9 | teaching getClasses mock 清理 | 真实端点已对接，仅需删 mock 代码 |
| 10 | teaching getClassStudents mock 清理 | 同上 |
| 12 | teaching getStudentReport mock 清理 | mock 路径 + mock 布局分叉需一起处理 |
| 13 | admin getAgentLogs mock 清理 | 真实端点已对接 |
| 14 | admin getSystemLogs mock 清理 | 需同时接入 AdminConsole 展示 |
| 15 | 学生画像知识统计前端展示 | 字段已补到 Backend，TSTeport 已用，需确认 SProfile 也展示 |
| 18 | AdminConsole 管控动作联调验证 | 前端已对接 `updateUser`/`removeUser`，需真实环境验证 |
| 19 | 资源生成异步任务链路 | 端点已存在但暂无页面调用 |

### P2 — 可降级或暂缓（1 条）

| # | 条目 | 理由 |
|---|------|------|
| 16 | Quiz 结果复盘字段覆盖度 | 基础 Quiz（出题→提交→得分）已在阶段一 E2E 通过 |

---

## 5. 不建议立即实现的项

以下能力在阶段二应有意识排除：

- **导出报告（PDF/Excel）**：需额外生成/下载端点、前端渲染管线。建议深度诊断字段稳定后再考虑。
- **班级排名/动力指数**：需数据积累和排名算法。建议先用班级洞察基础数据验证产品方向。
- **资源推荐/个性化**：涉及推荐算法和行为数据积累，当前阶段数据量不足。
- **系统运行状态仪表盘（CPU/内存/QPS）**：需系统级 metrics 采集，当前 Backend 无对应基础设施。

---

## 6. 下一步拆分任务建议

### 第一轮：mock 分支清理（可并行，~5 个任务）

1. 清理 `teaching.js` getClasses mock 分支，统一 mock/real 渲染字段（#9）
2. 清理 `teaching.js` getClassStudents mock 分支（#10）
3. 移除 `teaching.js` getConsoleInsights mock 路径 + `useMock &&` 守卫（为 #5/11 补端点做准备）
4. 清理 `teaching.js` getStudentReport mock 路径（为 #6/12 补字段做准备）
5. 清理 `admin.js` 两个 mock 分支 + AdminConsole 接入系统日志数据（#13, #14）

### 第二轮：P0 项 + 字段补全（~6 个任务）

6. 新增班级洞察 Client API 端点 + Backend 路由 + Agent 实现（#5/11）
7. AI Chat SSE 联调验证与错误处理加固（#17）
8. ResourceDetail 改造：新增资源详情端点或扩展 `GET /resources` 字段，页面接入 API（#1）
9. 学习时长字段补全（#2）
10. 认知成长趋势字段扩展（#3）
11. 教师深度诊断字段扩展 + 消除 `useMock` 布局分叉（#6/12）

### 第三轮：前端适配补全（~4 个任务）

12. 路径节点资源端点前端封装 + LearningPath.jsx 接入（#4/8）
13. 学生画像知识统计 StudentProfile 前端展示（#15）
14. AdminConsole 管控动作联调验证（#18）
15. 资源生成异步任务链路前端对接（#19）

### 每轮完成后的验证

- `npm run lint`
- `npm run build`
- `npm run test:e2e`（需 Backend + Agent + MySQL duagent_test 在线）
- 更新 WORKFLOW.md 记录本轮完成状态

---

## 附录 A：Agent API 端点清单

Agent Service 当前已实现以下端点（`agent_service/api/v1/`）：

| 端点 | 用途 | 对应前端能力 |
|------|------|------------|
| `GET /health` | 健康检查 | 运维 |
| `POST /evaluation/generate` | 生成学习效果评估 | LearningEffects（#3） |
| `POST /profile/generate` | 生成/刷新用户画像 | StudentProfile（#15） |
| `POST /memory/compress` | 记忆压缩与事实提取 | 内部 |
| `POST /tutoring` | 辅导对话（SSE） | AIChat（#17） |
| `POST /learning-path/generate` | 生成学习路径 | LearningPath（#4） |
| `POST /resources/generate` | 资源生成 | 资源生成异步任务（#19） |
| `POST /assessment/evaluate` | 测验评估 | Quiz 复盘（#16） |
| `POST /assessment/generate` | 生成测验题目 | Quiz |

班级洞察（#5）当前在 Agent 侧无专用端点，可能需要新增或复用 `POST /evaluation/generate` 并按班级维度聚合。

## 附录 B：关键发现汇总

本次分析中通过代码审查获得的非预期发现：

1. **ResourceDetail.jsx 为纯静态页面**（0 个 API 调用），阶段二需从零对接 API（#1）
2. **TeacherConsole Insights 区块被 `useMock &&` 守卫**，真实数据即使可用也无法渲染（#5/11）
3. **TeacherStudentReport 布局按 `useMock` 分叉**：mock 分支 20+ 字段 vs 真实分支 ~10 字段（#6/12）
4. **AdminConsole 已对接用户管控**（`updateUser`/`removeUser`），但 `getSystemLogs` 返回值未被使用（#14/18）
5. **`learningService.triggerResourceGeneration` 和 `getTaskStatus` 已封装但无页面调用**（#19）
