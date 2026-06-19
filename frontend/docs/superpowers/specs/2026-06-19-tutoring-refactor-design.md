# Backend Tutoring Route Refactor Design

## 背景

`backend/app/api/v1/tutoring.py` 当前约 591 行，是阶段二架构治理中的下一个胖路由目标。该文件同时承担：

1. Client API 路由、鉴权依赖和参数校验；
2. `chat`、`edit`、`regenerate` 三种会话写入流程；
3. Conversation 与 Message 查询、更新及事务提交；
4. Backend → Agent tutoring payload 组装；
5. Agent SSE 解析、Client SSE 适配和回复内容累积；
6. 流结束后的独立数据库会话落库；
7. 会话列表、历史详情及软删除；
8. 面向前端的响应字典组装。

这使路由层同时依赖 SQLAlchemy 查询细节、Agent API 字段、SSE 事件协议和 Client API DTO。当前会话列表还会为每条会话分别查询消息数和最后一条消息，形成 `2N+2` 查询。

本次重构复用已落地的 profile 分层样板，但 tutoring 具有长生命周期 SSE、双重 API 边界和流后落库，因此增加专属 Payload Builder 与 Stream Adapter，不把流式协议继续留在 Router 中。

## 目标

1. 将 `backend/app/api/v1/tutoring.py` 收敛为 Router：只负责依赖注入、请求级校验、HTTP 错误翻译、响应包装和 `EventSourceResponse` 创建。
2. 将会话与消息生命周期下沉到 `TutoringService`。
3. 将 Backend → Agent 请求白名单组装下沉到 `TutoringPayloadBuilder`。
4. 将 Agent SSE → Client SSE 的协议适配、内容累积和流后落库下沉到 `TutoringStreamAdapter`。
5. 将会话列表与历史详情 DTO 下沉到 `tutoring_presenters.py`。
6. 消除会话列表的 `2N+2` 查询，在保持排序和字段语义不变的前提下改为批量或聚合查询。
7. 保持 Client API、Agent API、数据库结构和 HTTP 状态码不变；仅实施本 Spec 明确列出的 SSE 可靠性修复。
8. 通过特征测试和分层单测保证重构不引入功能退化，相关新增或调整代码覆盖率不低于 80%。

## 非目标

- 不修改 `agent_service` 的 tutoring Agent、Prompt、检索或 SSE 生成逻辑。
- 不修改前端 `chatService`、`ChatContext` 或 UI 行为。
- 不清理前端 mock；该问题属于独立的数据真实性治理任务。
- 不新增 Conversation 或 Message 数据库字段，不引入消息状态迁移。
- 不改变 `chat`、`edit`、`regenerate` 的对外请求语义。
- 不新增 Repository 接口体系、通用 Pipeline 框架、事件总线或消息队列。
- 不在本次重构中调整全局 `AgentClient` 的 timeout、重试、熔断或连接池策略。
- 不修改 `.env`、依赖版本、密钥、volume 数据或用户数据。

## 当前行为基线

重构必须保持以下运行行为：

- `scope=course` 且缺少 `course_id` 返回现有 400 错误体。
- edit/regenerate 缺少 `conversation_id`、会话不存在或缺少用户消息时保持现有错误语义。
- 会话只能由所属用户读取、修改或删除。
- 新 chat 创建 user 消息与 assistant 占位；edit 更新最后一条 user 消息；regenerate 保留 user 消息并清空最后一条 assistant 消息。
- 当前轮 user 消息和 assistant 占位不进入发送给 Agent 的 `recent_messages`。
- 发送给 Agent 的画像使用字段白名单，不包含姓名、邮箱、学号、用户名等身份字段。
- Agent `done` 事件中的 `conversation_id` 与 `message_id` 必须被 Backend 的真实 ID 覆盖。
- Agent 不可用时，若尚未转发 done，则以现有 SSE `done` 错误事件结束流。
- 历史消息在数据库时间精度不足时仍稳定保持 user 在 assistant 之前。
- 删除采用 Conversation 软删除，不物理删除 Message。

### 已批准的内部可靠性修复

以下两项修复不新增 API 字段或状态码，但会改善异常情况下的持久化结果，因此不伪装成纯代码搬迁：

- SSE data 行跨多个上游字节块时，先缓冲为完整行再解析，避免合法事件因网络分片丢失累积。
- 客户端断开或生成器取消时，在 `finally` 路径持久化已经完整接收的 assistant 内容，避免用户刷新历史后丢失已展示片段。
- 会话列表的 last message 与历史详情统一采用稳定顺序：`create_time`、`update_time`、role rank（user 在 assistant 前）；取最后一条时使用该顺序的逆序，消除同秒写入时数据库返回顺序不确定。

### 既有契约文档漂移

