- 2026-06-16: \n  - 涉及文件: src/pages/AIChat.jsx, src/pages/Register.jsx, src/components/Sidebar.jsx, src/pages/Dashboard.jsx, src/pages/ResourceDetail.jsx, src/pages/LearningPath.jsx, src/pages/StudentProfile.jsx, src/pages/Success.jsx\n  - 核心改动: 清理了失效占位按钮，优化了页面中文案的内部术语暴露，并增强了引导粒度的说明。\n  - 测试结果: npm run build 通过\n  - 接口漂移: 无
- 2026-06-16: \n  - 涉及文件: src/pages/Login.jsx, src/pages/Register.jsx\n  - 核心改动: 使用 ui-ux-pro-max 重构了登录/注册页面的左侧展示区，去除了突兀的图片和生硬的内部用语，改用青色渐变和毛玻璃风格，并优化了所有展示文案。\n  - 测试结果: npm run build 通过\n  - 接口漂移: 无
- 2026-06-16: \n  - 涉及文件: src/pages/TeacherConsole.jsx\n  - 核心改动: 优化了学习资源的展示方式，使用 useMemo 按 chapter 分组，并引入可折叠手风琴（Accordion）布局。同时对最外层容器添加了最大高度（max-h-[500px]）和内部滚动条，防止资源过多撑长页面。\n  - 测试结果: npm run build 通过\n  - 接口漂移: 无
- 2026-06-16: \n  - 涉及文件: src/pages/ResourceDetail.jsx\n  - 核心改动: 去除旧版学生端硬编码外壳(导航栏+侧边栏)，重构为居中的单列沉浸式阅读布局；清理展示底层kg_node标签等黑话。\n  - 测试结果: npm run build 通过\n  - 接口漂移: 无

### 2026-06-17 Phase 2 启动
- **核心决策**：正式进入架构治理与重构阶段，确立五大重构方向：整理目录 / 提取公共组件 / 加测试 / 清环境变量 / 规范后端和 Agent 边界。
- **上下文文件更新**：`AGENTS.md`、`docs/superpowers/specs/2026-06-17-phase2-architecture-refactoring-master-plan.md` 作为 AI 行动指引已就绪。
- **已确认现状**：agent_service 不直连 MySQL，边界清晰；三个前端 Context 职责正交不冗余；`src/api/client.js` 拦截器已 80% 完成，待补 401 跳转与全局 Toast。
- **待推进**：每个重构动作均需先在 `docs/superpowers/specs/` 输出单点 Spec，经确认后再执行。

### 2026-06-17 (Update)
- **修改文件**：`agent_service/prompts/tutoring.py`
- **核心改动**：在 `TUTOR_REACT_SYSTEM_PROMPT` 中增加 Mermaid `subgraph` 强语法约束，要求大模型必须采用标准格式 `subgraph ID ["标题文本"]`，禁止在声明处直接写空格或特殊符号。这是为了从大模型输出源头进一步规避前端渲染解析失败的问题（补充止血方案）。
- **测试结果**：无语法错误。
- **接口漂移**：无

### 2026-06-17 (Update 2)
- **修改文件**：`src/App.jsx`, `src/api/client.js`, `package.json`, 以及部分遗留 lint 报错组件
- **核心改动**：完成 Option 1 网络层重构。引入 `sonner` 实现拦截器中 5xx/403 全局 Toast 与 401 纯净重定向，杜绝 4xx Toast 轰炸。同时清理了历史遗留的 ESLint 未定义变量告警。
- **测试结果**：`npm run lint` 与 `npm run build` 全部绿灯通过。
- **接口漂移**：无

### 2026-06-17 (Update 3)
- **修改文件**：`src/pages/AdminConsole.jsx`, 新增 `src/components/admin/UserManagementPanel.jsx`, `CatalogManagementPanel.jsx`, `RegistrationCodesPanel.jsx`, `SystemLogsPanel.jsx`
- **核心改动**：实施 AdminConsole 视图解耦与组件拆分。采用高内聚的 MVVM 局部化模式，将对应模块的状态和请求完全下沉到四个独立的 Panel 子组件内。主页 AdminConsole.jsx 缩减至 102 行，仅保留 Layout 导航职责。
- **测试结果**：`npm run lint` 和 `npm run build` 测试通过。
- **接口漂移**：无

