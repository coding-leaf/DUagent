# 前端 ↔ 后端 API 接口规范 (v4.0)

> 基础 URL: `https://api.eduagent.com/v1` (生产) 或 `http://localhost:8001` (开发)
> 除登录注册外，所有接口需 Header: `Authorization: Bearer <token>`
>
> **统一返回格式:**
> ```json
> { "code": 200, "message": "success", "data": { ... } }
> ```
> code: 200 成功 / 400 参数错误 / 401 未授权 / 500 服务器错误

---

## 1. 认证模块 (Auth)

### 1.1 获取图形验证码

- **GET** `/api/v1/auth/captcha`

**Response:**
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "captcha_token": "token_abc123",
    "captcha_image": "data:image/png;base64,iVBORw0KGgo..."
  }
}
```

| data 字段 | 类型 | 说明 |
|-----------|------|------|
| `captcha_token` | string | 验证码令牌，登录时回传 |
| `captcha_image` | string | Base64 编码的验证码图片 |

### 1.2 用户注册

- **POST** `/api/v1/auth/register`

**Request:**
```json
{
  "email": "student@example.com",
  "username": "student_01",
  "password": "password123",
  "registration_code": "STU_2026_ABC"
}
```

**Response:**
```json
{ "code": 200, "message": "注册成功", "data": null }
```

### 1.3 用户登录

- **POST** `/api/v1/auth/login`

**Request:**
```json
{
  "email": "student@example.com",
  "password": "password123",
  "captcha_code": "abcd",
  "captcha_token": "token_abc123"
}
```

**Response:**
```json
{
  "code": 200,
  "message": "登录成功",
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIs...",
    "expires_in": 3600
  }
}
```

| data 字段 | 类型 | 说明 |
|-----------|------|------|
| `token` | string | JWT 令牌，后续请求放入 Header |
| `expires_in` | integer | 过期秒数 |

### 1.4 发送邮箱验证码

- **POST** `/api/v1/auth/send-code`

**Request:**
```json
{ "email": "student@example.com" }
```

**Response:**
```json
{ "code": 200, "message": "验证码发送成功", "data": null }
```

### 1.5 找回密码

- **POST** `/api/v1/auth/reset-password`

**Request:**
```json
{
  "email": "student@example.com",
  "verification_code": "123456",
  "new_password": "newpassword123"
}
```

**Response:**
```json
{ "code": 200, "message": "密码重置成功", "data": null }
```

---

## 2. 用户信息

### 2.1 获取用户信息与画像

- **GET** `/api/v1/user/info`

**Response:**
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "user_id": "u_123",
    "username": "student_01",
    "email": "student@example.com",
    "role": "student",
    "profile": {
      "modality_preference": { "video": 30, "chart": 25, "text": 15, "code": 20, "formula": 10 },
      "guidance_level": "L2",
      "knowledge_coordinates": { "mastered": ["顺序表", "链表"], "learning": ["二叉树遍历"] },
      "cognitive_blind_spots": ["递归边界条件", "指针越界"],
      "drive_intent": "daily",
      "discipline_base": "bronze"
    },
    "current_path_node": "二叉树遍历"
  }
}
```

| data 字段 | 类型 | 说明 |
|-----------|------|------|
| `user_id` | string | 用户唯一标识 |
| `role` | string | `"student"` / `"teacher"` / `"admin"` |
| `profile.modality_preference` | object | 五维雷达图数据，百分比整数 |
| `profile.guidance_level` | string | `"L1"` 启发 / `"L2"` 伴学 / `"L3"` 保姆 |
| `profile.knowledge_coordinates` | object | `mastered`: 已掌握; `learning`: 正在学 |
| `profile.cognitive_blind_spots` | array[string] | 认知盲区/易错点列表 |
| `profile.drive_intent` | string | `"daily"` 日常 / `"exam_cram"` 突击 |
| `profile.discipline_base` | string | `"bronze"` / `"silver"` / `"gold"` |
| `current_path_node` | string | 当前学习路径所在的知识点名称 |

### 2.2 手动调整引导粒度

- **PUT** `/api/v1/user/guidance-level`

