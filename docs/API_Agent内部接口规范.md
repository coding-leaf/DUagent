# Agent Service 内部接口规范 (v4.1)

> 本文档定义后端 (Backend) 与 Agent Service 之间的全部 HTTP 接口。
> 基础 URL: `http://agent-service:8002`
> 无需鉴权（内网 RPC 调用）。
> Agent 强制使用 Pydantic Structured Output 保证返回严格 JSON。

---

## 1. 智能辅导对话

- **POST** `/agent/v1/chat`
- **工作流模式**: 单体 Agent + Tool Calling (SSE 流式返回)
- **触发时机**: 用户在对话页面发送消息时，后端组装上下文后调用

### Request

```json
{
  "user_id": "u_123",
  "message": "递归的终止条件怎么理解？",
  "user_profile": {
    "modality_preference": { "video": 30, "chart": 25, "text": 15, "code": 20, "formula": 10 },
    "guidance_level": "L2",
    "knowledge_coordinates": { "mastered": ["顺序表", "链表"], "learning": ["二叉树遍历"] },
    "cognitive_blind_spots": ["递归边界条件", "指针越界"],
    "drive_intent": "daily",
    "discipline_base": "bronze"
  },
  "recent_history": [
    { "role": "user", "content": "什么是二叉树？" },
    { "role": "assistant", "content": "二叉树是一种树形结构..." }
  ],
  "global_summary": "用户是个初学者，正在学数据结构，偏好图表解释。"
}
```

| 字段 | 类型 | 必填 | 来源 | 说明 |
|------|------|------|------|------|
| `user_id` | string | Y | 后端 JWT 解析 | 用户唯一标识，Agent 用它在 Qdrant 中检索该用户的长期记忆 |
| `message` | string | Y | 前端用户输入 | 当前这一轮的用户消息 |
| `user_profile` | object | Y | 后端从 SQL 查出 | 完整 6 维画像 JSON |
| `user_profile.modality_preference` | object | Y | SQL | 各模态百分比，影响回答中的示例类型偏好 |
| `user_profile.guidance_level` | string | Y | SQL | `"L1"` 启发点拨 / `"L2"` 伴学拆解 / `"L3"` 保姆生成 |
| `user_profile.knowledge_coordinates` | object | Y | SQL | `mastered`: 已掌握知识点列表; `learning`: 正在学习的 |
| `user_profile.cognitive_blind_spots` | array[string] | Y | SQL | 用户易错/薄弱的知识点列表 |
| `user_profile.drive_intent` | string | Y | SQL | `"daily"` 日常学习 / `"exam_cram"` 考前突击 |
| `user_profile.discipline_base` | string | Y | SQL | `"bronze"` / `"silver"` / `"gold"` 整体水平分档 |
| `recent_history` | array[object] | Y | 后端从 SQL 查最近 N 轮 | 每项含 `role`("user"/"assistant") 和 `content` |
| `global_summary` | string | Y | 后端从 SQL 查 | 全局历史压缩摘要 |

### Agent 内部处理流程

```
1. 用 user_id + message 在 Qdrant(user_memory) 向量搜索 → 召回长期记忆 facts
2. 用 message 在 Qdrant(course_knowledge) 向量搜索 → 召回课程资料
3. 组装 Prompt = [System(含guidance_level规则)] + [global_summary] + [user_profile]
                + [recalled_facts] + [course_chunks] + [recent_history] + [message]
4. 调用讯飞星火 LLM，根据需要调用 Tools (search_knowledge / draw_diagram / run_code)
5. SSE 流式返回
```

### Response (SSE Stream)

```text
event: message
data: {"type": "status", "content": "正在检索知识库..."}

event: message
data: {"type": "text", "content": "递归的终止条件是指"}

event: message
data: {"type": "text", "content": "函数停止调用自身的判断..."}

event: message
data: {"type": "tool_call", "tool_name": "draw_diagram", "tool_args": {"type": "mermaid", "code": "graph TD; A-->B; A-->C;"}}

event: message
data: {"type": "profile_update_suggestion", "content": {"cognitive_blind_spots_removed": ["递归边界条件"]}}

event: done
data: {"status": "finished"}
```

| event | data.type | 说明 |
|-------|-----------|------|
| `message` | `status` | 阶段状态提示文本 |
| `message` | `text` | 回答内容片段，前端逐字追加显示 |
| `message` | `tool_call` | 工具调用，前端根据 `tool_name` 渲染（如 Mermaid 图） |
| `message` | `profile_update_suggestion` | (可选) 随学随新机制，Agent 发现用户掌握了某盲点时，建议后端更新画像 |
| `done` | — | 本次请求结束 |
| `error` | — | 异常信息: `{"error": "描述"}` |

