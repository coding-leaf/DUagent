# AI 答疑页交互增强实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 AI Chat 页面增加编辑消息、重新生成回复、停止生成、复制消息、删除会话 5 个功能

**Architecture:** 后端改 schema（加 action 字段）+ tutoring.py（三路分流 / 新增 DELETE 端点），前端改 chat.js service + AIChat.jsx。编辑/重新生成通过 `action` 参数明确表态，不走文本盲猜。

**前提条件：** 设计文档 `docs/superpowers/specs/2026-06-16-chat-edit-regenerate-delete-design.md`

---

### Task 1: 后端 schema — 新增 action 字段

**Files:**
- Modify: `backend/app/schemas/operations.py`

- [ ] **Step 1: 给 TutoringChatRequest 加 action 字段**

```python
class TutoringChatRequest(BaseModel):
    message: str
    action: str = "chat"  # "chat" | "edit" | "regenerate"
    scope: str = "course"
    course_id: Optional[str] = None
    conversation_id: Optional[str] = None
    active_kg_nodes: list[dict] = Field(default_factory=list, description="当前课程绑定资源库的 Active KG 节点精简列表")
```

新增第 3 行 `action`，其余不变。

- [ ] **Step 2: 语法检查**

Run: `python3 -m py_compile backend/app/schemas/operations.py`
Expected: 无报错

- [ ] **Step 3: 提交**

```bash
git add backend/app/schemas/operations.py
git commit -m "feat: TutoringChatRequest 增加 action 字段(chat/edit/regenerate)"
```

---

### Task 2: 后端 — /chat 端点支持 edit/regenerate 三路分流

**Files:**
- Modify: `backend/app/api/v1/tutoring.py`

**原理：** 通过 `req.action` 区分三种行为：

- `action == "chat"`：现有逻辑不变（无 conversation_id 时新建对话、有 conversation_id 时追加新轮次）
- `action == "edit"`：UPDATE 最后一条 user_msg 内容 + CLEAR 最后一条 assistant_msg 内容，复用 ID 走流
- `action == "regenerate"`：CLEAR 最后一条 assistant_msg 内容，复用 ID 走流

- [ ] **Step 1: 新增工具函数：查对话中最后一条 user/assistant 消息**

在 `_message_order_key` 函数后（约 29 行附近），新增：

```python
async def _get_last_messages(
    db: AsyncSession, conversation_id: str
) -> tuple[Message | None, Message | None]:
    """返回 (last_user_msg, last_assistant_msg)。"""
    r = await db.execute(
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.is_deleted == False,
        )
        .order_by(Message.create_time.desc(), Message.update_time.desc())
        .limit(20)  # 取足够多以找到最后一对
    )
    all_msgs = list(r.scalars().all())
    last_user = None
    last_assistant = None
    for m in all_msgs:
        if m.role == "user" and last_user is None:
            last_user = m
        elif m.role == "assistant" and last_assistant is None:
            last_assistant = m
        if last_user is not None and last_assistant is not None:
            break
    return (last_user, last_assistant)
```

- [ ] **Step 2: 修改 /chat 端点的对话处理逻辑**

在原对话处理区（现有代码约 170-216 行），替换为三路分流：

