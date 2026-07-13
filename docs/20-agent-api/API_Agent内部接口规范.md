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