**Request:**
```json
{ "guidance_level": "L1" }
```

**Response:**
```json
{ "code": 200, "message": "已更新", "data": null }
```

---

## 3. 智能对话

### 3.1 发送聊天消息 (SSE 流式)

- **POST** `/api/v1/chat/completions`

**Request:**
```json
{
  "session_id": "sess_9527",
  "message": "能给我画个二叉树遍历的图吗？"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `session_id` | string | Y | 会话 ID，首次对话可为空由后端生成 |
| `message` | string | Y | 用户消息文本 |

**后端内部处理:**
1. 从 SQL 查出该用户的 `user_profile`、`global_summary`、最近 N 轮 `recent_history`
2. 组装 JSON POST 到 Agent `POST /agent/v1/chat`
3. 将 Agent 返回的 SSE 透传给前端
4. 同时将用户消息和 AI 回复存入 SQL `chat_messages` 表
5. 检查 `total_turns`，如满 10 轮则异步调用 `POST /agent/v1/memory/compress`

**Response (SSE Stream):**
```text
event: message
data: {"type": "status", "content": "正在检索知识库..."}

event: message
data: {"type": "text", "content": "二叉树的遍历通常分为"}

event: message
data: {"type": "text", "content": "前序、中序和后序三种。"}

event: message
data: {"type": "tool_call", "tool_name": "draw_diagram", "tool_args": {"type": "mermaid", "code": "graph TD; A-->B; A-->C;"}}

event: done
data: {"status": "finished"}
```

### 3.2 获取对话历史

- **GET** `/api/v1/chat/history?session_id=sess_9527&page=1&page_size=20`

**Response:**
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "session_id": "sess_9527",
    "total": 42,
    "page": 1,
    "messages": [
      { "role": "user", "content": "什么是二叉树？", "created_at": "2026-04-28T10:00:00Z" },
      { "role": "assistant", "content": "二叉树是一种树形结构...", "created_at": "2026-04-28T10:00:05Z" }
    ]
  }
}
```

### 3.3 获取会话列表

- **GET** `/api/v1/chat/sessions`

**Response:**
```json
{
  "code": 200,
  "message": "success",
  "data": [
    { "session_id": "sess_9527", "title": "二叉树遍历讨论", "last_message_at": "2026-04-28T10:30:00Z" },
    { "session_id": "sess_9528", "title": "递归算法入门", "last_message_at": "2026-04-27T15:00:00Z" }
  ]
}
```

---

## 4. 测验评估

### 支持的题型

| 题型 | `type` 值 | `answer` 格式 | 判分方式 |
|------|-----------|--------------|---------|
| 单选题 | `single_choice` | `"A"` | 代码对比 |
| 多选题 | `multi_choice` | `["A","C"]` | 代码集合对比 |
| 判断题 | `true_false` | `"true"` / `"false"` | 代码对比 |
| 填空题 | `fill_blank` | `"答案文本"` | 代码对比（支持多个正确答案） |
| 代码题 | `code` | `"def foo(): ..."` | 代码沙箱跑测试用例 |
| 简答题 | `short_answer` | `"用户的回答文本"` | LLM 判分 |

> **建议开发顺序**：先做前 4 种（纯代码判分），代码题和简答题作为加分项后期添加。

### 4.1 获取测验题目

- **GET** `/api/v1/assessment/quiz?knowledge_point_id=kp_traversal`

