# Backend Goals

## 模块目标

- 对前端提供稳定的业务 API。
- 负责用户、课程、对话、资源、测验、画像、评估、学习路径等 SQL 当前态持久化。
- 负责 `AsyncTask` 创建、状态维护和查询。
- 负责接收 Agent Webhook，并校验后写入 SQL。
- 负责把 Agent SSE/JSON 能力适配成前端可用协议。

## 明确不做

- 不实现 `agent_service/` 内部 LLM、AgentScope、Qdrant RAG、提示词和智能体编排。
- 不直接访问 Qdrant。
- 不通过 Python 模块导入方式调用 `agent_service`。
- 不把未在正式契约中声明的字段、状态、枚举暴露给前端。

## 对外边界

- Backend 只通过 HTTP 调用 Agent Service。
- Backend 负责校验 Agent 返回结果并决定是否、如何落库。
- Agent Service 不直接写 Backend SQL。

## 当前阶段目标

- 保持已联调主链稳定：profile/evaluation/learning-path refresh、resources + webhook、tutoring/chat、quiz 主链。
- 收口系统级缺口，而不是继续扩大接口面。
- 优先解决运行可靠性、临时方案治理和文档收口。

## 成功标准

- 前端可见 API 契约稳定，无漂移。
- SQL 当前态、任务状态和 Webhook 落库闭环清晰。
- 模块文档可以快速回答：做什么、不做什么、当前临时方案是什么。