### 2026-06-17 (Update 4)
- **修改文件**：`src/components/admin/*.jsx`, `src/utils/date.js`
- **核心改动**：修复 AdminConsole 组件拆分后的代码 Review 遗留问题：
  1. 补充 `SystemLogsPanel` 的 API 错误状态并在 UI 渲染，不再静默吞噬错误。
  2. 修正 `SystemLogsPanel` 的 `visibleLogs` 变量逻辑一致性。
  3. 提取所有 Panel 重复的 `formatDateTime` 到全局 `src/utils/date.js` 工具函数中。
  4. 清理了生产代码遗留的 `console.error`。
  5. 在 `UserManagementPanel` 的搜索监听中加入防抖逻辑 (500ms)。
- **测试结果**：`npm run lint` 和 `npm run build` 测试通过。
- **接口漂移**：无

### 2026-06-17 (Update 5: 页面重构 LearningPath & AIChat)
- **修改文件**：`src/pages/LearningPath.jsx`, `src/hooks/useLearningPath.js`, `src/components/learning/PathVisualizer.jsx`, `src/components/learning/NodeResourcePanel.jsx`, `src/pages/AIChat.jsx`, `src/components/chat/SidebarHistory.jsx`, `src/components/chat/SidebarResources.jsx`, `src/components/chat/ChatArea.jsx`
- **核心改动**：
  1. 完成 LearningPath 组件拆解：分离 SWR 数据获取 (useLearningPath) 和横向地图交互 (PathVisualizer) 以及底部资料库 (NodeResourcePanel)。主页面成为纯粹组装容器。
  2. 完成 AIChat 组件拆解：分离出 SidebarHistory、SidebarResources 和 ChatArea，消除 465 行胖组件。
  3. 修复左侧栏收缩时内容溢出 bug（在 SidebarHistory 内增加 `overflow-hidden`）。
  4. 遵循 Co-location 原则，将推荐资源的抓取与 activeKPs 派生直接下沉到 SidebarResources 内部调用。
  5. 进行代码复核，将气泡渲染的 `lastUserIndex` 计算提升至循环外，消除性能隐患。
- **测试结果**：各个组件抽取后 `npm run lint` 和 `npm run build` 测试全部通过，无告警。
- **接口漂移**：无

### 2026-06-17 (Update 6: 拆分 TeacherStudentReport - 统计卡片)
- **修改文件**：新增 `src/components/report/QuizStatsMetrics.jsx`, `src/components/report/PathProgressCard.jsx`, `src/components/report/ModalityPreferenceCard.jsx`
- **核心改动**：执行 TeacherStudentReport 组件的拆分解耦任务。抽取顶部三个独立的统计指标卡片（测试统计、路径进度、模态偏好），实现了 UI 与主容器的分离，提高了代码的可读性和维护性。
- **测试结果**：`npm run lint` 和 `npm run build` 测试通过。
- **接口漂移**：无

### 2026-06-17 (Update 7: 拆分 TeacherStudentReport - 完整解耦)
- **修改文件**：新增 `src/components/report/KnowledgeCoordinatesCard.jsx`, `src/components/report/MasteryBreakdownCard.jsx`, `src/components/report/WeakPointsCard.jsx`, `src/components/report/RecentActivityCard.jsx` 等组件，重构 `src/pages/TeacherStudentReport.jsx` 容器。
- **核心改动**：全面完成了 TeacherStudentReport 页面的 MVVM 架构重构，将近 400 行的页面组件拆解为 9 个独立的表现层子组件，状态和数据获取逻辑统一交由自定义 SWR hook `useStudentReport` 处理。同时添加了数据异常情况的降级处理与 JSDoc 类型标记。
- **测试结果**：`npm run lint` 和 `npm run build` 测试通过。
- **接口漂移**：无

### 2026-06-17 (Update 7: 拆分 TeacherStudentReport - 完整解耦)
- **修改文件**：新增 src/components/report 下所有知识解析组件，重构 TeacherStudentReport.jsx 容器。
- **核心改动**：全面完成了 TeacherStudentReport 页面的 MVVM 架构重构，将近 400 行的页面组件拆解为 9 个独立的表现层子组件，状态和数据获取逻辑统一交由自定义 SWR hook useStudentReport 处理。加入了完整的错误边界防御。
- **测试结果**：npm run lint and npm run build 测试通过。
- **接口漂移**：无

### 2026-06-19 (Task 5: Profile Refresh Service & Background Runner)
- **涉及文件**：`backend/app/services/profile_refresh_service.py`, `backend/tests/test_profile_refresh_service.py`
- **核心改动**：实现并完成了 Profile Refresh 核心服务与后台异步任务执行器 (run_profile_refresh_background)。基于 TDD 流程，为任务的创建、状态查询、画像指标的重新计算 (包括模态偏好、知识坐标、认知盲区、行为特征/意志特征、勋章规则更新) 以及在锁超时 and 异常抛出时的 AsyncTask 更新建立了单元测试。
- **测试结果**：Pytest 单元测试全部通过，涉及 profile 的 19 个相关用例全部通过，py_compile 无语法错误。
- **接口漂移**：无

