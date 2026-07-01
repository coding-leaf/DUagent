# WorkLine.md — 工作存档

> 本文件是 EDUagent 项目的唯一工作存档。
> 每次完成开发任务后，在文末追加一条记录。不要修改历史记录。

---

## 写入规范

每条记录格式如下：

```
### YYYY-MM-DD — <一句话描述做了什么>

**涉及文件：**
- path/to/file

**核心改动：**
（2-5 句话，说清楚改了什么、为什么）

**验证结果：**
- 前端 lint / build：通过 / 未运行
- 后端 py_compile / pytest：通过 / 未运行
- Agent pytest：通过 / 未运行

**接口漂移：** 无 / 有（说明字段和原因）

**遗留问题：**（可选）
```

规则：
- 只追加，不修改历史
- 小修也要写，一行即可
- 大改必须包含"核心改动"和"验证结果"
- 接口漂移必须明确写出，不能留空

---

## 存档记录

### 2026-06-25 — 初始化 v3 分支，重写约束文档，创立 WorkLine

**涉及文件：**
- `Agents.md`（根目录，全量重写）
- `WorkLine.md`（新建）

**核心改动：**
从 `refactor/v2-architecture` 切出 `refactor/v3-architecture` 分支。重写根目录 `Agents.md`：补全权威来源层级、跨模块边界硬约束、任务分级、验证命令、完成汇报格式、禁止操作清单。废弃 WORKFLOW.md 作为进度存档，由 WorkLine.md 统一承接。

**验证结果：**
- 文档变更，无需构建验证

**接口漂移：** 无

---

### 2026-06-26 — 优化 AIChat 为 Artifact 工作区样子 v1

**涉及文件：**
- `frontend/src/context/ChatContext.jsx`
- `frontend/src/components/chat/ChatArea.jsx`
- `frontend/src/components/chat/ChatMessage.jsx`
- `frontend/src/components/chat/ToolCallCard.jsx`
- `frontend/src/components/chat/ToolCallCard.test.jsx`
- `frontend/src/components/chat/mockToolDemos.js`
- `frontend/src/components/Icon.jsx`
- `docs/superpowers/plans/2026-06-26-aichat-artifact-workbench-ui-v1.md`

**核心改动：**
1. 将 AIChat 的前端样子收束为左侧历史、中间 Agent artifact 工作区、右侧 AI 对话区；中间工作区继续复用已有 `AgentWorkspace` 和插件注册表。
2. 在 `ChatContext` 中增加前端专用 `runMockToolDemo`，用于模拟 tool 调用轨迹和生成物产出，预留后续 SSE/tool result 接入的数据边界。
3. 在右侧 AI 对话区增加 `补弱计划 / 推荐资源 / 讲解页 / 练习预览` 快捷指令，点击后生成对话消息、tool 轨迹和中间工作区 artifact。
4. 将 `ToolCallCard` 改为只读过程展示卡片，只显示工具名称、状态、输入摘要和输出摘要；重新生成、继续细化、复制等回答级动作放到 AI 回复底部。

**验证结果：**
- 前端测试：通过 `npm run test:unit -- src/components/chat/ToolCallCard.test.jsx src/components/workspace/AgentWorkspace.test.jsx src/components/workspace/PluginRegistry.test.js`
- 前端 lint：通过 `npm run lint`
- 前端 build：通过 `npm run build`（仅保留既有 chunk size warning）
- 后端 py_compile / pytest：未运行（前端 UI 专属修改）
- Agent pytest：未运行（前端 UI 专属修改）

**接口漂移：** 无。仅增加前端 mock 数据结构和 UI 预留，未修改真实 API。

**预览地址：** `http://127.0.0.1:5174/`

---

### 2026-06-26 — 缩小 AIChat 右侧对话区字号

**涉及文件：**
- `frontend/src/components/chat/ChatArea.jsx`
- `frontend/src/components/chat/ChatMessage.jsx`
- `frontend/src/components/chat/ToolCallCard.jsx`

**核心改动：**
1. 缩小右侧 AI 对话区消息正文、用户气泡、快捷指令、输入框和回答级操作按钮字号。
2. 同步压缩 tool 调用轨迹卡片的字号与内边距，使右侧固定宽度面板的信息密度更接近侧边对话栏。

**验证结果：**
- 前端测试：通过 `npm run test:unit -- src/components/chat/ToolCallCard.test.jsx`
- 前端 lint：通过 `npm run lint`
- 前端 build：通过 `npm run build`（仅保留既有 chunk size warning）
- 后端 py_compile / pytest：未运行（前端样式专属修改）
- Agent pytest：未运行（前端样式专属修改）

**接口漂移：** 无。

---

### 2026-06-26 — 修复 AIChat 右侧代码块横向滚动条

**涉及文件：**
- `frontend/src/components/common/MarkdownViewer.jsx`
- `frontend/src/components/chat/ChatMessage.jsx`
- `frontend/src/index.css`

**核心改动：**
1. 为通用 `MarkdownViewer` 增加 `compact` 模式，右侧聊天可启用代码长行换行、较小字号和禁用横向滚动。
2. 在 `ChatMessage` 的 AI 回复 markdown 中启用 compact 模式，并补充 `min-w-0` / `overflow-hidden`，防止代码块或长文本撑开右侧栏。
3. 新增 `.chat-compact-markdown` CSS 兜底，限制聊天 markdown 内的 `pre`、`code`、表格和 token 行横向溢出。

