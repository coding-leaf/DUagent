# WORKFLOW.md

## 文件用途

本文件只记录 `backend/` 当前阶段状态、最近验证和下一步。

- 模块目标与边界：看 `docs/goals.md`
- 术语：看 `docs/glossary.md`
- 关键决策：看 `docs/decisions.md`
- 临时实现与已知限制：看 `docs/temporary-implementation.md`
- 正式契约：看根目录 `docs/10-client-api/*` 与 `docs/20-agent-api/*`

不要把以下内容继续堆回本文件：

- 长篇架构导读
- glossary 术语解释
- decisions 决策正文
- 历史实施设计与讨论过程
- 可独立存在的联调操作手册

## 接口实现状态维护约定

本文件开头固定维护一份“接口实现情况”总览，用于区分：

- `真实完成`：已接真实鉴权/SQL/Agent 调用，主链路可用
- `半完成`：有真实逻辑，但仍存在硬编码、弱校验、伪异步或部分占位
- `占位/规则完成`：仅完成返回结构、路由或基础协议，业务未真实落地
- `文档声明不做`：当前 v1 契约明确不提供

维护规则：

1. 只要修改了某个接口实现，必须同步更新本文件中的该接口“最近状态”。
2. 更新时至少补充：
   - 修改日期
   - 接口路径
   - 最新状态
   - 一句说明本次变更影响
3. 如果接口从 `占位/规则完成` 提升到 `半完成` 或 `真实完成`，必须直接修改总览表，不允许只写在“最近验证”。
4. 如果接口行为回退、发现假实现、联调不闭环，也必须回写状态，不允许只保留乐观描述。

## Backend 工作流程

后续在 `backend/` 内继续修接口，默认按下面流程执行：

1. 先做上下文检查：
   - `pwd`
   - `git status --short`
   - `curl -s http://127.0.0.1:8002/agent/v1/health`
   - 必要时重读 `AGENTS.md`、相关 OpenAPI 和本文件
2. 先审契约，再动代码：
   - 先核对 `docs/10-client-api` 与 `docs/20-agent-api`
   - 明确本次是否涉及 Client API / Agent API 契约变化
   - 若存在参数、字段、枚举、同步/异步语义变化，先停下说明，不直接落代码
3. 每次只推进一个接口或一个明确子能力：
   - 先找真实问题
   - 先收口最危险的 bug，再谈状态提升
   - 默认不一次性铺开多条链路
4. 修改前先写 4 件事并等待确认：
   - 问题分析
   - 计划修改的文件
   - 修改方案
   - 可能影响的功能
5. 修改时遵循最小闭环原则：
   - 优先 minimal diff
   - 先补异常路径和状态闭环
   - 只要引入锁、事务或异步任务，必须同时检查成功路径、失败路径、幂等和提交时序
6. 刷新类接口统一按稳定化模板审查：
   - task 创建后是否会因后续异常丢失
   - 锁是否在 `commit()` 之后才释放
   - 锁超时 / Agent 失败 / DB 异常是否都会落 `task failed`
   - GET 读取是否使用 `.order_by(...).first()` 避免多行 500
7. 改完立即同步本文件：
   - 更新总览状态
   - 更新“最近状态变更”
   - 若还有残留问题，写进“已知问题”，不要只写乐观结论
8. 最后做最小验证并提交：
   - 至少跑语法检查、导入检查或相关接口测试
   - 只提交本轮相关文件
   - 最终回复必须说明：当前完成、修改文件、测试结果、契约是否漂移、下一步建议
9. 需要及时通过git 存档 commit内容为简短的修改总结
10. 根据workflow内容,更新相关记录文件

## 当前接口实现情况总览

更新日期：`2026-06-02`

### 真实完成

