# 执行方案与步骤清单

## Phase 1: 依赖更新与环境就绪
- [x] 修改 `agent_service_v2/pyproject.toml`，升级 AgentScope 至 `2.0.10` 并切换精准 extras 组合。
- [x] 运行 `uv sync` 构建虚拟环境，验证安装成功且无构建编译警告。

## Phase 2: 独立事件流广播器实现
- [x] 创建 `agent_service_v2/src/agent_service_v2/runtime/event_broadcaster.py`。
- [x] 封装从 AgentScope 事件流到 Starlette `ServerSentEvent` 的统一转换器。
- [x] 编写轻量单元测试验证事件映射与序列化契约。

## Phase 3: 工作台 ReAct 主核构建与旧回环拔除
- [x] 重构 `workbench_factory.py`，使之直接创建基于 AgentScope 2.0.10 的 `ReActAgent`。
- [x] 移除 `team_app.py`、`leader_team.py`、`team/runtime_client.py` 等虚假 ASGI 回环代码。
- [x] 将 `/api/v2/chat/stream` 路由直接对接 `EventStreamBroadcaster` 与 `WorkbenchReActAgent`。

## Phase 4: 全链路验证与规范沉淀
- [x] 运行 `test_backend_learning_client.py` 及相关测试。
- [x] 验证后端调用 Agent 对话接口的连通性。
- [x] 更新 `.trellis/spec/agent_service_v2/` 对应文档，固化架构规范。
