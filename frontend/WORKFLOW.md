# Frontend Workflow

`WORKFLOW.md` 只记录当前阶段状态、最近验证和下一步，不承担接口契约、完整设计规范或历史资料归档职责。
需及时修改相关内容以更新状态
## 当前判断

- 前端处于前后端联调阶段。
- 阶段一前端主链路已在真实 Backend + Agent Service + `duagent_test` 种子数据环境下完成 E2E 验收。
- 阶段一遗留契约疑点已清理；阶段二学生端数据契约审查、P0 假展示清理、ResourceDetail 正文预览链路已完成。
- 当前前端目标仍超过既有 Client API 的完整承载范围；新增能力必须先有契约审查或明确设计，再进入实现。
- 现有 `../docs/10-client-api/*` 仍是正式契约来源。已确认进入契约的新增能力包括 `GET /api/v1/resources/{id}` 与 `ResourceDetailItem.content_preview`。
- 未完成契约审查的页面能力不得继续用硬编码字段、Mock 假数据、推测响应结构或临时页面状态补齐正式能力。

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

阶段一后续注意：

- 确认真实 API 返回空数组或空值时页面展示 Empty/Unknown，不回退到假数据。
- 前端 service 中曾存在的未声明调用已在 2026-06-05 清理；后续新增 service 方法必须先对齐 `../docs/10-client-api/Client-API.openapi.json`。

## 阶段二目标

阶段二先做契约审查，再进入实现。目标是让前端完整页面目标、Client API、Backend SQL 和必要的 Agent 数据来源重新对齐。

当前状态：

- 学生端数据契约审查已完成，审查文档见 `docs/superpowers/specs/2026-06-05-phase2-student-data-contract-review.md`。
- 已删除或降级：认知成长曲线、建议学习时长、学习动力指数、班级覆盖率、重点关注学生、排名类指标。
- 已实现：ResourceDetail 文字资源正文预览，新增 `GET /api/v1/resources/{id}`，`document`/`reading` 返回 `content_preview`，其他类型返回 `null`。
- 仍待设计或延期：累计学习时长、阅读进度、阅读时长、AIChat 活动摘要、资源偏好分布。

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
- 2026-06-05：AI Chat SSE 真实流 smoke 验证通过：
  - Agent `POST /agent/v1/tutoring/chat` 直接调用返回完整 SSE 流：chunk（文本）、diagram（Mermaid）、knowledge_points、suggestion、done 五种事件类型均正常产出
  - 事件 JSON 结构与前端 `chatService.streamChat` SSE 解析器兼容
  - spec #17 "运行时稳定性待验证" 降级：Agent 端协议已确认可用。剩余风险为 Backend 代理层 token 过期/网络中断，可通过前端错误重试兜底
  - 无代码变更，纯验证。
- 2026-06-05：完成阶段二学生端数据契约审查文档：
  - 审查范围：StudentProfile、Dashboard/ResourceDetail、LearningPath、Quiz/PracticeResult、AIChat，并标注教师端投影依赖。
  - 已确认删除：认知成长曲线、建议学习时长、学习动力指数、班级覆盖率、重点关注学生、排名类指标。
  - 待定：累计学习时长、阅读进度、阅读时长、AIChat 活动摘要、资源偏好分布。
  - OpenAPI 未修改，无契约漂移。
  - 审查文档：`docs/superpowers/specs/2026-06-05-phase2-student-data-contract-review.md`
  - 后续已选择 ResourceDetail 正文预览作为首个 OpenAPI 更新候选并完成实现。
- 2026-06-06：P0 前端假展示清理完成：
  - StudentProfile：删除学习动力指数、认知成长曲线；RadarChart 降级为占位；total_duration_hours 改为"待统计"
  - ResourceDetail：删除"建议用时 25m"静态展示
  - PracticeResult：删除"新纪录""历史击败"展示
  - LearningPath：降级静态个性化提示和推荐卡为通用占位文案
  - TeacherConsole：删除 mock Insights 内平均活跃时间、覆盖率、重点关注学生等假展示
  - TeacherStudentReport：删除 mock 分支 class_name/rank/motivation_index/total_duration_hours/认知曲线；修正 weak_points/recent_activity 注释（从"不在契约"改为"后端空数组"）
  - JS bundle 534→520 KB（-14KB 假展示代码）
  - `npm run lint` / `npm run build` 通过。无 OpenAPI/契约漂移。
- 2026-06-06：修正 P0 补刀审查遗留的 `TeacherStudentReport.jsx` JSX 属性名：
  - 将模态偏好占位文案的 `class` 改为 `className`，消除 React JSX 属性警告风险。
  - `npm run lint` / `npm run build` 通过。无 OpenAPI/契约漂移。
- 2026-06-06：ResourceDetail 正文预览契约实现完成：
  - Client API：新增 `GET /api/v1/resources/{id}` + `ResourceDetailItem` schema（`content_preview` 为 nullable string）
  - Backend：新增详情路由 `@router.get("/{id}")`，`document`/`reading` 类型返回正文预览，其他 null
  - Frontend：`learningService.getResourceDetail(id)`；ResourceDetail.jsx 接入 API，删除阅读进度/时长占位
  - `npm run lint` / `npm run build` / Backend pytest 通过。
