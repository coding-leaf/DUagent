# 多语言代码题、后端与 AgentScope 审计

审计日期：2026-07-11  
范围：`backend/app/`、`agent_service_v2/src/agent_service_v2/`，以及与代码题入口直接相关的前端代码。

## 结论

本轮多语言修复采用的架构合理：产品层只支持 `c`、`cpp`、`python`、`java`、`go`、`javascript` 六个规范值；输入别名在 Backend 入口归一化；Judge0 ID 映射集中在同一服务模块；Agent 和前端只消费规范值。这避免了模型、前端、Backend 和判题机各自维护一份语言表。

AgentScope v2 运行时判断为**框架原生使用，非伪框架实现**。实际执行由 `Agent.reply_stream()` 负责；`Toolkit`、`ToolGroup`、`FunctionTool`、`LocalWorkspace`、`Middleware` 都来自 AgentScope。项目自行维护的是 EDU SSE 协议适配层，这属于产品边界适配，不是重写 AgentScope 的推理/工具循环。

本次用户看到的 CORS 文案不是根因。根因是运行库表缺少
`user_personalized_resources.code_problem_id`；该 SQL 迁移已执行并验证查询恢复。FastAPI CORS 配置已显式包含 `http://localhost:5173`，符合带鉴权请求必须使用明确 Origin 白名单的约束。

## 本轮已修复并验证

| 问题 | 修复 | 验证 |
| --- | --- | --- |
| `C++` 等语言别名触发 Backend 422，Agent 错报为服务不可用 | 统一别名归一、六语言白名单和 Judge0 映射；422 映射为 `backend_validation_error` / `rejected` | Backend 36 passed；Agent 21 passed；前端 9 passed |
| 工具卡显示“完成”，内容却说后端不可用 | 前端把业务失败状态映射为错误，不再由传输层 `success` 覆盖 | `chatStreamEvents` 单测覆盖 |
| 个性化资源页请求 500 后被浏览器表现成 CORS | 执行已存在的数据库迁移并以真实 ASGI 查询验证 | 真实列表查询 HTTP 200 |

## 可借鉴的实现方向

1. **固定产品语言集，运行时适配器隔离 Judge0。** Judge0 的 Languages API 与 `language_id` 是运行时能力；产品支持范围应由教学、模板、测试覆盖和安全策略决定，不能等同于判题机全部能力。将运行时 ID 收敛在 `code_language.py`，未来升级 Judge0 只改适配器与契约测试。
2. **边界处做归一化，内部只存规范值。** `C++`、`Python3`、`Node.js` 等别名只允许出现在输入边界，数据库、工具返回和前端文件名判断均使用规范值。这是防止跨服务字段漂移的反腐层（Anti-Corruption Layer）用法。
3. **区分传输成功和业务成功。** AgentScope 的工具事件可正常结束，但业务返回 `rejected`、`degraded` 或 `unavailable`；协议适配和 UI 必须保留两层状态，不能把工具事件 `success` 当作业务成功。
4. **保留协议适配器，避免前端耦合框架事件。** `EDUProtocolAdapter` 将 AgentScope 事件翻译为稳定 EDU SSE 事件，隔离了 AgentScope 升级影响。这是本项目最值得保留的 Adapter 模式。

