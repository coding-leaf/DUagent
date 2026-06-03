# WORKFLOW.md

## 文件用途

本文件只记录 `agent_service/` 当前阶段状态、最近验证和下一步。

- 模块目标与边界：看 `docs/goals.md`
- 术语：看 `docs/glossary.md`
- 关键决策：看 `docs/decisions.md`
- 临时实现与已知限制：看 `docs/temporary-implementation.md`
- 正式契约：看根目录 `docs/20-agent-api/*`

不要把以下内容继续堆回本文件：

- 长篇模块导读
- glossary 术语解释
- decisions 决策正文
- 历史实施计划与演进讨论
- 可独立存在的操作手册或调试手册

## 当前方向

- Agent 全链路架构升级主干已完成：适合 Agent/Workflow 的重点链路已具备 Agent 编排、质量门禁和 fallback。
- 后续进入工程化收尾：真实 LLM/RAG 联调验证、统一 trace/log、AgentScope Studio trace 评估和比赛 demo 验收。
- 不再为了“升级架构”继续大改已完成接口；新增改动必须服务于联调质量、可观测性、部署稳定性或明确缺陷修复。
- deterministic / 统计型接口继续以 structured output + 规则保护为主：`profile/generate`、`evaluation/generate`、`assessment/evaluate`、`learning-path/generate`、`memory/compress`。
- AgentScope 接入必须落在 `agents/`、`memory/`、`tools/`、`prompts/`、`core/` 边界内，不泄漏到 API/schema/Backend 契约。

## 全链路升级状态

- 已完成主干升级的 Agent 化链路：
  - `tutoring/chat`：StrategyAgent → ReAct/chat → ResponseCritic → rule-based fallback。
  - `assessment/generate-questions`：ReActAgent + RAG toolkit → AssessmentQualityGate → LLM/skeleton fallback。
  - `resources/generate`：Planner → AgentScope fanout ResourceAgents → ResourceCriticAgent → Aggregator → fallback。
- 已保持 deterministic / 统计型接口稳定：`profile/generate`、`evaluation/generate`、`assessment/evaluate`、`learning-path/generate`、`memory/compress`。
- 未完成的是生产化收尾，不是架构主干：真实模型效果验证、统一观测、Studio trace 和 demo 链路验收。

## 接口进度

| 接口 | 状态 | 当前实现要点 |
|------|------|--------------|
| `GET /agent/v1/health` | 已完成 | health 探针逻辑在 `agents/health.py`，API 层薄路由 |
| `POST /agent/v1/tutoring/chat` | StrategyAgent + ResponseCritic 首阶段已完成 | StrategyAgent 先选提示式引导 / 直接解释 / 追问澄清 / 例题讲解；ResponseCriticAgent 对 ReAct/chat 候选答复做质量门禁；降级链：Strategy 规则兜底 → ReAct → critic → chat JSON → critic → rule-based |
| `POST /agent/v1/profile/generate` | 已完成 | LLM enrichment + schema/枚举/范围保护 + 规则 fallback |
| `POST /agent/v1/evaluation/generate` | 已完成 | LLM enrichment + 表格/summary 保护 + 规则 fallback |
| `POST /agent/v1/assessment/evaluate` | 已完成 | 判分由规则确定；LLM 只增强解析、诊断和建议 |
| `POST /agent/v1/assessment/generate-questions` | AssessmentQualityGate 已合并 | ReAct + RAG toolkit → 统一质量门禁（基础质量 / 知识点 / 难度）→ LLM fallback → 质量门禁（知识点 / 难度）→ 骨架题 |
| `POST /agent/v1/learning-path/generate` | 已完成 | LLM 只在节点白名单内补全；失败回落规则路径 |
| `POST /agent/v1/resources/generate` | Multi-Agent Workflow + ResourceCritic 已完成 | Planner → AgentScope fanout ResourceAgents → ResourceCriticAgent → Aggregator；单资源局部 fallback |
| `POST /agent/v1/memory/compress` | 已完成 | LLM fact extraction + 规则 fallback；Qdrant 写入 best-effort |

## AgentScope 使用状态

- 已接入：ChatModel/Formatter、Embedding、ReActAgent、Toolkit/ToolResponse、InMemoryMemory、Reader/PDFReader、QdrantStore、fanout_pipeline。
- tutoring 已接入内部 StrategyAgent 和 ResponseCriticAgent，策略选择/质量判断失败时回落规则策略或继续降级，不改变 SSE / schemas。
- tutoring toolkit 已返回 AgentScope 合法 TextBlock：`{"type": "text", "text": "..."}`。
- assessment toolkit 已返回 AgentScope 合法 TextBlock；assessment 出题质量门禁已合并到 `agents/assessment_quality.py`，统一处理基础质量、知识点贴合度和难度贴合度。
- resources workflow 已通过 AgentScope `fanout_pipeline` 调度 Document/Mindmap/Reading/Code ResourceAgent，并新增 `ResourceCriticAgent` 单资源质量门禁。
- Qdrant 已支持 `QDRANT_URL` server 模式，未配置时回落 `QDRANT_PATH` local 模式；readiness 探针会真实请求 Qdrant collections。

