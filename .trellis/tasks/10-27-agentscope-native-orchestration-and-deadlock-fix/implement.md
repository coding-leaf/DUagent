# Implementation Plan: 基于 AgentScope 原生编排重构多智能体生成并修复数据库死锁

## Execution Checklist

- [ ] **Step 1: 数据库死锁与数据契约防御加固 (Backend)**
  - 在 `backend/app/services/personalized_resource_generation_service.py` 的 `publish` 函数中，对 `knowledge_point`（截断至 100 字符）、`title`（截断至 200 字符）实施安全防护。
  - 在 `backend/app/api/v1/internal_personalized_resources.py` 中增加任务失败通知端点 `POST /internal/personalized-resources/tasks/{task_id}/fail`，支持可靠更新 `AsyncTask` 为 `failed`。
  - 编写单测覆盖超长文本写入与任务失败通知接口。
  - 验证命令: `pytest backend/tests/test_personalized_resource_generation_service.py backend/tests/test_internal_personalized_resources.py`

- [ ] **Step 2: 构建 AgentScope 原生 Member 智能体与工具箱 (Agent Service)**
  - 基于 `agentscope.agent.Agent` 与 `Toolkit` 构建专门的领域生成智能体（Lesson, Mindmap, Quiz, Reading）。
  - 将 RAG 检索、格式校验、草案保存与发布封装为标准 `FunctionTool`。
  - 验证命令: `uv run --project agent_service_v2 pytest agent_service_v2/tests/test_leader_team.py`

- [ ] **Step 3: 使用 AgentScope TeamPipeline 重构多智能体生成管道 (Agent Service)**
  - 在 `agent_service_v2/src/agent_service_v2/generators/personalized_resource_flow.py` 中，使用 AgentScope 原生 `TeamPipeline` 替换手写的 `PersonalizedResourceGenerationRunner` 过程式循环。
  - Leader 通过 `_TeamAssign` 并发分派生成任务，利用框架底层的 `asyncio.gather` 并发调度多 Member。
  - 接入框架原生 `reply_stream`，并在异常时可靠回调 Backend 失败端点。
  - 验证命令: `uv run --project agent_service_v2 pytest agent_service_v2/tests/test_personalized_resource_flow.py`

- [ ] **Step 4: 前端任务假死熔断与超时兜底 (Frontend)**
  - 在 `frontend/src/components/personalized/PersonalizedResourceCard.jsx` 及对应 Hook 中，加入生成超时状态判断（超过 180s 提示生成超时并提供删除/重新生成操作）。
  - 验证命令: `npm --prefix frontend test -- PersonalizedResourceCard`

- [ ] **Step 5: 全仓质量检查与门禁验证**
  - 运行全量代码风格检查与单元测试: `python -X utf8 check_all.py`
