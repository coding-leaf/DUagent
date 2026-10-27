# PRD: 基于 AgentScope 原生编排重构多智能体生成并修复数据库死锁

## 1. 目标与背景 (Goal & Context)
- **痛点一（致命死锁）**：个性化资源生成在落库阶段，当 `knowledge_point` 缺省使用用户长文本目标（如 170+ 字符）时，超出 MySQL `resources.knowledge_point`（`varchar(100)`）限制，抛出 `(pymysql.err.DataError) (1406, "Data too long")` 异常。由于缺乏异常闭环回调机制，后端 `async_tasks` 永久卡在 `processing`，前端卡片无休止转圈假死。
- **痛点二（手写伪多智能体轮子）**：现有实现绕开了 AgentScope 官方原生编排体系，手写了单线程 `for resource_type in resource_types:` 循环，多份资源生成线性累加耗时达到 90~150 秒，缺乏真正的并发与智能体协作。
- **核心目标**：全面废弃手写过程式轮子，迁移至 **AgentScope 原生 `TeamPipeline`** 编排架构；利用框架原生的 Leader-Member 动态并发分派将耗时压缩至单份资源水准；彻底修复数据库字段溢出与任务状态机未闭环导致的假死死锁。

---

## 2. 需求清单 (Requirements)

### 2.1 数据库死锁与任务状态机闭环修复 (P0 - 紧急修复)
- **数据契约防御**：
  - 在 `agent_service_v2` 与 `backend` 的落库层（`PersonalizedResourceGenerationService.publish` 及相关服务），对 `knowledge_point` 严格进行格式化与长度防御性截断（`[:100]`），禁止超长字符串引发 1406 致命异常。
  - 同样对 `title`（`varchar(200)`）等有限长字段进行边界防护。
- **全生命周期状态闭环**：
  - 在 `agent_service_v2` 增加统一的任务失败回调通知机制（无论是在起草、校验、审核还是落库阶段发生任何未捕获异常，均可靠通知 Backend 将对应的 `task_id` 更新为 `status='failed'` 并记录具体原因）。
  - 后端提供统一的失败标记端点或在发布/草案异常时自动触发 `AsyncTask` 失败更新。
  - 前端增加生成超时熔断（例如轮询超 180s 自动转为超时失败提示），杜绝永久转圈。

### 2.2 拥抱 AgentScope 原生 `TeamPipeline` 编排重构 (P0 - 架构重构)
- **全面废弃手写循环**：
  - 移除 `PersonalizedResourceGenerationRunner` 中手写的单线程 `for` 循环与手动重试胶水代码。
- **接入 AgentScope 原生 `TeamPipeline`**：
  - **Leader Agent（教学规划主管）**：作为 Leader，分析学生学习目标与偏好，一次性调用官方 `_TeamAssign` 向多个 Member 分派生成任务。
  - **Member Agents（领域专家智能体）**：
    - `LessonWorkerAgent`（课件与精讲专家）
    - `MindmapWorkerAgent`（思维导图专家）
    - `QuizWorkerAgent`（巩固习题专家）
    - `ReadingWorkerAgent`（拓展阅读专家）
  - **原生并发调度**：利用 AgentScope `TeamPipeline` 底层对同轮分配的 `asyncio.gather` 并发能力，同时并发执行多个资源的 RAG 检索与大模型生成，总耗时大幅压缩。
  - **标准 AgentScope `Toolkit` 挂载**：
    - 将 RAG 知识检索、确定性规则校验、草案与落库封装为标准 `FunctionTool` 挂载到对应 Agent 上；
    - 借助 AgentScope 框架原生对工具异常的容错机制（`ToolResultState.ERROR`），实现异常在框架内的自愈与安全终结，不再裸奔抛错。

### 2.3 事件流与前端体验提升 (P1)
- 打通 `TeamPipeline.reply_stream` 与现有 `EventStreamBroadcaster`，使 Leader 与 Member 的分派、思考与工具调用实时以 SSE 流式吐出，前端可感知具体生成步骤。

---

## 3. 验收标准 (Acceptance Criteria)
- [ ] 针对 170+ 字符的长目标请求，系统生成并发布资源时 100% 成功，不再出现 MySQL 1406 `Data too long for column 'knowledge_point'` 异常。
- [ ] 若发生任何网络中断或不可抗力错误，Backend `async_tasks` 能够在 5 秒内被正确置为 `failed` 并展示错误摘要，前端卡片坚决不再出现无休止转圈死锁。
- [ ] 多资源生成（如同时勾选课件、导图与练习）完全通过 AgentScope 原生 `TeamPipeline` 并发调度，生成耗时显著降低（相比原串行耗时减少 50% 以上）。
- [ ] 自动化测试验证：
  - `agent_service_v2` 单元测试通过；
  - `backend` 单元测试通过；
  - 全仓门禁 `python -X utf8 check_all.py` 7 项检查全绿。
