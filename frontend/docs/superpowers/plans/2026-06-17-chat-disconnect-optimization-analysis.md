# 学生端页面切换断联 — 优化方案分析

**背景：** 当前学生端 AIChat 页面切换时，因组件 unmount 导致 SSE 连接中断、聊天状态丢失。

**根因：** 聊天状态（messages/SSE abortController）绑定在 `AIChat.jsx` 组件局部 state 内，React Router 页面切换触发组件卸载和清理函数。

---

## 方案总览

| 方案 | 复杂度 | 是否解决断联 | 状态保持 | 覆盖范围 | 评估 |
|------|--------|-------------|---------|---------|------|
| A. localStorage 持久化 | ★ | 否 | 仅 messages | 所有页面 | 静态保持，仍断联 |
| B. ChatContext 全局状态 | ★★ | 是 | messages + SSE | 所有页面 | 推荐 |
| C. StudentLayout + Outlet | ★★ | 是 | messages + SSE | 学生路由 | 需配合 B |
| D. 浮动聊天窗架构 | ★★★ | 是 | messages + SSE + UI | 所有页面 | UI 大改 |
| **E. ChatContext + StudentLayout** | **★★** | **是** | **messages + SSE** | **所有页面** | **推荐** |

---

## 方案 A：localStorage 持久化

**原理：** unmount 时将 messages 序列化到 localStorage，remount 时恢复。SSE 仍会中断。

**文件改动：**
- Modify: `src/pages/AIChat.jsx`

**核心改动：**
```jsx
// 在 AIChat.jsx 中
const CHAT_STORAGE_KEY = 'ai_chat_messages';

useEffect(() => {
  // 挂载时恢复
  const saved = localStorage.getItem(CHAT_STORAGE_KEY);
  if (saved) {
    try { setMessages(JSON.parse(saved)); } catch {}
  }
}, []);

// unmount 时保存
useEffect(() => {
  return () => {
    localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(messages));
  };
}, [messages]);
```

**问题：**
- SSE 依然中断（在回复过程中切页面 → 回复丢失）
- 大数据量 messages 可能超出 localStorage 5MB 限制
- 仅保持静态数据，不保持连接状态

**结论：** 治标不治本，不推荐作为主方案。

---

## 方案 B：ChatContext 全局状态（推荐）

**原理：** 将聊天状态（messages、sessions、SSE 连接、abortController）提升到 `ChatContext`，挂载在 App 层，页面切换不卸载。

**核心架构：**
```
App
└── AuthProvider
    └── CourseProvider
        └── ChatProvider          ← 新增
            └── Routes
                └── AIChat (消费 ChatContext)
```

**文件改动：**
- Create: `src/context/ChatContext.jsx`
- Modify: `src/App.jsx`（包装 ChatProvider）
- Modify: `src/pages/AIChat.jsx`（读取/写入 ChatContext 代替局部 state）

**ChatContext 内部：**
- `messages`, `sessions`, `activeSession` 提升到 context
- `abortControllerRef` 使用 ref 在 context 内持有
- `streamOnMessage/OnDone/OnError` 回调在 context 内管理
- 提供 `sendMessage()`, `regenerate()`, `editMessage()`, `resetConversation()` 等 action
- SSE fetch 在 context 中发起，挂载在 provider 层级，不受页面路由影响

**AIChat.jsx 改动：**
- 删除 `useState` 级别的 messages/sessions/abortController 局部 state
- 改为 `const { messages, sessions, sendMessage, ... } = useChat()`
- UI 渲染逻辑几乎不变，只改数据来源
- `normalizeMessage`, `normalizeMessages` 等纯函数可以移到 utils 或保留

**优点：**
- 所有页面间切换聊天状态保持，导航回 AIChat 看到完整对话
- SSE 连接在后台持续接收（即使用户去看 Dashboard，AI 回复仍在流式渲染）
- Provider 可以做到只挂载一次，卸载时才清理
- 兼容未来加浮动窗功能

**缺点：**
- 需重构 AIChat 数据流向（提取~200 行状态逻辑到 context）
- 注意：ChatContext 如果只包 AIChat route 则切换页面仍会卸载 → **必须包到 Routes 外层**

**关键实现细节：**

```jsx
// App.jsx
<ChatProvider>
  <Routes>
    <Route path="/ai-chat" element={<ProtectedRoute><AIChat /></ProtectedRoute>} />
    ...
  </Routes>
</ChatProvider>
```

```jsx
// ChatContext.jsx
export function ChatProvider({ children }) {
  const [messages, setMessages] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [activeSession, setActiveSession] = useState(null);
  const [isSending, setIsSending] = useState(false);
  const abortRef = useRef(null);
  const { activeCourseId } = useCourse();

  // sync sessions / fetch history on activeCourseId/activeSession change
  // expose: messages, sessions, activeSession, isSending,
  //        sendMessage(), regenerate(), editMessage(), resetConversation(),
  //        setActiveSession, setSessions, setMessages

  return (
    <ChatContext.Provider value={value}>
      {children}
    </ChatContext.Provider>
  );
}
```

---

## 方案 C：StudentLayout + Outlet

**原理：** 用 React Router 的 Layout Route 模式创建 `StudentLayout`，所有学生页面共享布局。但**仅靠 layout 不解决状态保持问题**，必须配合 ChatContext 或类似机制。

**文件改动：**
- Create: `src/layouts/StudentLayout.jsx`
- Modify: `src/App.jsx`（路由结构重写）

**路由结构变化：**