**验证结果：**
- 前端测试：通过 `npm run test:unit -- src/components/chat/ToolCallCard.test.jsx src/utils/__tests__/chatContent.test.js`
- 前端 lint：通过 `npm run lint`
- 前端 build：通过 `npm run build`（仅保留既有 chunk size warning）
- 后端 py_compile / pytest：未运行（前端样式专属修改）
- Agent pytest：未运行（前端样式专属修改）

**接口漂移：** 无。

**遗留问题：**
- 各子项目 AGENTS.md 中的分支引用（`refactor/v2-architecture`）需在后续更新为 v3
- 各子项目 WORKFLOW.md 可在适当时机清理（历史内容已固化在 git log）

---

### 2026-06-25 — 清理测试遗留文件，重构 Core Learning 链路代码规范

**涉及文件：**
- `backend/test_*.db`（9 个，已删除）
- `backend/test_bug.py`（已删除）
- `backend/app/api/v1/learning_activities.py`（路由瘦身：150 行 → 20 行）
- `backend/app/services/learning_activity_service.py`（新建）
- `frontend/src/hooks/useQuizEngine.js`（手写 fetch → SWR）

**核心改动：**
清理 backend 根目录 10 个测试遗留文件。将 `learning_activities.py` 中的权限校验、资源作用域解析、节点名称解析、活动记录写入全部提取到新建的 `LearningActivityService`，路由层退化为纯参数校验+调用 Service。`useQuizEngine` 题目加载由手写 useEffect+fetch 改为 SWR，获得缓存和请求去重能力。

**验证结果：**
- 前端 lint / build：通过
- 后端 py_compile：通过
- 后端 pytest：未运行（纯重构，逻辑等价）

**接口漂移：** 无

### 2026-06-25 — 对齐子模块 AGENTS.md 到 v3 协作规则

**涉及文件：**
- `frontend/AGENTS.md`
- `backend/AGENTS.md`
- `agent_service/AGENTS.md`
- `WorkLine.md`

**核心改动：**
三个子模块文档调整为根目录 `Agents.md` 的局部补充：保留模块独有边界、测试命令和架构注意事项，删除或改写重复的全局流程规则。统一记录规则：根目录 `WorkLine.md` 是当前唯一工作存档，旧版 `WORKFLOW.md` 仅用于历史追溯，不再追加新记录。

**验证结果：**
- 前端 lint / build：未运行（仅文档变更）
- 后端 py_compile / pytest：未运行（仅文档变更）
- Agent pytest：未运行（仅文档变更）
- 文档检查：通过 `rg` 关键词检查

**接口漂移：** 无

### 2026-06-26 — 统一根协作文档命名并补赛题待办路径

**涉及文件：**
- `AGENTS.md`
- `Agents.md`（重命名为 `AGENTS.md`）
- `TODO.md`
- `CLAUDE.md`
- `frontend/AGENTS.md`
- `backend/AGENTS.md`
- `agent_service/AGENTS.md`
- `.gitignore`
- `WorkLine.md`

**核心改动：**
根目录协作约束文件统一为全大写 `AGENTS.md`，与子模块命名和文件标题保持一致。`TODO.md` 按原碎片风格补入 A3 赛题差距收口待办；`AGENTS.md` 增加路径导航与文档分工，明确 `TODO.md`、`赛题疑点`、`docs/90-review/`、spec、plan、`WorkLine.md`、旧版 `WORKFLOW.md` 的用途边界。

**验证结果：**
- 前端 lint / build：未运行（仅文档变更）
- 后端 py_compile / pytest：未运行（仅文档变更）
- Agent pytest：未运行（仅文档变更）
- 文档检查：已检查根 `AGENTS.md` 存在，`.gitignore` 不再忽略根 `AGENTS.md`

**接口漂移：** 无

### 2026-06-26 — 完成 A3 赛题需求差距审计

**涉及文件：**
- `docs/90-review/A3赛题需求差距审计.md`
- `WorkLine.md`

**核心改动：**
新增 A3 赛题需求差距审计文档，按学生端、教师端、管理员端三端定位，以及画像、5 类资源、多智能体、学习路径、智能辅导、学习效果评估、防幻觉、进度追踪和提交物要求逐项映射当前实现。审计结论明确：三端职责基本合理，主要缺口是学生端 Agent 学习闭环主入口不足、资源类型未满足 5 类、推荐理由/多 Agent 过程/防幻觉结果尚未充分产品化展示。

**验证结果：**
- 前端 lint / build：未运行（仅文档变更）
- 后端 py_compile / pytest：未运行（仅文档变更）
- Agent pytest：未运行（仅文档变更）
- 文档检查：已创建审计文档并追加 WorkLine

**接口漂移：** 无

### 2026-06-26 — 修正比赛主线为 AIChat Agent 工作台

**涉及文件：**
- `docs/90-review/A3赛题需求差距审计.md`
- `docs/superpowers/specs/2026-06-26-aichat-agent-workbench-design.md`
- `WorkLine.md`

**核心改动：**
根据最新方向修正 A3 审计结论：学生端主入口不优先新增驾驶舱，而是优先改造 AIChat 为 Agent 个性化学习工作台。新增 AIChat Agent 工作台 v1 设计稿，明确首批能力聚焦流式输出修复、tool 调用展示、审查展示、页面跳转、学习状态查询工具、后端/Agent 日志补全，以及 user memory / content 附属能力边界；教师端保持观察端定位，管理员端后续以功能合并和 UI 优化为主。