**Response:**
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "knowledge_point_id": "kp_traversal",
    "knowledge_point_name": "二叉树遍历",
    "questions": [
      {
        "id": "q1",
        "type": "single_choice",
        "question": "前序遍历的顺序是？",
        "options": { "A": "根左右", "B": "左根右", "C": "左右根" }
      },
      {
        "id": "q2",
        "type": "multi_choice",
        "question": "以下哪些属于二叉树的遍历方式？（多选）",
        "options": { "A": "前序", "B": "冒泡", "C": "中序", "D": "后序" }
      },
      {
        "id": "q3",
        "type": "true_false",
        "question": "完全二叉树的叶子节点只能出现在最后两层。"
      },
      {
        "id": "q4",
        "type": "fill_blank",
        "question": "二叉树前序遍历的访问顺序是：___、左子树、右子树。"
      },
      {
        "id": "q5",
        "type": "code",
        "question": "请用 Python 实现二叉树的前序遍历函数。",
        "code_template": "def preorder(root):\n    # 请在此处编写代码\n    pass",
        "language": "python"
      },
      {
        "id": "q6",
        "type": "short_answer",
        "question": "请简述前序遍历和中序遍历的区别。"
      }
    ]
  }
}
```

| questions[] 字段 | 类型 | 说明 |
|-----------------|------|------|
| `id` | string | 题目唯一 ID |
| `type` | string | 题型标识，前端据此渲染不同的答题 UI 组件 |
| `question` | string | 题干文本 |
| `options` | object | 仅 `single_choice` 和 `multi_choice` 有此字段 |
| `code_template` | string | 仅 `code` 题型有，提供代码模板 |
| `language` | string | 仅 `code` 题型有，指定编程语言 |

### 4.2 提交测验答案

- **POST** `/api/v1/assessment/submit`

**Request:**
```json
{
  "knowledge_point_id": "kp_traversal",
  "answers": {
    "q1": "A",
    "q2": ["A", "C", "D"],
    "q3": "true",
    "q4": "根节点",
    "q5": "def preorder(root):\n    if not root: return\n    print(root.val)\n    preorder(root.left)\n    preorder(root.right)",
    "q6": "前序遍历先访问根节点再访问左右子树，中序遍历先访问左子树再访问根节点最后访问右子树。"
  }
}
```

> **注意**：`answers` 的 value 类型取决于题型。单选/判断/填空/简答/代码为 `string`，多选为 `string[]`。

**后端内部处理:**
1. 从 SQL 查出题目（含正确答案）、用户当前 profile 和 mastery
2. 组装 JSON POST 到 Agent `POST /agent/v1/assessment/evaluate`
3. Agent 返回评估结果后，后端 MERGE 更新 SQL 中的 profile 和 mastery

**Response:**
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "score": 75,
    "evaluation": "你对遍历方式的分类掌握得很好，但对前序遍历的定义还需要更精确的理解。代码实现正确，逻辑清晰。",
    "question_results": [
      { "id": "q1", "correct": true },
      { "id": "q2", "correct": true },
      { "id": "q3", "correct": true },
      { "id": "q4", "correct": true },
      { "id": "q5", "correct": true, "test_passed": "3/3" },
      { "id": "q6", "correct": false, "feedback": "回答基本正确，但遗漏了后序遍历的对比说明。" }
    ],
    "mastery_changed": true,
    "recommended_next": [
      { "kp_id": "kp_recursion", "name": "递归", "reason": "递归终止条件掌握不足" }
    ]
  }
}
```

| data 字段 | 类型 | 说明 |
|-----------|------|------|
| `score` | integer | 百分制分数 |
| `evaluation` | string | LLM 生成的整体文字评语 |
| `question_results` | array | 每道题的对错详情，前端用于标红/标绿 |
| `question_results[].test_passed` | string | 仅代码题有，测试用例通过情况 |
| `question_results[].feedback` | string | 仅简答题有，LLM 给的单题反馈 |
| `mastery_changed` | boolean | 是否有画像/掌握度变更，前端据此决定是否刷新画像 |
| `recommended_next` | array | 推荐下一步学什么 |

---

## 5. 学习效果评估

### 5.1 获取评估图表数据

- **GET** `/api/v1/assessment/evaluation-charts`

