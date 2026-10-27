# Implementation Plan: Agent事件适配器容错重构与数据库窗口函数降维兼容

## Execution Checklist

- [x] **Step 1: Agent 协议适配器未知事件防御重构**
  - 在 `agent_service_v2/src/agent_service_v2/runtime/protocol_adapter.py` 中补充缺失的 AgentScope 事件类导入（`HintBlockEvent`, `DataBlockStartEvent`, `DataBlockEndEvent` 等）。
  - 重构事件路由逻辑：未知/未显式定义事件安全丢弃（返回 `None`）并记录 `logger.debug`，不再抛出 `WORKFLOW_FAILED`。
  - 在 `agent_service_v2/tests/` 补充针对 `HintBlockEvent` 及未知事件安全吸收的单元测试。
  - 验证命令: `uv run --project agent_service_v2 pytest agent_service_v2/tests/test_protocol_adapter.py`

- [x] **Step 2: Backend 窗口函数解耦与跨数据库方言兼容**
  - 修改 `backend/app/services/tutoring_service.py` 中的 `list_conversations`，消除 `ROW_NUMBER() OVER` 窗口函数，采用时间排序 + 内存映射获取会话最新消息。
  - 修改 `backend/app/services/class_insights_query.py` 中的 `get_class_insights`，消除 `ROW_NUMBER() OVER` 窗口函数，采用时间排序 + 内存映射获取学员最新学习路径。
  - 验证命令: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_tutoring_service.py` 及真实本地 MySQL 5.7 查询验证。

- [x] **Step 3: 前端会话错误边界防御与 JoinCourseDialog 单测**
  - 验证并保留 `frontend/src/components/JoinCourseDialog.jsx` 针对服务端错误信息的透传支持。
  - 验证并运行 `JoinCourseDialog.test.jsx`。
  - 验证命令: `npm --prefix frontend test -- JoinCourseDialog`

- [x] **Step 4: 部署脚本 MySQL 版本检测与透明化提示**
  - 在 `deploy_prod.sh` 的 `ensure_core_infrastructure` 复用分支中，增加对当前运行的 MySQL 版本的探测。
  - 如果检测到 MySQL 5.7，打印清晰提示信息。
  - 验证命令: `bash deploy_prod.sh check`

- [x] **Step 5: 真实环境链路端到端验证**
  - 验证实际调用 Agent Service 触发带 `HintBlockEvent` 的问答流，确认 SSE 连接持续不断且成功返回文字。
  - 验证通过学生账号调用 `/api/v1/tutoring/conversations` 成功返回 200。
  - 运行全量质检门禁: `python -X utf8 check_all.py`。
