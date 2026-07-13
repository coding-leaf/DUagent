# Agent API 内部接口规范

> Backend（8001）↔ Agent Service v2（8002）
>
> 当前运行时只支持 `/agent/v2/*`。精确字段、响应模型和校验规则以同目录 `Agent-Service.openapi.json` 为准。

## 边界

- Frontend 不直连 Agent Service。
- Backend 只通过 HTTP 调用 Agent Service，不导入其 Python 模块。
- Agent Service 不访问 MySQL；业务落库通过 Backend 内部 API 或 webhook。
- Qdrant 检索和 AgentScope Workspace 由 Agent Service 管理。
- Backend 创建的业务 `task_id` 必须由 Agent 原样传递。
- AgentScope 原始事件不得泄漏到公开协议。

## 通用响应

同步 JSON 接口使用：

```json
{"code": 200, "message": "success", "data": {}}
```

异步接收可返回 HTTP 202。Workbench 和个性化资源事件使用 SSE；其事件模型由 OpenAPI schema 和当前协议适配器共同约束。

## 当前接口

### Workbench

- `POST /agent/v2/workbench/chat`：AgentScope 工作台对话与工具事件流。
- `GET /agent/v2/workbench/artifacts`：在可信 user/course/conversation 边界内读取产物。

Workbench 保持 AgentScope 2.x `Agent.reply_stream + Toolkit + ToolGroup` 的自主工具调用。EDU 协议适配器将工具结果统一为：

```json
{
  "outcome": "success | neutral | warning | failure",
  "status": "published",
  "reason": null,
  "summary": {},
  "retryable": false,
  "data": {},
  "artifact": {},
  "sources": []
}
```

- `available/published/ok/success` → `success`，`empty/not_found` → `neutral`，`degraded` → `warning`，`rejected/unavailable/delivery_incomplete/error` → `failure`。
- AgentScope `ToolResultState.ERROR` 直接映射为 `tool_failed`。`tool_started` 携带 `tool_title/tool_category/read_only`。
- RAG 引用只使用 `payload.sources[]`，每项为 `source_file/snippet/score`；不再交叉使用 `citations`。
- 长期记忆只保存用户明确表达的长期偏好、目标和稳定事实；禁止保存推断掌握度、诊断、答案、敏感内容或工具原文。写入前去重，工具卡可见，审计日志不记忆正文。

### AI Chat 互动练习内部发布

Agent Service 通过 Backend 内部 HTTP 链路发布 QuizCard 和 CodeSandboxCard：

1. `POST /internal/ai-chat/personal-practices/prepare`：验证可信上下文与 draft，以稳定幂等键保存 `delivery_pending` generation，不创建用户可见题目。
2. `POST /internal/ai-chat/personal-practices/finalize`：锁定 generation，在同一 MySQL 事务中创建业务记录、关联和 artifact descriptor，然后标记 `published`。
3. `POST /internal/ai-chat/personal-practices/resume`：按 `generation_id` 幂等恢复 `delivery_failed` 或响应丢失的发布。

`idempotency_key` 由规范化 draft、user、conversation、run 和工具类型稳定派生。互动卡片由 Backend 作为唯一权威；Agent Workspace 只保留 Markdown/Mermaid 等文件型产物。旧 `/internal/ai-chat/code-problem-validations` 和 `/internal/ai-chat/choice-quizzes` 已删除。

### Knowledge

- `POST /agent/v2/knowledge/ingestions`：课程资料切片并写入 Qdrant。
- `POST /agent/v2/knowledge/knowledge-graphs/generations`：根据课程切片或文本生成知识图谱。
- `POST /agent/v2/knowledge/quiz/generations`：生成课程或个性化题目。
- `POST /agent/v2/knowledge/resources/generations`：异步生成公共学习资源。

### Evaluation

- `POST /agent/v2/evaluation/generations`：生成结构化学情评估。
- `POST /agent/v2/evaluation/quiz/diagnose`：根据作答事实生成诊断。

### Personalized Resources

- `POST /agent/v2/personalized-resources/generations`：启动个性化资源 Agent Team。
- `GET /agent/v2/personalized-resources/generations/{session_id}/events`：订阅生成事件。

### Team Runtime

- `/agent/v2/team-runtime`：AgentScope 团队运行时挂载点，不作为 Frontend 直连接口。

## 已退役能力

- 全部 `/agent/v1/*` 已删除，不提供兼容代理。
- 画像生成与刷新由 Backend 规则服务负责。
- 学习路径由 Backend 根据 active KG 和实时学习进度计算，不再调用 Agent 生成。
- 旧记忆压缩接口由 v2 Workbench 的记忆生命周期替代。

## 本地验证

```bash
cd agent_service_v2
./.venv/bin/uvicorn agent_service_v2.main:app --host 127.0.0.1 --port 8002
curl -fsS http://127.0.0.1:8002/openapi.json >/dev/null
```