```python
    is_edit = req.action == "edit"
    is_regenerate = req.action == "regenerate"

    # 校验 conversation
    if req.conversation_id:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == req.conversation_id,
                Conversation.user_id == current_user.id,
                Conversation.is_deleted == False,
            )
        )
        conv = result.scalar_one_or_none()
        if conv is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": 40400, "message": "对话不存在", "data": None},
            )
    else:
        conv = None

    if is_edit or is_regenerate:
        # ---------- 编辑 / 重新生成 ----------
        if not req.conversation_id:
            raise HTTPException(status_code=400, detail="编辑/重新生成需要 conversation_id")
        last_user, last_assistant = await _get_last_messages(db, req.conversation_id)
        if last_user is None:
            raise HTTPException(status_code=400, detail="无可编辑的消息")

        conversation_id = req.conversation_id

        if is_edit:
            # UPDATE user_msg 内容
            await db.execute(
                sql_update(Message)
                .where(Message.id == last_user.id)
                .values(content=req.message)
            )

        # 两路都 CLEAR assistant_msg
        if last_assistant:
            await db.execute(
                sql_update(Message)
                .where(Message.id == last_assistant.id)
                .values(content="", diagrams=None, knowledge_points=None)
            )

        # 用已有 ID（不新建消息）
        user_msg_id = last_user.id
        a_msg_id = last_assistant.id if last_assistant else None

        # 边缘情况：有 user_msg 但还没 assistant_msg（极小概率）
        if a_msg_id is None:
            assistant_msg = Message(
                conversation_id=conversation_id,
                role="assistant",
                content="",
                meta_json={"scope": req.scope, "course_id": req.course_id},
            )
            db.add(assistant_msg)
            await db.flush()
            a_msg_id = assistant_msg.id

        if is_edit:
            # 编辑时更新对话标题（可选，不改也行）
            pass
    elif req.conversation_id:
        # ---------- 已有对话的新消息（追加轮次）----------
        conversation_id = req.conversation_id
        conv_result = await db.execute(
            select(Conversation).where(
                Conversation.id == req.conversation_id,
                Conversation.user_id == current_user.id,
                Conversation.is_deleted == False,
            )
        )
        conv = conv_result.scalar_one_or_none()
        if conv is None:
            raise HTTPException(status_code=404, detail="对话不存在")
    else:
        # ---------- 全新对话 ----------
        title = req.message[:50] + ("..." if len(req.message) > 50 else "")
        conv = Conversation(
            user_id=current_user.id,
            scope=req.scope,
            course_id=effective_course_id,
            title=title,
        )
        db.add(conv)
        await db.flush()
        await db.refresh(conv)
        conversation_id = conv.id

    # 非 edit/regenerate 时创建新消息
    if not (is_edit or is_regenerate):
        user_msg = Message(
            conversation_id=conversation_id,
            role="user",
            content=req.message,
            meta_json={"scope": req.scope, "course_id": req.course_id},
        )
        db.add(user_msg)
        await db.flush()

        assistant_msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            content="",
            meta_json={"scope": req.scope, "course_id": req.course_id},
        )
        db.add(assistant_msg)
        await db.flush()
        user_msg_id = user_msg.id
        a_msg_id = assistant_msg.id

    conv_ref = conv or await db.get(Conversation, conversation_id)
    if conv_ref:
        conv_ref.update_time = datetime.now(timezone.utc)
        await db.flush()

    # Commit pre-stream DB writes
    await db.commit()
```

注意：原代码中 `conversation_id = conv.id` 那行逻辑被展开到各分支里了。需要确保 `conversation_id` 在所有分支都已赋值。

- [ ] **Step 3: 修改后续的 `exclude_message_ids` 传参**

原代码（约 225-228 行）：

```python
    payload = await _assemble_tutoring_payload(
        current_user.id, req.scope, effective_course_id,
        conversation_id, req.message, db,
        exclude_message_ids={user_msg.id, a_msg_id},
    )
```

改为：

```python
    exclude_ids = set()
    if user_msg_id:
        exclude_ids.add(user_msg_id)
    if a_msg_id:
        exclude_ids.add(a_msg_id)
    payload = await _assemble_tutoring_payload(
        current_user.id, req.scope, effective_course_id,
        conversation_id, req.message, db,
        exclude_message_ids=exclude_ids,
    )
```

- [ ] **Step 4: 语法检查**

Run: `python3 -m py_compile backend/app/api/v1/tutoring.py`
Expected: 无报错

- [ ] **Step 5: 提交**

```bash
git add backend/app/api/v1/tutoring.py
git commit -m "feat: /chat 三路分流(action=chat|edit|regenerate)"
```

---

### Task 3: 后端 — DELETE 会话端点

**Files:**
- Modify: `backend/app/api/v1/tutoring.py`

- [ ] **Step 1: 在文件末尾新增 DELETE 端点**

在 `get_conversation` 端点后追加：

```python
@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    c_result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
            Conversation.is_deleted == False,
        )
    )
    conv = c_result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40400, "message": "对话不存在", "data": None},
        )
    await db.execute(
        sql_update(Conversation)
        .where(Conversation.id == conversation_id)
        .values(is_deleted=True)
    )
    await db.commit()
    return {"code": 200, "message": "success", "data": None}
```

- [ ] **Step 2: 语法检查**

Run: `python3 -m py_compile backend/app/api/v1/tutoring.py`
Expected: 无报错