- 2026-06-06：ResourceDetail 审核修复批：
  - App.jsx：注册 `/resource/:id` 路由（student protected）
  - Dashboard.jsx：资源卡片添加 `onClick` 跳转到 `/resource/:id`
  - ResourceDetail.jsx：删除"更新于 2023.10.15"、DS 智能体建议卡片（含 85% 伪进度）、静态学习路径图
  - Backend `resources.py`：新增课程访问权限校验（`teacher_id` 匹配 + `CourseEnrollment` 检查），403 无权限
  - OpenAPI：`content_preview` 从 `"type": ["string", "null"]` 修正为 `"type": "string", "nullable": true`（OpenAPI 3.0 标准）
  - Backend 测试：27 条断言覆盖 401/404/403/document/reading/code/mindmap/video 各类型正确性
  - `npm run lint` / `npm run build` / Backend pytest 27/27 通过。
- 2026-06-06：ResourceDetail 后端测试断言修正：
  - `tests/test_resource_detail.py` 将最终 `return fail == 0` 改为 `assert fail == 0`，确保任一 `chk()` 失败都会让 pytest 报红。
  - `pytest -s -vv tests/test_resource_detail.py` 通过，输出 `27 OK, 0 FAIL`。
- 2026-06-06：LearningPath 节点资源接入完成：
  - OpenAPI：NodeResources schema 补充 `weak_point_tutorials[].id`、`chapter_materials[].id`，`content` 标注为摘要
  - Backend：`get_node_resources` 补充 `id` 字段，`weak_point_tutorials[].content` 截断为 160 字符
  - Backend 测试：`test_node_resources.py` 24 条断言覆盖 403 / id 字段 / content 160 截断 / 空资源
  - Frontend：`learningService.getNodeResources`；LearningPath.jsx 底部动态资源面板替换 3 张静态占位卡
  - 节点点击：completed/in_progress/recommended 可点，pending 不可点；默认选中 current_node
  - 新增 recommended 节点分支（星标图标，可点击）
  - 删除 completed/in_progress 节点内资源/习题占位文案，保留 Agent 提示占位
  - `npm run lint` / `npm run build` / Backend pytest 51/51 通过。
- 2026-06-06：LearningPath 节点资源接入审查补修：
  - `test_node_resources.py` 资源 fixture ID 改为动态值，避免默认 SQLite 测试库复跑时因 `resources.id` 唯一约束失败。
  - OpenAPI：`GET /learning-path/nodes/{node_id}/resources` 补充 `401`、`403` 错误响应描述，对齐后端认证和课程权限行为。
  - 运行时业务逻辑未变；本次补修用于测试可重复性和错误响应契约完整性。
- 2026-06-06：LearningPath 手工验收数据前置补齐：
  - `backend/scripts/seed_e2e_data.py` 新增 LearningPath smoke 数据：`completed` / `in_progress` / `recommended` 三个节点，当前节点为 `e2e-node-tree`。
  - 同步写入 `CourseKnowledgeGraph`、每节点 1 条资源、每节点 1 条练习题，使 LearningPath 节点选择 → 底部资源面板 → `/resource/:id` 跳转具备可验收数据。
  - 修正 seed 脚本直接运行时的 `app` 模块导入问题；仍保留 `ALLOW_E2E_SEED=true` 和测试库名安全检查。
  - `/tmp` SQLite 验证：首次 seed 后 `learning_paths=1`、`node_count=3`、资源=3、题目=3；复跑后数量不膨胀。
- 2026-06-06：LearningPath 资源面板 UI 收口：
  - weak_point_tutorials、exercises、chapter_materials 每组默认展示前 5 条，超出折叠 + "展开全部 (N 条)" 按钮
  - 每组 `max-h-80 overflow-y-auto` 防止面板过长
  - 节点切换时自动重置折叠状态
  - `npm run lint` / `npm run build` 通过。
- 2026-06-06：教师端学生 weak_points + recent_activity 聚合完成：
  - Backend 测试（TDD）：`test_teacher_student_learning.py` 26 条断言覆盖 403/weak_points 聚合/全对空数组/recent_activity max 5 + 排序
  - Backend：`get_student_learning` 补齐 `weak_points`（case() 条件聚合 + HAVING error_count > 0 + 过滤空 KP + top 5）和 `recent_activity`（最近 5 次 QuizSession，create_time DESC）
  - OpenAPI：`StudentLearning` schema 补齐字段定义
  - Frontend：`TeacherStudentReport.jsx` 去掉硬编码 `[]`，渲染真实数据 + 空态
  - 不新增端点、不调 Agent、不改 TeacherConsole Insights
  - `npm run lint` / `npm run build` / Backend pytest 77/77 通过。
