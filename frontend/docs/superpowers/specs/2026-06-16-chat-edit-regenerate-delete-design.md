# AI 答疑页：编辑消息 / 重新生成 / 停止生成 / 删除对话 / 复制

## 1. 目标

在 AI Chat 页面增加主流 chat web 必备的 5 个交互功能，提升使用体验。

## 2. 约束

- **只操作最后一对 (user_msg, assistant_msg)**，不影响历史消息
- 不新增 DB 表结构，不改 Agent Service
- 编辑/重新生成后端只做 UPDATE，不做 DELETE/INSERT，保持消息 ID 不变
- 所有改动向后兼容

## 3. 后端改动

### 3.1 编辑与重新生成

**原理**：复用已有 `/api/v1/tutoring/chat` POST 端点，通过 `message` 内容和已有 `conversation_id` 做区分，无需新增字段。

**重新生成流程（`message == 最后一条 user_msg 内容`）：**

```
1. 验证 conversation 存在、属于当前用户
2. 查最后一条 user_msg + 最后一条 assistant_msg
3. UPDATE assistant_msg SET content='', diagrams=NULL, knowledge_points=NULL
4. 调 _assemble_tutoring_payload（exclude_message_ids = 这对的 ID）
5. SSE 流，完成后 UPDATE 回这条 assistant_msg
```

**编辑流程（`message != 最后一条 user_msg 内容`）：**

```
1. 同重新生成 1-2
2. UPDATE user_msg SET content=新文本
3. UPDATE assistant_msg SET content='', diagrams=NULL, knowledge_points=NULL
4-5. 同重新生成 4-5
```

**不新建消息行，不软删，消息 ID 不变，历史查询零改动。**

对现有调用（无 `conversation_id` 的新对话）行为完全不变。

### 3.2 删除对话（软删）

- 新增 `DELETE /api/v1/tutoring/conversations/{conversation_id}`
- 验证 `user_id == current_user.id`
- `UPDATE conversations SET is_deleted=TRUE WHERE id=...`
- 不需要级联删 messages（查询全部带 `is_deleted==False`，不显示即可）
- 不需要过 Agent Service

### 3.3 改动的后端文件

| 文件 | 改动 |
|------|------|
| `backend/app/api/v1/tutoring.py` | `/chat` 端点增加编辑/重新生成逻辑 + 新增 DELETE 端点 |
| `backend/app/schemas/operations.py` | 无改动（无需新增字段） |

## 4. 前端改动

### 4.1 复制（纯前端，无需后端）

每条 AI 消息右下角加"复制"按钮，复制 `message.content` 到剪贴板。
代码块已有复制，只需在消息级别补一个。

### 4.2 停止生成（纯前端，无需后端）

生成中时：发送按钮 → 停止按钮（红色方块图标）。
点击触发 `abortControllerRef.current()`。

### 4.3 编辑

**交互**：hover 最后一条用户消息显示编辑铅笔图标，点击后将消息内容加载到输入框，输入框显示"正在编辑..."提示。发送后走编辑流程（后端判断 `message` 变化）。

- 只对 `messages` 数组最后一条 role=user 的消息显示编辑按钮
- 编辑中：输入框内容设为原消息文本，光标定位末尾
- 发送时：`message` 已经包含新文本，无需额外参数

### 4.4 重新生成

**交互**：hover 最后一条 AI 消息底部显示重新生成按钮（↻ 图标）。

- 只对最后一条 role=assistant 的消息显示
- 点击后走重新生成流程（后端判断 `message == 原 user_msg`）

### 4.5 删除会话

**交互**：侧边栏会话列表，hover 行显示删除图标（垃圾桶），点击确认后调 DELETE。

- 确认对话框："确定删除该对话？删除后不可恢复"
- 如果删除的正是当前激活会话，清除 `activeSession` 和 `messages`

### 4.6 改动的（仅）前端文件

| 文件 | 改动 |
|------|------|
| `src/pages/AIChat.jsx` | 所有 5 个功能的 UI 和逻辑 |

## 5. 影响面评估

- 所有改动在 `conversation_id` 为空（新对话）时行为不变
- 编辑/重新生成只在已有对话中生效
- 编辑后 SSE 流的目标是已有的 assistant_msg（ID 不变），所以 `<ChatMessage>` 的 key 不变，React 不会重建该组件
- 删除会话只影响侧边栏列表，不涉及正在进行的流