- [ ] **Step 3: 提交**

```bash
git add backend/app/api/v1/tutoring.py
git commit -m "feat: 新增 DELETE /conversations/{id} 软删除会话"
```

---

### Task 4: 前端 chat.js service — 新增 deleteSession + 支持 action 参数

**Files:**
- Modify: `src/api/services/chat.js`

- [ ] **Step 1: 新增 deleteSession 方法**

在 `chatService` 对象内追加：

```javascript
  deleteSession: (sessionId) => {
    return client.delete(`/tutoring/conversations/${sessionId}`);
  },
```

- [ ] **Step 2: streamChat 中透传 action 字段到请求体**

原 `streamChat`（约 74-85 行）的 body 构建：

```javascript
      body: JSON.stringify({
        message,
        scope,
        course_id,
        conversation_id: conversation_id || null
      }),
```

改为：

```javascript
      body: JSON.stringify({
        message,
        action: params.action || 'chat',
        scope,
        course_id,
        conversation_id: conversation_id || null
      }),
```

并在函数参数声明处（约 26 行）的 JSDoc 或默认值处注明 `params.action` 可用。

- [ ] **Step 3: 提交**

```bash
git add src/api/services/chat.js
git commit -m "feat: chatService 支持 action 参数 + deleteSession"
```

---

### Task 5: 前端 — 停止生成按钮

**Files:**
- Modify: `src/pages/AIChat.jsx`

- [ ] **Step 1: 将发送按钮改为条件渲染（发送/停止）**

定位发送按钮区（当前代码约 488-494 行）：

```jsx
                  <button 
                    onClick={() => handleSendMessage()}
                    disabled={isSending || !inputValue.trim() || !activeCourseId}
                    className="w-8 h-8 rounded-lg bg-cyan-500 text-white flex items-center justify-center cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed hover:bg-cyan-600 active:scale-95 transition-all shadow-sm"
                  >
                    <Icon name="arrow_upward" className="material-symbols-outlined text-[16px]"/>
                  </button>
```

改为：

```jsx
                  {isSending ? (
                    <button
                      onClick={() => {
                        abortControllerRef.current?.();
                        abortControllerRef.current = null;
                        setIsSending(false);
                      }}
                      className="w-8 h-8 rounded-lg bg-red-500 text-white flex items-center justify-center cursor-pointer hover:bg-red-600 active:scale-95 transition-all shadow-sm"
                      title="停止生成"
                    >
                      <Icon name="close" className="material-symbols-outlined text-[16px]"/>
                    </button>
                  ) : (
                    <button
                      onClick={() => handleSendMessage()}
                      disabled={!inputValue.trim() || !activeCourseId}
                      className="w-8 h-8 rounded-lg bg-cyan-500 text-white flex items-center justify-center cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed hover:bg-cyan-600 active:scale-95 transition-all shadow-sm"
                    >
                      <Icon name="arrow_upward" className="material-symbols-outlined text-[16px]"/>
                    </button>
                  )}
```

- [ ] **Step 2: 构建检查**

Run: `npm run build`
Expected: 构建成功

- [ ] **Step 3: 提交**

```bash
git add src/pages/AIChat.jsx
git commit -m "feat: 流式生成中显示红色停止按钮"
```

---

### Task 6: 前端 — 编辑、重新生成、复制消息（含 stream 目标 ID refactor）

**Files:**
- Modify: `src/pages/AIChat.jsx`

**关键设计：**
1. 用 `streamTargetIdRef` 替代硬编码的 `'ai-placeholder'`，使 SSE 回调可以定位到已有消息
2. 编辑/重新生成时不走 `handleSendMessage`（不 append 新消息），走新的 `handleEditSubmit` / `handleRegenerate`
3. `isLastUser` 用 `lastIndexOf('user')` 计算

- [ ] **Step 1: 新增 streamTargetIdRef**

在 state 声明区（约 64-81 行附近），在 `lastMessageIdRef` 后追加：

```jsx
  const lastMessageIdRef = useRef(null);
  const streamTargetIdRef = useRef('ai-placeholder');  // <-- 新增
  const [editingMsg, setEditingMsg] = useState(null); // <-- 新增
```

- [ ] **Step 2: 修改 SSE 回调中的 target 匹配逻辑**

