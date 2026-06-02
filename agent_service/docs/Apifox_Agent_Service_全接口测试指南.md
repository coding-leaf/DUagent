# Apifox Agent Service 全接口测试指南

目标：用 Apifox 覆盖测试 Agent Service 当前全部对外接口。

基础地址：

```text
http://127.0.0.1:8002
```

当前 resources webhook 云端 Mock：

```text
https://m1.apifoxmock.com/m1/8182577-7941807-7764192/api/v1/webhooks/agent
```

结果查看规则：

| 接口类型 | 怎么判断结果 |
|------|------|
| 同步 JSON | 直接看本次响应 Body |
| SSE | 看响应事件流，至少应有 `chunk` 和 `done` |
| 异步 webhook | 先看 `202 accepted`，再去 Apifox Mock 请求记录看回调 Body |

## 1. 全接口清单

| 序号 | 接口 | 类型 | 成功状态 |
|------|------|------|------|
| 1 | `GET /agent/v1/health` | 同步 JSON | HTTP 200 |
| 2 | `POST /agent/v1/tutoring/chat` | SSE | HTTP 200 + SSE 事件 |
| 3 | `POST /agent/v1/profile/generate` | 同步 JSON | HTTP 200 |
| 4 | `POST /agent/v1/evaluation/generate` | 同步 JSON | HTTP 200 |
| 5 | `POST /agent/v1/assessment/evaluate` | 同步 JSON | HTTP 200 |
| 6 | `POST /agent/v1/assessment/generate-questions` | 同步 JSON | HTTP 200 |
| 7 | `POST /agent/v1/learning-path/generate` | 同步 JSON | HTTP 200 |
| 8 | `POST /agent/v1/resources/generate` | 异步 webhook | HTTP 202 + webhook 回调 |
| 9 | `POST /agent/v1/memory/compress` | 同步 JSON | HTTP 200 |

## 2. Health

### 请求

```http
GET http://127.0.0.1:8002/agent/v1/health
```

无 Body。

### 成功判定

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "status": "healthy",
    "qdrant_connected": true,
    "model_loaded": true,
    "model_name": "deepseek-v4-flash",
    "uptime_seconds": 100
  }
}
```

必须检查：

- `data.status` 存在，取值通常是 `healthy` / `degraded` / `unhealthy`
- `data.qdrant_connected` 是 boolean
- `data.model_loaded` 是 boolean
- `data.model_name` 是 string
- `data.uptime_seconds` 是 integer

常见失败：

- `model_loaded=false` 且 `model_name=""`：服务进程没有读到 `.env`。如果 `.env` 在 `agent_service/.env`，优先从 `agent_service/` 目录启动服务。
- `status=degraded`：通常是 Qdrant 探针失败，不一定影响所有接口的规则版 fallback。
- Qdrant local lock：如果日志出现 `Storage folder ./qdrant_data is already accessed by another instance`，停止其他正在运行的 Agent Service/smoke/ingest/readiness 进程后重试。该问题不是 Apifox 请求体错误。

## 3. Tutoring Chat

### 请求

```http
POST http://127.0.0.1:8002/agent/v1/tutoring/chat
Content-Type: application/json
Accept: text/event-stream
```

### Body

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
  "recent_messages": [
    {
      "role": "user",
      "content": "链表我大概懂了",
      "meta": {
        "message_id": "msg_u_001"
      }
    }
  ]
}
```

### 成功判定

响应是 SSE，期望看到类似事件：

```text
data: {"type":"chunk","content":"..."}
data: {"type":"done","message_id":"..."}
```

必须检查：

- HTTP 200
- 至少出现文本内容事件
- 最终有 `done` 事件

常见失败：

- `course_id` 缺失且 `scope=course`：会 422。
- Apifox 不显示流式事件：看服务端日志，或切到支持 SSE 的调试方式。

## 4. Profile Generate

### 请求

```http
POST http://127.0.0.1:8002/agent/v1/profile/generate
Content-Type: application/json
```

### Body

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

### 成功判定

必须检查：

- HTTP 200
- `code=200`
- `data.modal_preference` 存在
- `data.guidance_level_suggestion` 存在
- `data.knowledge_coordinates` 是 array
- `data.cognitive_blindspots` 是 array

常见失败：

