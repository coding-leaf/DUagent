# WORKFLOW.md

## 文件用途

本文件用于记录 `agent_service` 当前开发进度、阶段目标、测试结果和跨窗口恢复上下文。
本文件不是接口契约来源，接口契约以 `../docs/20-agent-api` 下的 OpenAPI 与接口规范为准。

## 本文件修改注意事项

- 只记录跨窗口恢复开发所需的最小状态。
- 保留接口进度、当前焦点、近期完成摘要、最近测试结果和下一步建议。
- 不记录完整对话过程、详细推理过程、冗长历史背景。
- 每次完成小阶段后更新本文件，但应优先压缩为状态摘要。
- 不以更新本文件为理由扩大业务代码修改范围。

## 项目进度

> 以下为当前项目的接口开发进度，仅供恢复上下文使用。

| 接口 | 契约层 | API骨架 | Agent承接层 | 业务实现 | 测试状态 | 备注 |
|------|--------|---------|-------------|----------|----------|------|
| `GET /agent/v1/health` | 已完成 | 已完成 | 不适用 | 基础健康检查已完成 | 已覆盖 | 返回 Qdrant 探针结果和 uptime；探针失败会记录 warning；model 状态仍等待 AI 阶段 |
| `POST /agent/v1/tutoring/chat` | 已完成 | 已完成 | 已完成 | 规则版事件流 + AI 检索/Chat/Rerank 主链路已完成 | 已覆盖 | 输出 chunk / knowledge_points / suggestion / done；运行时已接入 embedding + Qdrant retrieval，候选上下文可经 reranker 重排，且模型可用结构化结果覆盖 `knowledge_points / suggestion` |
| `POST /agent/v1/profile/generate` | 已完成 | 已完成 | 已完成 | 规则版已完成 | 已覆盖 | 基于练习历史、资源使用、近期活跃度生成基础画像 |
| `POST /agent/v1/evaluation/generate` | 已完成 | 已完成 | 已完成 | 规则版已完成 | 已覆盖 | 基于学习进度、练习结果、资源使用生成表格和摘要 |
| `POST /agent/v1/assessment/evaluate` | 已完成 | 已完成 | 已完成 | 规则版已完成 | 已覆盖 | 基于标准答案和用户答案生成判分与诊断 |
| `POST /agent/v1/assessment/generate-questions` | 已完成 | 已完成 | 已完成 | 规则版骨架已完成 | 已覆盖 | 根据题型、数量、章节、知识点生成结构化占位题目 |
| `POST /agent/v1/learning-path/generate` | 已完成 | 已完成 | 已完成 | 规则版骨架已完成 | 已覆盖 | 基于知识图谱、薄弱点和掌握度生成结构化学习路径 |
| `POST /agent/v1/resources/generate` | 已完成 | 已完成 | 已完成 | 规则版闭环骨架已完成 | 已覆盖 | 202 + 后台任务 + webhook payload + retry/backoff 兜底，暂不接 LLM/Qdrant |
| `POST /agent/v1/memory/compress` | 已完成 | 已完成 | 已完成 | 规则版闭环已完成 | 已覆盖 | 生成对话摘要、提取基础薄弱点事实，并尝试写入 `user_memory_v1_1024` |

## 当前焦点

- `POST /agent/v1/tutoring/chat` 已接入 AI retrieval + chat + rerank 主链路：运行时会尝试构建异步 retrieval context，在保持首包即时性的前提下，用 reranker 重排候选上下文，并允许模型结构化结果覆盖 `knowledge_points / suggestion`。
- 当前推荐下一步优先增强 tutoring 的解耦和可替换性：把结构化元数据提炼进一步收拢为更明确的内部协议，再评估是否引入真正的模型结构化输出接口。
- 非 AI 工程收口已推进：`GET /health` 增加 Qdrant 探针和 uptime；`resources/generate` webhook 增加 retry/backoff 和发送失败兜底。
- 非 AI 契约收口已推进：Health response model 已补齐，memory / assessment / learning-path / health 的规范枚举值已在 Pydantic schema 中收紧。
- 进入 AI 阶段前最后收尾已完成：清理 Pydantic v2 `class Config` warning；新增标准库 logger 边界；新增未绑定具体模型的 AI provider 可替换接口。