当前回调函数中（约 184-261 行），所有 `m.id === 'ai-placeholder'` 替换为 `m.id === streamTargetIdRef.current`。

具体改动位置：
- status 事件：约 186-209 行 `if (m.id === 'ai-placeholder')` → 改为 `if (m.id === streamTargetIdRef.current)`
- chunk 事件：约 211-219 行同样的替换
- diagram 事件：约 223-229 行
- knowledge_points 事件：约 231-238 行
- suggestion 事件：约 241-248 行

done 事件回调（约 264-290 行）：

原：

```jsx
        setMessages(prev => prev.map(m => {
          if (m.id === 'ai-placeholder') {
            const updatedToolCalls = (m.toolCalls || []).map(tc =>
              tc.status === 'running' ? { ...tc, status: 'completed' } : tc
            );
            return {
              ...m,
              id: finalMessageId,
              loading: false,
              toolCalls: updatedToolCalls
            };
          }
          return m;
        }));
```

改为：

```jsx
        setMessages(prev => prev.map(m => {
          if (m.id === streamTargetIdRef.current) {
            const updatedToolCalls = (m.toolCalls || []).map(tc =>
              tc.status === 'running' ? { ...tc, status: 'completed' } : tc
            );
            return {
              ...m,
              // 仅当是新增消息（placeholder）时才替换 ID，编辑/重走复用不变
              id: streamTargetIdRef.current === 'ai-placeholder' ? finalMessageId : m.id,
              loading: false,
              toolCalls: updatedToolCalls
            };
          }
          return m;
        }));
```

error 回调也同理替换。

- [ ] **Step 3: 修改 handleSendMessage 中设置 streamTargetIdRef**

在 `handleSendMessage` 中，发送前加一行：

```jsx
    streamTargetIdRef.current = 'ai-placeholder';
```

位置在 `setIsSending(true)` 之前或之后均可。

- [ ] **Step 4: 提取 SSE 回调为命名函数（确保被 handleSendMessage 和 handleRegenerate/EditSubmit 复用）**

将当前 `handleSendMessage` 中 `chatService.streamChat(...)` 的三个内联回调解构提取为顶层 ref：

在 state 声明区（约 `streamTargetIdRef` 旁）追加：

```jsx
  const streamOnMessageRef = useRef(null);
  const streamOnDoneRef = useRef(null);
  const streamOnErrorRef = useRef(null);
```

然后将 `handleSendMessage` 末尾的 `chatService.streamChat` 调用改为引用 ref（不再内联定义回调）：

```jsx
    abortControllerRef.current = chatService.streamChat(
      {
        message: textToSend,
        action: 'chat',
        scope: 'course',
        course_id: activeCourseId,
        conversation_id: activeSession
      },
      (msg) => streamOnMessageRef.current?.(msg),
      (data) => streamOnDoneRef.current?.(data),
      (err) => streamOnErrorRef.current?.(err),
    );
```

在组件初始化（或 `useEffect` 中）将实际回调逻辑赋给这些 ref。但更简单的方式：**在 `handleSendMessage` 函数体内、调用 streamChat 之前**，先把内联回调赋给 ref，然后通过 ref 传入。这样回调里的闭包（`setMessages`, `activeCourseId` 等）永远指向最新值：

```jsx
  const handleSendMessage = (overrideText = '') => {
    const textToSend = (overrideText || inputValue).trim();
    if (!textToSend || isSending || !activeCourseId) return;
    if (!overrideText) setInputValue('');
    if (abortControllerRef.current) abortControllerRef.current();
    lastMessageIdRef.current = null;
    streamTargetIdRef.current = 'ai-placeholder';

    setMessages(prev => {
      const userMsg = { id: `user-${prev.length}`, role: 'user', content: textToSend };
      const aiPlaceholder = { id: 'ai-placeholder', role: 'assistant', content: '', loading: true, diagrams: [], knowledge_points: [], suggestions: [], toolCalls: [] };
      return [...prev, userMsg, aiPlaceholder];
    });
    setIsSending(true);

    // 将内联回调赋值给 ref
    const targetId = 'ai-placeholder';
    streamOnMessageRef.current = (msg) => {
      /* 从原来的 handleSendMessage 内联回调直接搬过来，把 'ai-placeholder' 替换为 targetId */
      if (msg.type === 'status') {
        setMessages(prev => prev.map(m => {
          if (m.id !== targetId) return m;
          ...
        }));
      } else if (msg.type === 'chunk') {
        ...
      } else if (msg.type === 'diagram') { ... }
      else if (msg.type === 'knowledge_points') { ... }
      else if (msg.type === 'suggestion') { ... }
    };
    streamOnDoneRef.current = (doneData) => {
      setMessages(prev => prev.map(m => {
        if (m.id !== targetId) return m;
        return { ...m, id: finalMessageId, loading: false, ... };
      }));
      ...
    };
    streamOnErrorRef.current = (err) => {
      setMessages(prev => prev.map(m => {
        if (m.id !== targetId) return m;
        return { ...m, content: m.content + '\n\n[发送失败]', loading: false, isError: true, ... };
      }));
      ...
    };

    abortControllerRef.current = chatService.streamChat(
      { message: textToSend, action: 'chat', ... },
      (msg) => streamOnMessageRef.current?.(msg),
      (data) => streamOnDoneRef.current?.(data),
      (err) => streamOnErrorRef.current?.(err),
    );
  };
```