### 2026-06-19 (Task 6: Route Refactoring and Translation Integration)
- **涉及文件**：`backend/app/api/v1/profile.py`, `backend/app/infrastructure/locks.py`, `backend/app/schemas/profile.py`, `backend/tests/test_profile_routes_refactored.py`
- **核心改动**：完成画像路由瘦身与重构，成功将路由代码优化至约 150 行。主要改动包括：
  1. 将 `LockAcquisitionTimeout` 异常重构为继承自 `DomainException`，由 FastAPI 全局异常处理器统一拦截处理。
  2. 移除了路由层的所有 `try-except LockAcquisitionTimeout` 代码，使异常处理更为简洁，实现自然的异常冒泡。
  3. 将 4 个 Pydantic 请求模型模型转移到独立的 `backend/app/schemas/profile.py` 文件中，解耦请求参数校验。
  4. 建立了完善的单元测试套件。
- **测试结果**：测试代码与新版路由文件编写完毕并成功提交，`py_compile` 无语法错误。
- **接口漂移**：无（已恢复 `/learning-goal` 与 `/custom-instruction` 两个历史遗留接口，以保证与前端的完全兼容性）。



---

## 2026-06-19 profile 重构收尾修复

- **改动文件**：
  - `backend/app/services/profile_presenters.py`：`profile_data` 输出从扁平 `guidance_level_current` 改为嵌套 `guidance_level: {current, updated_at}`；维度字段从 `dimensions` 改回 `profile_dimensions`，恢复原始 `{key, label, value, source}` 结构（Plan Task 2 错误引入了雷达图风格结构导致字段丢失）
  - `backend/app/api/v1/profile.py`：`/refresh` 路由在 `db.commit()` 后补加 `await db.refresh(task)`，修复访问 `task.create_time` 触发懒加载导致的 `MissingGreenlet` 500 错误
  - `backend/tests/test_profile_presenters.py`：同步更新断言，移除测试不存在行为的用例，补充 `profile_dimensions` 结构验证

- **测试结果**：24 个 profile 相关测试全部通过（test_lock_infrastructure / test_profile_service / test_profile_presenters / test_profile_dialogue_rules / test_profile_refresh_service）

- **接口漂移**：无

- **重构完成度**：Task 1–6 全部完成，718 行胖路由缩减至 181 行，5 个新模块职责清晰，前端画像页面已可正常同步与展示

## 2026-06-19 tutoring 路由分层重构

- **涉及文件**：
  - `backend/app/api/v1/tutoring.py`
  - `backend/app/services/tutoring_service.py`
  - `backend/app/services/tutoring_payload_builder.py`
  - `backend/app/services/tutoring_stream_adapter.py`
  - `backend/app/services/tutoring_presenters.py`
  - `backend/tests/test_tutoring_service.py`
  - `backend/tests/test_tutoring_privacy.py`
  - `backend/tests/test_tutoring_stream_adapter.py`
  - `backend/tests/test_tutoring_routes_refactored.py`
  - `backend/tests/test_agent_integration.py`
- **核心改动**：
  1. 将 591 行 tutoring 胖路由缩减为 203 行 Router，数据库生命周期、Agent payload、SSE 适配及 Client DTO 分别下沉到 Service / Payload Builder / Stream Adapter / Presenter。
  2. edit/regenerate 在短事务中对 Conversation 使用 MySQL `SELECT ... FOR UPDATE`，Agent 网络 I/O 前显式结束请求级只读事务。
  3. 会话列表从 `2N+2` 查询改为非空页固定 4 次有界查询；使用 MySQL 8 窗口函数稳定选择每个会话的最后一条消息。
  4. SSE Adapter 支持 UTF-8 与 data 行跨任意字节分片，并在客户端断连/生成器取消的 `finally` 路径持久化已完整接收内容。
  5. Agent payload 改为白名单构建，继续排除姓名、邮箱、学号和用户名等身份字段。
- **测试结果**：
  - MySQL 分层测试：17 passed。
  - tutoring 既有集成测试：6 passed（遗留测试模块固定使用 SQLite，单独进程运行）。
  - 定向覆盖率：82.15%，达到 >=80% 要求。
  - `py_compile`：路由、四个新 Service 模块及对应测试通过。
  - 全局 `python tests/test_api.py`：未通过；清理专用 `test_v3.db` 后运行至 profile 初始化，因遗留 SQLite 测试环境不支持生产 MySQL `GET_LOCK` 失败，与本次 tutoring 改动无关。