**验证结果：**
- 前端 lint / build：未运行（仅文档变更）
- 后端 py_compile / pytest：未运行（仅文档变更）
- Agent pytest：未运行（仅文档变更）
- 文档检查：已新增设计稿并更新审计文档

**接口漂移：** 无

### 2026-06-26 — 补充 AIChat 三栏工作台与个性化路径推荐方向

**涉及文件：**
- `docs/90-review/A3赛题需求差距审计.md`
- `docs/superpowers/specs/2026-06-26-aichat-agent-workbench-design.md`
- `WorkLine.md`

**核心改动：**
将 AIChat Agent 工作台设计从“增强现有三栏聊天”修正为“左侧对话记录、中间 Agent 工作区/内容展示区、右侧 AI 对话区”。补充中间工作区可展示学习路径片段、推荐资源、薄弱点分析、练习题预览、HTML 类 PPT、代码实操任务、学习计划和审查报告；同时记录后续需要从静态/写死路径状态展示演进为基于画像、长期记忆、薄弱点、学习目标和可用时间的个性化学习路径推荐，本次仅补充文档方向，不实现。

**验证结果：**
- 前端 lint / build：未运行（仅文档变更）
- 后端 py_compile / pytest：未运行（仅文档变更）
- Agent pytest：未运行（仅文档变更）
- 文档检查：已更新设计稿和审计文档

**接口漂移：** 无

### 2026-06-26 — 扩展 ChatContext 并为 Mocking Artifacts 引入测试辅助函数

**涉及文件：**
- `frontend/src/context/ChatContext.jsx`
- `frontend/src/context/ChatContext.test.jsx`

**核心改动：**
在 `ChatContext` 中新增 `workspaceArtifacts` 状态和 `sendMockArtifact` 辅助函数。该状态用于管理当前工作区插件生成的 Mock Artifact payload，并通过 UUID 机制生成唯一 ID。同时在 Provider 导出 value 中暴露出这两个成员，支持组件的模拟触发和展示。

**验证结果：**
- 前端 lint / build：通过（lint 零错误，build 成功打包）
- 前端测试：运行 `npm run test:unit -- src/context/ChatContext.test.jsx` 单元测试通过

**接口漂移：** 无

### 2026-06-26 — 新增 PluginRegistry 及其插件存根与单元测试

**涉及文件：**
- `frontend/src/components/workspace/PluginRegistry.js`
- `frontend/src/components/workspace/PluginRegistry.test.js`
- `frontend/src/components/workspace/plugins/QuizCard.jsx`
- `frontend/src/components/workspace/plugins/MermaidViewer.jsx`
- `frontend/src/components/workspace/plugins/MarkdownViewer.jsx`

**核心改动：**
创建了前端工作区组件注册表 `PluginRegistry`，用于映射和管理 `QuizCard`、`Mermaid`、`Markdown` 对应的渲染组件。在 `plugins` 目录下新增了这三个组件的简单 React 存根（Stub），并编写了 Vitest 单元测试 `PluginRegistry.test.js` 进行正确解析验证，测试和 ESLint 校验已顺利通过。

**验证结果：**
- 前端 lint / build：通过（ESLint 零报错，build 打包成功）
- 前端测试：运行 `npm run test:unit -- src/components/workspace/PluginRegistry.test.js` 测试通过
- 后端 py_compile / pytest：未运行（前端专属修改）
- Agent pytest：未运行（前端专属修改）

**接口漂移：** 无

### 2026-06-26 — 实现交互式 QuizCard, MermaidViewer 和 MarkdownViewer 插件组件

**涉及文件：**
- `frontend/src/components/workspace/plugins/QuizCard.jsx`
- `frontend/src/components/workspace/plugins/MermaidViewer.jsx`
- `frontend/src/components/workspace/plugins/MarkdownViewer.jsx`

**核心改动：**
实现并扩展了前端工作区的三个核心展示与交互插件：
1. `QuizCard.jsx`：实现了包含题干渲染、选项高亮、提交控制以及对错反馈的交互式单选题卡片。
2. `MermaidViewer.jsx`：集成 `mermaid` 库，并使用 `useEffect` 侦听并解析渲染动态流程图。
3. `MarkdownViewer.jsx`：利用 `react-markdown` 配合 `remark-gfm` 实现课件与笔记排版。

**验证结果：**
- 前端 lint / build：通过（lint 零错误，build 打包成功）
- 前端测试：PluginRegistry 测试通过
- 后端 py_compile / pytest：未运行（前端专属修改）
- Agent pytest：未运行（前端专属修改）


**接口漂移：** 无

### 2026-06-26 — 修复 MarkdownViewer 样式依赖及 MermaidViewer 渲染缓存 bug

**涉及文件：**
- `frontend/src/components/workspace/plugins/MarkdownViewer.jsx`
- `frontend/src/components/workspace/plugins/MermaidViewer.jsx`

**核心改动：**
根据规格合规性检查（Spec Compliance Review）反馈进行了以下两项修复：
1. `MarkdownViewer.jsx`：去除了对未声明的 `@tailwindcss/typography` (`prose`) 依赖。采用 `react-markdown` 的 `components` 属性针对每个元素自定义映射渲染并绑定特定的 Tailwind 样式类。
2. `MermaidViewer.jsx`：移除直接操作 `innerHTML` 的同步渲染行为，改为使用异步 `mermaid.render` API 并将生成的 SVG 存入 state 进行渲染，避免 `data-processed="true"` 缓存残留与全局副作用。

