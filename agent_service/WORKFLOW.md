# WORKFLOW.md

## 文件用途

本文件只记录 `agent_service` 跨窗口恢复开发所需的最小状态。
接口契约以 `../docs/20-agent-api/Agent-Service.openapi.json` 和 `../docs/20-agent-api/API_Agent内部接口规范.md` 为准，本文件不是接口契约来源。

## 当前方向

- Agent Service 负责智能体编排、RAG、工具调用和结构化结果生成，不直接写 Backend SQL 数据库。
- 后续以适合的 Agent/Workflow 编排替代低价值手写编排，但不为所有接口强行套用 multi-agent。
- Agent 化优先用于天然需要拆分、协作、检索、自检或并行的链路：`resources/generate`、`tutoring/chat`、`assessment/generate-questions`。
- deterministic / 统计型接口继续以 structured output + 规则保护为主：`profile/generate`、`evaluation/generate`、`assessment/evaluate`、`learning-path/generate`、`memory/compress`。
- AgentScope 接入必须落在 `agents/`、`memory/`、`tools/`、`prompts/`、`core/` 边界内，不泄漏到 API/schema/Backend 契约。

## 接口进度

| 接口 | 状态 | 当前实现要点 |
|------|------|--------------|
| `GET /agent/v1/health` | 已完成 | health 探针逻辑在 `agents/health.py`，API 层薄路由 |
| `POST /agent/v1/tutoring/chat` | StrategyAgent + ResponseCritic 首阶段已完成 | StrategyAgent 先选提示式引导 / 直接解释 / 追问澄清 / 例题讲解；ResponseCriticAgent 对 ReAct/chat 候选答复做质量门禁；降级链：Strategy 规则兜底 → ReAct → critic → chat JSON → critic → rule-based |
| `POST /agent/v1/profile/generate` | 已完成 | LLM enrichment + schema/枚举/范围保护 + 规则 fallback |
| `POST /agent/v1/evaluation/generate` | 已完成 | LLM enrichment + 表格/summary 保护 + 规则 fallback |
| `POST /agent/v1/assessment/evaluate` | 已完成 | 判分由规则确定；LLM 只增强解析、诊断和建议 |
| `POST /agent/v1/assessment/generate-questions` | ReActAgent + QuestionCritic 已完成 | ReAct + RAG toolkit → QuestionCriticAgent → LLM fallback → 骨架题 |
| `POST /agent/v1/learning-path/generate` | 已完成 | LLM 只在节点白名单内补全；失败回落规则路径 |
| `POST /agent/v1/resources/generate` | Multi-Agent Workflow 已完成 | Planner → AgentScope fanout ResourceAgents → Aggregator；单资源局部 fallback |
| `POST /agent/v1/memory/compress` | 已完成 | LLM fact extraction + 规则 fallback；Qdrant 写入 best-effort |

## AgentScope 使用状态

- 已接入：ChatModel/Formatter、Embedding、ReActAgent、Toolkit/ToolResponse、InMemoryMemory、Reader/PDFReader、QdrantStore、fanout_pipeline。
- tutoring 已接入内部 StrategyAgent 和 ResponseCriticAgent，策略选择/质量判断失败时回落规则策略或继续降级，不改变 SSE / schemas。
- tutoring toolkit 已返回 AgentScope 合法 TextBlock：`{"type": "text", "text": "..."}`。
- assessment toolkit 已返回 AgentScope 合法 TextBlock，并新增 `QuestionCriticAgent` 混合质量门禁。
- resources workflow 已通过 AgentScope `fanout_pipeline` 调度 Document/Mindmap/Reading/Code ResourceAgent。
- 当前 Qdrant local 模式已做懒加载以减少同进程重复 client，但多进程文件锁仍可能发生；长期建议迁移 Qdrant server。

## 当前注意事项

- 不修改 `../docs`，除非用户明确要求。
- 不改变 OpenAPI、schemas 或 Backend 调用契约。
- API 层保持薄路由，业务逻辑放入 `agents/`。
- 新增 AgentScope API 用法前必须查官方文档或用本地包 introspection 验证。
- 工作区存在用户/历史未提交改动，提交时只暂存本轮文件，不回滚无关改动。

## 最近验证

- `./.venv/bin/pytest tests/test_assessment_agent.py -q`：**41 passed**（QuestionCriticAgent）
- `./.venv/bin/pytest tests/test_openapi_alignment.py -q`：**25 passed**（OpenAPI 契约不漂移）
- `./.venv/bin/pytest tests/test_tutoring_tools.py tests/test_vector_store.py -q`：**16 passed**
- `./.venv/bin/pytest tests/test_tutoring_strategy.py tests/test_tutoring_react_flow.py tests/test_tutoring_agent.py tests/test_tutoring_prompts.py -q`：**31 passed**（StrategyAgent + tutoring prompt 传递）
- `./.venv/bin/pytest tests/test_tutoring_react_flow.py tests/test_tutoring_agent.py tests/test_tutoring_prompts.py -q`：**24 passed**
- `./.venv/bin/pytest tests/test_tutoring_api.py -q`：**10 passed**（SSE / 降级链回归）
- `./.venv/bin/pytest tests/test_tutoring_strategy.py tests/test_tutoring_react_flow.py tests/test_tutoring_agent.py tests/test_tutoring_prompts.py tests/test_tutoring_api.py -q`：**41 passed**（最终 tutoring 回归）
- `./.venv/bin/pytest tests/test_tutoring_response_critic.py tests/test_tutoring_strategy.py tests/test_tutoring_react_flow.py tests/test_tutoring_agent.py tests/test_tutoring_prompts.py tests/test_tutoring_api.py -q`：**50 passed**（ResponseCriticAgent + tutoring 回归）
- `./.venv/bin/pytest tests/test_resources_agent.py tests/test_resources_workflow.py -q`：**85 passed**
- 近期全量记录：`./.venv/bin/pytest -q` 曾为 **335 passed**；后续若改共享逻辑需重新跑相关范围或全量。

## 下一步建议

1. `assessment/generate-questions`：后续评估 `KnowledgePointGuard` / `DifficultyBalancer`，不改变题型契约。
2. `resources/generate`：补 `ResourceCriticAgent` / 质量门禁、真实 LLM 质量验证和 AgentScope Studio trace。
3. `tutoring/chat`：后续可做真实 LLM prompt 质量验证和 AgentScope Studio trace，不改变 SSE 和 schemas。
4. 部署联调：优先引入 Qdrant server 模式，减少 Apifox / 多进程真实 AI 流程中的 local 文件锁问题。
