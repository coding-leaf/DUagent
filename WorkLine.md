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