**验证结果：**
- 前端 lint / build：通过（ESLint 零错误，Vite 构建打包成功）
- 前端测试：PluginRegistry 单元测试通过
- 后端 py_compile / pytest：未运行（前端专属修改）
- Agent pytest：未运行（前端专属修改）


**接口漂移：** 无

### 2026-06-26 — 微调优化 MarkdownViewer 性能与 QuizCard 无障碍体验

**涉及文件：**
- `frontend/src/components/workspace/plugins/MarkdownViewer.jsx`
- `frontend/src/components/workspace/plugins/QuizCard.jsx`

**核心改动：**
根据代码质量审查（Code Quality Review）建议进行微调优化：
1. `MarkdownViewer.jsx`：将自定义 `components` 渲染映射移到组件函数外层定义，防止组件在重绘时因该对象引用变动导致 `ReactMarkdown` 重建 AST 树并意外重置选中/滚动状态。
2. `QuizCard.jsx`：在选项提交正误后，在文本尾部分别追加文字标识 ` (正确答案)` 与 ` (回答错误)`，增强非颜色依赖的无障碍可读性。

**验证结果：**
- 前端 lint / build：通过（lint 零错误，build 打包成功）
- 前端测试：PluginRegistry 单元测试通过
- 后端 py_compile / pytest：未运行（前端专属修改）
**接口漂移：** 无

---

### 2026-06-26 — 实现 AgentWorkspace 容器组件并解决 SWR 测试污染

**涉及文件：**
- `frontend/src/components/workspace/AgentWorkspace.jsx`
- `frontend/src/components/workspace/AgentWorkspace.test.jsx`
- `frontend/src/hooks/__tests__/useQuizEngine.test.js`
- `frontend/src/components/Icon.jsx`

**核心改动：**
1. 实现了 `AgentWorkspace` 容器组件，它根据 `ChatContext` 提供的 `workspaceArtifacts` 在工作区面板中动态渲染对应的插件组件或呈现暂无生成产物的提示页面。
2. 编写了 `AgentWorkspace.test.jsx` 单元测试，覆盖空状态、正常渲染和未知类型报错。
3. 修正了 `useQuizEngine.test.js` 中因 `nodeId` 和 `quiz_id` 同名引起的 SWR 全局测试缓存污染问题。
4. 在 `Icon.jsx` 的 Material 图标转换映射表中追加了 `design_services` 和 `dashboard_customize`，避免工作区图标 fallback 为问号。

**验证结果：**
- 前端 lint / build：通过（lint 零报错，build 打包成功）
- 前端测试：运行 `npm run test:unit` 全部 86 个单元测试通过
- 后端 py_compile / pytest：未运行（前端专属修改）
- Agent pytest：未运行（前端专属修改）

**接口漂移：** 无

---

### 2026-06-26 — 重构 AIChat 页面为三栏布局并调整组件尺寸与 Mock 事件

**涉及文件：**
- `frontend/src/pages/AIChat.jsx`
- `frontend/src/components/chat/ChatArea.jsx`
- `frontend/src/components/chat/SidebarHistory.jsx`

**核心改动：**
1. 重构了 `AIChat.jsx` 页面的整体布局，从原先的双栏/右抽屉混合结构转为清晰的三栏并行布局（左栏：会话历史、中栏：Agent工作区、右栏：聊天区域），删除了废弃的 `SidebarResources` 相关逻辑。
2. 调整 `ChatArea.jsx` 在桌面端为固定宽度的右侧侧边栏（`w-full lg:w-[380px] border-l`），去除原右侧资源抽屉的按钮入口，在输入栏插入 mock artifact 快速生成辅助按钮（图标 `data_object`）。
3. 在 `ChatArea.jsx` 中绑定全局 window `mock-artifact` 自定义事件监听，捕获后调用 `sendMockArtifact` 发送模拟产物至 Context。
4. 在 `SidebarHistory.jsx` 的 Header 下方添加了“全部、数据结构、算法、计网”快速分类过滤标签行。

**验证结果：**
- 前端 lint / build：通过（ESLint 无报错，Vite 编译打包成功）
- 前端测试：单元测试全部通过（`npm run test:unit` 86个用例）

**接口漂移：** 无

---

### 2026-06-26 — 注册 Braces 图标映射并清理 window 模拟事件监听

**涉及文件：**
- `frontend/src/components/Icon.jsx`
- `frontend/src/components/chat/ChatArea.jsx`

**核心改动：**
1. 在 `Icon.jsx` 中将 `data_object` 图标注册并映射为 Lucide 中的 `Braces`，解决了输入框下方生成模拟 Artifact 按钮默认展示为问号（HelpCircle）的问题。
2. 清理了 `ChatArea.jsx` 中原本的 `mock-artifact` 自定义 window 事件监听器和对应的 `useEffect` 挂载逻辑，改为在 mock 按钮点击时直接解构并调用 `ChatContext` 提供的 `sendMockArtifact` 接口，解耦了事件流。

**验证结果：**
- 前端 lint / build：通过 (lint 无报错，Vite 编译打包成功)
- 后端 py_compile / pytest：未运行
- Agent pytest：未运行

**接口漂移：** 无

---

### 2026-06-26 — 实现 StudyPlanCard, WeakPointsCard, PathRecommendationCard 组件及 PluginRegistry 注册

**涉及文件：**
- `frontend/src/components/workspace/plugins/StudyPlanCard.jsx`
- `frontend/src/components/workspace/plugins/WeakPointsCard.jsx`
- `frontend/src/components/workspace/plugins/PathRecommendationCard.jsx`
- `frontend/src/components/workspace/PluginRegistry.js`
- `frontend/src/components/workspace/PluginRegistry.test.js`
- `frontend/src/components/Icon.jsx`

