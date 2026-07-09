# CodeSandboxCard 前端重构设计方案

**日期：** 2026-07-10  
**状态：** 设计中 (等待评审)  
**目标组件：** `frontend/src/components/workspace/plugins/CodeSandboxCard.jsx`

---

## 1. 交互与布局设计 (LeetCode 风格)

为了提供极佳的编程体验并避免不必要的浏览器滚动条，我们将 `CodeSandboxCard` 调整为双栏分屏布局，并限制总高度为容器高度。

```text
+----------------------------------------------------------------------------------+
| CodeSandboxCard (LeetCode 风格)                                                  |
+------------------------------------+---------------------------------------------+
|                                    | [文件名.py]                 [AI答疑] [运行] |
| 题目描述                           | +-----------------------------------------+ |
| +--------------------------------+ | | 1 | def solve():                        | |
| |                                | | | 2 |     pass                            | |
| |  [Markdown 格式的题目描述]     | | | 3 |                                     | |
| |                                | | |   | ... (编辑器区域)                    | |
| |                                | | +-----------------------------------------+ |
| |                                | | [输入参数 (Stdin)]  [终端输出 (Stdout)]   | |
| |                                | | +-----------------------------------------+ |
| |                                | | | Stdout: 15                              | |
| |                                | | | CPU Time: 12ms | Memory: 120KB          | |
| +--------------------------------+ | +-----------------------------------------+ |
| [重置代码]                         |                                             |
+------------------------------------+---------------------------------------------+
```

### 1.1 布局规格说明
*   **外层容器**：`flex flex-col md:flex-row h-full w-full gap-4 overflow-hidden`。
*   **左侧栏 (题目描述)**：占宽 `md:w-[40%]`，高度充满并使用 `overflow-y-auto` 支持独立滚动。包含：
    *   顶部标题栏与重置按钮「重置代码」。
    *   渲染区：使用 `ReactMarkdown`，深度定制其标签样式（`h1/h2/h3`、`code`、`p` , `ul/ol`），使其排版规范漂亮。
*   **右侧栏 (编辑器与控制台)**：占宽 `md:w-[60%]`，高度充满，内部采用 `flex flex-col gap-4 overflow-hidden`。
    *   **编辑器区**：
        *   支持显示行号。通过一个左侧固定宽度的 gutter 容器，配合 `textarea` 的 `onScroll` 事件进行双向滚动对齐。
        *   右上角提供「请求 AI 答疑」与「运行代码」双控制键。
    *   **标签控制台**：
        *   拥有两个 Tab 页：`输入参数 (Stdin)` 与 `终端输出 (Stdout)`。
        *   运行代码时，系统会自动切到 `终端输出 (Stdout)` 展现等待动画与最终编译/运行信息。

---

## 2. 核心技术方案

### 2.1 基于 LocalStorage 的代码持久化与缓存映射

为防止刷新页面或切换工作区导致写到一半的代码丢失，引入基于题目特征哈希的轻量级缓存：

```javascript
// 计算哈希用于唯一标识题目缓存
const getCacheKey = (questionText, lang) => {
  if (!questionText) return `sandbox_code_${lang}`;
  let hash = 0;
  for (let i = 0; i < questionText.length; i++) {
    hash = (hash << 5) - hash + questionText.charCodeAt(i);
    hash |= 0;
  }
  return `sandbox_code_${lang}_${hash}`;
};
```

1.  **加载逻辑**：`useEffect` / 挂载时，优先读取 `localStorage.getItem(cacheKey)`。如果有值，则覆盖 `initialCode` 状态。
2.  **变更写入**：在 `code` 的 `onChange` 中更新本地状态并更新 `localStorage`。
3.  **重置逻辑**：点击左侧的「重置代码」按钮，将清除 `localStorage` 中对应的 key，并将编辑器状态还原为最原始的 `initialCode`。

### 2.2 编辑器行号实现方案 (免外部大型包)

为了规避引入 `monaco-editor` 导致的打包体积爆炸及环境配置风险，我们使用双列对齐技术来模拟原生 IDE 行号：

```jsx
// 1. 获取行数
const lineCount = code.split('\n').length || 1;

// 2. 滚动事件同步
const handleEditorScroll = (e) => {
  const gutter = document.getElementById('code-editor-gutter');
  if (gutter) {
    gutter.scrollTop = e.target.scrollTop;
  }
};

// 3. JSX 结构
<div className="flex flex-1 bg-slate-950 rounded-b-xl border border-slate-800 overflow-hidden font-mono text-sm leading-relaxed relative">
  {/* 行号槽 */}
  <div 
    id="code-editor-gutter" 
    className="w-12 select-none text-right pr-3 py-4 text-slate-600 bg-slate-900 border-r border-slate-800 overflow-hidden flex flex-col pointer-events-none"
  >
    {Array.from({ length: lineCount }).map((_, i) => (
      <span key={i} className="h-[21px]">{i + 1}</span>
    ))}
  </div>
  
  {/* 文本域 */}
  <textarea
    value={code}
    onChange={(e) => setCode(e.target.value)}
    onScroll={handleEditorScroll}
    className="flex-1 p-4 bg-transparent text-slate-100 border-none outline-none resize-none overflow-y-auto leading-relaxed h-full focus:ring-0"
    spellCheck="false"
  />
</div>
```
*(注意：需要精确保证行号高度 `h-[21px]` 或相同的 line-height 与 padding，从而在所有操作系统/浏览器下实现完美对齐。)*

---

## 3. UI 精细度与微交互

1.  **运行过渡状态**：
    *   点击「运行代码」后，切换至「终端输出」标签，显示带呼吸灯的加载状态：`正在向隔离沙箱投递评测任务...`
    *   运行结束时，根据结果状态展示绿色/红色/黄色底色或提示。
2.  **请求 AI 答疑**：
    *   读取 SWR 或 apiClient 最新的 execution 状态，将错误日志拼成带 Markdown 格式的提示词。
    *   按钮配有优雅的悬停阴影与滑入微动画。
3.  **支持 Stdin 动态更新**：
    *   在 Stdin Tab 页面，输入框支持多行或单行灵活配置，背景色与主终端融为一体。