- `GET /api/v1/auth/captcha`
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/users/me`
- `PUT /api/v1/users/me`
- `GET /api/v1/courses`
- `POST /api/v1/courses`
- `POST /api/v1/courses/join`
- `GET /api/v1/admin/users`
- `PUT /api/v1/admin/users/{user_id}`
- `DELETE /api/v1/admin/users/{user_id}`
- `GET /api/v1/admin/logs/agent`
- `GET /api/v1/admin/logs/operations`
- `GET /api/v1/tasks/{task_id}`
- `GET /api/v1/tutoring/conversations`
- `GET /api/v1/tutoring/conversations/{conversation_id}`
- `POST /api/v1/profile/refresh`
- `POST /api/v1/evaluation/refresh`
- `POST /api/v1/learning-path/refresh`

### 半完成

- `GET /api/v1/evaluation`
- `POST /api/v1/profile/initialize`
- `GET /api/v1/profile`
- `GET /api/v1/learning-path`
- `GET /api/v1/quiz/questions`
- `POST /api/v1/quiz/generate`
- `GET /api/v1/quiz/history`
- `GET /api/v1/resources`
- `POST /api/v1/resources/generate`
- `POST /api/v1/tutoring/chat`
- `GET /api/v1/teaching/classes/{class_id}/students`
- `GET /api/v1/teaching/classes/{class_id}/students/{student_id}`
- `GET /api/v1/teaching/classes/{class_id}/students/{student_id}/learning`
- `POST /api/v1/webhooks/agent`
- `GET /api/v1/learning-path/nodes/{node_id}/resources`
- `POST /api/v1/quiz/submit`
- `GET /api/v1/quiz/result`

### 占位/规则完成

_（当前无占位接口）_

### 文档声明不做

- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/send-reset-code`

## 最近状态变更

- `2026-06-04` `CourseKnowledgeGraph 智能生成与导入临时过渡工具`
  - **新增**：`tools/generate_knowledge_graph.py` — 作为单课程过渡方案的临时 KG 冷启动工具，不在 backend 内作为正式产品功能，仅供开发和运维阶段本地提取生成。
  - **新增**：`tests/test_generate_kg.py` — 针对该工具的数据去重、必填项过滤和悬空边剔除等核心校验逻辑进行单元测试。
  - **验证**：运行 `pytest tests/test_generate_kg.py`，所有 4 个测试点全部通过（4/4 passed）。
  - **契约**：无 HTTP API 契约变化（Client API 漂移：否，Agent API 漂移：否）。存在架构边界放宽/临时例外（在工具脚本内部直接实现了一次性 Prompt 和 LLM 接口调用）。

- `2026-06-03` `CourseKnowledgeGraph 手工导入工具`
  - **新增**：`tools/import_knowledge_graph.py` — CLI upsert 工具
  - **验证**：导入 7 nodes/6 edges → learning-path/refresh → task completed → GET 返回 7 nodes/6 edges（从降级到真实通过）
  - **契约**：无 HTTP API 变化

- `2026-06-03` `quiz diagnosis 语义收口（方向 A）`
  - **问题**：Agent LLM 诊断写入 `diagnosis_json` 后无任何 API 消费，Agent 计算被浪费
  - **修复**：`GET /quiz/result` 已开始部分消费 Agent 诊断；当前保持课程级 SQL `summary` / `weak_points`，`suggestions` 优先使用最新有效 Agent 诊断（带类型校验、空列表回退、空白字符串过滤、向旧 session 回溯）
  - **契约**：Client API 字段名/类型均不变；`error_pattern` 不暴露

- `2026-06-03` `quiz wrong_points 查询修复`
  - **问题**：`_assemble_quiz_generate_payload` 中"最近错题知识点"查询只从 `QuizQuestion` 表直接取点，无 `QuizAnswer.is_correct=False` 过滤、无 `user_id` 限定，传给 Agent 的不是真实错题
  - **修复**：改为显式 JOIN `QuizSession` + `QuizAnswer` + `QuizQuestion`，限定 `user_id` + `is_correct=False`，按 `QuizAnswer.create_time DESC` 去重取最近 10 个
  - **契约**：`wrong_points` 输出结构不变，Client/Agent API 均未漂移

