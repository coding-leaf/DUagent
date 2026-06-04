# Agent Service Goals

## 模块目标

- 对 Backend 提供稳定的 `/agent/v1/*` AI 计算接口。
- 负责 LLM 调用、AgentScope 编排、Qdrant 课程知识与用户记忆检索。
- 负责 tutoring SSE、structured output、resources 多阶段生成、memory compression 等 AI 侧能力。

## 明确不做

- 不直接写 Backend SQL。
- 不承担用户、课程、任务状态、Webhook 结果的业务持久化真值职责。
- 不修改 Backend 对前端暴露的业务契约语义。
- 不把 AgentScope 内部对象泄漏到 API schema。

## 对外边界

- Backend 传入结构化当前态，Agent Service 返回结构化结果或 SSE。
- Qdrant 检索由 Agent Service 自行完成。
- Webhook 只用于把异步结果回传 Backend，不直接写数据库。

## 当前阶段目标

- 维持已完成主链稳定，不为“更像智能体”而继续无收益大改。
- 优先收口联调质量、可观测性、运行稳定性和文档入口。
- 保持 deterministic / 统计型接口的 structured output + 规则保护。

## 成功标准

- OpenAPI 与 schema 不漂移。
- agent/workflow、memory、tools 边界清晰。
- 模块文档能快速回答：做什么、不做什么、当前临时方案是什么。
