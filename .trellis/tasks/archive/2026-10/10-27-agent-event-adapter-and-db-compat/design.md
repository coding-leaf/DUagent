# Technical Design: Agent事件适配器容错重构与数据库窗口函数降维兼容

## 1. Architecture Overview

本设计针对两个系统边界进行根因加固：
1. **Agent 服务事件总线边界** (`agent_service_v2`):
   将脆弱的“黑名单阻断机制”演进为“白名单透传 + 未知事件良性容错机制”，切断框架中间事件导致流式会话非预期失败的隐患。
2. **数据持久层与 ORM 查询边界** (`backend`):
   消除对 MySQL 8.0 特定窗口函数 `ROW_NUMBER() OVER` 的硬编码依赖，采用标准化聚合模式，保证跨数据库方言（MySQL 5.7, 8.0, PostgreSQL, SQLite）的一致性与高移植性。

---

## 2. Component Design & Changes

### 2.1 Agent Protocol Adapter (`protocol_adapter.py`)
```
AgentScope Framework Events
          │
          ├──> [ExceedMaxItersEvent] ───────────────> WORKFLOW_FAILED
          │
          ├──> [TextBlockDelta, ToolCall, etc.] ───> 业务 EduEvent (text_delta, etc.)
          │
          ├──> [HintBlock, DataBlock, Lifecycle] ───> None (安全吸收，不中断流)
          │
          └──> [Any Unknown/New Framework Event] ───> logger.debug & return None (安全放行)
```

- **实现细节**:
  1. 在 `agentscope.event` 导入列表中增加 `HintBlockEvent`, `DataBlockStartEvent`, `DataBlockEndEvent`。
  2. 在 `EDUProtocolAdapter.adapt(self, event: EventBase)` 中：
     - 若命中核心业务事件，转换为对应 `EduEvent`。
     - 若命中已知无须推给前端展示的内部生命周期/数据块/Hint 事件，返回 `None`。
     - 若命中未识别的事件类，调用 `logger.debug("Unhandled AgentScope event %s received; dropping safely", event.__class__.__name__)` 并返回 `None`，**绝不返回 `WORKFLOW_FAILED`**。

### 2.2 Database Query Refactor (`tutoring_service.py` & `class_insights_query.py`)

#### A. 会话最新消息获取 (`tutoring_service.py`)
- 原方案：使用 MySQL 8.0 的 `ROW_NUMBER() OVER (PARTITION BY messages.conversation_id ORDER BY ...)`。
- 新方案：
  在已查得当前页 20 个 `conversation_ids` 的前提下，执行：
  ```python
  role_rank = case((Message.role == "user", 0), else_=1)
  stmt = (
      select(Message)
      .where(
          Message.conversation_id.in_(conversation_ids),
          Message.is_deleted == False,
      )
      .order_by(
          Message.create_time.desc(),
          Message.update_time.desc(),
          role_rank.desc(),
      )
  )
  messages = (await self.db.execute(stmt)).scalars().all()
  last_by_conversation: dict[str, Message] = {}
  for msg in messages:
      if msg.conversation_id not in last_by_conversation:
          last_by_conversation[msg.conversation_id] = msg
  ```
  - **性能与兼容性分析**:
    - 单页会话数最多 20 条，即使包含全部消息，SQL 仅需走已建立的 `(conversation_id, is_deleted)` 索引按时间逆序检索。
    - 在 Python 内存中单次 O(N) 遍历即可构建出各会话最新的一条消息。
    - 执行速度更快，且 100% 兼容 MySQL 5.7、8.0 及 SQLite。

#### B. 班级学情最新学习路径获取 (`class_insights_query.py`)
- 原方案：使用 `ROW_NUMBER() OVER (PARTITION BY LearningPath.user_id ORDER BY ...)`。
- 新方案：
  ```python
  stmt = (
      select(LearningPath)
      .where(
          LearningPath.course_id == class_id,
          LearningPath.user_id.in_(active_enrollments),
          LearningPath.is_deleted.is_(False),
      )
      .order_by(
          LearningPath.generated_at.desc(),
          LearningPath.create_time.desc(),
          LearningPath.id.desc(),
      )
  )
  paths = (await self.db.execute(stmt)).scalars().all()
  latest_paths_by_user = {}
  for path in paths:
      if path.user_id not in latest_paths_by_user:
          latest_paths_by_user[path.user_id] = path.nodes
  ```
  - 提取 `latest_paths_by_user.values()` 进行后续的 `progress` 统计。

### 2.3 部署脚本版本感知 (`deploy_prod.sh`)
- 当复用已有 MySQL 端口时，执行简单 SQL 查询：
  `SELECT VERSION()`
- 解析出主次版本号，并在日志中明确提示当前检测到的 MySQL 版本：
  - 如果发现版本为 5.7，打印友好兼容提示与 Docker 8.0 升级建议。

---

## 3. Rollback & Testing Strategy
- **回滚方案**: 若有任何逻辑异常，可通过 Git 撤销对应 service 文件修改。
- **测试验证**:
  1. `agent_service_v2/tests/test_protocol_adapter.py`: 单元测试验证各种 AgentScope 事件的适配行为。
  2. 真实调用 `http://127.0.0.1:8002/agent/v2/workbench/chat` 验证流式文字输出中 `HintBlockEvent` 不再截断。
  3. 执行 `backend/app/services/tutoring_service.py` 的 `list_conversations` 验证 MySQL 5.7 真实数据库下返回 200。
  4. 全仓自动化回归 `python check_all.py`。