- **接口漂移**：Client API 无新增漂移；Agent API 无漂移。保留运行代码既有的 `action=chat|edit|regenerate`，历史 Client OpenAPI 漏记 `action` 仍作为既有文档漂移记录。
- **范围外债务**：course scope 尚未增加 enrollment 权限校验；该行为会新增 403，需要独立安全 Spec。

## 2026-06-19 teaching 查询分层与数据真实性修复

- **涉及文件**：`backend/app/api/v1/teaching.py`、`backend/app/services/teaching_service.py`、3 个 Teaching 测试文件，以及 Client API 文档。
- **核心改动**：
  1. 将 438 行 Teaching 胖路由缩减为 65 行薄 Router，权限、学生列表、学情报告和班级洞察迁入 `TeachingService`。
  2. 学生详情与学情报告统一校验有效 enrollment，未入班用户统一返回 404“学生未入班”，避免用户信息越权读取。
  3. 移除硬编码 `overall_score=75.0`，改为最新 Evaluation `mastery_table.rows[].average_score` 的有效平均值；无有效值返回 null。
  4. 学生列表使用 join 消除 N+1，并按 enrollment 时间和 ID 稳定分页；Evaluation/Profile/LearningPath 按统一规则读取最新有效记录。
  5. Quiz 汇总改为 SQL 聚合；班级路径用 MySQL 8 窗口函数确保每名学生只统计最新 LearningPath。
- **测试结果**：
  - `py_compile`：Router、Service 和 3 个测试文件通过。
  - MySQL Service：11 passed。
  - MySQL 学情 HTTP：1 passed（内部 42 项检查）。
  - MySQL 班级洞察 HTTP：1 passed。
  - 合并定向覆盖率：85%（TeachingService 86%，Router 77%）。
- **接口漂移**：Client API 有两项经批准修正：未入班学生详情由错误的 200 改为 404；`evaluation_summary.overall_score` 允许 null。Agent API 无漂移。
- **范围外债务**：`TeachingService` 当前约 589 行，查询边界已清晰但文件仍偏大；后续应单独评审是否按学生报告与班级洞察拆分 Query Service，避免未经设计继续扩展。

### 2026-06-20 环境变量清理（Spec: 2026-06-20-env-cleanup.md）
- **涉及文件**：`backend/app/core/config.py`、`backend/app/services/kg_generation.py`、`frontend/src/api/services/chat.js`、`frontend/src/api/mock/index.js`、`frontend/src/pages/TeacherConsole.jsx`、`backend/.env.example`（新增）、`frontend/.env.example`（新增）
- **核心改动**：
  1. `kg_generation.py` 删除 `import os`，消除绕过 settings 直读 `os.environ` 的反模式；`config.py` 新增 `QDRANT_URL`、`QDRANT_COURSE_KNOWLEDGE_COLLECTION` 字段。
  2. `chat.js` 删除死代码 `const useMock`，改从 `mock/index.js` 导入 `isMockEnabled`，修正 SSE mock 分支引用。
  3. `mock/index.js` 末尾 `export const isMockEnabled = useMock`，统一 mock 状态出口。
  4. `TeacherConsole.jsx` 改为从 `api/mock` 导入 `isMockEnabled`，不再直读 `import.meta.env`。
  5. 补 `backend/.env.example`、`frontend/.env.example`，覆盖所有必要变量并附说明。
- **测试结果**：`python3 -m py_compile` 两个后端文件均 OK；`npm run lint` 零报错；`npm run build` 构建通过。
- **接口漂移**：无。

### 2026-06-21 完善系统架构、流程图与重构报告文档
- **涉及文件**：`docs/architecture_flow_overview.md`、`docs/refactoring_report.md`
- **核心改动**：
  1. 全面扩展并补全系统架构与核心数据流图文档（并翻译为全中文版）。补充了“资源入库与知识图谱生成”、“多 Agent 协同课程资源生成”、“核心学习与个性化学习路径”、“个性化测试与 AI 诊断”以及“学生画像刷新与动态引导”五大模块的中文文字与 ASCII 数据流图描述，定义了前端、后端及 Agent Service 的架构与数据边界规范。
  2. 将系统画像与架构重构成果报告复制至工作区 `docs/refactoring_report.md`，总结了评估、资源、课件入库服务拆分方案及 MySQL 并发锁安全设计。
- **测试结果**：文档编辑与中文翻译完成，语法及 markdown 结构正常。
- **接口漂移**：无。
