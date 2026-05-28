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
| `GET /agent/v1/health` | 已完成 | Qdrant 探针 + model_loaded/model_name/uptime；HealthData 5 字段严格匹配 OpenAPI；探针逻辑在 agents/health.py，API 层薄路由 |
| `POST /agent/v1/tutoring/chat` | ReActAgent 最小垂直链路已完成 | 降级链：ReActAgent → chat JSON → rule-based；第一版无 toolkit |
| `POST /agent/v1/profile/generate` | LLM full enrichment + 规则版 fallback 已完成 | 降级链：LLM guarded full ProfileData enrichment → 规则版；LLM 输出经 schema/枚举/范围/观测名称保护后合并 |
| `POST /agent/v1/evaluation/generate` | LLM full enrichment + 规则版 fallback 已完成 | 降级链：LLM guarded full EvaluationData enrichment → 规则版；表格和 summary 均经列/范围/观测名称保护后合并 |
| `POST /agent/v1/assessment/evaluate` | LLM + 规则版 fallback 已完成 | 判分由规则确定；LLM 增强 explanation、diagnosis.summary、weak_points.error_pattern、suggestions；降级链：LLM enrichment → 规则版 |
| `POST /agent/v1/assessment/generate-questions` | LLM + RAG + fallback 已完成 | 降级链：LLM（含 course_knowledge RAG context）→ 骨架占位题；prompt 强化质量约束 |
| `POST /agent/v1/learning-path/generate` | LLM + 规则版 fallback 已完成 | 降级链：LLM（节点 ID 白名单 + name 回填）→ 规则版；LLM 不发明节点 |
| `POST /agent/v1/resources/generate` | LLM + RAG + fallback 已完成 | 202 + 后台任务；LLM 并行生成四类资源 + course_knowledge RAG 检索注入 prompt；skeleton fallback → webhook completed |
| `POST /agent/v1/memory/compress` | LLM + 规则版 fallback 已完成 | 降级链：LLM → 规则版；规则版补齐 mastered_point / cognitive_preference / blind_spot 三种类型；LLM 提取 3 种 fact 类型 + 生成摘要；Qdrant 写入 best-effort |

## 当前已确认能力

- FastAPI API 骨架、Pydantic schemas、OpenAPI 对齐测试体系已建立。
- 面向开发者自学的代码导读手册已补充：`docs/Agent-Service_代码导读与自学手册.md`，用于辅助阅读项目结构、调用链和常见修改路径。
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
- Knowledge ingestion 闭环 smoke 已完成：ingest → retrieve → RAG context 端到端验证，幂等，fake embedding/Qdrant 隔离。
- Qdrant collection 自动创建：`ensure_collection_exists()` 在 course_knowledge 和 user_memory 首次写入前确保 collection 存在，fresh Qdrant 不再报错。
- Readiness 不再调用 `get_ai_providers()` 混用全局 settings，直接使用注入的 provider。
- Structured output 结果可从 `ChatResponse.metadata` 提取，避免正文为空时路径失效。
- Agent observability INFO 日志：LLM enrichment/generation 成功、RAG 检索 chunk 数、ReAct/structured output 命中，共 12 条。
- AgentScope Studio 接入已完成最小配置化：FastAPI startup 经 `main.py` 在 lifespan 内按 `AGENTSCOPE_STUDIO_URL` best-effort 调用 `agentscope.init(...)`；`uvicorn agent_service.main:app` 和 `python -m agent_service.main` 路径统一生效，不再硬编码到 `__main__`。
- API 边界收束已完成：health 探针逻辑下沉到 `agents/health.py`；tutoring API 恢复薄路由且不暴露测试注入参数；assessment 出题不再从 API 层导入 agents 私有函数。
- OpenAPI 对齐测试已扩展到主要 request/result schema，当前 25 个 alignment 测试覆盖 HealthData、assessment、learning-path、resources、memory、tutoring SSE 参数等。
- 本地启动与运维文档已补充：`docs/Agent-Service_本地启动与运维.md` 记录 uvicorn 启动、health、readiness、smoke、知识入库和常见问题。

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

### 框架深入计划（竞赛评审可见度提升）

**背景**：当前只有 `tutoring/chat` 真正用到 AgentScope Agent 编排能力（ReActAgent + Toolkit + Memory），其他接口均为单次 LLM 调用包装。需将 AgentScope 编排能力扩展到更多模块以提升框架深度。

**原则**：
- 新增 AgentScope 链路必须保留三层降级：`ReActAgent → LLM enrichment → rule-based`
- 不改 OpenAPI / schema / 接口契约
- 不拆除现有 246 个测试已覆盖的逻辑
- 优先做"高可见度、低风险"的模块

#### P0：`assessment/generate-questions` 接入 ReActAgent

出题有明确多步推理需求（生成→格式自检→调整），且已有 RAG 工具可复用。

新建文件：
- `agents/assessment_react.py` — `QuestionGeneratorReActAgent`，参照 `tutoring_react.py` 结构
- `agents/assessment_tools.py` — toolkit：`retrieve_course_knowledge`（复用逻辑）+ `validate_question_format`（本地格式校验：type/options/answer 一致性、content 非占位符，无需外部依赖）

修改文件：
- `agents/assessment.py` — `generate_questions_with_llm()` 之前先尝试 `QuestionGeneratorReActAgent.generate()`
- `prompts/assessment.py` — 新增 ReActAgent 专用 system prompt（强调自检和格式约束）

