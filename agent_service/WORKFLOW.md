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
| `POST /agent/v1/tutoring/chat` | 已完成 | 已完成 | 已完成 | 规则版事件流 + AI 检索/Prompt 边界已完成 | 已覆盖 | 输出 chunk / knowledge_points / suggestion / done；已有 embedding provider、Qdrant 检索适配和 prompt/messages 转换边界，暂不绑定真实模型 |
| `POST /agent/v1/profile/generate` | 已完成 | 已完成 | 已完成 | 规则版已完成 | 已覆盖 | 基于练习历史、资源使用、近期活跃度生成基础画像 |
| `POST /agent/v1/evaluation/generate` | 已完成 | 已完成 | 已完成 | 规则版已完成 | 已覆盖 | 基于学习进度、练习结果、资源使用生成表格和摘要 |
| `POST /agent/v1/assessment/evaluate` | 已完成 | 已完成 | 已完成 | 规则版已完成 | 已覆盖 | 基于标准答案和用户答案生成判分与诊断 |
| `POST /agent/v1/assessment/generate-questions` | 已完成 | 已完成 | 已完成 | 规则版骨架已完成 | 已覆盖 | 根据题型、数量、章节、知识点生成结构化占位题目 |
| `POST /agent/v1/learning-path/generate` | 已完成 | 已完成 | 已完成 | 规则版骨架已完成 | 已覆盖 | 基于知识图谱、薄弱点和掌握度生成结构化学习路径 |
| `POST /agent/v1/resources/generate` | 已完成 | 已完成 | 已完成 | 规则版闭环骨架已完成 | 已覆盖 | 202 + 后台任务 + webhook payload + retry/backoff 兜底，暂不接 LLM/Qdrant |
| `POST /agent/v1/memory/compress` | 已完成 | 已完成 | 已完成 | 规则版骨架已完成 | 已覆盖 | 生成对话摘要并提取基础薄弱点事实 |

## 当前焦点

- `POST /agent/v1/tutoring/chat` 已形成规则版 SSE 主链路，并新增 AI 检索主干：配置字段、provider 注入边界、Qdrant vector store、异步 retrieval context 构建、prompt/messages 转换。
- 下一步推荐优先增强 `POST /agent/v1/tutoring/chat`：接入真实 OpenAI-compatible embedding/reranker provider，或先把异步 retrieval builder 接入 API/Agent 调用路径。
- 非 AI 工程收口已推进：`GET /health` 增加 Qdrant 探针和 uptime；`resources/generate` webhook 增加 retry/backoff 和发送失败兜底。
- 非 AI 契约收口已推进：Health response model 已补齐，memory / assessment / learning-path / health 的规范枚举值已在 Pydantic schema 中收紧。
- 进入 AI 阶段前最后收尾已完成：清理 Pydantic v2 `class Config` warning；新增标准库 logger 边界；新增未绑定具体模型的 AI provider 可替换接口。

## 今日开发记录

- 已完成 AI 前置配置收口：`.env` 配置字段、`.env.example` 中文注释、Qdrant collection 名称与向量维度配置化、embedding/reranker/chat provider 边界定义。
- 已完成 tutoring AI 骨架：Qdrant vector store、检索上下文构建、provider-neutral prompt/messages 转换、规则版 SSE 与 AI 检索边界兼容。
- 已完成非 AI 工程收口：health 探针日志、resources webhook retry/backoff/失败日志、Pydantic v2 warning 清理。

## 向量化规划记录

- 用户侧向量化主对象：`user_memory`。优先存记忆压缩后的 `facts` 与阶段性 `episode_summary`，不把全量原始对话作为主向量库内容。
- 课程侧向量化主对象：`course_knowledge`。优先存书籍/PDF/讲义/知识点说明/例题解析等课程资料切片，并保留 `course_id`、`chapter`、`knowledge_point`、`source_type` 等 metadata。
- 当前模型规划：embedding 使用 `BAAI/bge-m3`，维度 `1024`；reranker 使用 `BAAI/bge-reranker-v2-m3`；接入方式按 OpenAI-compatible URL 设计。
- 当前 collection 规划：`user_memory_v1_1024`、`course_knowledge_v1_1024`，避免与旧 `768` 维 collection 语义混用。

## 近期完成摘要

- `POST /agent/v1/assessment/generate-questions`：已接入 `agents.assessment.generate_questions_data`，可生成规则版结构化占位题目。
- `POST /agent/v1/learning-path/generate`：已接入 `agents.learning_path.generate_learning_path_data`，可基于知识图谱、薄弱点和掌握度生成规则版学习路径。
- `POST /agent/v1/memory/compress`：已接入 `agents.memory.compress_memory_data`，可生成对话摘要并提取基础 `blind_spot` 事实，暂不写 Qdrant。
- `POST /agent/v1/resources/generate`：已接入 `agents.resources`，支持 202 接收、后台任务、completed/failed webhook payload、retry/backoff 和发送失败兜底。
- `GET /agent/v1/health`：已从硬编码占位改为基础健康检查，支持 Qdrant client 探针和服务 uptime。
- 工程观测：Health 探针失败、资源生成失败和 webhook 最终失败会记录 warning；当前不引入第三方日志依赖。
- AI 供应商边界：`core.ai` 已定义 embedding/reranker/chat provider 协议、未配置实现和注入式 factory；`core.config` 已预留 `.env` 配置字段。
- 配置示例：新增 `.env.example`，对 AI/Qdrant 字段逐项添加注释；当前不引入 `config.json`，避免 JSON 注释和读取逻辑分叉。
- Qdrant 配置：collection 名称和向量维度已配置化，默认使用 BGE-M3 对应的 `1024` 维和 `*_v1_1024` collection 命名。
- AI 检索边界：`memory.vector_store.QdrantVectorStore` 已封装 `user_memory` / `course_knowledge` 查询；`memory.tutoring_retrieval.build_tutoring_retrieval_context_with_ai` 可注入 embedding provider 和 vector store，失败时降级为空检索上下文并记录 warning。
- Prompt 边界：`prompts.tutoring.build_tutoring_messages` 已将 tutoring request + retrieval context 转换为 provider-neutral `ChatMessage` 列表。
- `POST /agent/v1/tutoring/chat`：已接入 `agents.tutoring.generate_tutoring_events`，可基于用户画像、薄弱点、会话摘要和 `memory.tutoring_retrieval.TutoringRetrievalContext` 输出规则版 SSE 事件序列。
- Schema 契约：已用 `Literal` 收紧 Health status、Memory role/fact_type、Assessment question type/difficulty、LearningPath node status；Health 路由已声明 response model，OpenAPI 不再为空 schema。

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

## 下一步建议

- 首选：实现一个具体 OpenAI-compatible embedding provider 和 reranker provider，并按 `.env` 中的 `1024` 维 / `*_v1_1024` collection 配置接入。
- 次选：将 `build_tutoring_retrieval_context_with_ai` 和 `build_tutoring_messages` 接入 tutoring Agent 的可选 AI 路径，未配置 provider 时继续走规则版输出。