**Response:**
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "progress_data": [
      { "module": "线性表", "progress": 100 },
      { "module": "树", "progress": 40 },
      { "module": "图", "progress": 0 }
    ],
    "mastery_data": [
      { "knowledge_point": "前序遍历", "kp_id": "kp_preorder", "score": 90 },
      { "knowledge_point": "递归", "kp_id": "kp_recursion", "score": 45 }
    ],
    "resource_usage_data": [
      { "type": "video", "label": "视频", "ratio": 0.3 },
      { "type": "text", "label": "文档", "ratio": 0.25 },
      { "type": "code", "label": "代码", "ratio": 0.2 },
      { "type": "chart", "label": "图表", "ratio": 0.15 },
      { "type": "formula", "label": "公式", "ratio": 0.1 }
    ],
    "ai_summary": "该生近期在二叉树章节学习积极，但测试中反映出对递归的掌握仍有欠缺，偏好视频类资源。"
  }
}
```

| data 字段 | 类型 | 说明 |
|-----------|------|------|
| `progress_data` | array | 各章节学习进度百分比 (后端 SQL 统计) |
| `mastery_data` | array | 各知识点掌握度 (后端从 user_mastery 查) |
| `resource_usage_data` | array | 各资源类型使用比例 (后端 SQL 统计) |
| `ai_summary` | string | 后端调一次 LLM 生成的文字总结 |

---

## 6. 推荐与路径

### 6.1 获取学习路径

- **GET** `/api/v1/learning-path`

**Response:**
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "current_node": "kp_binary_tree",
    "nodes": [
      { "kp_id": "kp_array", "name": "数组", "mastery": 0.9, "status": "mastered" },
      { "kp_id": "kp_linkedlist", "name": "链表", "mastery": 0.8, "status": "mastered" },
      { "kp_id": "kp_recursion", "name": "递归", "mastery": 0.3, "status": "weak" },
      { "kp_id": "kp_binary_tree", "name": "二叉树", "mastery": 0.5, "status": "learning" },
      { "kp_id": "kp_traversal", "name": "二叉树遍历", "mastery": 0.0, "status": "locked" }
    ],
    "edges": [
      { "from": "kp_array", "to": "kp_linkedlist" },
      { "from": "kp_linkedlist", "to": "kp_binary_tree" },
      { "from": "kp_recursion", "to": "kp_binary_tree" },
      { "from": "kp_binary_tree", "to": "kp_traversal" }
    ],
    "recommended_next": [
      { "kp_id": "kp_recursion", "name": "递归", "reason": "前置依赖已满足，当前掌握度最低" }
    ]
  }
}
```

| data 字段 | 类型 | 说明 |
|-----------|------|------|
| `current_node` | string | 当前学习路径所在节点 ID |
| `nodes` | array | 所有知识点及其掌握度和状态 |
| `nodes[].status` | string | `"mastered"` >= 0.7 / `"learning"` 当前 / `"weak"` < 0.3 / `"locked"` 前置未满足 |
| `edges` | array | 前置依赖关系（前端用于画有向图） |
| `recommended_next` | array | 推荐下一步学习的节点 |

### 6.2 获取主页推荐资源

- **GET** `/api/v1/recommendations/daily`

**Response:**
```json
{
  "code": 200,
  "message": "success",
  "data": [
    {
      "resource_id": "res_001",
      "type": "mindmap",
      "title": "二叉树核心知识点导图",
      "knowledge_point": "二叉树",
      "created_at": "2026-04-28T08:00:00Z"
    },
    {
      "resource_id": "res_002",
      "type": "quiz",
      "title": "递归算法专项练习5题",
      "knowledge_point": "递归",
      "created_at": "2026-04-28T08:00:00Z"
    }
  ]
}
```

---

## 7. 资源生成与浏览

### 7.1 触发资源生成 (异步)

- **POST** `/api/v1/resource/generate`

**Request:**
```json
{
  "knowledge_point": "红黑树",
  "knowledge_point_id": "kp_rbtree",
  "resource_types": ["explanation_doc", "mindmap", "quiz", "extended_reading", "code_practice"]
}
```

**后端内部处理:**
1. 在 SQL `tasks` 表创建一条 status=`pending` 的记录
2. 从 SQL 查出用户画像
3. 异步 POST 到 Agent `POST /agent/v1/resource/generate`
4. 等待 Agent Webhook 回调后更新 SQL

**Response:**
```json
{
  "code": 200,
  "message": "任务已提交，后台生成中",
  "data": {
    "task_id": "task_8848",
    "status": "pending"
  }
}
```

### 7.2 查询生成任务状态

- **GET** `/api/v1/resource/task/task_8848`