## 今日开发记录

- 已完成 AI 前置配置收口：`.env` 配置字段、`.env.example` 中文注释、Qdrant collection 名称与向量维度配置化、embedding/reranker/chat provider 边界定义。
- 已完成 tutoring AI 骨架：Qdrant vector store、检索上下文构建、provider-neutral prompt/messages 转换、规则版 SSE 与 AI 检索边界兼容。
- 已完成 tutoring retrieval 接线：API 流式入口会先尝试 `build_tutoring_retrieval_context_with_ai`，失败时降级回规则版空检索上下文；现有 SSE 结构保持不变。
- 已完成 tutoring chat 接线：`core.ai` 已新增 OpenAI-compatible chat provider，`prompts.tutoring.build_tutoring_messages` 已接入 tutoring 主路径；当前会先即时返回规则版首个 `chunk`，再用真实模型补充一个后续 `chunk`。
- 已完成 tutoring reranker 接线：`core.ai` 已新增 OpenAI-compatible reranker provider，`memory.tutoring_retrieval` 会在候选命中后按相关性重排；未配置或失败时保留原检索顺序。
- 已完成 tutoring 结构化元数据增强：模型回答现在可通过 `<agent_result>{...}</agent_result>` 附带 `knowledge_points / suggestion`，由 agent 层解析后覆盖规则版结构化事件；解析失败时自动降级回规则版。
- 已完成 tutoring 运行态收口：`agents.tutoring` 新增统一内部结果对象，API 主路径不再分散传递 `model_text / knowledge_point_names / suggestion_text`，而是围绕单一 generation result 组装后续事件。
- 已完成 tutoring / memory 请求路径回归修复：`tutoring/chat` 现会先立即发送规则版首个 `chunk`，再等待 retrieval 并继续输出后续事件；`memory/compress` 的 Qdrant 初始化与 upsert 已改为真正 best-effort，不再因 store 初始化失败或同步 upsert 阻塞请求主路径。
- 已完成 tutoring reranker 兼容性修复：API 仅在 provider 实际存在时才向 retrieval builder 传 `reranker_provider`，避免无 reranker 场景和旧测试替身被错误打回规则版 fallback。
- 已完成非 AI 工程收口：health 探针日志、resources webhook retry/backoff/失败日志、Pydantic v2 warning 清理。
- 已修正 `memory.vector_store` 的 collection 读取方式，tutoring 检索现已跟随 `settings.QDRANT_*_COLLECTION`，不再硬编码旧的 `user_memory` / `course_knowledge`。
- 已完成 embedding provider 基础实现：`core.ai` 新增 OpenAI-compatible embeddings client，并支持按 settings 自动装配默认 embedding provider；reranker/chat 仍保持未配置占位。
- 已完成 `memory/compress -> Qdrant` 闭环：API 路由改为调用异步承接函数，提取出的 facts 会尝试向量化并 upsert 到 `user_memory_v1_1024`；embedding 或写入失败时降级返回原结果并记录 warning。

## 最近一轮审查结论

- 规则版开发进度较高：接口契约、API 骨架、规则版业务逻辑、SSE/202 协议、测试覆盖基本齐备；按规则版交付口径，当前完成度约 `85%~90%`。
- AI / RAG 闭环仍处于“骨架已搭好、主路径未完全串联”阶段；按文档目标口径，当前完成度约 `50%~60%`。
- 已识别的关键缺口有 1 个：
  - `/agent/v1/tutoring/chat` 的模型结构化输出目前仍基于 prompt 约定字符串标签解析，还没有专门的 provider 级结构化输出协议。
