# PRD: 修复聊天首字流式等待状态与学习面板代码题目渲染异常

## Goal
彻底消除学生在聊天框发送消息后出现空白假死并提前露出操作按钮的时序缺陷，重构 `MarkdownViewer` 无语言标识代码块为标准块级容器以解决代码题输入输出断裂成药丸标签的问题，并加固学习面板用例排版与 Tab 插件元数据。

## Requirements

### 1. 聊天流与首字等待加载态时序加固 (P0)
- **文件**: `frontend/src/context/ChatContext.jsx`, `frontend/src/components/chat/ChatMessage.jsx`
- **问题**: `startStream` 内部调用了 `cancelStream()`，导致刚创建的 `{ role: 'assistant', content: '', loading: true }` 占位消息的 `loading` 瞬间被刷成 `false`。在大模型首字到达前（1~3秒），页面不展示 Loading 跳动动效，反而提前暴露出操作按钮组（`重新生成`、`继续细化`、`复制`），呈现出内容空白却“已经生成完毕”的假死状态。
- **要求**:
  - 重构 `startStream`：仅中断已有未完成的 HTTP 连接控制器（`abortControllerRef.current?.()`），严禁调用重置新消息状态的 `cancelStream()`。
  - 确保首字到达前，消息持续保持 `loading: true`，`ChatMessage` 稳定展示跳动圆点加载动效。
  - 严格限制助手操作按钮栏（`重新生成`、`继续细化`、`复制`）的显示条件：必须在 `!message.loading && !message.isError && Boolean(message.content?.trim())` 或流式真正终止后才允许展示。
  - 补充单测覆盖该状态流转时序。

### 2. Markdown 代码块块级渲染重构 (P0)
- **文件**: `frontend/src/components/common/MarkdownViewer.jsx`
- **问题**: 原 `code` 组件逻辑为 `if (!inline && match)`，当围栏代码块未显式指定语言（如标准输入输出 ```` ``` \n 1 \n 7 \n ``` ````）时，`match` 为 `null`，导致多行块级代码错误回退为行内 `<code>` 标签，多行内容被拆碎为一个个孤立的药丸标签（Pill Badge），右侧大片空白。
- **要求**:
  - 重构 `code` 组件判断逻辑：只要 `!inline`，一律作为块级代码块渲染。
  - 若无语言或无法匹配语言，默认采用 `text` 语言模式，渲染带有代码头部、复制按钮、等宽字体的正规代码块容器。
  - 只有真正的行内代码（`inline === true`）才使用 `<code className="bg-slate-100 text-cyan-700 ...">` 渲染。
  - 编写单测验证未带语言标记的多行代码块渲染。

### 3. 学习面板代码沙箱与工作区 Tab 加固 (P1)
- **文件**: `frontend/src/components/workspace/plugins/codeSandbox/CodeSandboxCard.jsx`, `frontend/src/components/workspace/WorkspaceTabs.jsx`
- **要求**:
  - 在 `CodeSandboxCard.jsx` 的 `PublicTestCases` 中，为用例输入输出增加 `whitespace-pre-wrap font-mono`，确保包含多行换行的测试输入（如 `1\n7`）能够按行对齐排版。
  - 在 `WorkspaceTabs.jsx` 的 `pluginMeta` 中补充 `PersonalizedResourceCard` 的中文标题（`个性化资源`）与图标（`auto_stories`），消除未匹配时的英文类名回退。

## Acceptance Criteria
- [ ] 聊天框输入后，AI 头像旁正确显示 3 点跳动加载动画，且在大模型流式输出完毕前，操作按钮（重新生成/复制等）绝对不提前出现。
- [ ] 代码题题目要求中无语言围栏的样例输入输出（`1\n7`）渲染为整洁的等宽代码块，不再破碎为孤立的行内药丸标签。
- [ ] 沙箱卡片公开用例多行输入正常换行显示。
- [ ] `WorkspaceTabs` 正确展示个性化资源卡片中文名称与图标。
- [ ] 前端所有单元测试 `npm run test:unit` 全部通过，全仓门禁 `python check_all.py` 全部通过。