当前前端与 Backend 代码均使用 `action=chat|edit|regenerate`，但历史 Client OpenAPI 的 `ChatRequest` 尚未声明 `action`。本次重构以当前运行代码为行为真相，必须保留该字段和三种 action，不借重构删除或改名。由于本次不改变调用方式，该问题登记为既有文档漂移，不在本次修改历史 OpenAPI。

### 范围外安全债务

course scope 当前只要求提供 `course_id`，没有验证当前用户是否已加入或有权访问该课程。补充课程权限校验会新增 403 行为，属于可见契约变化，不能混入本次“契约不变”的分层重构。应另行产出安全修复 Spec 并确认契约后实施。

## 目标文件结构

### `backend/app/api/v1/tutoring.py`

职责：

- 声明 tutoring 路由；
- 注入当前用户、数据库会话和查询参数；
- 执行请求级、HTTP 级校验；
- 调用 Service、Builder 与 Stream Adapter；
- 将领域异常翻译为现有 HTTP 错误体；
- 返回统一 REST 包装或 `EventSourceResponse`。

禁止：

- 直接编写 Conversation/Message SQL；
- 直接解析 Agent SSE JSON；
- 在闭包中维护流式累积状态；
- 直接组装会话列表或历史详情 DTO。

### `backend/app/services/tutoring_service.py`

职责：会话与消息生命周期、归属校验及事务编排。

建议接口：

- `prepare_chat_turn(user_id, request) -> PreparedTutoringTurn`
- `prepare_edit_turn(user_id, request) -> PreparedTutoringTurn`
- `prepare_regenerate_turn(user_id, request) -> PreparedTutoringTurn`
- `list_conversations(user_id, scope, course_id, page, page_size)`
- `get_conversation(user_id, conversation_id)`
- `delete_conversation(user_id, conversation_id)`

`PreparedTutoringTurn` 是内部 DTO，至少包含：

- `conversation_id`
- `user_message_id`
- `assistant_message_id`
- `message`
- `scope`
- `course_id`

Service 使用注入的 `AsyncSession`，不依赖 FastAPI，不抛 `HTTPException`。事务提交仍由明确的应用层边界控制；外部 Agent I/O 开始前必须完成短事务提交。

### `backend/app/services/tutoring_payload_builder.py`

职责：白名单组装 Agent `TutoringChatRequest` payload。

输入：

- 已准备完成的 turn；
- 当前用户 ID；
- 需要从历史中排除的当前轮 message IDs；
- SQLAlchemy `AsyncSession`。

输出必须保持当前 Agent API 字段：

- `user_id`
- `scope`
- `course_id`（course scope）
- `catalog_id`（可解析时）
- `message`
- `conversation_id`
- `active_kg_nodes`
- `user_profile`
- `conversation_summary`（存在时）
- `recent_messages`

隐私约束：采用显式白名单，不允许把 User ORM、UserProfile ORM 或任意 `__dict__` 直接序列化进 Agent 请求。

### `backend/app/services/tutoring_stream_adapter.py`

职责：适配 Agent SSE 与 Client SSE，并负责流后持久化。

核心行为：

- 调用既有 `agent_client.stream_sse()`，禁止新建独立 httpx 访问路径；
- 从任意字节分片中解析完整 SSE data 行；
- 原样转发未知或不可解析事件，但不将其计入结构化累积；
- 累积 `chunk`、`diagram`、`knowledge_points`；
- 兼容现有 `points`、`knowledge_points`、`data` 读取优先级；
- 在 `done` 事件中写入 Backend conversation/message ID；
- 捕获 AgentServiceError 并保持当前降级事件语义；
- 流结束后使用 `async_session_factory` 创建独立 session，更新 assistant 内容及 Conversation 更新时间。

Stream Adapter 不依赖 FastAPI Router，但可以输出 `EventSourceResponse` 可消费的事件字典异步迭代器。

### `backend/app/services/tutoring_presenters.py`

职责：无状态 Client API DTO 转换。

建议函数：

- `conversation_item(conversation, message_count, last_message) -> dict`
- `conversation_detail(conversation, messages) -> dict`
- `message_item(message) -> dict`

Presenter 不访问数据库、不调用 Agent、不提交事务。

## 数据流与事务边界

### Chat/Edit/Regenerate

1. Router 完成 Pydantic 解析和请求级 scope 校验。
2. Router 根据 action 调用 `TutoringService` 的显式 preparation 方法。
3. Service 校验会话归属并创建或更新 user/assistant 消息。
4. 当前短事务 flush、commit，确保 ID 对后续独立 session 可见。
5. Payload Builder 在已提交状态上查询画像、KG、摘要和历史消息。
6. Payload 构建完成后显式结束 Builder 产生的只读事务，确保请求级 session 在开始 Agent I/O 前释放连接。
7. Router 创建 Stream Adapter 的异步事件迭代器并交给 `EventSourceResponse`。
8. Stream Adapter 调用 Agent、转换并转发事件，不持有请求级数据库 session 或连接。
9. 流结束后以独立 session 持久化已累积的 assistant 内容并更新时间。

