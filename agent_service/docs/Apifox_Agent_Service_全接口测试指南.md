# Apifox Agent Service 全接口测试指南

本文用于指导在 Apifox 中测试 Agent Service 的全部对外接口。

接口契约来源：

- `../docs/20-agent-api/Agent-Service.openapi.json`
- `../docs/20-agent-api/API_Agent内部接口规范.md`

完整 JSON 示例来源：

- `docs/Agent-Service-接口JSON示例说明.md`

## 1. 测试前准备

### 启动 Agent Service

在仓库根目录执行：

```bash
cd /home/yezisama/workspace/workflow/EDUagent
./.venv/bin/uvicorn agent_service.main:app --host 127.0.0.1 --port 8002
```

如需保存日志：

```bash
./.venv/bin/uvicorn agent_service.main:app --host 127.0.0.1 --port 8002 2>&1 | tee /tmp/eduagent.log
```

另开终端查看日志：

```bash
tail -f /tmp/eduagent.log
```

### Apifox 环境变量

建议在 Apifox 环境中配置：

| 变量名 | 值 |
|------|------|
| `agent_base_url` | `http://127.0.0.1:8002` |
| `apifox_webhook_url` | `https://m1.apifoxmock.com/m1/8182577-7941807-7764192/api/v1/webhooks/agent` |

后续接口地址统一写成：

```text
{{agent_base_url}}/agent/v1/...
```

## 2. 三类接口怎么验收

### 同步 JSON 接口

这类接口发送后直接在 Apifox 响应 Body 里看结果。

成功响应通常是：

```json
{
  "code": 200,
  "message": "success",
  "data": {}
}
```

同步 JSON 接口包括：

- `GET /agent/v1/health`
- `POST /agent/v1/profile/generate`
- `POST /agent/v1/evaluation/generate`
- `POST /agent/v1/assessment/evaluate`
- `POST /agent/v1/assessment/generate-questions`
- `POST /agent/v1/learning-path/generate`
- `POST /agent/v1/memory/compress`

### SSE 接口

`POST /agent/v1/tutoring/chat` 是 SSE 流式接口。

Apifox 中需要看事件流，实际格式类似：

```text
data: {"type":"chunk","content":"..."}
data: {"type":"done","message_id":"..."}
```

如果 Apifox 不方便看流式结果，优先看 Agent Service 日志确认是否命中 ReAct / fallback。

### 异步 webhook 接口

`POST /agent/v1/resources/generate` 是异步接口。

它的 `202 accepted` 只表示任务被接收，不包含最终生成资源。

真正资源结果在 Apifox Mock/Webhook 的请求记录里：

```text
Mock/Webhook 调用记录 -> Request Body -> result.resources
```

资源正文在：

```text
result.resources[].content
```

## 3. Apifox Webhook / Mock 设置

在 Apifox 中新建 Webhook：

```http
POST /api/v1/webhooks/agent
```

当前 WSL 本地调试建议使用云端 Mock URL：

```text
https://m1.apifoxmock.com/m1/8182577-7941807-7764192/api/v1/webhooks/agent
```

不要优先使用 Apifox 本地 Mock 的 `http://127.0.0.1:4523/...`，因为 Apifox 桌面端可能运行在 Windows，而 Agent Service 运行在 WSL，两边的 `127.0.0.1` 不是同一个网络命名空间。

Webhook 成功回调 body 示例：

```json
{
  "task_id": "apifox-resources-001",
  "task_type": "resource_generation",
  "status": "completed",
  "result": {
    "resources": [
      {
        "title": "一次函数学习资料",
        "type": "document",
        "description": "一次函数的概念、图像和应用",
        "content": "这里是生成内容",
        "chapter": "函数",
        "knowledge_point": "一次函数",
        "tags": ["函数", "一次函数", "document"]
      }
    ]
  }
}
```

## 4. 全接口测试清单

