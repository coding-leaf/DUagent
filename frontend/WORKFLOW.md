# Frontend Workflow

`WORKFLOW.md` 只记录当前阶段状态、最近验证和下一步，不承担接口契约、完整设计规范或历史资料归档职责。
需及时修改相关内容以更新状态
## 当前判断

- 前端处于前后端联调阶段。
- 阶段一前端主链路已在真实 Backend + Agent Service + `duagent_test` 种子数据环境下完成 E2E 验收。
- 当前阶段可以进入阶段一验收结果归档与遗留契约疑点清理；阶段二仍需先做契约审查，不直接实现新增页面能力。
- 当前前端目标已经超过现有 Client API 规范能够正确承载的范围。
- 现有 `../docs/10-client-api/*` 仍是正式契约来源，但其字段、页面能力和数据来源不足以覆盖当前完整产品页面。
- 在完成阶段二契约审查前，前端不应继续用硬编码字段、Mock 假数据、推测响应结构或临时页面状态补齐正式能力。

## 阶段一目标

阶段一只收口现有 Client API 已能支撑的主链路，目标是让真实 Backend API 下的基础流程可运行、可验证、可回归：

- 登录、注册、验证码、`/users/me` 鉴权恢复。
- 课程列表、课程切换、课程上下文。
- 学生 Dashboard 资源列表。
- 学习路径基础展示。
- Quiz 获取题目、提交和结果页。
- AI Chat SSE 流式对话。
- 教师端学生列表和基础学情报告。
- 管理员基础用户和日志页面。

阶段一约束：

- 不新增正式 API 字段。
- 不扩展 Agent API。
- 不新增 SQL Schema。
- 后端返回空数组或空值时，展示 Empty/Unknown 状态，不回退到假数据。

说明：2026-06-05 经用户确认，为修复 E2E 种子数据与当前 ORM 不一致，Backend 画像表补充了 `knowledge_mastered`、`knowledge_weak` 两个内部 SQL 字段；该变更不新增前端可见 API 字段，不改变 Client API 或 Agent API 契约。

## 阶段一当前状态

状态：真实联调 E2E 验收通过。

已具备：

- 前端页面、API service 封装和路由已覆盖阶段一主链路。
- `e2e/specs.spec.js` 已覆盖学生登录进入资源库、课程切换、学习路径、Quiz、教师登录查看学生报告等主流程。
- 本地静态检查已通过。
- 真实 Backend `http://127.0.0.1:8001`、Agent Service `http://127.0.0.1:8002`、MySQL `duagent_test` 种子数据环境下，`npm run test:e2e` 已通过 3/3。

仍需确认：

- 确认真实 API 返回空数组或空值时页面展示 Empty/Unknown，不回退到假数据。
- 核对前端 service 中未出现在当前 OpenAPI 路径清单的调用是否为历史遗留、Mock 辅助或需要删除/补契约。

当前已发现的契约疑点：

- `src/api/services/auth.js` 中存在 `/auth/logout`、`/auth/refresh`、reset-password 相关调用，当前 `Client-API.openapi.json` 路径清单未声明。
- `src/api/services/profile.js` 中存在 `PUT /profile` 调用，当前 `Client-API.openapi.json` 路径清单未声明。
- `src/api/services/course.js` 中存在 `/course/{courseId}/students` 风格调用，当前正式教学学生列表路径为 `/teaching/classes/{class_id}/students`。

这些疑点在阶段一验收前需要逐项确认；未确认前不作为正式 Client API 能力。

## 阶段二目标

阶段二先做契约审查，再进入实现。目标是让前端完整页面目标、Client API、Backend SQL 和必要的 Agent 数据来源重新对齐。

阶段二需要审查的能力包括：

- 资源详情正文阅读、阅读进度、累计学习时长、建议学习时长。
- 认知成长曲线、掌握度趋势、路径节点更细粒度状态。
- 班级 AI 洞察、覆盖率、排名、动力指数。
- 教师端学生深度诊断、资源偏好分布、复杂资源统计、导出报告。
- 管理员智能体日志、用户管控动作、系统运行状态。

阶段二输出应至少明确：

- 哪些字段进入 Client API 契约。
- 哪些字段需要 Backend SQL 或聚合查询支撑。
- 哪些能力需要 Agent API 或异步任务结果支撑。
- 哪些页面能力应降级、延期或删除。

## 文档定位

- `README.md`：前端模块入口、运行方式、阅读顺序。
- `AGENTS.md`：前端协作规则、修改约束、契约纪律。
- `WORKFLOW.md`：当前阶段状态、目标、下一步。
- `DESIGN.md`：视觉设计系统草案。
- `前端页面字段与布局结构数据报告.md`：页面设想和阶段二契约审查输入，不是当前实现契约。

## 最近验证

- 2026-06-05：运行 `npm run build`，通过；存在 Vite chunk size warning。
- 2026-06-05：运行 `npm run lint`，通过。
- 2026-06-05：运行 `npm run test:e2e`，通过 3/3；环境为 Backend 8001、Agent Service 8002、MySQL `duagent_test`。
- 2026-06-05：清理阶段一遗留契约疑点 — 删除 `src/api/services/` 中 6 个未使用且不在 `Client-API.openapi.json` 声明中的方法：
  - `authService.logout` / `refreshToken` / `sendResetPasswordCode` / `resetPassword`
  - `profileService.updateProfile`
  - `courseService.getCourseStudents`
  - 清理后 `npm run lint` / `npm run build` / `npm run test:e2e`（3/3）通过。
  - `AdminConsole.jsx` 日志渲染适配真实 `AgentLogItem` 字段：`agent_type`、`endpoint`、`latency_ms`、`tokens_used`、`status`、`error_message`（替代 mock 字段 `level`/`agent`/`message`/`metadata.*`）。
