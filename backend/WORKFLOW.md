# WORKFLOW.md

## 接口实现状态维护约定

本文件开头固定维护一份“接口实现情况”总览，用于区分：

- `真实完成`：已接真实鉴权/SQL/Agent 调用，主链路可用
- `半完成`：有真实逻辑，但仍存在硬编码、弱校验、伪异步或部分占位
- `占位/规则完成`：仅完成返回结构、路由或基础协议，业务未真实落地
- `文档声明不做`：当前 v1 契约明确不提供

维护规则：

1. 只要修改了某个接口实现，必须同步更新本文件中的该接口“最近状态”。
2. 更新时至少补充：
   - 修改日期
   - 接口路径
   - 最新状态
   - 一句说明本次变更影响
3. 如果接口从 `占位/规则完成` 提升到 `半完成` 或 `真实完成`，必须直接修改总览表，不允许只写在“最近验证”。
4. 如果接口行为回退、发现假实现、联调不闭环，也必须回写状态，不允许只保留乐观描述。

## 当前接口实现情况总览

更新日期：`2026-06-01`

### 真实完成

- `GET /api/v1/auth/captcha`
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/users/me`
- `PUT /api/v1/users/me`
- `GET /api/v1/courses`
- `POST /api/v1/courses`
- `POST /api/v1/courses/join`
- `GET /api/v1/admin/users`
- `PUT /api/v1/admin/users/{user_id}`
- `DELETE /api/v1/admin/users/{user_id}`
- `GET /api/v1/admin/logs/agent`
- `GET /api/v1/admin/logs/operations`
- `GET /api/v1/tasks/{task_id}`
- `GET /api/v1/tutoring/conversations`
- `GET /api/v1/tutoring/conversations/{conversation_id}`

### 半完成

- `GET /api/v1/evaluation`
- `POST /api/v1/evaluation/refresh`
- `POST /api/v1/profile/initialize`
- `GET /api/v1/profile`
- `POST /api/v1/profile/refresh`
- `GET /api/v1/learning-path`
- `POST /api/v1/learning-path/refresh`
- `GET /api/v1/quiz/questions`
- `POST /api/v1/quiz/generate`
- `POST /api/v1/quiz/submit`
- `GET /api/v1/quiz/history`
- `GET /api/v1/resources`
- `POST /api/v1/resources/generate`
- `POST /api/v1/tutoring/chat`
- `GET /api/v1/teaching/classes/{class_id}/students`
- `GET /api/v1/teaching/classes/{class_id}/students/{student_id}`
- `GET /api/v1/teaching/classes/{class_id}/students/{student_id}/learning`
- `POST /api/v1/webhooks/agent`

### 占位/规则完成

- `GET /api/v1/learning-path/nodes/{node_id}/resources`
- `GET /api/v1/quiz/result`

### 文档声明不做

- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/send-reset-code`

## 最近状态变更

- `2026-06-01` `接口盘点初始化`
  - 新增接口实现情况总览
  - 明确后续每次改接口时必须同步更新最近状态

## 文件用途

本文件记录 Backend 联调的开发进度和跨窗口恢复上下文。
接口契约以 `../docs/20-agent-api/Agent-Service.openapi.json` 和 `../docs/20-agent-api/API_Agent内部接口规范.md` 为准，本文件不是接口契约来源。

## 当前方向

- Backend 已具备对接 Agent Service 的基础：统一的 `AgentClient`、AsyncTask 管理、Webhook 接收落库。
- 6 个 Agent 接口全部完成对接，所有调用统一走 `agent_client` 单例。
- 后续进入联调验证：逐接口启动两个服务，验证完整链路（请求 → Agent 返回 → Backend 落库）。
- 发现的问题优先修 bug，再补 stub。

## Agent Service 接口对接状态

| Backend 接口 | Agent 路径 | 类型 | 状态 | 备注 |
|-------------|-----------|------|------|------|
| `POST /api/v1/profile/refresh` | `/agent/v1/profile/generate` | JSON 同步 | ✅ | 参考实现，payload 从 SQL 聚合 |
| `POST /api/v1/tutoring/chat` | `/agent/v1/tutoring/chat` | SSE 代理 | ✅ | SSE 流透传，累积 chunk 后保存 |
| `POST /api/v1/resources/generate` | `/agent/v1/resources/generate` | 异步+Webhook | ✅ | task_id + webhook_url 传入 |
| `POST /api/v1/quiz/generate` | `/agent/v1/assessment/generate-questions` | 异步 | ✅ | 生成后写 quiz_questions |
| `POST /api/v1/evaluation/refresh` | `/agent/v1/evaluation/generate` | JSON 同步 | ✅ | 聚合学习进度/练习结果 |
| `POST /api/v1/learning-path/refresh` | `/agent/v1/learning-path/generate` | JSON 同步 | ✅ | 传入 evaluation + knowledge_graph |
| `POST /api/v1/webhooks/agent` | — | Webhook | ⚠️ | 见已知问题 |

## 已知问题

1. **Webhook 未设 task.status**（`webhooks.py:53-75`）：completed/failed 回调设了 `result`、`progress`、`completed_at`，但未设 `task.status = "completed"`。前端轮询永远看到 "processing"，幂等保护失效。
2. **Webhook 无鉴权**：端点无 token 校验，文档注明"部署时通过内网限制访问"，v1 可接受。
3. **`GET /learning-path/nodes/{id}/resources`** 是硬编码 stub，返回空数组。
4. **`POST /quiz/submit` 诊断** 是硬编码文本，不调 LLM。

## 联调命令

```bash
# Agent Service（agent_service/ 目录，终端 1）
./.venv/bin/uvicorn agent_service.main:app --host 127.0.0.1 --port 8002

# Backend（backend/ 目录，终端 2）
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload

# 验证 Agent Service 健康
curl http://127.0.0.1:8002/agent/v1/health

# Backend 联调测试
python test_agent_integration.py

# Backend 冒烟测试
python test_api.py

# Agent Service 全量回归
cd agent_service && ./.venv/bin/pytest -q
```

## 测试文件

| 文件 | 用途 | 覆盖范围 |
|------|------|---------|
| `test_agent_integration.py` | Agent 联调集成测试 | 6 个 Agent 接口 + Webhook + 权限 + 降级 |
| `test_api.py` | 全量冒烟测试 | 所有端点的基础可用性 |

## 最近验证

_（联调进行中，逐接口填充）_

## 下一步建议

1. 修 Webhook task.status bug
2. Phase 1 联调：profile/refresh（JSON 同步，最简单，先打通）
3. Phase 2 联调：tutoring/chat（SSE 代理）
4. Phase 3 联调：resources/generate（异步 + Webhook 落库）
5. Phase 4 联调：quiz/generate（题目生成 + 落库）
6. Phase 5-6 联调：evaluation/refresh + learning-path/refresh
7. 补 stub：learning-path node resources、quiz submit 诊断