- `2026-06-03` `refresh 孤儿任务启动恢复`
  - **问题**：profile/evaluation/learning-path refresh 使用 `asyncio.create_task`，进程重启后协程丢失，task 永久卡在 `status="processing"`
  - **修复**：`app/main.py` lifespan 中新增 `_recover_orphaned_refresh_tasks()`，启动时将 refresh 三类 processing 任务标记 `failed`（`error_code=None`, `error_message="服务重启，后台任务丢失"`）
  - **验证**：插入 3 个 processing refresh 任务 → 运行恢复 → 3 个变为 failed, 1 个 resource_generation 未受影响
  - **契约**：不新增对外 API，`error_code` 保持 null

- `2026-06-03` `resources/generate + quiz/generate Agent 失败分支 task 可见性修复`
  - **问题**：Agent 同步调用失败时，`db.flush()` 不提交事务。`get_db` 在 HTTP 202 发出后才 `session.commit()`，导致客户端立即轮询 `GET /tasks/{id}` 时 task 行对其他事务不可见（MySQL REPEATABLE READ）
  - **修复**：`resources.py` 和 `quiz.py` 的 `except AgentServiceError` 分支中 `db.flush()` → `db.commit()`，确保 202 返回前 task 已稳定落库
  - **验证**：停 Agent → POST resources/generate → ORM 直查确认 `status=failed, error_code=agent_error` 在 202 返回时已可见
  - **契约**：Client API / Agent API 均未变化

- `2026-06-03` `tutoring knowledge_points 字段解析修复 + 联调验证`
  - **问题**：`tutoring/chat` SSE 解析中 `parsed.get("points", [])` 只匹配 `points` key，但 Agent 实际发送 `{"type":"knowledge_points","knowledge_points":[{...}]}`，导致 knowledge_points 静默丢失
  - **修复**：`app/api/v1/tutoring.py` event_generator 中扩大多 key 兼容：`points` → `knowledge_points` → `data`，并新增 `done.knowledge_points_used` 兜底捕获
  - **联调验证**（课程 `758aeff588e84044`，学生 `stu_1446b359@test.com`）：
    - SSE 事件解析 ✅（Agent key=`knowledge_points`，兼容命中）
    - GET conversation API ✅（3 个 knowledge_points 返回）
    - SQL messages.knowledge_points ✅（3 个知识点 JSON 已落库）
    - Agent/Client API 契约均未漂移
  - **结论**：knowledge_points 从「代码已修」升级为「联调已验证」

- `2026-06-03` `联调 v1 验收完成`
  - 根目录 `联调v1结果.md` 已记录 7 条链路的完整验收结果：服务健康、账号课程、profile/evaluation refresh、resources + webhook、tutoring/chat RAG、quiz/generate + submit + result、learning-path/refresh
  - `tutoring/chat` 首次拿到完整 RAG 证据：SSE 正常、课程知识命中、教材特征内容、Mermaid 图表、知识点和建议完整
  - `learning-path/refresh` 经手工灌入 `CourseKnowledgeGraph` 后复跑为 `7 nodes / 6 edges`，证明 learning-path 链路成立；当前缺口不再是接口本身，而是 KG 数据准备链路
  - 联调主链已从“逐接口打通”转入“收口系统级能力缺口”：KG 数据准备、refresh 任务持久化恢复、quiz 个性化质量与 diagnosis 语义、新课程 Qdrant 知识灌入流程
- `2026-06-04` `文档状态校正`
  - **修正**：移除已修复的 tutoring `knowledge_points` / resources-generate 失败可见性缺陷表述
  - **修正**：同步 quiz diagnosis、KG 导入工具、测试路径到当前真实状态
  - **目标**：避免后续 AI/人工继续基于过期状态重复修复
- `2026-06-02` `沉淀完整联调验收手册`
  - 重写 `../docs/30-dev-guide/联调测试指导.md`，将原有接口清单式说明升级为阶段化联调验收手册
  - 明确服务启动顺序、健康检查、环境一致性、AI 执行规则、通过/降级可用/未通过判定标准
  - 明确 `tutoring/chat` 是核心 RAG 验收链路，`learning-path/refresh` 非 RAG 且依赖 `CourseKnowledgeGraph`
  - 后续联调默认先按该手册执行，再把验收结果回写本文件