- 2026-06-05：阶段二第一轮联调断层收敛 — 清理 5 个 mock 分支 + AdminConsole 契约修正：
  - `teaching.js`：移除 getClasses / getClassStudents / getStudentReport 的 mock 路径
  - `admin.js`：移除 getAgentLogs / getSystemLogs 的 mock 路径，删除 useMock 声明
  - `AdminConsole.jsx`：搜索参数 search → keyword；删除状态列、封禁按钮、删除按钮（DELETE 语义待契约确认）；last_login 改为 N/A
  - 清理后 `npm run lint` / `npm run build` / `npm run test:e2e`（3/3）通过。
- 2026-06-05：修正 `courseService.joinCourse` 请求体：`{ invite_code }` → `{ course_code }`，对齐 OpenAPI `JoinCourseRequest`（`1161e43`）。
- 2026-06-05：MS-05/MS-06 前端适配完成：
  - MS-05：Navbar "+ 加入课程"按钮 + `JoinCourseDialog`；Dashboard 无课程状态辅助入口。加入成功后自动 `refreshCourses` + `changeCourse`。无 OpenAPI/契约漂移。
  - MS-06：TeacherConsole 顶部身份改为真实 `useAuth` 数据（姓名、`roleLabelMap` 角色映射、文字头像）。无 OpenAPI/契约漂移。
  - `npm run lint` / `npm run build` 通过。
- 2026-06-05：修复 Tailwind CSS v4 主题自定义间距别名（`--spacing-sm` 等）污染全局宽度类（`max-w-sm` 等）导致弹窗与空状态收缩、文字竖立展示的布局问题。在 `index.css` 的 `@theme` 块中显式指定标准的 `--width-*` 尺寸映射以隔离影响。`npm run lint` / `npm run build` 均编译通过。无 OpenAPI/契约漂移。
- 2026-06-05：MS-08 教师创建课程入口完成：
  - 新增 `CreateCourseDialog`：输入课程名称 → `POST /courses` → 展示课程码 + 一键复制（含 clipboard 失败兜底）
  - TeacherConsole：`refreshClasses` callback 替代原有 effect 内直接 fetch；顶部加"创建课程"按钮；无班级空状态用 Fragment 包裹 + Dialog 确保 early return 路径可打开弹窗
  - `npm run lint` / `npm run build` 通过。无 OpenAPI/契约漂移。
- 2026-06-05：修复 MS-05/MS-08 新增入口的窄容器 UI 中文逐字竖排问题：
  - `FeedbackStatus`：loading/empty/error 根容器加 `w-[min(92vw,24rem)] min-w-[18rem] box-border`；title 加 `whitespace-nowrap`；description 加 `whitespace-normal break-words`
  - `JoinCourseDialog` / `CreateCourseDialog`：弹窗卡片宽度从 `max-w-sm` 改为 `w-[min(92vw,24rem)] min-w-[18rem]`；按钮/标题加 `whitespace-nowrap`
  - `Dashboard` / `TeacherConsole`：空状态父容器加 `w-full px-4`；按钮加 `whitespace-nowrap min-w-fit`
  - `npm run lint` / `npm run build` 通过。无 OpenAPI/契约漂移。

## 本地联调注意事项

- 2026-06-05：验证码接口 `GET /auth/captcha` 使用 `curl` 正常，但浏览器前端报 `net::ERR_FAILED 200 (OK)` / Axios `Network Error` 时，优先检查 CORS origin。Backend 当前 CORS 默认允许 `http://localhost:5173`，不包含 `http://127.0.0.1:5173`；本地验证前端需统一使用 `http://localhost:5173`，并以 `VITE_USE_MOCK=false VITE_API_BASE_URL=http://localhost:8001/api/v1 npm run dev` 启动。长期可考虑在 Backend CORS 配置中补充 `http://127.0.0.1:5173`。

## 标记：阶段二第二轮 P0 阻塞项

以下为当前代码中保留的 mock/空实现，需在第二轮优先解决：

- `teaching.js` `getConsoleInsights`：mock 分支调用 `/api/v1/course/{id}/insights`（不在 OpenAPI），真实分支返回 `data: null`（空实现）。需新增班级洞察端点（spec #5/#11）。
- `TeacherConsole.jsx:214` `useMock &&`：守卫 Insights 区块，端点就绪后需移除。
- 详见 `docs/superpowers/specs/2026-06-05-phase2-gap-analysis.md`。

## 下一步建议

- 阶段一契约疑点已清理完毕。
- 阶段二第一轮 mock 分支清理已完成。第二轮 P0：新增班级洞察端点、移除 TeacherConsole useMock && Insights 守卫。第二轮 P1：教师深度诊断字段扩展、ResourceDetail 页面改造、学习路径节点资源接入、Admin 用户状态/删除契约确认。
- 阶段二接口差距分析材料见 `docs/superpowers/specs/2026-06-05-phase2-gap-analysis.md`（19 条差距台账）。
- 轻量手工体验反馈见 `docs/superpowers/specs/2026-06-05-manual-smoke-feedback.md`，包含学生端个人信息/加入课程入口/资源预期和教师端身份展示/数据丰富度问题。
- 完成契约审查后，再决定是否修改 Client API、Backend Schema 或 Agent API。