这样 `handleRegenerate` 和 `handleEditSubmit` 也可以在调用 `streamChat` 前先赋值这三个 ref，再通过 ref 传参。回调体完全一致，唯一区别是传的 `targetId` 不同（`'ai-placeholder'` vs 已有消息 ID）。

- [ ] **Step 5: 新增 handleRegenerate 和 handleEditSubmit**

在 `handleResetConversation` 后新增（约 154 行后）：

```jsx
  const handleRegenerate = () => {
    if (isSending) return;
    const lastUserMsg = [...messages].reverse().find(m => m.role === 'user');
    if (!lastUserMsg) return;

    const lastAiIdx = messages.map(m => m.role).lastIndexOf('assistant');
    if (lastAiIdx < 0) return;

    const lastAssistantId = messages[lastAiIdx].id;
    streamTargetIdRef.current = lastAssistantId;

    // 在 UI 中清空 assistant 内容并设 loading
    setMessages(prev => prev.map((m, i) =>
      i === lastAiIdx
        ? { ...m, content: '', loading: true, diagrams: [], knowledge_points: [], suggestions: [], toolCalls: [{ id: 'regenerating', name: '正在重新生成...', status: 'running' }] }
        : m
    ));
    setIsSending(true);

    if (abortControllerRef.current) abortControllerRef.current();

    // 按 Step 4 的 ref 模式：先赋回调再传 ref
    // 回调体与 handleSendMessage 中的 streamOnMessageRef.current 完全一致，
    // 仅两处不同：① 所有 'ai-placeholder' 替换为 targetId(=lastAssistantId)
    // ② done 回调中，targetId !== 'ai-placeholder' 时不替换 msg.id(id 复用不变)
    streamOnMessageRef.current = (msg) => { /* 同 handleSendMessage 回调，targetId = lastAssistantId */ };
    streamOnDoneRef.current = (doneData) => { /* 同 handleSendMessage 回调，targetId = lastAssistantId，不替换 id */ };
    streamOnErrorRef.current = (err) => { /* 同 handleSendMessage 回调 */ };

    abortControllerRef.current = chatService.streamChat(
      {
        message: lastUserMsg.content,
        action: 'regenerate',
        scope: 'course',
        course_id: activeCourseId,
        conversation_id: activeSession,
      },
      (msg) => streamOnMessageRef.current?.(msg),
      (data) => streamOnDoneRef.current?.(data),
      (err) => streamOnErrorRef.current?.(err),
    );
  };

  const handleEditSubmit = (newContent) => {
    if (!newContent.trim() || isSending) return;

    const lastUserIdx = messages.map(m => m.role).lastIndexOf('user');
    const lastAiIdx = messages.map(m => m.role).lastIndexOf('assistant');
    if (lastUserIdx < 0) return;

    let targetId = 'ai-placeholder';
    if (lastAiIdx >= 0) {
      targetId = messages[lastAiIdx].id;
    }
    streamTargetIdRef.current = targetId;

    // UI 更新：用户消息替换内容，AI 消息置为 loading
    setMessages(prev => prev.map((m, i) => {
      if (i === lastUserIdx) return { ...m, content: newContent };
      if (i === lastAiIdx) return { ...m, content: '', loading: true, diagrams: [], knowledge_points: [], suggestions: [], toolCalls: [{ id: 'regenerating', name: '正在重新生成...', status: 'running' }] };
      return m;
    }));
    setIsSending(true);

    if (abortControllerRef.current) abortControllerRef.current();

    streamOnMessageRef.current = (msg) => { /* 同 handleSendMessage 中的逻辑，用 targetId 代替 'ai-placeholder' */ };
    streamOnDoneRef.current = (doneData) => { /* 同 handleSendMessage 中的逻辑 */ };
    streamOnErrorRef.current = (err) => { /* 同 handleSendMessage 中的逻辑 */ };

    abortControllerRef.current = chatService.streamChat(
      {
        message: newContent,
        action: 'edit',
        scope: 'course',
        course_id: activeCourseId,
        conversation_id: activeSession,
      },
      (msg) => streamOnMessageRef.current?.(msg),
      (data) => streamOnDoneRef.current?.(data),
      (err) => streamOnErrorRef.current?.(err),
    );
  };
```

