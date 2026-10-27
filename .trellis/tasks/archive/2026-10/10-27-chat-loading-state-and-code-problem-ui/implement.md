# Implementation Plan: 修复聊天首字流式等待状态与学习面板代码题目渲染异常

## Execution Checklist

- [x] **Step 1: ChatContext 流式启动与加载状态解耦**
  - 在 `frontend/src/context/ChatContext.jsx` 中，将 `startStream` 内部调用的 `cancelStream()` 替换为细粒度的连接终止逻辑（只 abort 上一个 fetch，不把当前消息 `loading` 刷成 `false`）。
  - 在 `frontend/src/context/ChatContext.test.jsx` 中补充测试用例，验证在流开始时占位消息保持 `loading: true`。
  - 验证命令: `npm --prefix frontend test -- ChatContext`

- [x] **Step 2: ChatMessage 操作按钮显示条件防御加固**
  - 在 `frontend/src/components/chat/ChatMessage.jsx` 中加固 `canUseAssistantActions`，增加对 `hasMeaningfulContent || hasOrderedParts` 的检查，杜绝空内容时露出操作按钮。
  - 在 `frontend/src/components/chat/ChatMessage.test.jsx` 中增加在 `content === ''` 场景下的按钮隐藏断言。
  - 验证命令: `npm --prefix frontend test -- ChatMessage`

- [x] **Step 3: MarkdownViewer 无语言代码块块级渲染**
  - 在 `frontend/src/components/common/MarkdownViewer.jsx` 中重构 `code` 渲染函数，只要 `!inline` 均渲染为 `SyntaxHighlighter` 代码块（无语言默认回退为 `text`），单反引号 `inline` 代码才渲染为行内药丸标签。
  - 在 `frontend/src/components/common/MarkdownViewer.test.jsx` 中增加无语言代码围栏（如 ```` ```\n1\n7\n``` ````）的块级渲染测试。
  - 验证命令: `npm --prefix frontend test -- MarkdownViewer`

- [x] **Step 4: 学习面板测试用例换行排版与 Tab 元数据补齐**
  - 在 `frontend/src/components/workspace/plugins/codeSandbox/CodeSandboxCard.jsx` 的 `PublicTestCases` 中，输入与输出 span 增加 `whitespace-pre-wrap font-mono` 样式。
  - 在 `frontend/src/components/workspace/WorkspaceTabs.jsx` 中为 `PersonalizedResourceCard` 增加元数据配置。
  - 验证命令: `npm --prefix frontend test -- CodeSandboxCard`

- [x] **Step 5: 前端全量单元测试与全仓门禁质检**
  - 运行前端单元测试: `npm --prefix frontend run test:unit`
  - 运行全量代码风格检查: `npm --prefix frontend run lint`
  - 运行全仓门禁: `python -X utf8 check_all.py`