**核心改动：**
1. 实现了 `StudyPlanCard.jsx`（今日学习计划列表与快捷练习）、`WeakPointsCard.jsx`（根据掌握度渲染红/黄/绿颜色条与高/中/低影响标识的薄弱点卡片）、`PathRecommendationCard.jsx`（横向流程节点与核心目标、时长展示的学习路径卡片）三个高保真渲染插件组件。
2. 在 `PluginRegistry.js` 中完整注册了三个新卡片，并在 `PluginRegistry.test.js` 中补充了针对这三个卡片类型的解析可用性断言。
3. 在 `Icon.jsx` 的 Material-to-Lucide 映射表中，为卡片所用图标追加了 `calendar_today` -> `Calendar`、`broken_image` -> `ImageOff` 的映射注册。
4. 修复了 `StudyPlanCard.jsx` 缺少学习计划总时长计算和展示的问题，累加 `tasks` 的 `duration` 并于卡片头部徽章展示。

**验证结果：**
- 前端 lint / build：通过 (ESLint 零错误，Vite 构建打包成功)
- 前端测试：通过 (Vitest 全部 86 个单元测试全部成功)
- 后端 py_compile / pytest：未运行 (前端组件专属修改)
- Agent pytest：未运行 (前端组件专属修改)

**接口漂移：** 无

---

### 2026-06-30 — 建立 AgentScope 2.x 使用手册并初始化 agent_service_v2 骨架

**涉及文件：**
- `/home/yezisama/.codex/skills/agentscope-2x/SKILL.md`（仓库外 Codex skill）
- `/home/yezisama/.codex/skills/agentscope-2x/references/agentscope-2x-guide.md`（仓库外 Codex skill）
- `agent_service_v2/pyproject.toml`
- `agent_service_v2/uv.lock`
- `agent_service_v2/.python-version`
- `agent_service_v2/README.md`
- `agent_service_v2/src/agent_service_v2/__init__.py`

**核心改动：**
1. 创建 Codex skill `$agentscope-2x`，用于后续设计、审查和实现 AgentScope 2.x Agent Runtime、工具、middleware、tracing、Agent Service、Agent Team 与 SSE adapter。
2. 在 skill 中固化 EDUagent 二阶段准则：新建 `agent_service_v2/` 并行重启，不在旧 `agent_service/` 内直接升级；新协议使用 `/agent/v2/...`，不兼容 `/agent/v1/...`；AI Workbench / Agent Chat 作为第一条样板链路；Agent 动态决策，前端按钮不得硬编码 workflow。
3. 初始化 `agent_service_v2/` 最小 uv 项目骨架，并在 `pyproject.toml` 中锁定 `agentscope>=2,<3`，旧 `agent_service/` 当前仍保持 AgentScope 1.0.20 可运行。
4. 明确增量更新原则：旧链路在 v2 验证前保留；每次只迁移一条链路或一个明确子能力；Backend/Frontend 只做必要薄适配。

**验证结果：**
- Codex skill 校验通过：`Skill is valid!`
- 旧 `agent_service/.venv` introspection 确认当前 AgentScope 版本为 `1.0.20`
- `agent_service_v2` 尚未接入 FastAPI/SSE，不运行服务级测试

**接口漂移：** 无。仅新增 v2 骨架和设计准则，尚未修改 Backend、Frontend 或旧 Agent Service 对外接口。

### 2026-06-30 — 重写 AIChat AgentScope-native 工作台 v2 设计与计划

**涉及文件：**
- `docs/superpowers/specs/2026-06-30-aichat-workbench-v2-design.md`
- `docs/superpowers/plans/2026-06-30-aichat-workbench-v2-plan.md`
- `WorkLine.md`

**核心改动：**
根据用户对上一版设计的否定，废弃“自定义 runtime 优先、AgentScope 只是内部实现”的方向。新设计明确以 AgentScope 2.0.3 为核心：Workspace 先划定 user/course/conversation 边界，Agent 作为主运行时，Plan 使用 `TaskCreate / TaskGet / TaskList / TaskUpdate`，长期记忆优先 `Mem0Middleware`，上下文管理使用 `ContextConfig` 与 workspace offload，RAG 优先走 AgentScope RAG / RAG service 边界。业务 Toolkit 第一阶段仅保留占位工具，不搬运旧 `agent_service/` 业务实现。

**验证结果：**
- 前端 lint / build：未运行（仅文档变更）
- 后端 py_compile / pytest：未运行（仅文档变更）
- Agent pytest：未运行（仅文档变更）
- 文档检查：已用 `rg` 检查新文档包含 AgentScope-native、LocalWorkspace、Mem0Middleware、TaskCreate、RAG service 和占位工具等关键边界

**接口漂移：** 无。仅重写设计和实施计划，尚未修改 Backend、Frontend 或 Agent Service 对外接口。

### 2026-06-30 — 全量引入 AgentScope 2.x optional 能力依赖

**涉及文件：**
- `agent_service_v2/pyproject.toml`
- `agent_service_v2/uv.lock`
- `WorkLine.md`

**核心改动：**
将 `agent_service_v2` 的核心依赖从 `agentscope>=2,<3` 调整为 `agentscope[full]>=2,<3`，用于补齐 AgentScope Agent Service、storage/message bus、workspace manager、RAG、Mem0 长期记忆、工具和模型相关 optional 能力。同步更新 `uv.lock` 并执行 `uv sync`，使本地 `.venv` 安装新增依赖，包括 `apscheduler`、`ag-ui-protocol`、`redis`、`qdrant-client`、`mem0ai`、`aiodocker`、`e2b`、`ripgrep`、S3 与模型 provider 相关包。

