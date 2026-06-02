# WORKFLOW.md

## 文件用途

本文件只记录 `agent_service` 跨窗口恢复开发所需的最小状态。
接口契约以 `../docs/20-agent-api/Agent-Service.openapi.json` 和 `../docs/20-agent-api/API_Agent内部接口规范.md` 为准，本文件不是接口契约来源。

## 当前方向

- Agent Service 负责智能体编排、RAG、工具调用和结构化结果生成，不直接写 Backend SQL 数据库。
- Agent 全链路架构升级主干已完成：适合 Agent/Workflow 的重点链路已具备 Agent 编排、质量门禁和 fallback。
- 真实联调主链已完成：resources live workflow、tutoring/chat 真实 RAG、Backend v1 联调闭环均已验证。
- 后续不再为“升级架构”继续大改已完成接口；新增改动必须服务于质量收口、可观测性、部署稳定性、数据准备流程或明确缺陷修复。
- deterministic / 统计型接口继续以 structured output + 规则保护为主：`profile/generate`、`evaluation/generate`、`assessment/evaluate`、`learning-path/generate`、`memory/compress`。
- AgentScope 接入必须落在 `agents/`、`memory/`、`tools/`、`prompts/`、`core/` 边界内，不泄漏到 API/schema/Backend 契约。

## 全链路升级状态

- 已完成主干升级的 Agent 化链路：
  - `tutoring/chat`：StrategyAgent → ReAct/chat → ResponseCritic → rule-based fallback。
  - `assessment/generate-questions`：ReActAgent + RAG toolkit → AssessmentQualityGate → LLM/skeleton fallback。
  - `resources/generate`：Planner → AgentScope fanout ResourceAgents → ResourceCriticAgent → Aggregator → fallback。
- 已保持 deterministic / 统计型接口稳定：`profile/generate`、`evaluation/generate`、`assessment/evaluate`、`learning-path/generate`、`memory/compress`。
- Backend 联调 v1 已验证 3 类关键事实：
  - Agent 实时对话链路可用：`tutoring/chat` 已拿到真实 RAG 证据。
  - Agent 异步生成链路可用：`resources/generate` 已完成真实 webhook 回写闭环。
  - Agent 课程推荐/出题链路可用：`assessment/generate-questions`、`learning-path/generate` 已被 Backend 主链消费验证。
- 当前未完成项已转为系统化收尾，不是架构主干问题：质量指标、统一 trace/log、KG/Qdrant 数据准备流程、比赛 demo 整理。

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
- `QdrantVectorStore().search_course_knowledge("758aeff588e84044", embedding("数据结构 顺序表 随机访问"), limit=3)`：**3 hits**（真实课程知识检索可用，证明 Backend 课程 ID 已可命中 Qdrant）
- `./.venv/bin/pytest tests/test_ai_providers.py tests/test_core_config.py -q`：**19 passed**（SiliconFlow embedding 请求维度开关；默认不向 embeddings API 发送 `dimensions`）
- `./.venv/bin/python -m agent_service.tools.smoke_resources_workflow --live`：**PASS**（resources live multi-agent workflow，path=`multi_agent`）
- `curl -N -X POST /agent/v1/tutoring/chat`：**SSE 通过**（chunk / knowledge_points / suggestion / done，课程知识真实参与回答）
- `./.venv/bin/python -m agent_service.tools.readiness_check`：**ready**（LLM / embedding / reranker provider_built=true，Qdrant ok=true）
- `curl http://127.0.0.1:8002/agent/v1/health`：**200**（`qdrant_connected=true`，`model_loaded=true`）
- `./.venv/bin/pytest tests/test_openapi_alignment.py tests/test_schema_contracts.py -q`：**49 passed**（OpenAPI + schema/import contract）
- `./.venv/bin/pytest tests/test_tutoring_agent.py tests/test_assessment_agent.py tests/test_resources_workflow.py -q`：**133 passed**（tutoring / assessment / resources 主链路回归）
- `./.venv/bin/pytest -q`：**418 passed**（当前全量回归基线）

## 下一步建议

1. 统一 `agent_trace` / gate 日志：补齐 tutoring、assessment、resources 的拒绝原因、fallback 路径和最终输出来源，便于联调和 demo 解释。
2. 收口质量问题而非继续大改架构：重点看 assessment 出题质量、resources 课程贴合度、tutoring 回答稳定性。
3. 与 Backend 协同处理数据准备链路：新课程 Qdrant 知识灌入流程、`CourseKnowledgeGraph` 准备流程仍未产品化。
4. 保持 `learning-path/generate` 的契约稳定：当前空结果多来自 Backend 未提供 KG，而不是 Agent 链路故障。
5. 如需展示 AgentScope Studio 或比赛 demo，再单独整理最小展示路径：health/readiness → Qdrant count/search → resources workflow → tutoring SSE → 关键 `agent_trace`。