- 2026-06-06：阶段二轻量手工验收记录：
  - ResourceDetail / LearningPath 链路可用：路径规划下可正常展示节点资源内容，并可进入资源详情。
  - 暂未发现前端存在容易进入无权限资源详情的入口；资源权限仍以后端 403 校验兜底。
  - 教师端学生报告可看到部分真实数据，`weak_points` / `recent_activity` 最小聚合方向成立。
  - 已知但非本轮重点：资源内容质量偏低，归入后续资源生成/资源库质量专项；学生侧“学习”状态和进度流转仍不完整，归入后续行为采集/学习状态设计。
  - 本轮不扩大到资源质量、行为采集、累计学习时长或阅读进度。
- 2026-06-06：阶段二文档收口完成：
  - `WORKFLOW.md` 已清理 TeacherConsole Insights 过期 P0 阻塞描述，当前统一口径为：阶段二 P0 已完成，转入 P1 收尾。
  - `../docs/10-client-api/API_前端接口规范.md` 已补齐 `/resources/{id}`、`/learning-path/nodes/{node_id}/resources`、`/teaching/classes/{class_id}/students/{student_id}/learning`、`/teaching/classes/{class_id}/insights` 的联调说明与空态语义。
  - 本轮未修改运行时代码、OpenAPI JSON 或后端实现；当前无新的 OpenAPI / 契约漂移。
  - 已运行 `git diff --check` 完成基础文档一致性检查。

## 本地联调注意事项

- 2026-06-05：验证码接口 `GET /auth/captcha` 使用 `curl` 正常，但浏览器前端报 `net::ERR_FAILED 200 (OK)` / Axios `Network Error` 时，优先检查 CORS origin。Backend 当前 CORS 默认允许 `http://localhost:5173`，不包含 `http://127.0.0.1:5173`；本地验证前端需统一使用 `http://localhost:5173`，并以 `VITE_USE_MOCK=false VITE_API_BASE_URL=http://localhost:8001/api/v1 npm run dev` 启动。长期可考虑在 Backend CORS 配置中补充 `http://127.0.0.1:5173`。

## 阶段二当前结论

- 阶段二 P0 已完成，不再存在 TeacherConsole Insights 的当前阻塞项。
- TeacherConsole 班级 Insights 最小 SQL 聚合已完成，OpenAPI / Backend / Frontend 三层已对齐。
- `students` / `insights` 独立错误处理已闭环，真实模式下不再依赖旧 mock 守卫。
- AI Chat SSE 真实流已验证通过（2026-06-05），不作为当前阻塞。
- `docs/superpowers/specs/2026-06-05-phase2-gap-analysis.md` 继续作为剩余事项台账来源，但其中已关闭的 P0 项不再视为当前状态。

## 下一步建议

- 阶段一契约疑点已清理完毕。
- 阶段二第一轮 mock 分支清理和 MS-05/MS-06/MS-08 轻量前端适配已完成。
- ResourceDetail 正文预览、LearningPath 节点资源、教师端学生报告个体聚合已完成并完成轻量手工验收。
- TeacherConsole 班级 Insights 最小 SQL 聚合已完成（2026-06-06）：OpenAPI 契约（ClassInsights/ClassWeakPoint/PathNodeProgress）、Backend `GET /teaching/classes/{class_id}/insights` 聚合端点（39 项集成测试全通过）、Frontend 接入。`useMock &&` 守卫已移除，真实模式展示班级平均练习分（一位小数）、练习次数、薄弱知识点 Top 5（含错题数/答题总次数/错误率）、路径节点分布。Students 和 Insights 独立错误处理已闭环。
- StudentProfile 真实字段展示补齐已完成（2026-06-06）：5 张卡片全部重接 GET /profile 契约字段（modal_preference 进度条、guidance_level 动态 L1-L3、knowledge_coordinates 双色列表 + cognitive_blindspots 严重度标签、drive_intent 类型/强度 + discipline_badge 勋章展示）。7 个幽灵字段全量删除（name/level/title/current_course/system_suggestion/knowledge_nodes/weekly_max_accuracy/total_duration_hours）。effectsData state/请求/Promise.all 分支全量清理。`!activeCourseId` 无限 loading bug 已修复为空态页面（标题+说明+去课程页按钮）。Backend/OpenAPI/Agent 零改动。
- 第二轮 P1 剩余：TeacherStudentReport 深度诊断字段扩展、AdminConsole 契约对齐补完、资源生成异步任务链路接入。
- 第二轮 P2：累计学习时长、阅读进度/阅读时长、AIChat 活动摘要、资源偏好分布、学生学习状态流转；这些需要行为采集口径和可能的 activity 表设计，暂不直接实现。
- 资源内容质量偏低暂不作为本轮阻塞，后续应归入资源生成/资源入库质量专项。
- 阶段二接口差距分析材料见 `docs/superpowers/specs/2026-06-05-phase2-gap-analysis.md`（19 条差距台账）。
- 轻量手工体验反馈见 `docs/superpowers/specs/2026-06-05-manual-smoke-feedback.md`，包含学生端个人信息/加入课程入口/资源预期和教师端身份展示/数据丰富度问题。
- 新增契约能力必须先走设计/审查；禁止用前端静态字段补齐未确认业务能力。