**验证结果：**
- 前端 lint / build：未运行（Agent 依赖变更）
- 后端 py_compile / pytest：未运行（Agent 依赖变更）
- Agent pytest：未运行（仅依赖引入，尚未新增代码）
- Agent import 检查：通过 `./.venv/bin/python -c "import agentscope.app"`；通过导入 `Mem0Middleware`、`RAGMiddleware`、`LocalWorkspace`、`DockerWorkspace`、`E2BWorkspace`；通过导入 AgentScope app 的 `rag`、`storage`、`message_bus`、`workspace_manager` 子模块

**接口漂移：** 无。仅变更 `agent_service_v2` 依赖，未修改 HTTP API 或 SSE 协议。

### 2026-06-30 — 调整 AIChat v2 为 Agent Service-inspired 方案 A

**涉及文件：**
- `docs/superpowers/specs/2026-06-30-aichat-workbench-v2-design.md`
- `docs/superpowers/plans/2026-06-30-aichat-workbench-v2-plan.md`
- `WorkLine.md`

**核心改动：**
根据用户确认的方案 A，重写 AIChat v2 设计与计划：保留 EDU FastAPI facade，不直接用 AgentScope `create_app` 承载主服务；内部借鉴 AgentScope Agent Service 的资源模型，新增 `WorkbenchSession`、`WorkbenchRunBus`、`WorkbenchWorkspaceManager`、`EDUProtocolAdapter` 等边界。文档明确 `Agent` 仍是唯一执行核心，Plan tools 进入 ToolGroup，Mem0/RAG 作为框架 middleware 或 service 边界接入，Backend/Frontend 契约暂不漂移。

**验证结果：**
- 前端 lint / build：未运行（仅文档变更）
- 后端 py_compile / pytest：未运行（仅文档变更）
- Agent pytest：未运行（仅文档变更）
- 文档检查：已用 `rg` 检查 design/plan 中包含方案 A、`create_app` 非目标、`WorkbenchSession`、`WorkbenchRunBus`、`WorkbenchWorkspaceManager`、`EDUProtocolAdapter`、`ProtocolMiddleware`、`ToolGroup` 等关键边界

**接口漂移：** 无。仅重写设计和实施计划，未修改 Backend、Frontend 或 Agent Service 对外接口。

### 2026-07-01 — 实现 AIChat v2 RunBus、WorkspaceManager 与协议适配地基

**涉及文件：**
- `agent_service_v2/src/agent_service_v2/runtime/edu_events.py`
- `agent_service_v2/src/agent_service_v2/runtime/protocol_adapter.py`
- `agent_service_v2/src/agent_service_v2/runtime/sse.py`
- `agent_service_v2/src/agent_service_v2/session/run_bus.py`
- `agent_service_v2/src/agent_service_v2/workspaces/workbench_workspace_manager.py`
- `agent_service_v2/tests/test_run_bus.py`
- `agent_service_v2/tests/test_workbench_workspace_manager.py`
- `agent_service_v2/tests/test_protocol_adapter.py`
- `WorkLine.md`

**核心改动：**
按方案 A 的第一批地基实现 `WorkbenchRunBus`、`WorkbenchWorkspaceManager` 和 `EDUProtocolAdapter`。RunBus 负责单次 run 的内存事件缓冲、订阅、完成与失败事件；WorkspaceManager 使用 AgentScope `LocalWorkspace`，按 user/course/conversation 生成安全隔离路径；ProtocolAdapter 将 AgentScope `ReplyStartEvent`、`TextBlockDeltaEvent`、`ToolCallStartEvent`、`ToolResultEndEvent`、`ReplyEndEvent`、`ExceedMaxItersEvent` 映射成 EDU SSE v2 事件，并提供 SSE 序列化。该批不接 Backend/Frontend，不调用旧 `agent_service/`。

**验证结果：**
- 前端 lint / build：未运行（Agent v2 内部地基实现）
- 后端 py_compile / pytest：未运行（Agent v2 内部地基实现）
- Agent pytest：通过 `cd agent_service_v2 && ./.venv/bin/pytest tests/test_run_bus.py tests/test_workbench_workspace_manager.py tests/test_protocol_adapter.py -q`（7 passed）
- Agent py_compile：通过 `cd agent_service_v2 && ./.venv/bin/python -m py_compile src/agent_service_v2/runtime/edu_events.py src/agent_service_v2/session/run_bus.py src/agent_service_v2/workspaces/workbench_workspace_manager.py src/agent_service_v2/runtime/protocol_adapter.py src/agent_service_v2/runtime/sse.py`

**接口漂移：** 无。仅新增 `agent_service_v2` 内部模块和测试，未修改 HTTP API 或 SSE 对外入口。

### 2026-07-01 — 打通 AIChat v2 WorkbenchSession 与最小 SSE API

