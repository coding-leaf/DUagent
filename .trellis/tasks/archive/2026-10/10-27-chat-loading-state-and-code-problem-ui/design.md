# Technical Design: 修复聊天首字流式等待状态与学习面板代码题目渲染异常

## 1. Architecture & State Flow Overview

```
User Input ("111")
      │
      ▼
sendMessage()
      ├──> append User message
      └──> append Assistant message { loading: true, content: '' }
      │
      ▼
startStream()
      ├──> abort previous controller: abortControllerRef.current?.()
      │    (DO NOT call cancelStream() which sets loading: false)
      │
      ▼
Pending / Thinking State (1~3s)
      ├──> message.loading === true
      ├──> ChatMessage: shows bouncing loading dots
      └──> Assistant actions (Regenerate, Refine, Copy) STRICTLY HIDDEN
      │
      ▼
SSE Events (text_delta, etc.)
      ├──> message.content grows
      └──> message.loading === true (actions still hidden)
      │
      ▼
workflow_completed / workflow_failed
      ├──> completeMessage() sets loading: false
      └──> Assistant actions safely rendered
```

---

## 2. Detailed Component Changes

### 2.1 ChatContext Streaming Lifecycle (`ChatContext.jsx`)
- **变更点**:
  - 在 `startStream` 中，将：
    ```javascript
    cancelStream();
    ```
    重构为细粒度的连接终止：
    ```javascript
    if (abortControllerRef.current) {
      abortControllerRef.current();
      abortControllerRef.current = null;
    }
    ```
    保留 `cancelStream` 仅供用户显式点击取消/停止生成或组件销毁卸载时调用。
  - 在 `completeMessage` 中确保 `loading: false` 正常生效。

### 2.2 ChatMessage Action Guard (`ChatMessage.jsx`)
- **变更点**:
  - 加固 `canUseAssistantActions` 条件：
    ```javascript
    const hasMeaningfulContent = typeof message.content === 'string' && message.content.trim().length > 0;
    const canUseAssistantActions = !isUser && !message.loading && !isSafetyBlocked && !message.isError && (hasMeaningfulContent || hasOrderedParts);
    ```
    防御任何意外情况下空内容或加载中状态露出操作栏。

### 2.3 Markdown Code Block Rendering (`MarkdownViewer.jsx`)
- **变更点**:
  - 原逻辑：
    ```javascript
    const match = /language-(\w+)/.exec(codeClassName || '');
    if (!inline && match) { ... }
    ```
  - 新逻辑：
    只要 `!inline` 为真（来自 ` ``` ` 代码围栏），无论是否有语言标注，均进入块级代码分支：
    ```javascript
    if (!inline) {
      const language = match ? match[1] : 'text';
      if (language === 'mermaid') { ... }
      return (
        <div className="relative rounded-xl overflow-hidden my-4 group/code shadow-sm border border-slate-200">
          <div className="flex items-center justify-between px-4 py-2 bg-slate-50 text-slate-500 text-[11px] font-mono uppercase tracking-wider border-b border-slate-200">
            <span>{match ? match[1] : 'code'}</span>
            <button onClick={() => handleCopy(codeStr)} ...>Copy</button>
          </div>
          <SyntaxHighlighter
            ...
            language={language}
          />
        </div>
      );
    }
    ```
  - 仅当 `inline === true`（来自单反引号 ` `code` `）时，返回行内 `<code className="bg-slate-100 text-cyan-700 px-1.5 py-0.5 rounded ...">`。

### 2.4 Code Sandbox Multi-line Test Cases (`CodeSandboxCard.jsx`)
- **变更点**:
  - 在 `PublicTestCases` 中，输入输出的 `<span>` 增加 `whitespace-pre-wrap font-mono break-all`：
    ```jsx
    <span className="text-slate-700 bg-slate-50 px-2 py-1 rounded border border-slate-100 min-w-[30px] inline-block whitespace-pre-wrap font-mono">
      {String(testCase.stdin || '').trim() || '(无输入)'}
    </span>
    ```

### 2.5 Workspace Tabs Metadata (`WorkspaceTabs.jsx`)
- **变更点**:
  - 在 `pluginMeta` 中补充：
    ```javascript
    PersonalizedResourceCard: { title: '个性化资源', icon: 'auto_stories' },
    ```

---

## 3. Verification & Safety
- **回归影响**: 纯前端逻辑与表现层优化，不改动后端 API 与数据库结构。
- **单测计划**:
  - 针对 `ChatContext`：验证 `sendMessage` 后首字到达前 `loading: true`，`cancelStream` 不在 `startStream` 中错误置空 `loading`。
  - 针对 `ChatMessage`：验证在 `loading: true` 且 `content: ''` 时展示加载动画且不渲染重新生成按钮；在 `content: ''` 且 `loading: false` 时同样不渲染重新生成按钮。
  - 针对 `MarkdownViewer`：增加无语言标记代码块的测试用例，验证其渲染出 SyntaxHighlighter 块级代码结构。
  - 运行全量 `npm run test:unit` 与 `check_all.py`。
