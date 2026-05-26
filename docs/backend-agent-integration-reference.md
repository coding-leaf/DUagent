# Backend 接入 Agent Service 参考说明

## 目标

本文给 Backend 开发者说明如何接入 `agent_service`。

Backend 只通过 HTTP 调用 Agent Service 的 `/agent/v1/*` 接口，不导入 `agent_service` Python 模块。Backend 继续负责用户、课程、SQL 持久化、任务状态和前端 API 响应；Agent Service 负责 LLM、RAG、AgentScope 编排、Qdrant 检索和结构化 AI 结果生成。

契约来源：

1. `docs/20-agent-api/Agent-Service.openapi.json`
2. `docs/20-agent-api/API_Agent内部接口规范.md`

## 当前 Backend 状态判断

新版 Backend 已具备接入基础：

- `backend/app/core/config.py` 已有 `AGENT_SERVICE_URL = "http://localhost:8002"`
- `backend/app/models/others.py` 已有 `AsyncTask`
- `backend/app/api/v1/webhooks.py` 已有 `POST /api/v1/webhooks/agent`
- `backend/app/api/v1/tutoring.py` 已有 SSE 响应框架
- 已有 `UserProfile`、`Evaluation`、`LearningPath`、`Resource`、`QuizQuestion` 等 SQL 模型

当前主要缺口：

- 缺少统一的 `backend/app/services/agent_client.py`
- 各 AI 入口仍主要是本地 mock 或同步假完成
- webhook 当前只更新任务状态，尚未把 `result.resources` 写入 `resources`
- tutoring SSE 当前返回本地模拟文本，尚未代理 Agent SSE

## 推荐接入顺序

### 第一批：Profile Refresh

优先接 `POST /api/v1/profile/refresh` 到：

```text
POST /agent/v1/profile/generate
```

原因：

- JSON 请求、JSON 响应
- 无 SSE
- 无 webhook
- SQL 写入范围小，只涉及 `UserProfile` 和 `AsyncTask`
- 最适合作为第一条真实 Agent 链路

建议 Backend 流程：

1. 校验用户是否有课程权限。
2. 创建 `AsyncTask(task_type="profile_refresh", status="processing")`。
3. 从 SQL 组装最小 payload。
4. 调用 Agent Service。
5. 校验 Agent 返回的 `data`。
6. upsert `UserProfile`。
7. 标记任务 `completed`；失败则标记 `failed`，不要静默成功。

### 第二批：Tutoring SSE

接 `POST /api/v1/tutoring/chat` 到：

```text
POST /agent/v1/tutoring/chat
```

建议 Backend 流程：

1. Backend 继续负责 conversation 校验或创建。
2. Backend 保存用户原始消息。
3. Backend 从 SQL 组装：
   - `user_id`
   - `scope`
   - `course_id`
   - `conversation_id`
   - `message`
   - `user_profile`
   - `conversation_summary`
   - `recent_messages`
4. Backend 代理 Agent Service SSE 给前端。
5. Backend 累积 `chunk` 内容，完成后写入 assistant message。

注意：

- 课程知识 RAG 由 Agent Service 自行检索。
- 用户长期记忆 Qdrant 检索由 Agent Service 自行完成。
- Backend 只传 SQL 中已有的结构化画像、摘要和最近消息。

### 第三批：Resources Async + Webhook

接 `POST /api/v1/resources/generate` 到：

```text
POST /agent/v1/resources/generate
```

建议 Backend 流程：

1. Backend 创建 `AsyncTask(task_type="resource_generation")`。
2. Backend 把 `task_id` 原样传给 Agent Service。
3. Backend 提供 `webhook_url`，指向：

```text
POST /api/v1/webhooks/agent
```

4. Agent Service 立即返回 202。
5. Agent Service 生成完成后回调 Backend webhook。
6. Backend webhook 校验 `task_id` 和 `task_type`。
7. Backend 把 `result.resources` 写入 `resources` 表。
8. Backend 标记任务 `completed`。

注意：

- Agent Service 不直接写 Backend SQL。
- webhook 要做幂等，避免重复写入资源。

### 第四批：Quiz Generate

接 `POST /api/v1/quiz/generate` 到：

```text
POST /agent/v1/assessment/generate-questions
```

建议 Backend 流程：

