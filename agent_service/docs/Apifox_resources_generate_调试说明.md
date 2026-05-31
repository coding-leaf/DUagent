# Apifox resources/generate 调试说明

本文用于在 Backend 尚未完成时，用 Apifox 验证 Agent Service 的 `resources/generate` 异步资源生成链路。

## 1. 启动服务

在项目根目录启动 Agent Service：

```bash
cd /home/yezisama/workspace/workflow/EDUagent
./.venv/bin/uvicorn agent_service.main:app --host 127.0.0.1 --port 8002
```

如果需要保存日志：

```bash
./.venv/bin/uvicorn agent_service.main:app --host 127.0.0.1 --port 8002 2>&1 | tee /tmp/eduagent.log
```

另一个终端查看日志：

```bash
tail -f /tmp/eduagent.log
```

## 2. Apifox Webhook 配置

本项目的 `webhook_url` 不是 Agent Service 暴露出来的接口，而是 Agent Service 生成完成后要回调的接收地址。

正式联调时，这个地址由 Backend 提供：

```http
POST /api/v1/webhooks/agent
```

Backend 尚未完成时，可以在 Apifox 里新建一个专门的 Webhook 接口临时代替 Backend 接收回调。

### 新建 Webhook

在 Apifox 项目左侧点击 `+`，选择 `新建 Webhook`。

建议配置：

```http
POST /api/v1/webhooks/agent
```

这个 Webhook 表示：当 Agent Service 完成资源生成后，会向这个地址发送 POST JSON。

### Webhook 请求体示例

在 Apifox Webhook 的请求体里配置 Agent Service 回调 payload 示例：

~~~json
{
  "task_id": "apifox-resources-001",
  "task_type": "resource_generation",
  "status": "completed",
  "result": {
    "resources": [
      {
        "title": "函数 - 一次函数 - 知识讲解",
        "type": "document",
        "description": "面向 一次函数 的知识讲解。",
        "content": "## 一次函数\n形如 y = kx + b 的函数称为一次函数。",
        "chapter": "函数",
        "knowledge_point": "一次函数",
        "tags": ["函数", "一次函数", "document"]
      }
    ]
  }
}
~~~

然后复制 Apifox 为该 Webhook 提供的接收/调试 URL。后续调用 `resources/generate` 时，把这个完整 URL 填入 `webhook_url`。

当前 WSL 本地调试优先使用 Apifox 的云端 Mock 地址，避免 Apifox 桌面端本地 Mock 的 `127.0.0.1` 指向 Windows 而不是 WSL。

当前可用云端 Mock 示例：

```text
https://m1.apifoxmock.com/m1/8182577-7941807-7764192/api/v1/webhooks/agent
```

注意：Apifox Webhook 是被 Agent Service 回调的接口，不是你手动发送资源生成请求的接口。

调用方向是：

```text
你手动请求 -> POST /agent/v1/resources/generate -> Agent Service
Agent Service 生成完成 -> POST webhook_url -> Apifox Webhook
```

## 3. Apifox 资源生成请求配置

### 基本信息

```http
POST http://127.0.0.1:8002/agent/v1/resources/generate
Content-Type: application/json
```

`webhook_url` 填上一步复制到的 Apifox Webhook 接收/调试 URL，或正式 Backend 的 `/api/v1/webhooks/agent` 完整地址。当前建议使用 Apifox 云端 Mock URL。

### 请求体示例

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

字段说明：

| 字段 | 类型 | 说明 |
|------|------|------|
| `task_id` | string | Backend 传入的任务 ID，webhook 回调会原样带回 |
| `user_id` | string | 用户 ID |
| `course_id` | string | 课程 ID，用于课程知识检索 |
| `webhook_url` | string | Agent Service 生成完成后 POST 回调的地址 |
| `chapter` | string/null | 章节名，可为空 |
| `knowledge_point` | string/null | 知识点，可为空 |
| `resource_types` | array/null | 可选：`document`、`mindmap`、`reading`、`code`；不填默认生成四类 |

## 4. 立即响应示例

接口是异步协议，Apifox 调用后应立即返回 `202`：

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

`estimated_duration` 按资源类型数量估算，四类资源通常是 `120` 秒。

## 5. Webhook 成功回调示例

资源生成完成后，Agent Service 会向请求体中的 `webhook_url` 发送 POST JSON。