| 序号 | 接口 | 类型 | 结果在哪里看 |
|------|------|------|------|
| 1 | `GET /agent/v1/health` | 同步 JSON | 响应 Body |
| 2 | `POST /agent/v1/tutoring/chat` | SSE | Apifox 事件流 / 服务端日志 |
| 3 | `POST /agent/v1/profile/generate` | 同步 JSON | 响应 Body |
| 4 | `POST /agent/v1/evaluation/generate` | 同步 JSON | 响应 Body |
| 5 | `POST /agent/v1/assessment/evaluate` | 同步 JSON | 响应 Body |
| 6 | `POST /agent/v1/assessment/generate-questions` | 同步 JSON | 响应 Body |
| 7 | `POST /agent/v1/learning-path/generate` | 同步 JSON | 响应 Body |
| 8 | `POST /agent/v1/resources/generate` | 异步 webhook | 先看 202，再看 Apifox Mock 请求记录 |
| 9 | `POST /agent/v1/memory/compress` | 同步 JSON | 响应 Body |

## 5. 接口逐个测试

### 5.1 Health

```http
GET {{agent_base_url}}/agent/v1/health
```

无 Body。

验收：

- HTTP 200
- `code=200`
- `data.status` 是 `healthy` / `degraded` / `unhealthy`
- `data.qdrant_connected`、`data.model_loaded`、`data.model_name`、`data.uptime_seconds` 字段存在

### 5.2 Tutoring Chat

```http
POST {{agent_base_url}}/agent/v1/tutoring/chat
Content-Type: application/json
Accept: text/event-stream
```

最小 Body：

```json
{
  "user_id": "user_001",
  "scope": "course",
  "course_id": "course_ds_c",
  "conversation_id": "conv_apifox_001",
  "message": "请用一个简单例子解释栈和队列的区别",
  "user_profile": {
    "guidance_level": "L2",
    "modal_preference": {
      "video_animation": 70,
      "chart_logic": 88,
      "text_analysis": 65,
      "code_practice": 72,
      "formula_derivation": 30
    },
    "knowledge_mastered": ["顺序表", "链表"],
    "knowledge_weak": ["栈", "队列"]
  },
  "conversation_summary": "用户已经理解顺序表和链表。",
  "recent_messages": []
}
```

验收：

- HTTP 200
- 响应是 SSE 流
- 至少能看到 `chunk` 和最终 `done` 事件
- 如果没有真实 LLM，也可能走规则版 fallback，但仍应返回可读文本

### 5.3 Profile Generate

```http
POST {{agent_base_url}}/agent/v1/profile/generate
Content-Type: application/json
```

最小 Body：

```json
{
  "user_id": "user_001",
  "course_id": "course_ds_c",
  "evaluation_data": {
    "progress": {
      "completed": 3,
      "total": 10
    },
    "mastery": {
      "栈": 45,
      "队列": 70
    },
    "resource_usage": {
      "document": 3,
      "code": 1
    }
  },
  "quiz_history": [
    {
      "score": 60,
      "chapter": "栈与队列",
      "created_at": "2026-05-31T10:00:00Z"
    }
  ],
  "resource_usage_stats": {
    "video_count": 1,
    "document_count": 3,
    "code_count": 1,
    "quiz_count": 2
  },
  "drive_intent_data": {
    "recent_7d_sessions": 4,
    "recent_7d_duration": 180
  }
}
```

验收：

- HTTP 200
- `data.guidance_level_suggestion` 存在
- `data.modal_preference` 存在
- `data.knowledge_coordinates` 是数组
- `data.cognitive_blindspots` 是数组

完整请求示例见 `docs/Agent-Service-接口JSON示例说明.md` 的“生成/刷新用户画像”章节。

### 5.4 Evaluation Generate

```http
POST {{agent_base_url}}/agent/v1/evaluation/generate
Content-Type: application/json
```

最小 Body：

```json
{
  "user_id": "user_001",
  "course_id": "course_ds_c",
  "learning_progress": {
    "chapter_progress": [
      {
        "chapter": "栈与队列",
        "completion_rate": 70,
        "time_spent": 240
      }
    ]
  },
  "quiz_results": [
    {
      "chapter": "栈与队列",
      "score": 80,
      "created_at": "2026-05-31T10:00:00Z"
    }
  ],
  "resource_usage": {
    "by_type": {
      "document": 3,
      "mindmap": 1,
      "reading": 1,
      "code": 1,
      "video": 0
    },
    "by_chapter": {
      "栈与队列": 6
    }
  }
}
```