- `created_at` 不是 ISO 时间字符串：会 422。
- `score` 不是数字：会 422。

## 5. Evaluation Generate

### 请求

```http
POST http://127.0.0.1:8002/agent/v1/evaluation/generate
Content-Type: application/json
```

### Body

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

### 成功判定

必须检查：

- HTTP 200
- `data.progress_table` 存在
- `data.mastery_table` 存在
- `data.resource_usage_table` 存在
- `data.summary_text` 存在

常见失败：

- `completion_rate` / `score` 超出 0-100：会 422。
- `learning_progress.chapter_progress` 缺失：会 422。

## 6. Assessment Evaluate

### 请求

```http
POST http://127.0.0.1:8002/agent/v1/assessment/evaluate
Content-Type: application/json
```

### Body

```json
{
  "user_id": "user_001",
  "course_id": "course_ds_c",
  "quiz_id": "quiz_apifox_001",
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

### 成功判定

必须检查：

- HTTP 200
- `data.per_question_results` 是 array
- `data.per_question_results[0].is_correct=true`
- `data.diagnosis` 存在
- `data.diagnosis.suggestions` 是 array

常见失败：

- 缺 `quiz_id` / `questions` / `answers`：说明 Body 不是本接口格式。
- `type` 必须是 `single_choice` / `multi_choice` / `code` / `short_answer`。

## 7. Assessment Generate Questions

### 请求

```http
POST http://127.0.0.1:8002/agent/v1/assessment/generate-questions
Content-Type: application/json
```

### Body

```json
{
  "user_id": "user_001",
  "course_id": "course_ds_c",
  "knowledge_base_id": "kb_course_ds_c",
  "chapter": "栈与队列",
  "knowledge_point": "队列",
  "question_types": ["single_choice"],
  "count": 3,
  "difficulty": "medium",
  "personalized": true,
  "personalization_context": {
    "evaluation": null,
    "profile": null
  }
}
```

### 成功判定

必须检查：

- HTTP 200
- `data.questions` 是 array
- 每题有 `type`
- 每题有 `content`
- 每题有 `answer`
- 每题有 `knowledge_point`

常见失败：

- `difficulty` 必须是 `easy` / `medium` / `hard`。
- `question_types` 内元素必须是 `single_choice` / `multi_choice` / `code` / `short_answer`。

## 8. Learning Path Generate

### 请求

```http
POST http://127.0.0.1:8002/agent/v1/learning-path/generate
Content-Type: application/json
```

### Body

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
        "to": "kp_queue"
      }
    ]
  }
}
```

### 成功判定

必须检查：

- HTTP 200
- `data.nodes` 是 array
- `data.edges` 是 array
- `data.current_position` 存在或为 null
- 返回节点 ID 不应超出请求里的 `knowledge_graph.nodes[].id`

常见失败：

- `knowledge_graph.nodes` 缺失：会 422。
- `edges` 中 `from` / `to` 指向不存在节点：接口可能 fallback，但结果质量会差。

## 9. Resources Generate

### 请求

```http
POST http://127.0.0.1:8002/agent/v1/resources/generate
Content-Type: application/json
```

### Body

```json
{
  "task_id": "apifox-resources-001",
  "user_id": "apifox-user",
  "course_id": "smoke-course",
  "webhook_url": "https://m1.apifoxmock.com/m1/8182577-7941807-7764192/api/v1/webhooks/agent",
  "chapter": "函数",
  "knowledge_point": "一次函数",
  "resource_types": ["document", "mindmap", "reading", "code"]
}
```

### 第一步成功判定：任务接收

本接口立即返回：

```json
{
  "code": 202,
  "message": "accepted",
  "data": {
    "task_id": "apifox-resources-001",
    "estimated_duration": 120
  }
}
```

必须检查：

- HTTP 202
- `code=202`
- `data.task_id` 与请求一致
- `data.estimated_duration` 存在

注意：这里看不到生成资源。`202` 只代表任务已接收。

### 第二步成功判定：查看生成资源

去 Apifox 的 webhook / Mock 请求记录里看 Agent Service 发来的 POST。

资源位置：

```text
Request Body.result.resources
```

资源正文位置：

```text
Request Body.result.resources[].content
```

成功回调示例：

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

必须检查：

