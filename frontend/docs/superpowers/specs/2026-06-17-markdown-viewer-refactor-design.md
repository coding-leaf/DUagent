# 全局 MarkdownViewer 组件抽取与 ResourceDetail 渲染修复设计文档 (Design Spec)

## 1. 背景与目标 (Context & Goals)
当前前端代码中存在以下问题：
1. **渲染失效**：`ResourceDetail.jsx` 针对 AI 生成的富文本内容缺少 Markdown 解析引擎，导致排版完全错乱。
2. **代码重复与耦合**：`ChatMessage.jsx` 中内置了一套非常完善的 Markdown 和 Mermaid 渲染逻辑（近 200 行），但与聊天气泡组件高度耦合，无法复用。

**目标**：抽取全局可复用的 `MarkdownViewer` 组件，修复资源详情页的排版问题，同时为后续的全局重构打下基础，遵守“最小修改原则”。

## 2. 系统架构与模块划分 (Architecture & Modules)

### 2.1 新建工具集: `src/utils/mermaid.js`
- **内容**：提取原 `ChatMessage.jsx` 中的 `normalizeMermaidSource` 与复杂的 `sanitizeMermaidSource`（subgraph 标题转义、括号标签等逻辑）。
- **全局初始化**：在此文件中统一调用 `mermaid.initialize`，并使用原 `ChatMessage` 中的最完整配置（包含 `suppressErrors: true` 和 `errorCallback: () => {}` 等防崩溃机制）。
- **目的**：保证 Mermaid 图解渲染能力的完整保留与复用，防止功能退化，并统一应用全局配置。

### 2.2 新增目录与模块: `src/components/common/MarkdownViewer.jsx`
- **注意**：需新建 `src/components/common/` 目录。
- **定位**：自带富文本样式的全局 Markdown 渲染器。
- **UI 特性（统一提供，无需 Override）**：
  - 继承自原聊天气泡的整套 UI：带“语言标签 + 复制按钮”的代码块 (`SyntaxHighlighter` + `vscDarkPlus` 主题)。
  - 带“图解模式标题 + schema 图标”的 Mermaid 块。
  - 特定样式的行内代码（`bg-slate-100 text-cyan-700`）。
  - 带完整 Loading 状态（"正在生成可视化图解..."）和错误源码 fallback 的 `MermaidDiagram`。
- **职责**：内部集成 `react-markdown`、`SyntaxHighlighter` 和 `MermaidDiagram`。
- **接口属性 (Props)**：`<MarkdownViewer content={text} className={...} />`。
  - `className` 会通过模版字符串直接追加（Append）到最外层的包装容器上。这样 `ChatMessage` 中特有的 `text-white`（用户）和 `text-slate-700`（AI）等字体颜色控制类就能被安全地传递生效。

### 2.3 修改模块: `src/components/chat/ChatMessage.jsx`
- **改动**：移除其内部所有的 Markdown/Mermaid 渲染逻辑、导入语句、`mermaid.initialize` 及帮助函数（移交给 `MarkdownViewer` 和 `mermaid.js`）。
- **接入**：导入 `MarkdownViewer`，将原有的 `<ReactMarkdown>...</ReactMarkdown>` 替换为 `<MarkdownViewer content={extractModelText(message.content)} className={isUser ? 'text-white' : 'text-slate-700 text-[15px]'} />`。

### 2.4 修改模块: `src/pages/ResourceDetail.jsx`
- **清理工作 (关键)**：明确删除本文件顶部的 `mermaid` 导入、`mermaid.initialize`、`normalizeMermaidSource` 函数，以及 `MermaidDiagram` 内部组件的定义。同时，**删除包裹资源的 `<section>` 标签上冗余的 `prose prose-slate...` 等 Tailwind Typography 相关类**，以防止与 `MarkdownViewer` 的原生样式冲突。
- **改动**：移除原有的条件渲染分支（`<pre><code>` 以及 `whitespace-pre-wrap`）。
- **数据自适应层 (Adapter)**：预处理逻辑保留在 `ResourceDetail.jsx` 内部的 `getDisplayContent` 后独立处理：
  ```javascript
  let finalContent = getDisplayContent(resource) || '';
  if (resource.type === 'mindmap' && !/^```/m.test(finalContent)) {
    // 兼容所有图解代码块如 ```mermaid 或 ```mindmap
    finalContent = `\`\`\`mermaid\n${finalContent}\n\`\`\``;
  } else if (resource.type === 'code' && !finalContent.includes('```') && !/^#+\s/m.test(finalContent)) {
    // 使用正则判断是否包含 Markdown 标题。如果不包含代码块且非 Markdown 格式，用通用语言块包裹
    finalContent = `\`\`\`\n${finalContent}\n\`\`\``; 
  }
  ```
- **接入**：导入 `<MarkdownViewer content={finalContent} className="markdown-body break-words leading-[1.7] text-[15px] text-slate-700" />`。

## 3. 依赖确认与测试检查步骤
- **依赖确认**：已核实 `package.json` 中存在 `remark-gfm`, `react-syntax-highlighter`, `react-markdown`, `mermaid`，**无需任何 npm install**。
- **测试检查**：
  - 执行修改后，必须运行 `npm run lint` 和 `npm run build`。
  - 界面测试：检查聊天界面的旧消息气泡、导图是否依然正常；检查资源详情页是否能完美渲染代码块及图解。

## 4. 后续重构计划 (Agenda for WORKFLOW.md)
将在项目的 `WORKFLOW.md` 中添加如下全局重构与技术债清理计划日程：
- 抽取全局状态管理和重复的 Context。
- 标准化接口请求层（Axios）与统一错误处理。
- 梳理冗余 UI 组件并迁移至统一组件库。
