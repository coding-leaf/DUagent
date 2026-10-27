# PRD: Agent事件适配器容错重构与数据库窗口函数降维兼容

## Goal
从架构根源解决聊天流因框架未知事件被误断的问题（消除 `unsupported_agentscope_event` 误杀），重构数据访问层中非必要的 MySQL 8.0+ 窗口函数依赖以保障跨版本（MySQL 5.7 / 8.0 / 测试 SQLite）完全兼容，并增加数据库版本感知防护。

## Requirements

### 1. Agent 协议适配器事件防御模型重构 (P0)
- **文件**: `agent_service_v2/src/agent_service_v2/runtime/protocol_adapter.py`
- **问题**: 原适配器在遇到未显式白名单化的 AgentScope 事件时，直接返回 `EduEventType.WORKFLOW_FAILED`，导致大模型在输出中间推理、工具调用提示（如 `HintBlockEvent`、`DataBlockStartEvent`）时整场会话被截断报错。
- **要求**:
  - 明确划分事件处理边界：
    1. **致命中断事件**: 仅针对明确的框架致命错误（如 `ExceedMaxItersEvent`）返回 `EduEventType.WORKFLOW_FAILED`。
    2. **核心业务流式事件**: 精准翻译为前端协议（`text_delta`, `tool_call`, `workflow_completed` 等）。
    3. **良性中间生命周期事件**: 显式包含 `HintBlockEvent`, `DataBlockStartEvent`, `DataBlockEndEvent`, `ThinkingBlockDeltaEvent`, `ThinkingBlockStartEvent`, `ThinkingBlockEndEvent`, `ModelCallStartEvent`, `ModelCallEndEvent` 等，安全返回 `None`。
    4. **未知/扩展事件防御**: 未识别的框架扩展事件记录 `logger.debug` 并安全返回 `None`（丢弃/略过），绝不让任何良性或新增事件阻断工作流。
  - 为 `protocol_adapter.py` 补充单元测试，验证各类正常、忽略与未知事件的流转行为。

### 2. 数据库窗口函数降维解耦与跨版本兼容 (P0)
- **文件**: `backend/app/services/tutoring_service.py`, `backend/app/services/class_insights_query.py`
- **问题**: 原代码在 `list_conversations` 和 `get_class_insights` 中使用了 MySQL 8.0 引入的 `ROW_NUMBER() OVER (PARTITION BY ...)`，在 MySQL 5.7 环境下报 1064 语法错误，导致会话列表与班级学情报 500。
- **要求**:
  - `tutoring_service.py` (`list_conversations`):
    - 将窗口函数获取最新消息逻辑改造为标准 SQL 排序 + 应用层单次内存聚合（或标准子查询），兼容 MySQL 5.7、8.0 以及 SQLite。
  - `class_insights_query.py` (`get_class_insights`):
    - 将窗口函数获取学员最新学习路径逻辑改造为标准 SQL 排序 + 应用层映射，消除语法限制。
  - 编写/补充针对 MySQL 5.7 语法的无窗口函数回归单元测试。

### 3. 前端流式错误优雅降级与会话防御 (P1)
- **文件**: `frontend/src/context/ChatContext.jsx`, `frontend/src/components/JoinCourseDialog.jsx`
- **要求**:
  - 当会话历史为空或未创建会话时，`regenerate` 与 `editMessage` 应做边界保护，避免发送非法 `conversation_id: null` 请求。
  - 保留并验证此前针对 `JoinCourseDialog.jsx` 提取真实后端错误详情的优化及单测。

### 4. 部署与环境检查的数据库版本感知 (P1)
- **文件**: `deploy_prod.sh`
- **要求**:
  - 在复用宿主机 MySQL 端口时，自动探测实际数据库版本（如 `SELECT VERSION()`）。
  - 若检测到 MySQL < 8.0（如 5.7），输出明确的黄色友好提示，告知核心服务已做向下兼容，但建议切换至官方推荐的 Docker MySQL 8.0 镜像，提升透明度。

## Acceptance Criteria
- [ ] `agent_service_v2` 处理 `HintBlockEvent` 及未知事件时，不再返回 `workflow_failed`，聊天流正常输出。
- [ ] `backend` 针对会话列表 `list_conversations` 的请求在 MySQL 5.7 实例上成功返回 200，无 SQL 1064 报错。
- [ ] `backend` 针对班级学情 `get_class_insights` 的请求成功执行，无 `ROW_NUMBER() OVER` 语法报错。
- [ ] `deploy_prod.sh` 检测并如实提示数据库版本。
- [ ] 全仓门禁 `python check_all.py`（含前后端 lint、build、pytest）全部通过。