- webhook body 里 `task_id` 与请求一致
- `task_type=resource_generation`
- `status=completed`
- `result.resources` 是 array
- 期望包含 `document` / `mindmap` / `reading` / `code`
- 每个资源都有 `title` / `type` / `description` / `content` / `chapter` / `knowledge_point` / `tags`
- 不应出现内部字段 `generated_by` / `fallback_reason` / `is_skeleton`

常见失败：

- 只有 `202`，没有 Mock 记录：看 Agent Service 日志是否有 `Resource generation webhook failed`。
- `Connection refused`：`webhook_url` 不可达，不要用 WSL 不可达的 `http://127.0.0.1:4523/...`。
- `model_loaded=false`：服务没有读到 `.env`，资源可能直接 fallback 到占位内容。
- Mock 有记录但内容很空：链路通了，但真实 LLM 可能没工作，查看日志里的 `fallback`、`LLM`、`ResourceAgent`。

## 10. Memory Compress

### 请求

```http
POST http://127.0.0.1:8002/agent/v1/memory/compress
Content-Type: application/json
```

### Body

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

### 成功判定

必须检查：

- HTTP 200
- `data.new_summary` 存在
- `data.extracted_facts` 是 array
- 每个 fact 的 `fact_type` 如存在，应是 `blind_spot` / `mastered_point` / `cognitive_preference`

常见失败：

- `role` 必须是 `user` / `assistant`。
- `timestamp` 必须是 ISO 时间字符串。

## 11. 最小回归顺序

建议按这个顺序测：

1. `GET /agent/v1/health`
2. `POST /agent/v1/profile/generate`
3. `POST /agent/v1/evaluation/generate`
4. `POST /agent/v1/assessment/evaluate`
5. `POST /agent/v1/assessment/generate-questions`
6. `POST /agent/v1/learning-path/generate`
7. `POST /agent/v1/memory/compress`
8. `POST /agent/v1/tutoring/chat`
9. `POST /agent/v1/resources/generate`

原因：

- 先测同步 JSON，最快定位 schema / Body 问题。
- SSE 放后面，因为 Apifox 展示可能不稳定。
- resources 最后测，因为它是异步，需要额外看 webhook 回调。

## 12. Studio 可见性矩阵

| 接口 | 当前 AI 实现 | AgentScope Studio 预期 |
|------|------|------|
| `tutoring/chat` | `TutorReActAgent` + tools + memory | 应能看到 Agent 流 |
| `assessment/generate-questions` | `QuestionGeneratorReActAgent` + `retrieve_course_knowledge` + `validate_question_format` | 应能看到 `QuestionGenerator` |
| `resources/generate` | Planner + AgentScope `fanout_pipeline` + ResourceAgent adapter + Aggregator | 可能不像 ReAct 聊天流一样完整展示，主要看日志和 webhook |
| `profile/generate` | 规则结果 + LLM structured output 增强 | 不会显示 Agent 流 |
| `evaluation/generate` | 规则表格 + LLM structured output 增强 | 不会显示 Agent 流 |
| `assessment/evaluate` | 规则判分 + LLM 解释增强 | 不会显示 Agent 流 |
| `learning-path/generate` | LLM structured output + 规则 fallback | 不会显示 Agent 流 |
| `memory/compress` | LLM 提取 + 规则 fallback + Qdrant best-effort 写入 | 不会显示 Agent 流 |

## 13. 真实 AI 命中证据

Apifox 只能证明接口协议和最终结果，不能直接证明内部 Agent 路径。

仅 HTTP 200 / 202 不能证明真实 AI 路径命中。需要同时检查：

- health: `model_loaded=true` 且 `model_name` 为当前模型。
- 日志出现 `LLM ... succeeded` 或 `ReActAgent ... succeeded`。
- 日志没有 `chat_provider=None`。
- 日志没有关键路径 `falling back`。
- resources webhook body 中 `result.resources[].content` 不是空内容或规则占位内容。

可以重点观察以下日志：

```text
LLM generation succeeded
LLM Planner succeeded
ResourceAgent succeeded
Aggregator merged results
ReActAgent succeeded
```

如果看到：

```text
falling back
chat_provider=None
LLM resource generation failed
```

说明接口可能仍返回成功，但结果来自 fallback，不代表真实 LLM 质量已验证。