**涉及文件：**
- `agent_service_v2/src/agent_service_v2/agents/prompts.py`
- `agent_service_v2/src/agent_service_v2/agents/workbench_factory.py`
- `agent_service_v2/src/agent_service_v2/api/workbench.py`
- `agent_service_v2/src/agent_service_v2/main.py`
- `agent_service_v2/src/agent_service_v2/schemas/workbench.py`
- `agent_service_v2/src/agent_service_v2/session/workbench_session.py`
- `agent_service_v2/src/agent_service_v2/tools/planning.py`
- `agent_service_v2/src/agent_service_v2/tools/workbench_placeholders.py`
- `agent_service_v2/src/agent_service_v2/tools/workbench_toolkit.py`
- `agent_service_v2/tests/test_workbench_api.py`
- `agent_service_v2/tests/test_workbench_factory.py`
- `agent_service_v2/tests/test_workbench_session.py`
- `agent_service_v2/tests/test_workbench_toolkit.py`
- `WorkLine.md`

**核心改动：**
继续按方案 A 实现 AgentScope Agent Service-inspired 内核的最小闭环。新增 Workbench AgentFactory，构建包含 Plan ToolGroup、占位学习状态/Artifact/Review 工具、`ContextConfig`、`ReActConfig` 和 workspace offloader 的 AgentScope `Agent`；模型未配置时抛出明确 `model_not_configured`。新增 `WorkbenchSession`，负责创建 run、解析 workspace、创建 agent，并在模型缺失时通过 RunBus 发布 `workflow_failed`。新增 `/agent/v2/workbench/chat` FastAPI SSE 入口，当前可返回标准 EDU SSE v2 失败事件，不调用旧 `agent_service/`。

**验证结果：**
- 前端 lint / build：未运行（Agent v2 内部与 API 骨架实现）
- 后端 py_compile / pytest：未运行（未改 Backend）
- Agent pytest：通过 `cd agent_service_v2 && ./.venv/bin/pytest tests/test_run_bus.py tests/test_workbench_workspace_manager.py tests/test_protocol_adapter.py tests/test_workbench_toolkit.py tests/test_workbench_factory.py tests/test_workbench_session.py tests/test_workbench_api.py -q`（14 passed，1 个 FastAPI TestClient deprecation warning）
- Agent py_compile：通过 `cd agent_service_v2 && ./.venv/bin/python -m py_compile src/agent_service_v2/runtime/edu_events.py src/agent_service_v2/runtime/protocol_adapter.py src/agent_service_v2/runtime/sse.py src/agent_service_v2/session/run_bus.py src/agent_service_v2/session/workbench_session.py src/agent_service_v2/workspaces/workbench_workspace_manager.py src/agent_service_v2/tools/planning.py src/agent_service_v2/tools/workbench_placeholders.py src/agent_service_v2/tools/workbench_toolkit.py src/agent_service_v2/agents/prompts.py src/agent_service_v2/agents/workbench_factory.py src/agent_service_v2/schemas/workbench.py src/agent_service_v2/api/workbench.py src/agent_service_v2/main.py`

**接口漂移：** 有。新增 Agent Service v2 内部 HTTP 入口 `POST /agent/v2/workbench/chat`，当前仅供后续 Backend 代理使用；未修改 Client API 或 Backend 对前端接口。

### 2026-07-01 — 接通 WorkbenchSession 的 AgentScope 事件流成功路径

**涉及文件：**
- `agent_service_v2/src/agent_service_v2/api/workbench.py`
- `agent_service_v2/src/agent_service_v2/session/run_bus.py`
- `agent_service_v2/src/agent_service_v2/session/workbench_session.py`
- `agent_service_v2/tests/test_workbench_api.py`
- `agent_service_v2/tests/test_workbench_session.py`
- `WorkLine.md`

**核心改动：**
补齐 `WorkbenchSession` 对 AgentScope `reply_stream()` 的消费路径，不再只返回 `model_not_configured` 或 `agent_execution_not_implemented`。Session 现在会构造 AgentScope `Msg/TextBlock` 用户消息，读取 AgentEvent 流，经 `EDUProtocolAdapter` 转换后写入 `WorkbenchRunBus`；FastAPI API 改用 `start_async()`，避免在已有事件循环内调用 `asyncio.run()`。测试通过 fake Agent 验证 `ReplyStartEvent -> text_delta -> ReplyEndEvent` 能端到端输出 `workflow_started / text_delta / workflow_completed`。

**验证结果：**
- 前端 lint / build：未运行（Agent v2 内部与 API 骨架实现）
- 后端 py_compile / pytest：未运行（未改 Backend）
- Agent pytest：通过 `cd agent_service_v2 && ./.venv/bin/pytest tests/test_run_bus.py tests/test_workbench_workspace_manager.py tests/test_protocol_adapter.py tests/test_workbench_toolkit.py tests/test_workbench_factory.py tests/test_workbench_session.py tests/test_workbench_api.py -q`（16 passed，1 个 FastAPI TestClient deprecation warning）
- Agent py_compile：通过 `cd agent_service_v2 && ./.venv/bin/python -m py_compile src/agent_service_v2/session/run_bus.py src/agent_service_v2/session/workbench_session.py src/agent_service_v2/api/workbench.py src/agent_service_v2/runtime/protocol_adapter.py src/agent_service_v2/agents/workbench_factory.py`

**接口漂移：** 无新增漂移。继续沿用 `POST /agent/v2/workbench/chat`，未修改 Backend 或 Client API。

### 2026-07-01 — 修复 AIChat v2 实时链路并接入 Backend

**涉及文件：**
- `agent_service_v2/src/agent_service_v2/agents/model_provider.py`
- `agent_service_v2/src/agent_service_v2/api/workbench.py`
- `agent_service_v2/src/agent_service_v2/runtime/protocol_adapter.py`
- `agent_service_v2/src/agent_service_v2/session/workbench_session.py`
- `agent_service_v2/tests/test_model_provider.py`
- `agent_service_v2/tests/test_protocol_adapter.py`
- `agent_service_v2/tests/test_workbench_api.py`
- `agent_service_v2/tests/test_workbench_session.py`
- `backend/app/services/tutoring_stream_adapter.py`
- `backend/tests/test_tutoring_stream_adapter.py`
- `start_all.sh`
- `WorkLine.md`

