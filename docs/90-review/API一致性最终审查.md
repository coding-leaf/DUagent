# API 一致性最终审查

> 日期：2026-05-21
> 范围：非归档 Markdown 文档与 OpenAPI 文档。
> 说明：`docs/00-overview/README.md` 只作项目总览；字段、端点、状态码、调用流程以正式 API 文档和 OpenAPI 为准。

## 一、最终契约来源

前端与 Backend 契约：

- `docs/10-client-api/API_前端接口规范.md`
- `docs/10-client-api/Client-API.openapi.json`

Backend 与 Agent Service 契约：

- `docs/20-agent-api/API_Agent内部接口规范.md`
- `docs/20-agent-api/Agent-Service.openapi.json`

Agent Service 开发参考：

- `docs/30-dev-guide/Agent-Service_开发导读.md`

## 二、状态码与响应外壳

所有 JSON 响应使用统一外壳：

```json
{ "code": 200, "message": "success", "data": {} }
```

成功状态约定：

- HTTP `200`：普通查询、登录、更新、删除、Webhook 接收成功；body `code: 200`，`message: "success"`。
- HTTP `201`：新建成功；body `code: 201`，`message: "created"`。
- HTTP `202`：异步任务已接受；body `code: 202`，`message: "accepted"`，`data.task_id` 用于轮询。

错误状态约定：

- HTTP 表示错误大类，如 `400`、`401`、`403`、`404`、`409`、`500`。
- body `code` 使用业务错误码，如 `40001`、`40300`、`40400`。

## 三、分页响应