硬约束：Agent 网络 I/O 期间不得持有请求级数据库事务或连接，而不只是“不得持有未提交写事务”。实现必须通过显式 transaction 结束和注入 session 的状态测试证明该约束。

### 会话查询

会话列表禁止把本页会话的全部历史消息加载到 Python 内存。采用有界数据库查询：

1. Conversation 总数查询；
2. Conversation 分页查询；
3. 按本页 conversation IDs 分组的 Message count 聚合查询；
4. 使用 MySQL 8 窗口函数 `row_number() over (partition by conversation_id order by create_time desc, update_time desc, role_rank desc)` 获取每个会话最多一条 last message，其中 user 的 role rank 为 0、assistant 为 1。

查询次数固定为 4 次，返回数据规模为 O(页大小)，不随单个会话历史消息总量增长。历史详情与列表使用同一排序定义；特征测试必须锁定同秒 user/assistant 时列表 last message 为 assistant。

## SSE 生命周期与异常处理

### 正常完成

- 转发全部 Agent 可见事件；
- Backend 覆盖 done 中的 conversation/message ID；
- 完整累积并写回 assistant 消息；
- 更新 Conversation `update_time`。

### AgentServiceError

- 若尚未转发 done，发送现有 `done` 错误事件；
- 不改变 HTTP 状态，因为 SSE 响应可能已经开始；
- 按当前行为保存已经收到的内容；
- 记录结构化异常，包含 conversation/message ID，不记录完整消息正文。

### 非法或未知 SSE 数据

- 保持当前兼容原则：可转发的数据原样转发；
- JSON 解析失败的数据不参与正文、图表或知识点累积；
- 不新增前端协议字段表达内部解析错误。

### 客户端断开或生成器取消

- 取消上游 Agent 流，不继续无界读取；
- 在 `finally` 路径处理已经累积内容的落库；
- 不把客户端断开翻译成新的 Client API 事件。

这是本 Spec 明确批准的内部可靠性修复：当前实现的取消异常可能跳过生成器尾部落库；修复后，已经完整接收并转发的内容会进入历史记录。

### 持久化失败

- 记录结构化错误；
- 已开始的 SSE 流不追加未定义错误事件；
- 不吞掉测试环境中可观察的异常，具体日志与异常传播边界在实现计划中通过特征测试固定。

### 并发 edit/regenerate

Service 在短事务内使用 MySQL 行锁（例如对所属 Conversation 执行 `SELECT ... FOR UPDATE`）串行化同一会话的 edit/regenerate 准备过程，并在持锁后重新读取最后一组消息。锁只覆盖数据库读写和提交，不覆盖 Payload Builder 或 Agent 网络 I/O。

本次不新增数据库状态字段、分布式锁或新的冲突响应。若行锁方案无法在不改变现有 HTTP/SSE 行为的前提下保证一致性，则暂停相应实现并请求契约确认。

## 架构与设计模式选型

| 架构或模式 | 状态 | 理由 |
| --- | --- | --- |
| 分层架构 | 选用 | 采用 Router → Service/Builder/Adapter → DB/AgentClient，消除胖路由。 |
| Service Layer | 选用 | 集中会话生命周期、归属校验和事务编排。 |
| Adapter | 选用 | Backend 必须在 Agent SSE 与 Client SSE 之间转换 ID 和兼容事件字段。 |
| Presenter / DTO | 选用 | 隔离 ORM 与 Client API 输出，避免响应字典散落。 |
| 依赖注入 | 选用 | AsyncSession 与 AgentClient 可替换，便于隔离数据库和 Agent 测试。 |
| Clean Architecture 依赖方向 | 局部选用 | Service、Builder、Adapter 不依赖 Router/FastAPI 异常；不建设完整端口体系。 |
| Repository | 不选用完整抽象 | 仅 Conversation/Message 两个核心实体，额外接口层收益不足；查询统一收口到 Service。 |
| 悲观并发控制 | 局部选用 | edit/regenerate 在短事务内对 Conversation 加 MySQL 行锁，避免同一会话并发覆盖；禁止锁区间内调用 Agent。 |
| 策略模式 | 不选用独立策略类 | 三个 action 稳定且数量有限，三个显式 Service 方法更直观。 |
| 命令模式 | 不选用 | 无撤销、重放或命令队列需求。 |
| 状态模式 | 不选用 | 当前模型无消息流状态字段，采用会扩大数据库及契约范围。 |
| 管道—过滤器 | 仅采用分步思想 | Payload 组装按来源拆函数，但不引入通用 Pipeline 框架。 |
| 观察者/事件驱动 | 保持既有 SSE | SSE 已是实时事件通道，无需增加内部 EventBus。 |
| 中间件/责任链 | 不选用 | SSE 协议转换属于 tutoring 业务边界，不是全局横切逻辑。 |
| CQRS | 不选用 | 当前读写规模不足以支撑独立模型和基础设施成本。 |
| 微服务/API Gateway | 不选用 | Backend ↔ Agent HTTP 边界已存在，本次只治理 Backend 内部分层。 |