---

## 2. 记忆压缩与事实提取

- **POST** `/agent/v1/memory/compress`
- **工作流模式**: Pipeline 状态机（同步返回 JSON）
- **触发时机**: 后端检测到用户累计对话满 10 轮后自动调用

### Request

```json
{
  "user_id": "u_123",
  "old_summary": "用户是个初学者，正在学C语言。",
  "recent_dialogues": [
    { "role": "user", "content": "指针太难了，总是段错误" },
    { "role": "assistant", "content": "段错误通常是因为访问了未分配的内存地址..." },
    { "role": "user", "content": "那怎么调试呢？" },
    { "role": "assistant", "content": "推荐使用 valgrind 工具..." }
  ]
}
```

| 字段 | 类型 | 必填 | 来源 | 说明 |
|------|------|------|------|------|
| `user_id` | string | Y | 后端 | Agent 用它在 Qdrant 中按 user_id 分区存储提取的 facts |
| `old_summary` | string | Y | 后端从 SQL 查 `user_summary.summary` | 上一次压缩后的全局摘要 |
| `recent_dialogues` | array[object] | Y | 后端从 SQL 查最早的 10 轮 | 待压缩的原始对话列表 |

### Agent 内部处理流程

```
Step 1: 轻量 LLM 融合 old_summary + recent_dialogues → new_summary
Step 2: LLM 从 recent_dialogues 提取事实 → ["卡点：指针段错误", "偏好：图解内存"]
Step 3: 将 facts 向量化 → 存入 Qdrant(user_memory)，metadata 含 user_id 和 timestamp
```

### Response