## 当前注意事项

- 不修改 `../docs`，除非用户明确要求。
- 不改变 OpenAPI、schemas 或 Backend 调用契约。
- API 层保持薄路由，业务逻辑放入 `agents/`。
- 新增 AgentScope API 用法前必须查官方文档或用本地包 introspection 验证。
- 工作区存在用户/历史未提交改动，提交时只暂存本轮文件，不回滚无关改动。

## 最近验证

- `./.venv/bin/python -m agent_service.tools.ingest_knowledge /tmp/758aeff588e84044`：**通过**（将 `knowledge_base/data_structures` 以 Backend 课程 ID `758aeff588e84044` 摄入 Qdrant，写入 `course_knowledge_v1_1024`，760 chunks）
- `QdrantVectorStore().search_course_knowledge("758aeff588e84044", embedding("数据结构 顺序表 随机访问"), limit=3)`：**3 hits**（真实课程知识检索可用，collection count=760）
- `./.venv/bin/pytest tests/test_ai_providers.py tests/test_core_config.py -q`：**19 passed**（SiliconFlow embedding 请求维度开关；默认不向 embeddings API 发送有效 dimensions，保留 `EMBEDDING_DIMENSION` 给 Qdrant collection）
- `./.venv/bin/pytest -q`：**418 passed**（统一 agent_trace 日志后全量回归）
- `./.venv/bin/pytest tests/test_tutoring_agent.py tests/test_assessment_agent.py tests/test_resources_workflow.py -q`：**133 passed**（tutoring / assessment / resources trace 与主链路回归）
- `./.venv/bin/pytest tests/test_openapi_alignment.py tests/test_schema_contracts.py -q`：**49 passed**（OpenAPI + schema/import contract）
- `./.venv/bin/python -m agent_service.tools.smoke_resources_workflow --live`：**PASS**（resources live multi-agent workflow，4 类资源齐全，path=multi_agent）
- `curl -X POST /agent/v1/assessment/generate-questions`：**200**（`course_id=data_structures`，生成顺序存储结构单选题）
- `curl -N -X POST /agent/v1/tutoring/chat`：**SSE 通过**（chunk / knowledge_points / suggestion / done，知识点来自 `data_structures`）
- `./.venv/bin/python -m agent_service.tools.readiness_check`：**ready**（LLM / embedding / reranker provider_built=true，Qdrant ok=true）
- `curl http://127.0.0.1:8002/agent/v1/health`：**200**（`qdrant_connected=true`，`model_loaded=true`）
- `./.venv/bin/pytest -q`：**416 passed**（readiness provider 构建修复后全量回归）
- `./.venv/bin/pytest tests/test_course_knowledge_store.py tests/test_knowledge_ingestion_smoke.py tests/test_readiness.py tests/test_qdrant_store.py -q`：**21 passed**（Qdrant ingestion/readiness 相关回归）
- `./.venv/bin/python -m agent_service.tools.ingest_knowledge knowledge_base/data_structures`：**通过**（Qdrant server 写入 `course_id=data_structures`，760 chunks）
- `QdrantClient(...).count(course_knowledge_v1_1024)`：**760**（server collection 已创建且非空）
- `QdrantVectorStore().search_course_knowledge("data_structures", embedding("顺序表的随机访问"), limit=3)`：**3 hits**（真实 RAG 检索可用）
- `./.venv/bin/pytest -q`：**415 passed**（Qdrant server 首导入修复后全量回归）
- `./.venv/bin/pytest tests/test_course_knowledge_store.py tests/test_knowledge_ingestion_smoke.py tests/test_qdrant_store.py tests/test_readiness.py -q`：**20 passed**（fresh collection、UUID point id、embedding batch、Qdrant server/local）
- `./.venv/bin/pytest tests/test_openapi_alignment.py tests/test_schema_contracts.py -q`：**49 passed**（OpenAPI + schema/import contract）
- `./.venv/bin/pytest -q`：**413 passed**（Qdrant server URL 模式接入后全量回归）
- `./.venv/bin/pytest tests/test_qdrant_store.py tests/test_core_config.py tests/test_vector_store.py tests/test_readiness.py -q`：**21 passed**（Qdrant server/local 配置与 readiness 探针）
- `./.venv/bin/python ... build_qdrant_store(...).get_client().get_collections()`：**通过**（提权访问本机 `http://127.0.0.1:6333`，collections 当前为空）
- `./.venv/bin/python ... build_readiness_report(live=False)`：**Qdrant check ok=True**（整体 status degraded 来自其他配置/服务检查，不影响 Qdrant 子项）
- `./.venv/bin/pytest tests/test_openapi_alignment.py -q`：**25 passed**（OpenAPI 契约不漂移）
- `./.venv/bin/pytest tests/test_schema_contracts.py -q`：**24 passed**（schema/import contract 回归）
- `./.venv/bin/pytest -q`：**408 passed**（AssessmentQualityGate 合并后全量回归）
- `./.venv/bin/pytest tests/test_resources_workflow.py tests/test_tutoring_agent.py tests/test_tutoring_response_critic.py -q`：**91 passed**（resources/tutoring 相关回归）
- `./.venv/bin/pytest tests/test_openapi_alignment.py -q`：**25 passed**（OpenAPI 契约不漂移）
- `./.venv/bin/pytest tests/test_schema_contracts.py -q`：**24 passed**（schema/import contract 回归）
- `./.venv/bin/pytest tests/test_assessment_quality.py tests/test_assessment_knowledge_guard.py tests/test_assessment_difficulty_balancer.py tests/test_assessment_agent.py -q`：**69 passed**（AssessmentQualityGate 合并与 assessment 出题降级链）
- `./.venv/bin/pytest tests/test_resources_critic.py tests/test_resources_workflow.py -q`：**77 passed**（ResourceCriticAgent + resources workflow 回归）
- `./.venv/bin/pytest tests/test_openapi_alignment.py -q`：**25 passed**（OpenAPI 契约不漂移）
- `./.venv/bin/pytest tests/test_schema_contracts.py -q`：**24 passed**（schema/import contract 回归）
- `./.venv/bin/pytest tests/test_assessment_difficulty_balancer.py tests/test_assessment_agent.py -q`：**55 passed**（DifficultyBalancer + assessment 出题降级链）
- `./.venv/bin/pytest tests/test_openapi_alignment.py -q`：**25 passed**（OpenAPI 契约不漂移）
- `./.venv/bin/pytest tests/test_schema_contracts.py -q`：**24 passed**（schema/import contract 回归）
- `./.venv/bin/pytest tests/test_assessment_knowledge_guard.py tests/test_assessment_agent.py -q`：**51 passed**（KnowledgePointGuard + assessment 出题降级链）
- `./.venv/bin/pytest tests/test_openapi_alignment.py -q`：**25 passed**（OpenAPI 契约不漂移）
- `./.venv/bin/pytest tests/test_schema_contracts.py -q`：**24 passed**（schema/import contract 回归）
- `./.venv/bin/pytest tests/test_assessment_agent.py -q`：**41 passed**（QuestionCriticAgent）
- `./.venv/bin/pytest tests/test_openapi_alignment.py -q`：**25 passed**（OpenAPI 契约不漂移）
- `./.venv/bin/pytest tests/test_tutoring_tools.py tests/test_vector_store.py -q`：**16 passed**
- `./.venv/bin/pytest tests/test_tutoring_strategy.py tests/test_tutoring_react_flow.py tests/test_tutoring_agent.py tests/test_tutoring_prompts.py -q`：**31 passed**（StrategyAgent + tutoring prompt 传递）
- `./.venv/bin/pytest tests/test_tutoring_react_flow.py tests/test_tutoring_agent.py tests/test_tutoring_prompts.py -q`：**24 passed**
- `./.venv/bin/pytest tests/test_tutoring_api.py -q`：**10 passed**（SSE / 降级链回归）
- `./.venv/bin/pytest tests/test_tutoring_strategy.py tests/test_tutoring_react_flow.py tests/test_tutoring_agent.py tests/test_tutoring_prompts.py tests/test_tutoring_api.py -q`：**41 passed**（最终 tutoring 回归）
- `./.venv/bin/pytest tests/test_tutoring_response_critic.py tests/test_tutoring_strategy.py tests/test_tutoring_react_flow.py tests/test_tutoring_agent.py tests/test_tutoring_prompts.py tests/test_tutoring_api.py -q`：**50 passed**（ResponseCriticAgent + tutoring 回归）
- `./.venv/bin/pytest tests/test_resources_agent.py tests/test_resources_workflow.py -q`：**85 passed**
- `./.venv/bin/pytest tests/test_ingest_knowledge_cli.py tests/test_ingest_knowledge.py --cov=agent_service.tools.ingest_knowledge -q`：**12 passed**（`ingest_knowledge.py` CLI 工程化加固，支持异常捕获、更完备的前置校验包括单文件后缀校验、与退出码，测试覆盖率 96%）
- 近期全量记录：`./.venv/bin/pytest -q` 曾为 **335 passed**；后续若改共享逻辑需重新跑相关范围或全量。

## 下一步建议

1. 统一 trace/log：记录 assessment/resources/tutoring 中各 gate 拒绝原因、fallback 路径和最终输出来源，不改变 API/schema/webhook。
2. 真实 LLM/RAG 联调：验证 assessment 出题质量、resources 生成质量和 tutoring prompt 效果。
3. AgentScope Studio trace：先查官方文档或本地安装包 introspection，再决定是否接入；不凭空编造 Studio API。
4. 如需展示 AgentScope Studio，先启动 Studio 或临时清空 `AGENTSCOPE_STUDIO_URL` 避免启动日志里出现连接失败堆栈。
5. 整理比赛 demo 顺序：health/readiness → Qdrant count/search → resources workflow → assessment 出题 → tutoring SSE，并展示 `agent_trace` 日志。
