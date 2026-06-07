# 2026-06-07 Agent 字段与异步链路后续流程

## 当前结论

前后端 Agent 相关能力需要按链路拆开判断，不能笼统视为全部完成。

- `tutoring/chat` 智能辅导 SSE 链路已基本完成联调：Frontend 调 Backend `/api/v1/tutoring/chat`，Backend 代理 Agent `/agent/v1/tutoring/chat`，真实 Agent smoke 已确认 `chunk`、`diagram`、`knowledge_points`、`suggestion`、`done` 事件可产出。
- Admin Agent 日志字段已按 Client API 对齐：Frontend 使用 `agent_type`、`endpoint`、`latency_ms`、`tokens_used`、`status`、`error_message`，不再消费旧 mock 字段。
- 资源生成异步链路尚未完成前端闭环：Backend 创建 `resource_generation` 任务并调用 Agent `/agent/v1/resources/generate`，Agent webhook 回调后 Backend 可校验 `result.resources` 并写入 SQL；但 Frontend 页面还没有实际接入“触发生成 -> 轮询任务 -> 完成后刷新资源列表”的用户流程。

## 需要优先解决的问题

### P1: 资源生成异步任务链路接入

目标：教师能在前端触发课程资源生成，并看到任务状态和结果刷新。

涉及现有接口：

- `POST /api/v1/resources/generate`
- `GET /api/v1/tasks/{task_id}`
- `GET /api/v1/resources?course_id=...`
- 内部链路：Backend -> Agent `/agent/v1/resources/generate` -> Backend `/api/v1/webhooks/agent`

计划步骤：

1. 契约复核
   - 确认 `POST /resources/generate` 请求字段：`course_id`、`chapter`、`knowledge_point`、`resource_types`。
   - 确认 `GET /tasks/{task_id}` 返回字段：`task_id`、`task_type`、`status`、`progress`、`result`、`error_code`、`error_message`。
   - 确认任务完成后前端是否只刷新资源列表，还是需要读取 `result.resource_ids`。当前 Backend webhook 保存的是 `task.result = req.result`，不显式返回 `resource_ids`。

2. 前端入口设计
   - 优先放在教师端课程相关页面或资源管理区域，不放到学生 Dashboard。
   - 提供最小输入：课程、章节、知识点、资源类型。
   - 发起后保留 `task_id`，展示 processing/completed/failed 状态。

3. 前端轮询与刷新
   - 调用 `learningService.triggerResourceGeneration()` 获取 `task_id`。
   - 调用 `learningService.getTaskStatus(task_id)` 轮询。
   - `completed` 后刷新 `learningService.getResources({ course_id })`。
   - `failed` 时展示 `error_message`，不要只显示“已提交”。

4. 验证闭环
   - Frontend: `npm run lint`
   - Frontend: `npm run build`
   - Backend: 优先运行 `tests/test_resources_async.py`
   - 条件允许时运行 `npm run test:e2e`，要求 Backend、Agent Service、MySQL 测试数据在线。

完成判定：

- 教师在前端可以触发资源生成。
- 页面能展示任务进行中、成功、失败三类状态。
- 成功后资源列表出现新资源或至少重新拉取资源列表。
- Agent 不可用时任务失败状态能被前端感知并展示。
- 不新增未确认 Client API 字段，不让前端直连 Agent Service。

## 已知奇怪点与风险

### Webhook 鉴权契约不一致

`API_前端接口规范.md` 当前写 v1 webhook 无需额外鉴权，但 Backend 实现依赖 `verify_webhook_secret`，即需要 `X-Webhook-Secret`。

处理建议：

- 不在资源生成前端接入中临时绕过鉴权。
- 单独确认是否以 Backend 实现为准更新文档，或调整 Agent Service 回调配置。
- 若 Agent Service 已能带 header，则文档需要补齐；若不能带 header，则联调会卡在 webhook 403。

### learner_context helper 未进入 Agent payload

Backend 已有脱敏 helper，但当前不写入 `/tutoring/chat` payload，避免 Agent API 漂移。

处理建议：

- 不在资源生成链路中顺手扩展 Agent chat payload。
- 如需让 Agent 使用 `major`、`grade`、`guidance_level`，另开契约审查：Agent API schema、Backend payload、测试一起改。

### 资源质量不是当前阻塞

资源内容质量偏低应归入资源生成质量专项，不阻塞“异步任务链路是否打通”的验收。

## P2 后续收尾

- Admin 用户列表持久展示停用状态：需要扩展 `GET /admin/users` 返回 `is_active` 或状态字段。
- 管理员初始化账号固化：确认 seed 或 schema 初始化方式。
- `overall_score` 真实计算口径：单独走契约审查。
- AIChat 活动摘要、阅读进度、学习时长、资源偏好分布：需要行为采集或 activity 表设计，暂不直接用静态字段补齐。

## 修改边界

- Frontend 不直接调用 Agent Service。
- 不为页面展示硬编码 Agent 字段、mock 字段或假任务状态。
- 不修改 `../docs/`，除非用户明确要求。
- 如需改变 OpenAPI 或 Agent API，先输出冲突点、影响范围和测试方案，再等待确认。