**Response:**
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "task_id": "task_8848",
    "status": "completed",
    "resource_ids": ["res_101", "res_102", "res_103", "res_104", "res_105"]
  }
}
```

### 7.3 获取资源详情

- **GET** `/api/v1/resource/res_101`

**Response:**
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "resource_id": "res_101",
    "type": "explanation_doc",
    "title": "红黑树详解",
    "knowledge_point": "红黑树",
    "content_md": "# 红黑树\n\n红黑树是一种自平衡二叉搜索树...",
    "created_at": "2026-04-28T10:30:00Z"
  }
}
```

### 7.4 获取资源列表

- **GET** `/api/v1/resources?type=quiz&page=1&page_size=10`

**Response:**
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "total": 15,
    "page": 1,
    "resources": [
      {
        "resource_id": "res_103",
        "type": "quiz",
        "title": "红黑树专项练习",
        "knowledge_point": "红黑树",
        "created_at": "2026-04-28T10:30:00Z"
      }
    ]
  }
}
```

---

## 8. 课程与班级管理

### 8.1 教师生成课程码

- **POST** `/api/v1/course/generate-code`

**Request:**
```json
{ "course_name": "数据结构与算法(2026春)" }
```

**Response:**
```json
{
  "code": 200,
  "message": "课程创建成功",
  "data": {
    "course_id": "c_1001",
    "course_code": "DS2026",
    "course_name": "数据结构与算法(2026春)"
  }
}
```

### 8.2 学生加入课程

- **POST** `/api/v1/course/join`

**Request:**
```json
{ "course_code": "DS2026" }
```

**Response:**
```json
{ "code": 200, "message": "成功加入课程", "data": null }
```

### 8.3 教师获取班级学生列表

- **GET** `/api/v1/course/{course_id}/students`

**Response:**
```json
{
  "code": 200,
  "message": "success",
  "data": [
    {
      "user_id": "u_123",
      "username": "student_01",
      "profile": {
        "modality_preference": { "video": 30, "chart": 25, "text": 15, "code": 20, "formula": 10 },
        "guidance_level": "L2",
        "knowledge_coordinates": { "mastered": ["顺序表"], "learning": ["二叉树遍历"] },
        "cognitive_blind_spots": ["递归边界条件"],
        "drive_intent": "daily",
        "discipline_base": "bronze"
      },
      "current_path_node": "二叉树遍历",
      "overall_mastery": 0.45
    }
  ]
}
```

---

## 9. 系统管理 (Admin)

### 9.1 分发注册码

> **说明**：为了简化比赛开发，注册码分发机制改为**硬编码**，不再提供动态生成接口。
> 
> 系统默认内置以下几个长期有效的注册码供演示与测试使用（写死在代码/数据库中）：
> - 学生注册码：`STU_TEST_2026`
> - 教师注册码：`TCH_TEST_2026`


### 9.2 获取系统日志

- **GET** `/api/v1/admin/logs?page=1&page_size=20`

**Response:**
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "total": 120,
    "logs": [
      { "time": "2026-04-28 10:00:00", "type": "agent_latency", "value": "1.2s", "details": "Chatbot response" },
      { "time": "2026-04-28 10:05:00", "type": "security_block", "value": "幻觉拦截", "details": "Blocked hallucinated content" }
    ]
  }
}
```

---

## 10. 后端 Webhook (Agent 回调)

### 10.1 资源生成完成回调

- **POST** `/internal/webhook/resource_completed`
- 由 Agent Service 在资源生成完成后调用，无需前端鉴权

**Request (Agent 发给后端):**
```json
{
  "task_id": "task_8848",
  "status": "success",
  "generated_resources": {
    "explanation_doc": { "title": "红黑树详解", "content_md": "..." },
    "mindmap": { "title": "红黑树导图", "mermaid_code": "graph TD; ..." },
    "quiz": [{ "question": "...", "options": {}, "answer": "B", "explanation": "..." }],
    "extended_reading": { "title": "...", "content_md": "..." },
    "code_practice": { "title": "...", "language": "python", "code": "...", "explanation": "..." }
  }
}
```

**Response:**
```json
{ "code": 200, "message": "Webhook received", "data": null }
```