- `2026-06-02` `RAG embeddings 400 修复 + resources 复验通过`
  - Agent 侧 commit 2febbe6 修复 SiliconFlow `BAAI/bge-m3` embeddings 400（根因：AgentScope `OpenAITextEmbedding` 发送不支持的 `dimensions` 参数；通过 `EMBEDDING_REQUEST_DIMENSIONS_ENABLED=false` 解决）
  - Qdrant `course_knowledge_v1_1024` collection 已灌入 760 chunks 课程知识数据
  - 复验 resources/generate：Agent 日志确认 embeddings 200、Qdrant query 200、RAG 检索参与生成；resource 质量从泛化模板提升为课程知识驱动的具体内容
- `2026-06-01 ~ 2026-06-02` `主链打通与稳定化`
  - 已完成 refresh 真异步化、resources + webhook 闭环、quiz 收口、锁与 webhook 集成测试、联调启动手册补充等主干工作
  - 细节以 git 提交记录和最近验证为准，不再在此处逐条展开历史流水账

## 当前联调结论

- Backend -> Agent Service 主干已打通，且不是仅“能调接口”，而是已完成任务状态闭环、SQL 落库闭环和真实业务验收。
- 联调 v1 已完成 7 条目标链路验收：
  - 服务健康
  - 账号课程
  - `POST /api/v1/profile/refresh` + `POST /api/v1/evaluation/refresh`
  - `POST /api/v1/resources/generate` + `POST /api/v1/webhooks/agent`
  - `POST /api/v1/tutoring/chat`
  - `POST /api/v1/quiz/generate` + `POST /api/v1/quiz/submit` + `GET /api/v1/quiz/result`
  - `POST /api/v1/learning-path/refresh`
- 当前可以确认：
  - refresh 三条链路在运行态下真异步语义成立
  - resources + webhook 真实闭环成立
  - tutoring/chat 已验证真实 RAG 命中，不再只是“可回答”
  - quiz 主链功能成立，评分、结果统计、后台 diagnosis 写入都可用
  - learning-path 链路成立，但前提是课程已有 `CourseKnowledgeGraph`
- 当前阶段的主要问题已不再是“接口是否能通”，而是“系统级数据准备和生产可靠性是否收口”。
- 当前阶段优先级决策：
  - 优先继续收口 Backend-Agent 联调本身的问题
  - 优先修复会影响 Agent 输入质量、Agent 输出消费、任务状态闭环和系统级可靠性的缺陷
  - 前端展示层相关问题（例如教师看板展示质量）可在前端真实接入对应页面时再集中修复

## Agent Service 接口对接状态

| Backend 接口 | Agent 路径 | 类型 | 状态 | 备注 |
|-------------|-----------|------|------|------|
| `POST /api/v1/profile/refresh` | `/agent/v1/profile/generate` | 真异步 | ✅ | 202 + task_id；后台 asyncio.create_task 执行 Agent 调用 + 写库 |
| `POST /api/v1/tutoring/chat` | `/agent/v1/tutoring/chat` | SSE 代理 | ✅ | SSE 流透传，累积 chunk 后保存 |
| `POST /api/v1/resources/generate` | `/agent/v1/resources/generate` | 异步+Webhook | ✅ | task_id + webhook_url 传入 |
| `POST /api/v1/quiz/generate` | `/agent/v1/assessment/generate-questions` | 异步 | ✅ | 生成后写 quiz_questions |
| `POST /api/v1/evaluation/refresh` | `/agent/v1/evaluation/generate` | 真异步 | ✅ | 202 + task_id；后台 asyncio.create_task 执行 Agent 调用 + 写库 |
| `POST /api/v1/learning-path/refresh` | `/agent/v1/learning-path/generate` | 真异步 | ✅ | 202 + task_id；后台 asyncio.create_task 执行 Agent 调用 + 写库 |
| `POST /api/v1/webhooks/agent` | — | Webhook | ⚠️ | 见已知问题 |

## 未完成项