- [ ] **Step 6: 编辑按钮交互 + 操作按钮区渲染**

将消息列表渲染改为（替换当前约 448-451 行的简单 map）：

```jsx
                {messages.map((msg, idx) => {
                  const lastUserIndex = messages.map(m => m.role).lastIndexOf('user');
                  const lastAiIndex = messages.map(m => m.role).lastIndexOf('assistant');
                  const isLastUser = idx === lastUserIndex;
                  const isLastAi = idx === lastAiIndex;

                  return (
                    <div key={msg.id} className="group/message relative pb-3">
                      <ChatMessage message={msg} onSendMessage={handleSendMessage} />

                      {/* 编辑表单：仅最后一条用户消息在被编辑时显示 */}
                      {isLastUser && editingMsg && editingMsg.msgId === msg.id ? (
                        <div className="mt-2 bg-white border border-cyan-300 rounded-2xl p-3 shadow-sm">
                          <textarea
                            className="w-full border-none focus:ring-0 px-2 py-1 text-[15px] text-slate-800 resize-none outline-none rounded-lg bg-slate-50 min-h-[60px]"
                            value={editingMsg.content}
                            onChange={e => setEditingMsg({ ...editingMsg, content: e.target.value })}
                            autoFocus
                          />
                          <div className="flex justify-end gap-2 mt-2">
                            <button
                              onClick={() => setEditingMsg(null)}
                              className="px-3 py-1.5 text-[13px] rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 cursor-pointer transition-colors"
                            >
                              取消
                            </button>
                            <button
                              onClick={() => {
                                handleEditSubmit(editingMsg.content);
                                setEditingMsg(null);
                              }}
                              disabled={!editingMsg.content.trim() || isSending}
                              className="px-3 py-1.5 text-[13px] rounded-lg bg-cyan-500 text-white hover:bg-cyan-600 cursor-pointer disabled:opacity-50 transition-colors"
                            >
                              发送修改
                            </button>
                          </div>
                        </div>
                      ) : null}

                      {/* 操作按钮：hover 显示 */}
                      <div className="absolute -bottom-1 right-2 flex gap-0.5 opacity-0 group-hover/message:opacity-100 transition-opacity">
                        {isLastUser && !editingMsg && !isSending && (
                          <button
                            onClick={() => setEditingMsg({ msgId: msg.id, content: typeof msg.content === 'string' ? msg.content : '' })}
                            className="w-7 h-7 rounded-lg bg-white border border-slate-200 shadow-sm flex items-center justify-center text-slate-400 hover:text-slate-600 hover:border-slate-300 cursor-pointer transition-all text-[14px]"
                            title="编辑"
                          >
                            <Icon name="edit" className="material-symbols-outlined text-[16px]"/>
                          </button>
                        )}
                        {msg.role !== 'user' && !msg.loading && (
                          <button
                            onClick={() => navigator.clipboard?.writeText(typeof msg.content === 'string' ? msg.content : '').catch(console.error)}
                            className="w-7 h-7 rounded-lg bg-white border border-slate-200 shadow-sm flex items-center justify-center text-slate-400 hover:text-slate-600 hover:border-slate-300 cursor-pointer transition-all text-[14px]"
                            title="复制"
                          >
                            <Icon name="content_copy" className="material-symbols-outlined text-[16px]"/>
                          </button>
                        )}
                        {isLastAi && !msg.loading && !isSending && (
                          <button
                            onClick={handleRegenerate}
                            className="w-7 h-7 rounded-lg bg-white border border-slate-200 shadow-sm flex items-center justify-center text-slate-400 hover:text-slate-600 hover:border-slate-300 cursor-pointer transition-all text-[14px]"
                            title="重新生成"
                          >
                            <Icon name="refresh" className="material-symbols-outlined text-[16px]"/>
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
```