Judge0 官方文档说明其可以支持 60+ 种语言、以 `language_id` 创建提交，并提供运行时语言查询；这支持“运行时能力与产品白名单分离”的决定。[Judge0 API Docs](https://ce.judge0.com/docs)

## 质量审查发现

### P1：个性化资源列表仍未展示已经保存的代码题（待契约确认）

- 证据：`backend/app/services/code_problem_service.py:174` 会写入 `code_problem_id`，但 `backend/app/api/v1/personalized_resources.py:26` 只批量加载资源、题目和任务，未查询或返回代码题；`frontend/src/pages/PersonalizedResources.jsx:141` 仅渲染资源卡或题目分组。
- 影响：迁移后列表不再 500，但 AI 生成并成功保存的代码题不会在“个性化资源”页可见，用户只能在生成它的聊天流内操作。
- 建议：增加稳定的 `code_problem` 摘要字段（`id`、`title`、`language`、`difficulty`），并增加一个只复用现有 `CodeSandboxCard` 的受保护详情路由。需要同时更新 Client API 文档、Backend 路由测试和前端页面测试。
- 未直接实施原因：这是 Client API 响应字段与页面导航的新契约，不在已确认的“六语言扩展”范围内；按项目契约纪律需要单独确认。

### P1：`personalized_resources` 路由是胖路由，违反 Router -> Service 分层

- 证据：`backend/app/api/v1/personalized_resources.py` 共 346 行；`list_personalized_resources` 122 行（第 26 行）、`generate_personalized_resource` 153 行（第 151 行）。二者直接组织多表 SQL、业务分支、Agent 请求和写入。
- 风险：资源、题目、代码题的三类聚合会继续向路由堆叠，新增任何资源类型都容易产生 N+1、遗漏字段或事务不一致。
- 建议：提取 `personalized_resource_service`，按“查询聚合”“同步题目生成”“异步资源生成”三个单一职责函数拆分；Router 只保留鉴权、请求校验、调用服务和响应包装。

### P2：Backend 仍有多个超过 300 行的高耦合文件

| 文件 | 行数 | 优先级 |
| --- | ---: | --- |
| `backend/app/services/catalog_quiz_generation_service.py` | 443 | P2 |
| `backend/app/services/kg_generation.py` | 422 | P2 |
| `backend/app/api/v1/quiz.py` | 420 | P2 |
| `backend/app/services/tutoring_service.py` | 413 | P2 |
| `backend/app/services/evaluation_service.py` | 378 | P2 |
| `backend/app/services/catalog_resource_generation_service.py` | 370 | P2 |
| `backend/app/api/v1/personalized_resources.py` | 346 | P1 |

还发现 `student_report_query.execute`（184 行）、`catalog_ingestion_service.run_catalog_ingestion_background`（179 行）等长函数。它们不应在本轮做机械切分；应按一次业务流程一个小型重构计划推进，并在切分前补充行为测试。

### P2：AgentScope 运行时整体内聚，但会话编排函数偏长

- 正向证据：`agents/workbench_factory.py` 创建 AgentScope `Agent` / `Toolkit`；`tools/workbench_toolkit.py` 按业务分组 `ToolGroup`；`session/workbench_session.py:185` 调用 `agent.reply_stream()`；工作区通过 `LocalWorkspace` 隔离。
- 待改进：`session/workbench_session.py:_run_agent` 为 115 行，同时承担事件遍历、调试日志、权限失败、协议发布、运行状态和内容安全复核。建议分为 `_publish_debug_event`、`_publish_protocol_events`、`_handle_terminal_event`，不改变事件语义。
- 协议适配器 `runtime/protocol_adapter.py:_map_event` 为 65 行，但其职责是有限的事件映射，当前不属于伪框架。新增 AgentScope 事件类型时必须先加映射测试，避免静默变成 `unsupported_agentscope_event`。
- 测试缺口：已有工厂和适配器单测，但缺少一条使用 AgentScope 事件序列的 `WorkbenchSession` 端到端会话测试，覆盖“业务失败工具结果 -> EDU error -> run 状态”的完整链路。

## 未发现的问题

- Agent Service 没有直接导入 Backend ORM 或写 MySQL；其学习数据和代码题保存均通过 Backend HTTP client。
- Backend 没有导入 Agent Service Python 模块或直接访问 Qdrant。
- 本轮新增语言映射没有引入新依赖、没有扩散 Judge0 ID 到前端或提示词。
- AgentScope 没有手写 ReAct `while` 循环或自行解析模型工具调用；框架负责推理与工具执行。

## 后续顺序

1. 若确认 Client API 契约扩展，优先补齐“个性化资源页可见并打开代码题”，并为列表聚合提取服务。
2. 为 `WorkbenchSession` 增加事件序列集成测试，再小步拆分 `_run_agent`。
3. 分别为 `personalized_resources.py`、`quiz.py` 写独立重构规格，不建议一次性拆所有大文件。