以下项目不是“链路没通”，而是联调通过后暴露出的系统级能力缺口或待收口问题。

### 优先级高

- `CourseKnowledgeGraph` 数据准备与冷启动链路
  - `learning-path/refresh` 接口本身已验证成立，但课程若无 KG 则只能返回空 `nodes/edges`。
  - 已提供手工导入工具 `tools/import_knowledge_graph.py` 与智能提取导入工具 `tools/generate_knowledge_graph.py`。
  - 后者可直接加载大纲并通过 LLM 智能生成合规的 nodes 和 edges，自动去重并清洗悬空边，已成功降低了课程图谱准备的难度，满足单课程图谱的数据冷启动需要。
- refresh 真异步任务持久化/恢复
  - `POST /api/v1/profile/refresh`、`POST /api/v1/evaluation/refresh`、`POST /api/v1/learning-path/refresh` 当前在返回 `202` 后使用进程内 `asyncio.create_task`
  - 当前已补“启动时将孤儿 refresh task 标记 failed”的止血方案
  - 仍缺真正的持久化执行/恢复机制；worker reload / 进程重启 / crash 后不会恢复继续执行
- `POST /api/v1/quiz/submit` + `GET /api/v1/quiz/result`
  - 功能主链已成立，MySQL 集成测试已补齐（71/71 通过）
  - 仍未收口的是个性化质量与语义统一：
    - 没有足够 profile/evaluation/context 时，题目会退化为泛化题
    - diagnosis 当前是折中融合：课程级 SQL `summary/weak_points` + Agent `suggestions`
  - 需与前端/Agent 侧对齐后单独收口
- `POST /api/v1/webhooks/agent`
  - failed 回调当前已验证 `error_code present`
  - 若继续收口，可补精确 `error_code` 值校验与更多异常负例
- KG 自动生成能力
  - 当前不是没有 learning-path，而是没有正式的 KG 生成/导入机制
  - 若后续希望新课程自动具备 learning-path，需要补：
    - 手工导入工具
    - 或 Agent 生成候选 KG + Backend 落库
  - 当前这块尚未开始实现

### 优先级中

- RAG 检索 embeddings 400 排查与修复
  - ✅ Agent 侧已修复（`agent_service` commit 2febbe6）：根因为 AgentScope `OpenAITextEmbedding` 对 SiliconFlow `BAAI/bge-m3` 发送了不支持的 `dimensions` 参数；通过 `EMBEDDING_REQUEST_DIMENSIONS_ENABLED=false` 默认不传 `dimensions` 解决
  - ✅ 课程知识已灌入 Qdrant（`course_knowledge_v1_1024`，760 chunks from 数据结构教材），实测 `search_course_knowledge` limit=3 命中 3 hits
  - ✅ embeddings 400 和空 collection 问题已不再是当前联调阻塞；RAG 检索链路已验证可用
  - 后续：验证 tutoring/chat 等场景下 RAG 命中率与检索质量
- `POST /api/v1/profile/initialize`
  - 当前可用，但仍属于半完成
  - 若后续继续稳定化，可补更多重复提交和异常路径测试
- `POST /api/v1/resources/generate` + `POST /api/v1/webhooks/agent`
  - 当前主链路和鉴权/幂等已覆盖
  - 若后续继续加强，可补更高并发 webhook 场景验证
- 新课程的 Qdrant 知识灌入流程
  - 老课程已验证真实 RAG 可用，但新课程若要复现课程级 RAG，仍需单独灌入课程知识
  - 当前属于“能力存在，但流程未产品化”

## 已知问题