```json
{
  "new_summary": "用户是个初学者，正在学C语言。目前在学习指针，经常遇到段错误，对内存地址概念模糊，偏好图解方式理解。",
  "extracted_facts": [
    "卡点：指针段错误",
    "偏好：需要图解内存",
    "工具：已推荐 valgrind"
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `new_summary` | string | 后端拿到后更新 SQL `user_summary.summary` 字段 |
| `extracted_facts` | array[string] | 仅供后端日志记录，实际 facts 已由 Agent 存入 Qdrant |

---

## 3. 测验评估与画像更新

- **POST** `/agent/v1/assessment/evaluate`
- **工作流模式**: Pipeline 状态机（同步返回 JSON）
- **触发时机**: 用户提交测验答题后，后端调用

### Request

```json
{
  "user_id": "u_123",
  "current_profile": {
    "guidance_level": "L2",
    "cognitive_blind_spots": ["指针越界"]
  },
  "current_mastery": {
    "kp_binary_tree": 0.5,
    "kp_recursion": 0.3
  },
  "quiz_data": {
    "knowledge_point_id": "kp_traversal",
    "knowledge_point_name": "二叉树遍历",
    "questions": [
      {
        "id": "q1",
        "question": "前序遍历的顺序是？",
        "options": { "A": "根左右", "B": "左根右", "C": "左右根" },
        "correct_answer": "A"
      },
      {
        "id": "q2",
        "question": "递归遍历的终止条件是？",
        "options": { "A": "节点为空", "B": "节点为叶子", "C": "深度超限" },
        "correct_answer": "A"
      }
    ],
    "user_answers": { "q1": "A", "q2": "C" }
  }
}
```

| 字段 | 类型 | 必填 | 来源 | 说明 |
|------|------|------|------|------|
| `user_id` | string | Y | 后端 | 用户标识 |
| `current_profile` | object | Y | 后端从 SQL 查 | 当前画像的部分字段（Agent 需要参考来调整建议） |
| `current_mastery` | object | Y | 后端从 SQL 查 | 各知识点当前掌握度 `{"[kp_id]": 0.0~1.0}` (动态 Key) |
| `quiz_data.knowledge_point_id` | string | Y | 后端 | 本次测验对应的知识点 ID |
| `quiz_data.knowledge_point_name` | string | Y | 后端 | 知识点中文名 |
| `quiz_data.questions` | array | Y | 后端从 SQL 查题目 | 题目列表，含 `correct_answer` |
| `quiz_data.user_answers` | object | Y | 前端提交 | 用户的答案 `{"[q_id]": "选项"}` (动态 Key) |

### Agent 内部处理流程

```
Step 1: 代码对比 user_answers vs correct_answer → 计算 score = 答对数/总题数
Step 2: LLM 分析错题原因 → 输出 evaluation_text + 提取 weak_points
Step 3: 代码更新 mastery: new_mastery[kp_id] = score (或加权平均)
Step 4: 代码查 knowledge_graph.json → 找出前置依赖满足且 mastery 最低的节点
Step 5: LLM 判断是否需要调整 guidance_level（输出枚举值）
```

### Response

```json
{
  "score": 50,
  "evaluation_text": "你对前序遍历掌握得很好，但对递归终止条件理解有误。递归遍历在节点为空时应停止，而非节点为叶子时。",
  "updated_profile_patch": {
    "guidance_level": "L2",
    "cognitive_blind_spots": ["指针越界", "递归终止条件"]
  },
  "updated_mastery_patch": {
    "kp_traversal": 0.5,
    "kp_recursion": 0.2
  },
  "recommended_next_nodes": [
    { "kp_id": "kp_recursion", "name": "递归", "reason": "递归终止条件掌握不足" }
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `score` | integer | 百分制分数，代码算 (答对数/总题数*100) |
| `evaluation_text` | string | LLM 生成的文字评语 |
| `updated_profile_patch` | object | 需要更新的画像字段（增量补丁），后端 MERGE 进 SQL |
| `updated_mastery_patch` | object | 需要更新的知识点掌握度 `{"[kp_id]": float}`，后端 UPSERT 进 SQL |
| `recommended_next_nodes` | array | 推荐下一步学习的知识点，含 ID、名称、推荐理由 |

---

## 4. 异步资源生成

- **POST** `/agent/v1/resource/generate`
- **工作流模式**: Manager-Worker 并行（异步，完成后通过 Webhook 回调）
- **触发时机**: 用户主动请求生成 或 路径推荐自动触发

### Request

```json
{
  "task_id": "task_8848",
  "knowledge_point": "红黑树",
  "knowledge_point_id": "kp_rbtree",
  "user_profile": {
    "modality_preference": { "video": 30, "chart": 25, "text": 15, "code": 20, "formula": 10 },
    "guidance_level": "L2",
    "discipline_base": "silver"
  },
  "types": ["explanation_doc", "mindmap", "quiz", "extended_reading", "code_practice"]
}
```

| 字段 | 类型 | 必填 | 来源 | 说明 |
|------|------|------|------|------|
| `task_id` | string | Y | 后端生成 (UUID) | 异步任务跟踪 ID |
| `knowledge_point` | string | Y | 前端选择 | 知识点中文名称 |
| `knowledge_point_id` | string | Y | 前端选择 | 知识点 ID，Agent 用于 RAG 检索 |
| `user_profile` | object | Y | 后端从 SQL 查 | 画像（Worker 据此调整难度和风格） |
| `types` | array[string] | Y | 前端选择 | 要生成的资源类型列表 |

### Response (立即返回)

```json
{
  "status": "accepted"
}
```

### Webhook 回调 (Agent 生成完成后 POST 给后端)

- **POST** `http://backend:8001/internal/webhook/resource_completed`

```json
{
  "task_id": "task_8848",
  "status": "success",
  "generated_resources": {
    "explanation_doc": {
      "title": "红黑树详解",
      "content_md": "# 红黑树\n\n红黑树是一种自平衡二叉搜索树...\n\n## 五大性质\n..."
    },
    "mindmap": {
      "title": "红黑树核心知识导图",
      "mermaid_code": "graph TD;\n  A[红黑树] --> B[性质];\n  A --> C[操作];\n  B --> D[根节点黑色];\n  C --> E[插入];\n  C --> F[删除];"
    },
    "quiz": [
      {
        "question": "红黑树的根节点是什么颜色？",
        "options": { "A": "红色", "B": "黑色", "C": "任意" },
        "answer": "B",
        "explanation": "根据红黑树性质1，根节点必须为黑色。"
      }
    ],
    "extended_reading": {
      "title": "从AVL到红黑树的演进",
      "content_md": "## 背景\n\nAVL树虽然严格平衡，但旋转操作频繁..."
    },
    "code_practice": {
      "title": "Python 实现红黑树插入",
      "language": "python",
      "code": "class Node:\n    def __init__(self, val):\n        self.val = val\n        self.color = 'RED'\n        ...",
      "explanation": "这段代码实现了红黑树的基本插入操作..."
    }
  }
}
```

后端收到 Webhook 后将各资源存入 SQL `resources` 表，更新 `task_id` 对应记录的 status 为 `completed`。

---

## 5. 画像初始构建 (冷启动)

- **POST** `/agent/v1/profile/initialize`
- **工作流模式**: 引导式对话 Agent (SSE 流式返回)
- **触发时机**: 新用户首次登录，系统无其画像时，前端进入“画像初始化”引导流程

### Request

```json
{
  "user_id": "u_123",
  "session_id": "init_999",
  "message": "我平时喜欢看视频学习，觉得指针很难。",
  "recent_history": [
    { "role": "assistant", "content": "你好！为了给你提供更好的学习体验，能告诉我你平时喜欢看视频还是看文字吗？觉得C语言里哪部分最难？" }
  ]
}
```

| 字段 | 类型 | 必填 | 来源 | 说明 |
|------|------|------|------|------|
| `user_id` | string | Y | 后端 | 用户标识 |
| `session_id` | string | Y | 后端 | 会话标识 |
| `message` | string | Y | 前端 | 用户回复内容 |
| `recent_history` | array[object] | Y | 后端 | 引导对话历史 |

### Response (SSE Stream)

```text
event: message
data: {"type": "text", "content": "好的，了解了。那么你平时学习是每天坚持，还是考前突击比较多呢？"}

event: message
data: {"type": "profile_extracted", "content": {"modality_preference": {"video": 60, "text": 10, "chart": 10, "code": 10, "formula": 10}, "cognitive_blind_spots": ["指针"]}}

event: done
data: {"status": "finished"}
```

| event | data.type | 说明 |
|-------|-----------|------|
| `message` | `text` | 引导提问文本 |
| `message` | `profile_extracted` | 当 Agent 认为收集到足够信息时，输出结构化画像数据，后端据此初始化 SQL |
| `done` | — | 本次请求结束 |

---

## 6. 个性化学习路径规划

- **POST** `/agent/v1/learning-path/plan`
- **工作流模式**: Pipeline 状态机 (同步 JSON)
- **触发时机**: 用户进入“学习路径”页面，或完成大章节测验后请求重新规划

### Request

```json
{
  "user_id": "u_123",
  "user_profile": {
    "guidance_level": "L2",
    "discipline_base": "silver"
  },
  "all_mastery": {
    "kp_array": 0.9,
    "kp_linkedlist": 0.8,
    "kp_recursion": 0.3,
    "kp_binary_tree": 0.5
  },
  "target_goal": "掌握二叉树遍历"
}
```

| 字段 | 类型 | 必填 | 来源 | 说明 |
|------|------|------|------|------|
| `user_id` | string | Y | 后端 | 用户标识 |
| `user_profile` | object | Y | 后端 | 完整画像 |
| `all_mastery` | object | Y | 后端 | 用户所有知识点的掌握度 `{"[kp_id]": float}` |
| `target_goal` | string | N | 前端 | 用户可选的短期目标 |

### Agent 内部处理流程

```
Step 1: Agent 读取本地 knowledge_graph.json 获取全局拓扑
Step 2: 结合 all_mastery，找出前置已满足但尚未掌握的节点
Step 3: LLM 根据 user_profile (如 discipline_base) 决定路径的陡峭程度和推荐顺序
```

### Response

```json
{
  "path_nodes": [
    {
      "kp_id": "kp_recursion",
      "name": "递归",
      "status": "learning",
      "reason": "二叉树遍历的前置基础，当前掌握度较低(0.3)，建议优先巩固。"
    },
    {
      "kp_id": "kp_binary_tree",
      "name": "二叉树",
      "status": "locked",
      "reason": "需先提升递归掌握度。"
    },
    {
      "kp_id": "kp_traversal",
      "name": "二叉树遍历",
      "status": "locked",
      "reason": "最终目标。"
    }
  ],
  "estimated_hours": 5.5
}
```

---

## 7. 数据库归属总结

| 数据 | 存储位置 | 归谁管 |
|------|----------|--------|
| 用户账号/密码/邮箱 | SQL | 后端 |
| 原始对话历史 (全量) | SQL | 后端 |
| 最近 N 轮对话 (活跃窗口) | SQL 查出通过 HTTP 传 | 后端 |
| 全局摘要 (summary) | SQL `user_summary` 表 | 后端存，Agent 算 |
| 6 维画像 | SQL `user_profile` 表 | 后端存，部分 Agent 算 |
| 知识点掌握度 | SQL `user_mastery` 表 | 后端存，Agent 算 |
| 生成的资源 | SQL `resources` 表 | 后端存 |
| 提取的用户事实 facts | Qdrant `user_memory` | Agent |
| 课程知识库切片 | Qdrant `course_knowledge` | Agent |