降级链：
```
QuestionGeneratorReActAgent.generate()   ← AgentScope ReActAgent + toolkit
  ↓ 失败/None
generate_questions_with_llm()            ← 现有单次 LLM + RAG
  ↓ 失败/None
generate_questions_data()                ← 现有规则版骨架题
```

#### P1：tutoring/chat diagram 事件触发

当前 `DiagramEvent` 是空壳，`generate_tutoring_sse_events()` 没有任何路径 yield diagram 事件。

修改文件：
- `agents/tutoring.py` — `_TutoringStructuredOutput` 增加 `diagram: str | None = None`；`generate_tutoring_sse_events()` 检查 model_response 是否含 diagram 字段，有则 yield `DiagramEvent`
- `prompts/tutoring.py` — system prompt 增加策略：涉及数据结构操作流程时，在 JSON 输出中附带可选的 `diagram` 字段（Mermaid 语法）

#### P2：prompt + 后处理修正（解决 docs/analysis_results.md 标注的实际痛点）

- `prompts/assessment.py` — 出题 prompt 增加多样性指令 + knowledge_point 必须使用题目中原有名称的约束
- `agents/assessment.py` — `_coerce_questions()` 增加 answer/type 一致性修正（multi_choice answer 如果是 str 自动转 list）；`_enrich_rule_result()` 增加 knowledge_point 白名单过滤
- `prompts/memory.py` — 摘要生成指令增加维度约束（已掌握/仍困惑/提问风格/近期话题）和字数下限（不少于 100 字）
- `agents/memory.py` — `_coerce_extracted_facts()` 对 LLM 返回的 confidence 用规则版固定值覆盖，不依赖 LLM 自评

#### P3：AgentScope Studio 演示就绪

`main.py` 已有 `agentscope.init(studio_url=...)` 最小配置。演示时确保 Studio 可见：
- tutoring ReActAgent 推理过程
- assessment ReActAgent（P0 完成后）的 tool call 链路

#### 暂不升级的模块

- `assessment/evaluate`：判分必须由规则确定，多轮推理无收益
- `profile/generate`、`evaluation/generate`：统计数据转画像，规则版已足够
- `learning-path/generate`：核心是拓扑排序，不是推理问题
- `memory/compress`：Backend 已在请求体传 `existing_facts`，用 tool 查 Qdrant 和现有方案等价
- `resources/generate`：异步 webhook，适合后续 workflow 升级，竞赛阶段不动

## 当前不继续推进的事项

- 不继续修旧 `tutoring/chat` 的单路径 JSON mode / fallback 细节。
- 不继续围绕 Qdrant local 文件锁、UUID point id、shared client 做扩大修补。
- 不继续执行耗时的全量 PDF 入库 smoke。

## 最近测试/验证

- `./.venv/bin/pytest -q`：**246 passed**
- `./.venv/bin/pytest tests/test_core_config.py -q`：**5 passed**
- OpenAPI 对齐：25 个测试覆盖全部主要 request/result schema，并守卫 tutoring/chat 不暴露测试注入参数
- `./.venv/bin/python -m agent_service.tools.smoke_all`：9/9 PASS；smoke 工具直接调用 API handlers，避免本地验收依赖外部 Qdrant/TestClient lifespan/webhook
- 本地启动验证：`./.venv/bin/uvicorn agent_service.main:app --host 127.0.0.1 --port 8002` 可启动到 `Application startup complete`
- LearningPath / KnowledgeGraph edge alias 支持 Python 内部 `from_` + OpenAPI `from` 输出

## 下一步

### 执行顺序（框架深入 + 痛点修复）

1. **P2 prompt/后处理修正**（最快，预计 1 天）
   - `prompts/assessment.py` 多样性指令 + knowledge_point 白名单约束
   - `agents/assessment.py` `_coerce_questions()` answer/type 修正；`_enrich_rule_result()` 白名单过滤
   - `prompts/memory.py` 摘要维度约束 + 字数下限
   - `agents/memory.py` confidence 规则覆盖

2. **P1 diagram 触发**（预计 1 天）
   - `agents/tutoring.py` `_TutoringStructuredOutput` + `generate_tutoring_sse_events()`
   - `prompts/tutoring.py` diagram 触发策略

3. **P0 assessment ReActAgent**（预计 2-3 天）
   - 新建 `agents/assessment_react.py` + `agents/assessment_tools.py`
   - 修改 `agents/assessment.py` 接入三层降级链
   - 运行 `tests/test_assessment_agent.py` 确认现有测试通过

4. **Backend 联调**
   - 按 `docs/superpowers/plans/2026-05-26-backend-agent-integration.md` 联调
   - tutoring/chat SSE proxy、resources webhook 落库

### 中远期

- Backend 开放只读接口（知识点名称表 + 已有题目查询）后，`assessment_tools.py` 补充 `query_existing_questions` tool，支持出题去重和推荐真实练习题
- resources/generate 升级为 AgentScope workflow 多智能体并行生成（四类资源）
- Qdrant server 模式 / shared client 改造

## 文档补充记录

- 新增根目录文档 `Agent-Service-接口JSON示例说明.md`
- 文档内容覆盖全部 9 个 Agent Service 对外接口
- 每个接口补充了可直接复制到 Apifox 的请求/响应 JSON 示例
- tutoring/chat 额外补充 SSE 单事件 mock 示例
- resources/generate 额外补充 202 响应、Webhook 成功回调、Webhook 失败回调示例

## 最近测试/验证补充

- 本次未修改业务代码，未新增或变更 OpenAPI 契约
- 文档内容以 `../docs/20-agent-api/Agent-Service.openapi.json` 和 `../docs/20-agent-api/API_Agent内部接口规范.md` 对齐整理