1. **Webhook 鉴权需要两端同步配置**（`webhooks.py` + Agent Service `resources.py`）：Backend 已实现 `X-Webhook-Secret` 校验，Agent Service 的 `_post_json_payload` 已同步发送该 header。两端需配置一致的 `WEBHOOK_SECRET` 环境变量，未配时鉴权自动跳过（向后兼容）。
2. **`GET /learning-path/nodes/{id}/resources` chapter_materials 依赖 KG 预置数据**：`chapter_materials` 从 `CourseKnowledgeGraph.nodes` JSON 中提取 `chapter` 字段并匹配 `Resource.chapter`。若 KG 未预置完整数据，该字段将返回空数组（不影响其他字段）。
3. **`POST /quiz/submit` 诊断链路已后台异步化，GET /quiz/result 为折中融合语义**：后台 `_run_diagnosis_background` 通过 `asyncio.create_task` 调用 Agent `/assessment/evaluate`，使用 UPDATE 写入 `QuizSession.diagnosis_json`（无 DB 读依赖，消除竞态）。当前 `GET /quiz/result` 保持课程级 SQL `summary/weak_points`，只部分消费 Agent `suggestions`；这条链路已不再“完全未消费 Agent 诊断”，但语义尚未最终收口。
4. **refresh 真异步任务当前不具备持久执行能力**：`POST /api/v1/profile/refresh`、`POST /api/v1/evaluation/refresh`、`POST /api/v1/learning-path/refresh` 在返回 `202` 后使用进程内 `asyncio.create_task` 执行 Agent 调用和写库。当前已补启动恢复：服务启动时将残留 refresh `processing` 任务标记为 `failed`；但尚未解决任务持久化执行/恢复问题。
5. ~~**RAG 检索当前可能整体失效**~~（已修复，2026-06-02）：Agent 侧 embeddings 400 已修复（commit 2febbe6），课程知识已灌入 Qdrant（course `758aeff588e84044`，760 chunks，检索命中 3/3）。RAG 不再整体失效，resources/generate 真实链路验收已确认日志中不再出现 embeddings 400 或 Qdrant collection 404。
6. **`learning-path/refresh` 依赖 KG 数据准备已具备临时工具支持**：当前已通过手工写入与 `generate_knowledge_graph.py` 智能命令行提取导入工具验证 learning-path 拓扑结构闭环。新课程若不准备 KG 图谱，则 learning-path 仍会空结果，但现在可通过 CLI 工具快速完成图谱抽取与数据灌入。
7. **新课程课程知识灌入流程未产品化**：已验证课程 `758aeff588e84044` 的 RAG 可用，但新课程若要复现课程级 tutoring/resources/quiz 上下文，仍需额外灌入 Qdrant 数据。

## 当前待修复缺陷

- **高优先级：teaching 学习看板存在假数据/占位数据**
  - `GET /api/v1/teaching/classes/{class_id}/students/{student_id}/learning` 仍存在硬编码/空数组字段，不能作为真实学习看板结果使用
  - 该问题更偏前端接入阶段的数据真实性缺口，不属于当前 Backend-Agent 主链阻塞
- **中优先级：`GET /api/v1/quiz/questions` 可能创建空 `QuizSession` 污染历史**
  - 刷新或重复打开题目页可能产生空会话，影响 `/quiz/history` 与统计数据质量
  - 当前不阻断主链，但应在 quiz 页面真实接入前收口

## 延期处理问题

- **资源列表接口课程权限校验不足**
  - 当前审查意见：任意已登录用户若知道 `course_id`，可能读取该课程资源
  - 当前阶段先记录为延期处理，不作为联调 v1 阻塞项；后续进入权限治理阶段时再统一修复
- **任务查询接口对教师放权过宽**
  - 当前审查意见：任意教师可能查询任意 `resource_generation` 任务，不仅限任务归属人或课程归属范围
  - 当前阶段先记录为延期处理，不作为联调 v1 阻塞项；后续进入权限治理阶段时再统一修复

## 联调命令

```bash
# Agent Service（agent_service/ 目录，终端 1）
./.venv/bin/uvicorn agent_service.main:app --host 127.0.0.1 --port 8002

# Backend（backend/ 目录，终端 2）
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload

# 验证 Agent Service 健康
curl http://127.0.0.1:8002/agent/v1/health

# Backend 联调测试
python tests/test_agent_integration.py

# Backend 冒烟测试
python tests/test_api.py

# Agent Service 全量回归
cd agent_service && ./.venv/bin/pytest -q
```

## 测试文件