- 推荐修复顺序：
  - 先评估是否将 tutoring 的结构化输出协议从字符串标签解析升级为更明确的 provider-neutral 内部接口。

## 向量化规划记录

- 用户侧向量化主对象：`user_memory`。优先存记忆压缩后的 `facts` 与阶段性 `episode_summary`，不把全量原始对话作为主向量库内容。
- 课程侧向量化主对象：`course_knowledge`。优先存书籍/PDF/讲义/知识点说明/例题解析等课程资料切片，并保留 `course_id`、`chapter`、`knowledge_point`、`source_type` 等 metadata。
- 当前模型规划：embedding 使用 `BAAI/bge-m3`，维度 `1024`；reranker 使用 `BAAI/bge-reranker-v2-m3`；接入方式按 OpenAI-compatible URL 设计。
- 当前 collection 规划：`user_memory_v1_1024`、`course_knowledge_v1_1024`，避免与旧 `768` 维 collection 语义混用。

## 近期完成摘要

- `POST /agent/v1/assessment/generate-questions`：已接入 `agents.assessment.generate_questions_data`，可生成规则版结构化占位题目。
- `POST /agent/v1/learning-path/generate`：已接入 `agents.learning_path.generate_learning_path_data`，可基于知识图谱、薄弱点和掌握度生成规则版学习路径。
- `POST /agent/v1/memory/compress`：已接入异步承接函数，可生成对话摘要、提取基础 `blind_spot` 事实，并尝试向量化后写入 `user_memory_v1_1024`。
- `POST /agent/v1/resources/generate`：已接入 `agents.resources`，支持 202 接收、后台任务、completed/failed webhook payload、retry/backoff 和发送失败兜底。
- `GET /agent/v1/health`：已从硬编码占位改为基础健康检查，支持 Qdrant client 探针和服务 uptime。
- 工程观测：Health 探针失败、资源生成失败和 webhook 最终失败会记录 warning；当前不引入第三方日志依赖。
- AI 供应商边界：`core.ai` 已定义 embedding/reranker/chat provider 协议、未配置实现和注入式 factory；`core.config` 已预留 `.env` 配置字段。
- AI 供应商边界：`core.ai` 已提供 OpenAI-compatible embedding provider、未配置 reranker/chat 占位实现和注入式 factory；`core.config` 已预留 `.env` 配置字段。
- AI 供应商边界：`core.ai` 已提供 OpenAI-compatible embedding provider、reranker provider 和 chat provider。
- 配置示例：新增 `.env.example`，对 AI/Qdrant 字段逐项添加注释；当前不引入 `config.json`，避免 JSON 注释和读取逻辑分叉。
- Qdrant 配置：collection 名称和向量维度已配置化，默认使用 BGE-M3 对应的 `1024` 维和 `*_v1_1024` collection 命名。
- AI 检索边界：`memory.vector_store.QdrantVectorStore` 已按 settings 封装 `user_memory` / `course_knowledge` 查询；`memory.tutoring_retrieval.build_tutoring_retrieval_context_with_ai` 可注入 embedding provider 和 vector store，失败时降级为空检索上下文并记录 warning。
- Prompt 边界：`prompts.tutoring.build_tutoring_messages` 已将 tutoring request + retrieval context 转换为 provider-neutral `ChatMessage` 列表。
- `POST /agent/v1/tutoring/chat`：已在 API 主路径接入异步 retrieval context 构建和 chat provider 调用；首个 `chunk` 仍立即走规则版，若模型可用则追加一个模型生成 `chunk`，后续结构化事件继续沿用规则版。
- `POST /agent/v1/tutoring/chat`：为避免首包被 embedding/Qdrant 卡住，当前会先立即发送规则版首个 `chunk`，再等待 retrieval 并发送后续 `knowledge_points / suggestion / done` 事件。
- `POST /agent/v1/tutoring/chat`：retrieval 候选现可在进入 prompt 前由 reranker 按相关性重排；未配置 reranker 时保持原始向量召回顺序。
- `POST /agent/v1/tutoring/chat`：模型回答现可附带 `<agent_result>` JSON 块，agent 层负责解析并在不改变 SSE 契约的前提下覆盖 `knowledge_points / suggestion`；若输出缺失或解析失败，则自动回退到规则版结构化结果。
- `POST /agent/v1/tutoring/chat`：tutoring 运行态已进一步收口为单一内部结果对象，当前与 Backend/SQL/具体模型 SDK 已基本解耦；剩余耦合点主要是模型结构化输出仍依赖 prompt 约定的 `<agent_result>` 标签格式。
- Schema 契约：已用 `Literal` 收紧 Health status、Memory role/fact_type、Assessment question type/difficulty、LearningPath node status；Health 路由已声明 response model，OpenAPI 不再为空 schema。
- `POST /agent/v1/memory/compress`：已接入异步持久化承接函数，当前会对 `extracted_facts` 做向量化并写入 `user_memory_v1_1024`；`new_summary` 暂不写入向量库。
- `POST /agent/v1/memory/compress`：Qdrant store 初始化与 upsert 已纳入 best-effort 降级路径；Qdrant 慢时通过 `asyncio.to_thread` 执行同步 upsert，避免阻塞事件循环。