验收：

- HTTP 200
- `data.progress_table` 存在
- `data.mastery_table` 存在
- `data.resource_usage_table` 存在
- `data.summary_text` 存在

完整请求示例见 `docs/Agent-Service-接口JSON示例说明.md` 的“生成学习效果评估”章节。

### 5.5 Assessment Evaluate

```http
POST {{agent_base_url}}/agent/v1/assessment/evaluate
Content-Type: application/json
```

最小 Body：

```json
{
  "quiz_id": "quiz_apifox_001",
  "user_id": "user_001",
  "course_id": "course_ds_c",
  "questions": [
    {
      "id": "q1",
      "type": "single_choice",
      "content": "队列的特点是什么？",
      "options": [
        {
          "key": "A",
          "text": "先进先出"
        },
        {
          "key": "B",
          "text": "后进先出"
        }
      ],
      "correct_answer": "A",
      "knowledge_point": "队列"
    }
  ],
  "answers": [
    {
      "question_id": "q1",
      "answer": "A"
    }
  ],
  "user_mastery": {
    "队列": 70
  }
}
```

验收：

- HTTP 200
- `data.per_question_results` 是数组
- `data.diagnosis` 存在
- `data.diagnosis.suggestions` 是数组

如果看到 `quiz_id/questions/answers Field required`，说明你当前调的是本接口，但 Body 填成了别的接口的格式。

### 5.6 Assessment Generate Questions

```http
POST {{agent_base_url}}/agent/v1/assessment/generate-questions
Content-Type: application/json
```

最小 Body：

```json
{
  "user_id": "user_001",
  "course_id": "course_ds_c",
  "knowledge_base_id": "kb_course_ds_c",
  "chapter": "栈与队列",
  "knowledge_point": "队列",
  "difficulty": "medium",
  "count": 3,
  "question_types": ["single_choice"],
  "personalized": true,
  "personalization_context": {
    "evaluation": null,
    "profile": null
  }
}
```

验收：

- HTTP 200
- `data.questions` 是数组
- 题目数量尽量接近 `count`
- 每题有 `type`、`content`、`answer`、`knowledge_point`

### 5.7 Learning Path Generate

```http
POST {{agent_base_url}}/agent/v1/learning-path/generate
Content-Type: application/json
```

最小 Body：

```json
{
  "user_id": "user_001",
  "course_id": "course_ds_c",
  "evaluation": {
    "progress": {
      "completed": 3,
      "total": 10
    },
    "mastery": {
      "栈": 45,
      "队列": 70
    },
    "resource_usage": {
      "document": 3,
      "video": 1,
      "quiz": 2
    },
    "summary": "用户对队列掌握较好，对栈仍需强化。"
  },
  "profile": {
    "guidance_level": "L2",
    "modal_preference": {
      "video_animation": 70,
      "chart_logic": 80,
      "text_analysis": 60,
      "code_practice": 75,
      "formula_derivation": 30
    },
    "knowledge_mastered": ["队列"],
    "knowledge_weak": ["栈"]
  },
  "knowledge_graph": {
    "nodes": [
      {
        "id": "kp_stack",
        "name": "栈"
      },
      {
        "id": "kp_queue",
        "name": "队列"
      }
    ],
    "edges": [
      {
        "from": "kp_stack",
        "to": "kp_queue",
        "relation": "prerequisite"
      }
    ]
  }
}
```

验收：

- HTTP 200
- `data.nodes` 是路径节点列表
- `data.edges` 是路径边列表
- 节点 ID 应来自请求中的 `knowledge_graph.nodes`
- 不应出现请求里没有的知识点 ID

完整字段以 OpenAPI 和 `docs/Agent-Service-接口JSON示例说明.md` 为准。

### 5.8 Resources Generate

```http
POST {{agent_base_url}}/agent/v1/resources/generate
Content-Type: application/json
```

Body：

```json
{
  "task_id": "apifox-resources-001",
  "user_id": "apifox-user",
  "course_id": "smoke-course",
  "webhook_url": "{{apifox_webhook_url}}",
  "chapter": "函数",
  "knowledge_point": "一次函数",
  "resource_types": ["document", "mindmap", "reading", "code"]
}
```

