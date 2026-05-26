# WORKFLOW.md

## 文件用途

本文件只记录 `agent_service` 跨窗口恢复开发所需的最小状态。
接口契约以 `../docs/20-agent-api/Agent-Service.openapi.json` 和 `../docs/20-agent-api/API_Agent内部接口规范.md` 为准，本文件不是接口契约来源。

## 当前方向

- 当前不继续打磨旧 `tutoring/chat` 主链路；后续 tutoring 计划切换到 AgentScope ReActAgent / ReAct 编排。
- 非主线能力以简洁可用为准，避免为了本地 smoke 继续扩大 Qdrant、ID、并发 client 等实现细节。
- AgentScope 仍是后续 AI 编排主框架，但接入应落在 `agents/`、`memory/`、`tools/` 边界内，不泄漏到 OpenAPI/schema。
- `WORKFLOW.md` 不再记录长流水日志，只保留当前状态、最近验证和下一步。

## 接口进度

| 接口 | 状态 | 备注 |
|------|------|------|
| `GET /agent/v1/health` | 已完成 | Qdrant 探针 + uptime + llm_configured / embedding_configured / reranker_configured / qdrant_collection；纯读 settings 不发请求 |
| `POST /agent/v1/tutoring/chat` | ReActAgent 最小垂直链路已完成 | 降级链：ReActAgent → chat JSON → rule-based；第一版无 toolkit |
| `POST /agent/v1/profile/generate` | LLM full enrichment + 规则版 fallback 已完成 | 降级链：LLM guarded full ProfileData enrichment → 规则版；LLM 输出经 schema/枚举/范围/观测名称保护后合并 |
| `POST /agent/v1/evaluation/generate` | LLM full enrichment + 规则版 fallback 已完成 | 降级链：LLM guarded full EvaluationData enrichment → 规则版；表格和 summary 均经列/范围/观测名称保护后合并 |
| `POST /agent/v1/assessment/evaluate` | LLM + 规则版 fallback 已完成 | 判分由规则确定；LLM 增强 explanation、diagnosis.summary、weak_points.error_pattern、suggestions；降级链：LLM enrichment → 规则版 |
| `POST /agent/v1/assessment/generate-questions` | LLM + RAG + fallback 已完成 | 降级链：LLM（含 course_knowledge RAG context）→ 骨架占位题；prompt 强化质量约束 |
| `POST /agent/v1/learning-path/generate` | LLM + 规则版 fallback 已完成 | 降级链：LLM（节点 ID 白名单 + name 回填）→ 规则版；LLM 不发明节点 |
| `POST /agent/v1/resources/generate` | LLM + RAG + fallback 已完成 | 202 + 后台任务；LLM 并行生成四类资源 + course_knowledge RAG 检索注入 prompt；skeleton fallback → webhook completed |
| `POST /agent/v1/memory/compress` | LLM + 规则版 fallback 已完成 | 降级链：LLM → 规则版；LLM 提取 3 种 fact 类型 + 生成摘要；Qdrant 写入 best-effort |

## 当前已确认能力

- FastAPI API 骨架、Pydantic schemas、OpenAPI 对齐测试体系已建立。
- 多个非 tutoring 接口已有规则版实现和测试覆盖。
- AgentScope 依赖已进入项目，ReActAgent、Reader、Embedding、QdrantStore 可用。
- 课程知识摄入 CLI 已完成幂等闭环：支持 PDF/MD/TXT，重复执行跳过已摄入源文件。
- `knowledge_base/` 已加入 `.gitignore`，含 `README.md` 说明用法。
- ReActAgent 最小垂直链路已接入 `tutoring/chat`：`agents/tutoring_react_flow.py` 做胶水层，`_build_model_response()` 内部顺序 ReAct → chat JSON → None。
- `retrieve_course_knowledge` + `retrieve_user_memory` toolkit 已挂载：两个工具均闭包隐藏内部参数，模型只暴露 query。user_memory_facts 首轮注入保持不变。
- 《数据结构（C语言版）》PDF 可被 AgentScope PDFReader 解析，约 760 chunks。
- embedding provider 已验证可返回 1024 维向量。
- Provider readiness CLI 已完成：`./.venv/bin/python -m agent_service.tools.readiness_check` 默认检查配置与 provider 构建；`--live` 才发真实 LLM/Embedding/Reranker 探针。
- tutoring/chat structured output 已接入：`generate_tutoring_model_response()` 优先用 AgentScope `structured_model` → 失败回落 `parse_tutoring_model_response()` → 再失败回落 rule-based；不改 SSE/API/schema。
- E2E smoke 验收工具已完成：`./.venv/bin/python -m agent_service.tools.smoke_all` 一次命令验证全部 9 接口最小可用。

## AgentScope 使用审查

### 已使用的框架能力