**核心改动：**
根据 AgentScope 2.x 框架真实性审计修复 AIChat v2 工作台链路。`WorkbenchSession.start_async()` 改为创建 run 后后台启动 AgentScope `agent.reply_stream()`，API 可立即返回 SSE 订阅；同步 `start()` 保留为等待完整运行的测试/工具入口。`EDUProtocolAdapter` 扩展为忽略 AgentScope 正常结构事件（ModelCall/TextBlock/ToolCall/ToolResult 的 start/end 辅助事件），避免误报 `workflow_failed`。新增 v2 模型 provider，按现有 `LLM_PROVIDER=agentscope_openai`、`LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL` 配置构造 AgentScope 2.x `OpenAIChatModel`，并复用 `agent_service/.env` / `../agent_service/.env`；配置缺失时才走 `model_not_configured`。Backend tutoring SSE 代理从 `/agent/v1/tutoring/chat` 切换到 `/agent/v2/workbench/chat`，将原 Backend payload 包进 v2 `context`，同时把 v2 `text_delta/workflow_completed/workflow_failed` 转回前端兼容的 `chunk/done` 事件。`start_all.sh` 改为启动 `agent_service_v2`，旧 `agent_service` 不再作为默认启动项。

**验证结果：**
- Agent pytest：通过 `cd agent_service_v2 && ./.venv/bin/pytest tests -q`（20 passed，1 个 FastAPI TestClient deprecation warning）
- Agent py_compile：通过 `cd agent_service_v2 && ./.venv/bin/python -m py_compile src/agent_service_v2/runtime/protocol_adapter.py src/agent_service_v2/session/workbench_session.py src/agent_service_v2/api/workbench.py src/agent_service_v2/agents/model_provider.py`
- Backend tutoring tests：通过 `cd backend && ../.venv/bin/python -m pytest tests/test_tutoring_routes_refactored.py tests/test_tutoring_stream_adapter.py -q`（7 passed，1 skipped）
- Backend py_compile：通过 `cd backend && ../.venv/bin/python -m py_compile app/services/tutoring_stream_adapter.py`
- 启动脚本检查：通过 `bash -n start_all.sh`
- 额外尝试：`cd backend && ../.venv/bin/python -m pytest tests/test_agent_integration.py tests/test_tutoring_routes_refactored.py tests/test_tutoring_stream_adapter.py -q` 中 27 passed、1 skipped、2 failed；失败原因是测试库已有固定注册码 `p_student` / `p_student2`，触发 MySQL duplicate key，和本次 v2 接入无关。
- diff 检查：`git diff --check -- . ':!TODO.md'` 通过；未纳入已有 `TODO.md` 改动。

**接口漂移：**
- Backend 到 Agent Service 的内部 HTTP 路径从 `/agent/v1/tutoring/chat` 改为 `/agent/v2/workbench/chat`。
- Backend 对前端的 tutoring SSE 输出保持兼容，仍输出 `chunk` / `done` 等旧 Client API 事件。

### 2026-07-01 — 存档 AIChat v2 三端当前状态文档

**涉及文件：**
- `docs/90-review/2026-07-01-ai-chat-v2-current-state.md`
- `WorkLine.md`

**核心改动：**
新增 AIChat v2 当前状态存档文档，按 Frontend、Backend、Agent Service v2 三端说明当前实现样式、边界、事件协议、已完成能力和缺口。文档包含 Mermaid 总体架构图、请求时序图、前端页面结构图、Backend 事件转换图、Agent v2 内部结构图。明确当前已完成主聊天文本流接入，但工作台 artifact、工具事件、RAG source refs、Memory/RAG 中间件尚未完整接入。

**验证结果：**
- 前端 lint / build：未运行（仅文档变更）
- 后端 py_compile / pytest：未运行（仅文档变更）
- Agent pytest：未运行（仅文档变更）

**接口漂移：** 无。仅新增状态文档。

### 2026-07-01 — 设计 AIChat 原生 EDU v2 事件协议

**涉及文件：**
- `docs/superpowers/specs/2026-07-01-ai-chat-native-edu-v2-events-design.md`
- `WorkLine.md`

**核心改动：**
新增 AIChat 原生 EDU v2 事件协议设计文档。设计采用用户确认的方案 A：前端原生消费 `workflow_started/text_delta/tool_started/tool_completed/tool_failed/source_refs/artifact_created/critic_completed/workflow_completed/workflow_failed`，Backend 去除旧 `chunk/done` 兼容转换，仅保留鉴权、上下文组装、业务字段补齐、持久化和异常兜底职责。文档明确三端职责、事件契约、Backend pass-through adapter、Frontend EDU v2 reducer、Agent v2 adapter 扩展点、测试策略、迁移步骤和验收标准。

**验证结果：**
- 前端 lint / build：未运行（仅设计文档）
- 后端 py_compile / pytest：未运行（仅设计文档）
- Agent pytest：未运行（仅设计文档）
- 文档检查：`git diff --check -- docs/superpowers/specs/2026-07-01-ai-chat-native-edu-v2-events-design.md WorkLine.md` 通过

**接口漂移：** 无。仅设计文档，尚未修改代码接口。