1. Backend 创建 `AsyncTask(task_type="quiz_generation")`。
2. Backend 调 Agent Service 生成结构化题目。
3. Backend 校验题目字段。
4. Backend 补充 SQL 字段：
   - `course_id`
   - `source`
   - `personalized`
   - `owner_user_id`
5. Backend 写入 `quiz_questions`。
6. Backend 标记任务完成。

### 第五批：Evaluation / Learning Path

后续补齐：

```text
POST /api/v1/evaluation/refresh      -> POST /agent/v1/evaluation/generate
POST /api/v1/learning-path/refresh   -> POST /agent/v1/learning-path/generate
```

这两个接口依赖 Backend 先从 SQL 组装学习进度、练习结果、资源使用、画像、知识图谱等上下文。建议放在 profile、tutoring、resources、quiz 之后。

## 建议新增 Backend Client

建议新增：

```text
backend/app/services/agent_client.py
```

职责：

- 统一读取 `settings.AGENT_SERVICE_URL`
- 统一 timeout
- 统一 POST JSON
- 统一校验 Agent 返回包装 `{code, message, data}`
- 统一处理 HTTP 错误、超时、Agent 错误码
- 支持 SSE streaming proxy

建议接口形态：

```python
class AgentServiceClient:
    async def post_json(self, path: str, payload: dict) -> dict:
        ...

    async def stream_sse(self, path: str, payload: dict):
        ...
```

Backend 路由层不要散落 `httpx.post()`，统一走这个 client，后续方便加日志、超时、重试和熔断。

## 首批建议修改文件

第一批只建议改这些文件：

```text
backend/app/services/__init__.py
backend/app/services/agent_client.py
backend/app/core/config.py
backend/app/api/v1/profile.py
backend/test_api.py
```

如果要严格控制风险，第一批甚至可以先只做：

```text
backend/app/services/__init__.py
backend/app/services/agent_client.py
backend/app/api/v1/profile.py
backend/test_api.py
```

## 责任边界

Backend 负责：

- 用户鉴权
- 课程权限校验
- SQL 查询和写入
- `AsyncTask` 创建和状态维护
- 前端 API 响应格式
- webhook 接收和落库
- 原始对话消息保存

Agent Service 负责：

- LLM 调用
- AgentScope 编排
- RAG 检索
- Qdrant course knowledge / user memory 读写
- 结构化 AI 结果生成
- tutoring SSE 内容生成
- resources 异步生成并回调 webhook

禁止：

- Backend 直接访问 Qdrant。
- Backend 导入 `agent_service` Python 模块。
- Agent Service 写 Backend SQL。
- Agent Service 自己生成 Backend `task_id`。

## 本地联调启动

Agent Service：

```bash
cd agent_service
./.venv/bin/uvicorn agent_service.main:app --host 127.0.0.1 --port 8002
```

Backend：

```bash
cd backend
python test_api.py
```

## 首批验收标准

Profile refresh 首批验收：

- `POST /api/v1/profile/refresh?course_id=...` 返回 HTTP 202。
- 返回值包含 Backend 创建的 `task_id`。
- Backend 调用了 `POST /agent/v1/profile/generate`。
- Agent 成功时，`AsyncTask.status = "completed"`。
- Agent 失败时，`AsyncTask.status = "failed"`，并写入 `error_code` / `error_message`。
- `UserProfile` 被 Agent 返回结果更新。
- Backend 不直接访问 Qdrant。
- Agent Service 不写 Backend SQL。

## 后续验收标准

Tutoring：

- `POST /api/v1/tutoring/chat` 仍返回 `text/event-stream`。
- 前端能收到 Agent 的 `chunk` / `done` 事件。
- Backend 能保存用户消息和 assistant 消息。

Resources：

- `POST /api/v1/resources/generate` 返回 202。
- Backend 传入自己的 `task_id`。
- Agent webhook 回调后，Backend 写入 `resources`。
- 重复 webhook 不重复写资源。

Quiz：

- `POST /api/v1/quiz/generate` 返回 202。
- Agent 生成题目后，Backend 写入 `quiz_questions`。
- `GET /api/v1/quiz/questions` 能查到生成题目。

## 推荐结论

不要一次性全量改完。

推荐第一步只做：

```text
Agent client + profile refresh
```

这条链路打通后，再接：

```text
tutoring SSE -> resources webhook -> quiz generate -> evaluation/learning-path
```