| 能力 | 当前文件 | 用途 |
|------|----------|------|
| AgentScope ChatModel + Formatter | `core/ai.py` | `AgentScopeChatProvider` 封装 OpenAIChatModel + DeepSeekChatFormatter，作为项目 `ChatProvider` 边界实现 |
| AgentScope Embedding | `core/ai.py` | `AgentScopeEmbeddingProvider` 封装 OpenAITextEmbedding，作为项目 `EmbeddingProvider` 边界实现 |
| ReActAgent | `agents/tutoring_react.py` | tutoring/chat 的 ReAct 编排适配器，失败时回落到 chat JSON / rule-based |
| Msg / InMemoryMemory | `agents/tutoring_react.py` | 将用户消息转为 AgentScope Msg，并为 ReActAgent 提供短期内存 |
| Toolkit / ToolResponse | `agents/tutoring_tools.py` | 挂载 `retrieve_course_knowledge`、`retrieve_user_memory` 两个模型可调用工具 |
| Reader / PDFReader 路径 | `tools/ingest_knowledge.py`、`memory/course_knowledge_store.py` | 课程知识摄入：PDF/MD/TXT → chunks → embedding → Qdrant course_knowledge |

### 可用但尚未充分使用的框架能力

| AgentScope 能力 | 推荐状态 | 说明 |
|-----------------|----------|------|
| Structured output | 推荐优先评估 | 可替代当前多处 `json.loads` / markdown fence / prompt-only JSON 解析，降低 LLM 输出脆弱性 |
| Knowledge / Generic RAG | 推荐用于 tutoring/chat | 可把课程知识作为 ReActAgent knowledge 注入，和现有工具检索形成对照；先保持现有 Qdrant 检索 fallback |
| Agentic RAG / retrieve_knowledge tool | 暂缓 | 依赖模型稳定 tool-use，当前已手写 retrieve_course_knowledge 工具，短期够用 |
| Planning / multi-step workflow | 适合 resources/generate 后续升级 | resources/generate 是多资源并行/多步骤任务，适合后续 AgentScope workflow/planning；不要先用于简单 deterministic 接口 |
| Memory/session/state | 暂缓 | 当前长期记忆 schema 和 Qdrant 写入是产品边界，先不迁移到 AgentScope memory |
| Observability/evaluation hooks | 生产化后推荐 | 适合后续追踪 ReAct tool call、LLM 输出、降级路径；不影响当前 OpenAPI |

### 推荐使用 AgentScope 的链路优先级

1. `POST /agent/v1/tutoring/chat`
   - 推荐方向：Structured output 或 Generic Knowledge 集成。
   - 涉及文件：`agents/tutoring_react.py`、`agents/tutoring_react_flow.py`、`agents/tutoring_tools.py`、`prompts/tutoring.py`、`memory/tutoring_retrieval.py`。
   - 原因：当前已经有 ReActAgent + toolkit，继续用 AgentScope 的收益最高；仍需保持 SSE 输出和 rule fallback。

2. `POST /agent/v1/resources/generate`
   - 推荐方向：后续引入 AgentScope planning / workflow 编排四类资源生成。
   - 涉及文件：`agents/resources.py`、`prompts/resources.py`、`tests/test_resources_agent.py`。
   - 原因：资源生成是多步骤异步任务，适合 workflow；但 webhook worker 调试复杂，应排在 readiness 之后。

3. `POST /agent/v1/assessment/generate-questions`
   - 推荐方向：Structured output，不优先 ReActAgent。
   - 涉及文件：`agents/assessment.py`、`prompts/assessment.py`、`tests/test_assessment_agent.py`。
   - 原因：已有 RAG + LLM 主路径，主要痛点是结构化题目输出稳定性。

### 不推荐优先使用 AgentScope 的链路

- `GET /agent/v1/health` / provider readiness：基础设施确定性检查，不需要 Agent。
- `POST /agent/v1/assessment/evaluate`：判分必须由规则确定，LLM 只做诊断 enrichment。
- `POST /agent/v1/profile/generate`、`POST /agent/v1/evaluation/generate`：当前 guarded schema enrichment 已清晰可控，除非先验证 structured output，否则不引入 ReActAgent。
- `POST /agent/v1/memory/compress`：可后续评估 AgentScope memory，但当前 fact 类型和 Qdrant 写入属于产品记忆边界，暂不迁移。

## 当前不继续推进的事项

- 不继续修旧 `tutoring/chat` 的单路径 JSON mode / fallback 细节。
- 不继续围绕 Qdrant local 文件锁、UUID point id、shared client 做扩大修补。
- 不继续执行耗时的全量 PDF 入库 smoke。

## 最近测试/验证

- `./.venv/bin/pytest -q`：**228 passed**（2026-05-26 E2E smoke 验收后验证）
- E2E smoke_all：`./.venv/bin/python -m agent_service.tools.smoke_all` 覆盖全部 9 接口，9/9 PASS
- Provider readiness CLI：5 个测试（默认不发请求、live 模式探针、live 失败降级、Qdrant 失败降级、CLI 导入）
- evaluation/generate full enrichment：12 个测试（含 2 个新 full-table 用例，覆盖完整 EvaluationData + invalid/fabricated 行拒绝）
- resources/generate RAG：22 个测试
- OpenAPI 对齐：15 passed

## 下一步

- 短期：provider readiness CLI ← **已完成**
- 中期：tutoring/chat AgentScope structured output 替换 prompt JSON 解析
- 中期：tutoring/chat AgentScope structured output 或 Generic Knowledge 集成
- 远期：Qdrant server 模式 / shared client 改造
