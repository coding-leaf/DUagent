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
- **接口漂移**：更新了部分路由路径（如从旧版的 `/learning-goal` 迁移到 `/update-goal`，`/custom-instruction` 迁移到 `/update-instruction`）。

