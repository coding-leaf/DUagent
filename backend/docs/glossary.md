# Backend Glossary

## `AsyncTask`

Backend 持久化的异步任务记录。用于表达 `processing/completed/failed` 状态、错误码和结果摘要。

## `refresh`

指 Backend 接收请求后创建 `AsyncTask`，再触发 Agent 生成并回写 SQL 当前态的刷新链路。

## `task polling`

前端通过 `GET /api/v1/tasks/{task_id}` 轮询异步任务状态。

## `webhook`

Agent Service 在异步资源生成完成后回调 Backend 的 HTTP 请求。Backend 负责鉴权和落库。

## `current state`

指 SQL 中供前端查询和后续业务编排使用的结构化当前态，例如 `UserProfile`、`Evaluation`、`LearningPath`。

## `raw conversation`

对话的原始消息全量保存，用于前端展示和数据溯源，不等于 Agent prompt 上下文本身。

## `degraded available`

链路未崩但仍存在临时方案或上游依赖未满足，结果可用但不代表能力完全收口。