第一步验收：

- HTTP 202
- `code=202`
- `data.task_id` 与请求一致
- `data.estimated_duration` 存在

第二步看生成资源：

1. 打开 Apifox 的 `POST /api/v1/webhooks/agent` Webhook。
2. 进入 Mock 页面。
3. 查看云端 Mock 的调用记录。
4. 点开 Agent Service 发来的 POST 请求。
5. 看 Request Body。
6. 资源在 `result.resources`。
7. 正文在 `result.resources[].content`。

成功回调应类似：

```json
{
  "task_id": "apifox-resources-001",
  "task_type": "resource_generation",
  "status": "completed",
  "result": {
    "resources": [
      {
        "title": "函数 - 一次函数 - 知识讲解",
        "type": "document",
        "description": "面向一次函数的知识讲解。",
        "content": "生成的资源正文",
        "chapter": "函数",
        "knowledge_point": "一次函数",
        "tags": ["函数", "一次函数", "document"]
      }
    ]
  }
}
```

如果只看到 `202`，但 Mock 没有记录：

- 检查 `webhook_url` 是否为 `https://m1.apifoxmock.com/...`
- 看 Agent Service 终端是否有 `Resource generation webhook failed`
- 不要使用 WSL 不可达的 `http://127.0.0.1:4523/...`

如果 Mock 有记录但内容像占位：

- 说明接口链路通了
- 但真实 LLM 可能未配置或失败，系统走了 skeleton fallback
- 继续查看 Agent Service 日志里的 `fallback` / `LLM` / `ResourceAgent` 信息

### 5.9 Memory Compress

```http
POST {{agent_base_url}}/agent/v1/memory/compress
Content-Type: application/json
```

最小 Body：

```json
{
  "user_id": "user_001",
  "conversation_id": "conv_apifox_001",
  "old_summary": "用户已经学习了顺序表和链表。",
  "messages_to_compress": [
    {
      "role": "user",
      "content": "我总是分不清栈和队列。",
      "timestamp": "2026-05-31T10:00:00Z"
    },
    {
      "role": "assistant",
      "content": "可以先记住栈是后进先出，队列是先进先出。",
      "timestamp": "2026-05-31T10:00:20Z"
    }
  ],
  "existing_facts": []
}
```

验收：

- HTTP 200
- `data.new_summary` 存在
- `data.extracted_facts` 是数组

## 6. 常见问题

### 只看到 202，看不到资源

这是正常的第一阶段结果。`resources/generate` 是异步接口，资源不在 202 响应里。

继续去 Apifox Mock 请求记录看：

```text
Request Body -> result.resources
```

### 422 提示缺字段

一般是接口选错或 Body 用错。

例子：

- `quiz_id/questions/answers Field required`：你调的是 `assessment/evaluate`，但填了 resources 的 Body。
- `task_id/user_id/course_id/webhook_url Field required`：你调的是 `resources/generate`，但 Body 缺异步任务字段。

### Webhook connection refused

说明 `webhook_url` 指向的接收服务不可达。

在 WSL 下不要优先用：

```text
http://127.0.0.1:4523/...
```

优先用 Apifox 云端 Mock：

```text
https://m1.apifoxmock.com/m1/8182577-7941807-7764192/api/v1/webhooks/agent
```

### 如何判断真实 AI 工作流是否运行

Apifox 只能看到最终协议结果。内部是否命中多 Agent / LLM，需要看 Agent Service 日志。

resources 成功命中时可能看到：

```text
Multi-agent workflow started
LLM Planner succeeded
ResourceAgent succeeded
Aggregator merged results
```

如果没有真实 LLM 配置，可能看到 fallback 日志，最终仍可能返回 completed。

### 本地快速总体验证

不依赖 Apifox 时，可运行：

```bash
cd /home/yezisama/workspace/workflow/EDUagent/agent_service
./.venv/bin/python -m agent_service.tools.smoke_all
```

resources 单独验证：

```bash
./.venv/bin/python -m agent_service.tools.smoke_resources_workflow
```