分页列表统一把业务数组和分页字段都放在 `data` 内：

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "resources": [],
    "total": 142,
    "page": 1,
    "page_size": 20
  }
}
```

当前已统一的分页字段：

- `data.students`
- `data.users`
- `data.resources`
- `data.conversations`
- `data.records`

## 四、认证与账号

- 注册使用硬编码或预置 `registration_code`：`student` 注册学生，`teacher` 注册教师。
- `admin` 不开放注册，由系统预置。
- 验证码使用简单算术题，Backend 开发阶段可用内存临时保存答案。
- 登录只返回单个 JWT `token`。
- v1 暂不实现 `refresh_token`、`/auth/refresh`、邮箱/短信找回密码。
- 管理员可通过用户更新接口传入 `new_password` 重置用户密码。

## 五、课程与身份边界

- `registration_code` 只用于账号注册。
- `course_code` 是教师创建课程后分发给学生的课程码。
- `course_id` 是教师创建的课程/班级空间 ID，v1 不拆分课程模板与教学班。
- `class_id` 与 `/courses` 返回的 `courses[].id` 同源，仅用于教师视角接口命名。
- 课程资料由开发阶段预置并向量化，前端不上传课程原始资料。

## 六、画像、评估、路径

- 冷启动画像由前端固定问卷完成，Backend 按 `user_id + course_id` 保存。
- Agent Service 不提供冷启动多轮画像引导接口。
- `GET /profile`、`GET /evaluation`、`GET /learning-path` 只读最近一次结果，不实时调用 Agent。
- 刷新接口返回 `202 + task_id`，完成后前端再调用对应 GET 读取最新数据。
- 学习路径由静态课程知识图谱决定节点范围和依赖，Agent 只做个性化排序、推荐理由和当前位置建议。

## 七、题目与资源

题目体系：

- 题型固定为 `single_choice`、`multi_choice`、`code`、`short_answer`。
- 题目答案统一允许 `string` 或 `string[]`：单选、简答、代码题通常为 `string`，多选题为 `string[]`。
- 题目选项统一为数组；非选择题的 `options` 返回空数组 `[]`，不返回 `null`。
- 题库包含通用题和当前学生的个性化题。
- 个性化题由 `POST /quiz/generate` 触发，Backend 调用 Agent 生成结构化题目后校验入库。
- Agent Service 不直接写 SQL。

资源体系：

- 资源库只存学习资料，不承担练习题主链路。
- v1 资源类型为 `document`、`mindmap`、`reading`、`code`。
- `video` 作为预留类型，v1 默认不生成或返回视频内容。
- 资源生成由教师触发，生成课程级学习资料，不生成个性化题目。

## 八、智能辅导与记忆

- 智能辅导分为 `course` 和 `global` 两种 scope。
- `scope=course` 必须传 `course_id`，使用课程知识库 RAG、用户画像和长期记忆。
- `scope=global` 不传 `course_id`，不读取课程知识库，只作为全局 AI Bot 使用。
- 教师不能查看学生智能辅导对话。
- Backend 保存完整 user/assistant 原始消息和 `meta`；记忆压缩只生成摘要和长期事实，不替代原始消息。
- Agent 每次回复前检索长期记忆和相关历史事实。

## 九、异步任务与 Webhook

- 前端刷新/生成接口先拿 `task_id`，再通过 `GET /tasks/{task_id}` 轮询。
- Backend 先创建本地任务记录，再调用 Agent。
- 需要 Agent 异步处理的任务，由 Backend 把同一个 `task_id` 传给 Agent。
- Agent 回调 Backend webhook 时原样带回 `task_id`。
- Backend 根据 `task_id` 和 `task_type` 校验并幂等落库。
- Agent Service 不直接写 Backend SQL。
- 内部链路无需额外鉴权，部署时通过内网地址或容器网络限制访问。

## 十、已确认保留项

- Client 的 `/profile/initialize` 固定问卷接口保留。
- `refresh_token` 只在“暂不实现”的说明中出现，保留。
- `video_animation` 作为画像偏好维度保留，不代表 v1 会生成视频。
- `class_id` / `course_id` 当前说明已足够，暂不继续补强。

## 十一、本轮修订记录

本轮按“排除归档，`docs/00-overview/README.md` 只作总览”的规则继续审查并修订：

- 统一 Client 与 Agent 测验链路中的答案字段：`answers[].answer`、`questions[].correct_answer`、`per_question_results[].correct_answer` 均支持 `string | string[]`。
- 统一题目选项空值口径：非选择题 `options` 使用空数组 `[]`，不使用 `null`。
- 在 Client OpenAPI 中补充文档已声明的 `nullable: true`，覆盖日志空错误、系统日志空用户、未生成快照时间、未完成任务时间、全局对话课程 ID、诊断未完成等字段。
- 修正 `docs/30-dev-guide/Agent-Service_开发导读.md`：Agent Service 能力数由 8 类改为 9 类，并补入 `POST /agent/v1/assessment/generate-questions`。
- 保持两份 Agent OpenAPI 内容同步。

## 十二、jq 复核结果

在 `jq` 可用后，已重新全文复核非归档 Markdown 文档与 OpenAPI 文档：

- `docs/10-client-api/Client-API.openapi.json`、`docs/20-agent-api/Agent-Service.openapi.json` 均可被 `jq -e .` 正常解析。
- Client OpenAPI 的 `servers.url` 为 `/api/v1`，正式 Markdown 中的 `/api/v1/...` 与 OpenAPI paths 规范化后仍为 36 个端点，集合一致。
- Agent OpenAPI 的 `servers.url` 为 `/agent/v1`，正式 Markdown 中的 `/agent/v1/...` 与 OpenAPI paths 规范化后仍为 9 个端点，集合一致。
- 两份 Agent OpenAPI 使用 `cmp` 复核仍完全一致。
- 所有 JSON 成功响应外壳均包含 `code`、`message`、`data`。
- HTTP `200` / `201` / `202` 的 body 示例仍分别对齐 `success` / `created` / `accepted`。
- 所有 path 参数均显式 `required: true`。
- `TaskStatus` 与 `WebhookPayload` 的枚举仍与正式文档一致。
- `answers[].answer`、`questions[].correct_answer`、`per_question_results[].correct_answer` 的多选数组口径已在 OpenAPI 中用 `oneOf` 表达。
- 文档中仍提到 `null` 的主要字段已经落到 OpenAPI 的 `nullable: true`；仅 `EvaluationData`、`LearningPathData` 的对象级说明中提到子字段为空状态，本身不需要设置为 nullable。
- 旧冲突词 `X-API-Key`、`internal_key`、`内部密钥`、`slides`、`exercise_count`、`非选择题时为 null` 未在正式契约文档中残留；`docs/00-overview/README.md` 中历史总览残留按本审查规则忽略。

## 十三、自审结果

当前已完成以下一致性检查：

- Client Markdown 与 Client OpenAPI 端点集合一致。
- Agent Markdown 与 Agent OpenAPI 端点集合一致。
- 两份 Agent OpenAPI 完全一致。
- OpenAPI JSON 均可解析。
- HTTP `200` / `201` / `202` 成功响应的 body `code` 与 `message` 已对齐。
- 多选题答案字段已从单一 `string` 修正为 `string | string[]`。
- 非选择题 `options` 已统一为空数组 `[]`。
- Markdown 中声明为 `null` 的主要响应字段已在 Client OpenAPI 中补充 `nullable: true`。
- 非归档正式文档中已清理 `slides`、`exercise_count`、Agent 侧 `profile/initialize`、`X-API-Key`、`internal_key`、`内部密钥` 等残留。