```
// 之前 — 扁平路由
<Route path="/dashboard" element={...} />
<Route path="/ai-chat" element={...} />

// 之后 — Layout 路由
<Route element={<StudentLayout />}>
  <Route path="/dashboard" element={...} />
  <Route path="/ai-chat" element={...} />
</Route>
```

**StudentLayout 职责：**
- Navbar（现在每个页面自己 import Navbar，可以提到 layout 统一管理）
- 页面容器（h-screen, pt-16 等公共布局）
- `<Outlet />` 渲染子路由

**优点：**
- 解决 Navbar 在每个页面单独引用的问题（DRY）
- 布局 level 的组件不会在子路由切换时 unmount
- 为浮动窗方案提供布局基础

**缺点：**
- 不解决根本的 SSE 断联问题 — 需要配合 ChatContext 一起用
- 需要改动所有学生页面的 JSX（移除各自的 Navbar + 外层容器 div）

**修正：** 方案 C 单独不做状态保持，它只是给了 ChatContext 一个更好的架构基础。

---

## 方案 D：浮动聊天窗架构

**原理：** 不再将 AIChat 作为独立路由页面，而是改造为全局可展开/收起的浮动窗，永远挂载在 App/Layout 层，不随路由切换卸载。

**文件改动：**
- Create: `src/context/ChatContext.jsx`
- Create: `src/components/chat/FloatingChat.jsx`（浮动窗 UI）
- Modify: `src/App.jsx` 或 `src/layouts/StudentLayout.jsx`
- Delete/Refactor: `src/pages/AIChat.jsx`（大部分功能移到浮动窗组件）

**架构：**

```
StudentLayout
├── Navbar
├── Outlet (其他页面内容)
└── FloatingChat (固定在右下角)
    ├── 展开/收起按钮
    ├── 消息列表
    └── 输入框
```

**优点：**
- 聊天从"页面"变成"功能"，用户体验最好
- 切换页面时聊天完全不受影响
- Navbar 可以多个位置放快速入口

**缺点：**
- UI 设计量大 — 聊天窗在窄屏（移动端如何展示？）
- 需要对 ChatContext 做同样的事（状态提升无法绕过）
- 在功能打通阶段，UI 改造成本与收益需要权衡

**最少化路径：** 先做 ChatContext（方案 B），浮动窗是后续可选 UI 升级。

---

## 方案 E：ChatContext + StudentLayout 混合方案（首选推荐）

**原理：** 先用 ChatContext 解决核心的状态保持/SSE 断联问题，同时引入 StudentLayout 让架构更清晰。这是渐进式路径：B 是必做，C 是锦上添花。

**分阶段执行：**

### Phase 1：ChatContext（核心）
- Create: `src/context/ChatContext.jsx`
- Modify: `src/App.jsx`（包 ChatProvider 到 routes 外层）
- Modify: `src/pages/AIChat.jsx`（消费 ChatContext 代替局部 state）

将以下状态从 AIChat 移到 ChatContext：
- `messages`, `sessions`, `activeSession`, `isSending`
- `abortControllerRef`, `lastMessageIdRef`, `streamTargetIdRef`
- `streamOnMessageRef`, `streamOnDoneRef`, `streamOnErrorRef`
- 所有 handle 函数：`handleSendMessage`, `handleRegenerate`, `handleEditSubmit`, `handleResetConversation`

AIChat 中保留：
- UI 渲染逻辑（JSX）
- `inputValue`（纯 UI state）
- `editingMsg`（纯 UI state）
- drawer/collapse 相关 state（纯 UI state）

### Phase 2：StudentLayout（可选）
- Create: `src/layouts/StudentLayout.jsx`
- Modify: `src/App.jsx`（Layout Route 改造）
- Modify: 所有学生页面（移除 Navbar 和外层容器）

---

## 推荐执行路径

**选 E（推荐），但分两阶段：**

**Phase 1（必做 — ChatContext）：**
- 解决核心问题：切换页面不断联、状态不丢失
- 文件：2 个创建 + 1 个修改 ≈ ~250 行新代码
- 风险：低（纯数据层重构，UI 不变）
- 验证：在 AIChat 发起对话 → 切到 Dashboard → 切回 AIChat → 对话仍在

**Phase 2（建议 — StudentLayout）：**
- 架构优化：Navbar 统一管理、布局级持久化
- 文件：1 个创建 + 1 个修改 + 所有学生页面修改
- 风险：中（需要改所有学生页面 JSX，可能有遗漏）

---

## 反对的方案及理由

- **方案 A（localStorage）**：治标不治本，SSE 仍然中断，数据完整性问题
- **方案 D（浮动窗）**：在当前阶段成本过高（UI 大改），建议先解耦状态层，UI 层可后续升级
- **方案 C 单独做**：没有 ChatContext 配合则无法保持 SSE 和状态

---

## 验证标准

```bash
# 1. Phase 1 验证：切换页面不丢状态
# 在 /ai-chat 发起一个 AI 对话 → 点击导航到 /dashboard
# → 点击导航回到 /ai-chat → 对话历史完整显示
# → SSE 流式输出在后台持续完成（不需要等到回到页面才完成）

# 2. Phase 1 验证：取消功能正常
# 在 /ai-chat 发起对话 → 在回复过程中切走 → 切回来 → 停止按钮可正常终止 SSE

# 3. Phase 2 验证：Navbar 统一
# 所有学生页面顶栏一致，Navbar 不随页面切换闪烁

# 4. 构建检查
npm run lint && npm run build
```