~~~json
{
  "task_id": "apifox-resources-001",
  "task_type": "resource_generation",
  "status": "completed",
  "result": {
    "resources": [
      {
        "title": "函数 - 一次函数 - 知识讲解",
        "type": "document",
        "description": "面向 一次函数 的知识讲解。",
        "content": "## 一次函数\n形如 y = kx + b 的函数称为一次函数。",
        "chapter": "函数",
        "knowledge_point": "一次函数",
        "tags": ["函数", "一次函数", "document"]
      },
      {
        "title": "函数 - 一次函数 - 知识导图",
        "type": "mindmap",
        "description": "面向 一次函数 的知识导图。",
        "content": "mindmap\n  root((一次函数))\n    定义\n      y = kx + b\n    性质\n      图像是一条直线",
        "chapter": "函数",
        "knowledge_point": "一次函数",
        "tags": ["函数", "一次函数", "mindmap"]
      },
      {
        "title": "函数 - 一次函数 - 拓展阅读",
        "type": "reading",
        "description": "面向 一次函数 的拓展阅读。",
        "content": "## 拓展阅读\n一次函数是最基础的线性模型。",
        "chapter": "函数",
        "knowledge_point": "一次函数",
        "tags": ["函数", "一次函数", "reading"]
      },
      {
        "title": "函数 - 一次函数 - 代码示例",
        "type": "code",
        "description": "面向 一次函数 的代码示例。",
        "content": "## 代码\n```c\n#include <stdio.h>\nint main(){ return 0; }\n```",
        "chapter": "函数",
        "knowledge_point": "一次函数",
        "tags": ["函数", "一次函数", "code"]
      }
    ]
  }
}
~~~

验收重点：

- `task_id` 与请求一致。
- `task_type` 是 `resource_generation`。
- `status` 是 `completed`。
- `result.resources` 非空。
- 每个资源都有 `title`、`type`、`description`、`content`、`chapter`、`knowledge_point`、`tags`。
- webhook payload 不应出现内部字段：`generated_by`、`fallback_reason`、`is_skeleton`。

## 6. Webhook 失败回调示例

如果资源生成过程出现未被降级链兜住的异常，会发送失败回调：

```json
{
  "task_id": "apifox-resources-001",
  "task_type": "resource_generation",
  "status": "failed",
  "error_message": "error detail"
}
```

正常情况下，资源生成链路会优先返回 `completed`，因为有以下降级链：

```text
multi-agent workflow
  -> generate_resources_with_llm()
  -> skeleton resources
  -> failed webhook
```

## 7. 常见 422 排错

如果 Apifox 返回类似：

```json
{
  "detail": [
    { "loc": ["body", "quiz_id"], "msg": "Field required" },
    { "loc": ["body", "questions"], "msg": "Field required" },
    { "loc": ["body", "answers"], "msg": "Field required" }
  ]
}
```

说明你当前发送到的不是 `resources/generate`，而是类似 `assessment/evaluate` 的接口。

请确认手动发送的地址是：

```http
POST http://127.0.0.1:8002/agent/v1/resources/generate
```

不要手动把资源生成请求体发送到 Apifox Webhook 接口。Webhook 接口只负责接收 Agent Service 的异步回调。

## 8. 如何判断 AI 工作流是否命中

Apifox 只能看到外部协议，不会暴露内部字段。判断 multi-agent 是否命中，需要看服务端日志。

启动服务的终端中应能看到类似日志：

```text
Multi-agent workflow started
LLM Planner succeeded
ResourceAgent succeeded
Aggregator merged results
```

如果没有配置真实 LLM，可能会看到 fallback 相关日志：

```text
Multi-agent workflow returned None, falling back to LLM parallel path
LLM resource generation failed, falling back to skeleton
```

这种情况下 Apifox 仍可能收到 `completed`，但内容会是规则版 skeleton 占位资源。

## 9. 不依赖 Apifox 的本地验证命令

验证 resources multi-agent fake provider 路径：

```bash
./.venv/bin/python -m agent_service.tools.smoke_resources_workflow
```

期望输出包含：

```json
{
  "status": "PASS",
  "path": "multi_agent",
  "resource_count": 4,
  "missing_types": [],
  "leaked_internal_fields": [],
  "mindmap_format_ok": true
}
```

验证真实 LLM 配置：

```bash
./.venv/bin/python -m agent_service.tools.smoke_resources_workflow --live
```

如果 `.env` 没有配置真实 LLM provider，会输出：

```json
{
  "status": "SKIP",
  "reason": "LLM provider is not configured",
  "mode": "live"
}
```

## 10. 真实 LLM 配置提示

要让 Apifox 触发真实 LLM 资源生成，需要 `.env` 中配置：

```env
LLM_PROVIDER=agentscope_openai
LLM_BASE_URL=...
LLM_API_KEY=...
LLM_MODEL=...
LLM_JSON_MODE_ENABLED=true
```

可选 embedding 配置用于课程知识 RAG：

```env
EMBEDDING_PROVIDER=agentscope_openai
EMBEDDING_BASE_URL=...
EMBEDDING_API_KEY=...
EMBEDDING_MODEL=...
EMBEDDING_DIMENSION=1024
```

未配置 LLM 时，接口仍可通过降级链返回 `completed`，但不能证明真实 LLM 输出质量。
