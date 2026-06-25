# AI Chat UI 架构与工作区重构设计文档

## 背景 (Background)
当前的 `AIChat` 采用传统的三栏对话布局（历史记录-对话框-侧边资源）。随着 Agent 能力的增强，纯文本对话已无法满足复杂的交互需求。
本次重构旨在引入“声明式插件化渲染”机制，将页面核心转变为“Agent 工作区 (Workspace)”，让 Agent 能够通过输出结构化数据（JSON）驱动丰富的视图组件（图表、题目、编辑器等）。

## 目标与范围 (Scope)
* **包含 (In Scope)**:
  * 前端布局重构：左侧历史记录，中间工作区，右侧对话框。
  * `PluginRegistry` 机制的搭建与数据接口预留。
  * 基础 UI 插件实现（QuizCard, Mermaid静态图等）。
  * 供前端独立调试的本地 Mock 数据入口。
* **不包含 (Out of Scope)**:
  * 后端 SSE 流适配及 AgentScope Python 端代码开发（本期仅做前端预留）。
  * 引入过重的外部库（尽量复用现有库，需要复杂编辑器时再按需引入）。

## 架构设计 (Architecture)

### 1. 布局划分 (Layout)
基于 TailwindCSS 实现三栏弹性布局 (`flex` / `w-*`)：
- **左栏 (w-1/5)**: `SidebarHistory` - 包含历史记录与新增的分类过滤标签。
- **中栏 (w-3/5)**: `AgentWorkspace` - 核心工作区，用于挂载与展示卡片产物。
- **右栏 (w-1/5)**: `ChatArea` - 紧凑型 AI 消息流与输入框，增加 Agent 思考过程状态。

### 2. 状态管理 (State Management)
扩展现有的 `ChatContext` 预留如下数据结构：
```javascript
const workspaceArtifacts = [
  {
    id: "card-123",
    type: "QuizCard",
    props: { question: "...", choices: [] }
  }
];
```
右侧聊天流可通过特定的工具调用事件，向该数组内推入数据。

### 3. 插件注册表 (Plugin Registry)
在 `src/components/workspace/PluginRegistry.js` 中建立映射字典：
```javascript
import QuizCard from './plugins/QuizCard';
import MermaidViewer from './plugins/MermaidViewer';
import MarkdownViewer from './plugins/MarkdownViewer';

export const PluginRegistry = {
  QuizCard,
  Mermaid: MermaidViewer,
  Markdown: MarkdownViewer
  // 预留位置，按需注册第三方插件如 Monaco Editor (CodeEditor) 等
};
```
中间栏 `AgentWorkspace` 遍历 `workspaceArtifacts`，通过动态组件 `const Component = PluginRegistry[type]` 进行渲染。

## 实施建议与防重复造轮子 (Implementation Notes)
* **富文本/代码块**: 使用项目现有的 `react-markdown` + `react-syntax-highlighter`。
* **架构图/流程图**: 使用项目现有的 `mermaid`。
* **业务数据卡片**: 组合 TailwindCSS 基础组件构建。