| 文件 | 用途 | 覆盖范围 |
|------|------|---------|
| `tests/test_agent_integration.py` | Agent 联调集成测试 | 6 个 Agent 接口 + Webhook + 权限 + 降级 |
| `tests/test_api.py` | 全量冒烟测试 | 所有端点的基础可用性 |
| `tests/test_refresh_async.py` | refresh 真异步链路集成测试 | profile / evaluation / learning-path 的 202、processing、completed、DB 写入、Agent error |
| `tests/test_resources_async.py` | resources 异步链路集成测试 | generate 202 + task_type、webhook completed/failed、幂等、鉴权、task_type mismatch |
| `tests/test_lock_async.py` | refresh 锁相关集成测试 | 三条 refresh 的 lock_timeout + profile/refresh 锁竞争一致性 |
| `tests/test_quiz_async.py` | quiz 链路集成测试 | submit 评分 + 落库、多选题评分、非法 question_id 容错、Agent payload 对齐、空答案、404、后台诊断写入/失败、result 聚合 + 统计 + trend 排序 + diagnosis 字段形状检查 |

## 最近验证

- `2026-06-02`
  - `python tests/test_quiz_async.py`
  - 结果：`71/71` 通过
  - 覆盖：
    - `POST /api/v1/quiz/submit`
    - `GET /api/v1/quiz/result`
  - 断言：
    - submit 评分 + QuizAnswer 落库 + 多选题评分（完整/排序无关/不完整/全错）
    - 非法 question_id → `is_correct=False` + 无 FK 违规 + 仍计入 total_count + 不进入 Agent 诊断 payload
    - 空答案 → 200 score=0、无效 quiz_id → 404
    - 后台 Agent 诊断写入 + Agent 失败容错 + 后台任务触发验证
    - result 统计计算（total_attempts/avg_score/avg_time）+ score_trend 排序 + diagnosis 字段形状检查（无额外键；语义仍待确认）
- `2026-06-02`
  - `python tests/test_refresh_async.py`
  - 结果：`24/24` 通过
  - 覆盖：
    - `POST /api/v1/profile/refresh`
    - `POST /api/v1/evaluation/refresh`
    - `POST /api/v1/learning-path/refresh`
  - 断言：
    - `202 + task_id`
    - immediate poll = `processing`
    - 最终 `completed`
    - SQL 写入成功
    - Agent error -> `failed + error_code`
- `2026-06-02`
  - `python tests/test_resources_async.py`
  - 结果：`15/15` 通过
  - 覆盖：
    - `POST /api/v1/resources/generate`
    - `POST /api/v1/webhooks/agent`
  - 断言：
    - `202 + task_id + task_type=resource_generation`
    - webhook completed -> `200` + task `completed` + resources 写入
    - webhook failed -> `200` + task `failed` + `error_code present`
    - 重复 completed 回调不重复写入 resources
    - `X-Webhook-Secret` 正确时业务正常处理，错误时 `401`
    - `task_type mismatch -> 400`
- `2026-06-02`
  - `python tests/test_lock_async.py`
  - 结果：`16/16` 通过
  - 覆盖：
    - `POST /api/v1/profile/refresh`
    - `POST /api/v1/evaluation/refresh`
    - `POST /api/v1/learning-path/refresh`
  - 断言：
    - 真实 MySQL `GET_LOCK` 超时路径 -> `task failed + error_code=lock_timeout`
    - `profile/refresh` 并发两个请求 -> 两个 task 都终态，且只保留一条 `is_deleted = false` 活跃记录

## 下一步建议

1. 优先推进新课程 Qdrant 知识灌入流程工程化，先把样板课程能力变成可复制流程。
2. 为 refresh 三条真异步链路设计最小可行的持久化执行/恢复策略，避免运行中可用但重启后不可靠。
3. 统一收口 KG 工具与 RAG 工具的工程化规范，而不是重复证明 learning-path 主链是否可用。
4. 前端真实接入相关页面前，再集中处理 teaching 看板数据真实性、空 `QuizSession` 等展示侧问题。