## 组件与依赖判断

本次不新增第三方依赖。复用：

- FastAPI 依赖注入和路由；
- `sse-starlette.EventSourceResponse`；
- SQLAlchemy 2.x async session 与查询；
- Pydantic 现有请求 Schema；
- `app.services.agent_client.agent_client`；
- `app.db.session.async_session_factory`；
- `app.services.course_knowledge_graphs.get_active_knowledge_graph`；
- profile/catalog 已落地的 Service 与 Presenter 组织经验。

引入新的 SSE parser、Repository 框架、工作流引擎或状态机库会增加依赖与迁移成本，且不能直接解决当前职责边界问题，因此不采用。

## 测试设计

### 特征测试

重构前先锁定：

- scope 校验和错误体；
- chat/edit/regenerate 的消息变化；
- conversation 所有权；
- Agent payload 字段；
- done ID 覆盖；
- Agent 不可用时的 SSE 降级；
- 同秒 user/assistant 排序；
- 删除后的可见性。

### Payload Builder 单测

- 用户隐私字段不会进入 payload；
- course/global scope 的画像默认值；
- catalog 与 Active KG 节点映射；
- conversation summary；
- 最近 20 条消息的稳定排序；
- 当前轮 message IDs 排除。

### Stream Adapter 单测

- 多个事件位于同一字节块；
- 单个 JSON/SSE 行跨多个字节块；
- chunk、diagram、knowledge_points 累积；
- knowledge point 兼容字段优先级；
- done ID 覆盖；
- 非法 JSON 和未知事件；
- AgentServiceError；
- 客户端取消后的上游结束与部分内容落库；
- 流后独立 session 更新。

### Service 单测与集成测试

- 三种 action 的消息准备；
- 会话不存在与非所有者访问；
- 无最后 user/assistant 消息的边界；
- 软删除；
- 同一会话并发 edit/regenerate 的行锁串行化；
- 会话列表筛选、分页、message_count 和 last_message；
- 会话列表固定 4 次查询，且不会加载本页会话的全部历史 Message；
- Payload Builder 完成后请求级 session 不再处于 transaction 中。

纯转换逻辑使用无数据库单测；涉及 MySQL 一致性或 SQL 行为的测试使用 MySQL 测试库，不用 SQLite 结果代替生产行为。相关新增或调整代码覆盖率目标不低于 80%。

## 分阶段实施约束

为遵守 Backend 单批最多 5 个文件的规则，实施计划必须拆分阶段，例如：

1. 特征测试与 Service 会话生命周期；
2. Payload Builder 与隐私/上下文测试迁移；
3. Stream Adapter 与 SSE 测试；
4. Presenter、查询优化与 Router 收口；
5. 全链路回归、覆盖率、WORKFLOW 与 requirements coverage 更新。

每阶段遵循 RED → GREEN → IMPROVE，并只提交该阶段文件。实施前由 writing-plans 技能把阶段细化为可执行任务。

## 契约判断

- Client API 契约：**不改变**；保留代码中既有但历史 OpenAPI 漏记的 `action` 字段。
- Agent API 契约：**不改变**。
- 数据库 Schema：**不改变**。
- 前端 UI 行为：**不改变**。

实现前后均需核对 Client API 与 Agent API 的路径、参数、响应字段、SSE 事件和 nullable 语义。若实施中发现并发一致性无法在现有契约内保证，必须停止相应改动并向用户申请契约确认，不得先扩展契约。

## 验收标准

1. Router 不再包含 Conversation/Message SQL、payload 组装或 SSE JSON 解析。
2. Agent 调用期间不持有请求级数据库事务或连接。
3. 会话列表固定 4 次有界查询，不加载本页会话的全部历史消息。
4. Client API 与 Agent API 契约测试通过。
5. tutoring 隐私、SSE、排序、CRUD 与 action 回归测试通过。
6. 相关新增或调整代码覆盖率不低于 80%。
7. Backend 相关测试通过，并完成语法检查。
8. `WORKFLOW.md` 记录分层改动、测试结果和“无接口漂移”。
9. `docs/requirements-coverage.md` 更新 tutoring 接口实现记录。
