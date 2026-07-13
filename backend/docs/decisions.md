# Backend Decisions

## 决策 1：Backend 只通过 HTTP 调 Agent Service

- 背景
  - 需要维持服务边界，避免把 Agent 内部实现耦合进 Backend。
- 决策
  - 统一通过 `app/services/agent_client.py` 访问 `/agent/v2/*`。
- 原因
  - 保持部署边界、错误边界和契约边界清晰。
- 代价
  - 需要维护 payload 组装和错误适配。

## 决策 2：SQL 当前态以 Backend 落库为准

- 背景
  - Agent 返回的是 AI 计算结果，不应直接成为数据库写入方。
- 决策
  - Backend 校验 Agent 返回，再写入 SQL。
- 原因
  - 保持关系数据一致性、权限校验和事务控制集中在 Backend。

## 决策 3：resources 使用 202 + webhook

- 背景
  - 资源生成耗时长，且是多阶段异步链路。
- 决策
  - Backend 先返回 `task_id`，Agent 完成后回调 `POST /api/v1/webhooks/agent`。
- 原因
  - 符合当前契约，避免长请求阻塞前端。

## 决策 4：refresh 当前保持进程内后台协程

- 背景
  - 当前已打通 profile/evaluation/learning-path refresh 主链，但尚未引入持久化 worker。
- 决策
  - 暂时使用 `asyncio.create_task` 完成后台刷新。
- 原因
  - 以最小实现先打通联调。
- 代价
  - 进程重启后任务不可恢复，这是已知临时方案，不是最终形态。