## 历史完成详情

- `POST /agent/v1/profile/generate`：规则版已完成，基于练习历史、资源使用和近期活跃度生成基础画像。
- `POST /agent/v1/evaluation/generate`：规则版已完成，基于学习进度、练习结果和资源使用生成评估摘要。
- `POST /agent/v1/assessment/evaluate`：规则版已完成，基于标准答案和用户答案生成判分与诊断。
- `GET /agent/v1/health`：健康检查接口已完成基础设施探针，暂不包含真实模型加载状态。
- 当前所有规则版业务实现均不接 LLM、不写 SQL、不做语义检索；后续可按接口逐步替换为 AgentScope / RAG / LLM 实现。

## 最近测试结果

- `./.venv/bin/pytest tests/test_assessment_agent.py`：6 passed
- `./.venv/bin/pytest tests/test_learning_path_agent.py`：3 passed
- `./.venv/bin/pytest tests/test_memory_agent.py`：3 passed
- `./.venv/bin/pytest tests/test_resources_agent.py`：6 passed
- `./.venv/bin/pytest tests/test_schema_contracts.py`：17 passed
- `./.venv/bin/pytest tests/test_openapi_alignment.py`：15 passed
- `./.venv/bin/pytest tests/test_tutoring_agent.py tests/test_tutoring_api.py tests/test_schema_contracts.py tests/test_openapi_alignment.py`：33 passed，存在既有 Pydantic v2 deprecation warning
- `./.venv/bin/pytest tests/test_tutoring_retrieval.py tests/test_tutoring_agent.py tests/test_tutoring_api.py tests/test_schema_contracts.py tests/test_openapi_alignment.py`：36 passed，存在既有 Pydantic v2 deprecation warning
- `./.venv/bin/pytest tests/test_health.py tests/test_resources_agent.py tests/test_schema_contracts.py tests/test_openapi_alignment.py`：42 passed，存在既有 Pydantic v2 deprecation warning
- `./.venv/bin/pytest tests/test_health.py tests/test_assessment_agent.py tests/test_learning_path_agent.py tests/test_memory_agent.py tests/test_schema_contracts.py tests/test_openapi_alignment.py`：54 passed，存在既有 Pydantic v2 deprecation warning
- `./.venv/bin/pytest tests/test_core_config.py tests/test_ai_providers.py tests/test_health.py tests/test_resources_agent.py`：15 passed
- `./.venv/bin/pytest tests/test_openapi_alignment.py`：15 passed
- `./.venv/bin/pytest`：79 passed
- `./.venv/bin/pytest tests/test_core_config.py tests/test_ai_providers.py tests/test_vector_store.py tests/test_tutoring_retrieval.py tests/test_tutoring_prompts.py`：11 passed
- `./.venv/bin/pytest tests/test_tutoring_agent.py tests/test_tutoring_api.py tests/test_tutoring_retrieval.py tests/test_tutoring_prompts.py`：8 passed
- `./.venv/bin/pytest tests/test_openapi_alignment.py`：15 passed
- `./.venv/bin/pytest tests/test_core_config.py tests/test_ai_providers.py tests/test_qdrant.py`：5 passed
- `./.venv/bin/pytest tests/test_openapi_alignment.py`：15 passed
- `./.venv/bin/pytest`：87 passed
- `./.venv/bin/pytest tests/test_vector_store.py tests/test_tutoring_retrieval.py tests/test_qdrant.py`：7 passed
- `./.venv/bin/pytest tests/test_ai_providers.py -vv`：4 passed
- `./.venv/bin/pytest tests/test_memory_agent.py tests/test_user_memory_store.py`：8 passed
- `./.venv/bin/pytest tests/test_memory_agent.py tests/test_user_memory_store.py tests/test_openapi_alignment.py`：23 passed
- `./.venv/bin/pytest`：94 passed
- `./.venv/bin/pytest tests/test_tutoring_api.py`：4 passed
- `./.venv/bin/pytest tests/test_tutoring_api.py tests/test_tutoring_agent.py tests/test_tutoring_retrieval.py tests/test_openapi_alignment.py`：25 passed
- `./.venv/bin/pytest`：97 passed
- `./.venv/bin/pytest tests/test_tutoring_api.py tests/test_memory_agent.py tests/test_user_memory_store.py`：15 passed
- `./.venv/bin/pytest tests/test_tutoring_api.py tests/test_memory_agent.py tests/test_user_memory_store.py tests/test_openapi_alignment.py`：30 passed
- `./.venv/bin/pytest`：100 passed
- `./.venv/bin/pytest tests/test_ai_providers.py tests/test_tutoring_api.py`：13 passed
- `./.venv/bin/pytest tests/test_ai_providers.py tests/test_tutoring_api.py tests/test_tutoring_prompts.py tests/test_openapi_alignment.py`：29 passed
- `./.venv/bin/pytest`：104 passed
- `./.venv/bin/pytest tests/test_ai_providers.py tests/test_tutoring_retrieval.py`：15 passed
- `./.venv/bin/pytest tests/test_ai_providers.py tests/test_tutoring_retrieval.py tests/test_tutoring_api.py`：22 passed
- `./.venv/bin/pytest tests/test_ai_providers.py tests/test_tutoring_retrieval.py tests/test_tutoring_api.py tests/test_tutoring_prompts.py tests/test_openapi_alignment.py`：38 passed
- `./.venv/bin/pytest`：109 passed
- `./.venv/bin/pytest tests/test_tutoring_agent.py tests/test_tutoring_api.py tests/test_tutoring_prompts.py`：14 passed
- `./.venv/bin/pytest tests/test_openapi_alignment.py tests/test_tutoring_agent.py tests/test_tutoring_api.py tests/test_tutoring_prompts.py`：29 passed
- `./.venv/bin/pytest`：113 passed
- `./.venv/bin/pytest tests/test_tutoring_agent.py tests/test_tutoring_api.py -q`：14 passed
- `./.venv/bin/pytest tests/test_openapi_alignment.py tests/test_tutoring_agent.py tests/test_tutoring_api.py tests/test_tutoring_prompts.py`：30 passed
- `./.venv/bin/pytest`：114 passed

## 下一步建议

- 首选：把 tutoring 的模型结构化输出从字符串标签约定进一步收拢为更明确的 provider-neutral 内部协议，减少对具体提示词格式的耦合。
- 次选：扩展长期记忆事实类型，不再只覆盖 `blind_spot`，补 `mastered_point`、`cognitive_preference` 等更稳定的学习特征。