- [ ] **Step 7: 构建检查**

Run: `npm run build`
Expected: 构建成功

- [ ] **Step 8: 提交**

```bash
git add src/pages/AIChat.jsx
git commit -m "feat: 支持编辑消息、重新生成回复、复制消息内容"
```

---

### Task 7: 前端 — 删除会话

**Files:**
- Modify: `src/pages/AIChat.jsx`

- [ ] **Step 1: 在侧边栏会话列表中追加删除按钮**

定位 session 列表渲染区（当前代码约 366-385 行），每个 session item 改为 flex row 布局：

```jsx
                {sessions.map(session => (
                  <div key={session.id} className="group/session flex items-center">
                    <div 
                      onClick={() => {
                        if (abortControllerRef.current) {
                          abortControllerRef.current();
                          abortControllerRef.current = null;
                        }
                        setActiveSession(session.id);
                        setLeftDrawerOpen(false);
                      }}
                      className={`flex-1 px-3 py-2 rounded-lg cursor-pointer text-[13px] truncate transition-colors ${
                        activeSession === session.id 
                          ? 'bg-slate-100 text-slate-800 font-semibold' 
                          : 'text-slate-500 hover:bg-slate-50'
                      }`}
                    >
                      {session.title}
                    </div>
                    <button
                      onClick={async (e) => {
                        e.stopPropagation();
                        if (!window.confirm('确定删除该对话？删除后不可恢复。')) return;
                        try {
                          await chatService.deleteSession(session.id);
                          setSessions(prev => prev.filter(s => s.id !== session.id));
                          if (activeSession === session.id) {
                            setActiveSession(null);
                            setMessages([]);
                          }
                        } catch (err) {
                          console.error('删除对话失败:', err);
                        }
                      }}
                      className="opacity-0 group-hover/session:opacity-100 px-2 py-1 text-slate-400 hover:text-red-500 cursor-pointer transition-all"
                      title="删除对话"
                    >
                      <Icon name="delete" className="material-symbols-outlined text-[16px]"/>
                    </button>
                  </div>
                ))}
```

- [ ] **Step 2: 构建检查**

Run: `npm run build`
Expected: 构建成功

- [ ] **Step 3: 提交**

```bash
git add src/pages/AIChat.jsx
git commit -m "feat: 支持删除历史对话"
```

---

### Task 8: 综合验证

- [ ] **Step 1: 启动服务**

```bash
# 终端 1 - 后端
cd backend && python3 -m app.main &

# 终端 2 - 前端
cd frontend && npm run dev
```

- [ ] **Step 2: 验证清单**

1. **正常对话**：发送消息 → 流式回复 → 正常追加新轮次
2. **停止生成**：发送后发送按钮变红色停止按钮 → 点击 → 流中断
3. **复制消息**：hover AI 回复 → 右下角显示复制按钮 → 点击复制
4. **重新生成**：hover 最后一条 AI 回复 → 显示 ↻ 按钮 → 点击 → 该条消息清空并重新流式生成 → 同一位置替换
5. **编辑消息**：hover 最后一条用户消息 → 显示 ✏️ 按钮 → 点击 → 消息下方弹出编辑表单 → 修改 → 发送 → 用户消息内容更新 + AI 重新回复（同一位置）
6. **删除会话**：侧边栏 hover 会话 → 显示 🗑 按钮 → 点击 → 确认对话框 → 确认 → 会话消失

- [ ] **Step 3: 更新 WORKFLOW.md**

```markdown
2026-06-16 AI Chat 交互增强
- 后端: TutoringChatRequest 新增 action 字段; /chat 三路分流(chat/edit/regenerate); DELETE /conversations/{id}
- 前端: 停止生成、编辑消息、重新生成、复制消息、删除会话
- 注意: streamTargetIdRef 替代硬编码 'ai-placeholder'; isLastUser 用 lastIndexOf 计算
```
