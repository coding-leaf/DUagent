# Agent Service AI 编排审计

本文记录 `agent_service` 当前 AI / AgentScope / RAG 编排现状，并给出后续多智能体升级边界。

本文不是接口契约来源。接口契约以以下文件为准：

- `../docs/20-agent-api/Agent-Service.openapi.json`
- `../docs/20-agent-api/API_Agent内部接口规范.md`

## 当前结论

EduAgent 后续架构方向调整为：**多智能体优先，AgentScope 可落地能力优先**。

这不意味着所有接口都强行改成多 Agent。当前判断是：

- 对话、出题、资源生成适合 Agent / tool / workflow 编排。
- 画像、评价、学习路径、记忆压缩、测验判分更适合 structured output + 规则保护。
- API 和 schema 不承载 AgentScope 细节，AgentScope 能力只落在 `agents/`、`memory/`、`tools/`、`prompts/`、`core/` 内部。

## 总体分层

| 层 | 当前职责 | 主要文件 |
|---|---|---|
| API 路由 | FastAPI 路由、参数接收、响应包装、SSE、后台任务协议 | `api/v1/*.py` |
| Schema | Pydantic 请求/响应模型，对齐 OpenAPI | `schemas/*.py` |
| Agent 编排 | 规则逻辑、LLM 调用、ReActAgent、fallback 链 | `agents/*.py` |
| Prompt | system/user message、ReAct 指令、结构化输出要求 | `prompts/*.py` |
| Memory/RAG | Qdrant 检索、课程知识、用户长期记忆 | `memory/*.py` |
| Tools | 知识摄入、readiness、smoke、Agent 工具封装 | `tools/*.py`、`agents/*_tools.py` |
| Core | 配置、AgentScope provider、Studio init、日志 | `core/*.py`、`main.py` |

## AgentScope 能力使用现状

| 能力 | 当前状态 | 说明 |
|---|---|---|
| ChatModel / Formatter | 已接入 | `core/ai.py` 封装 AgentScope OpenAIChatModel + DeepSeekChatFormatter |
| Embedding | 已接入 | 课程知识和用户记忆检索使用 embedding provider |
| structured_model | 已覆盖主要 LLM 接口 | 用于 tutoring、profile、evaluation、assessment、learning-path、memory 等结构化输出路径 |
| ReActAgent | 已用于 2 条主链路 | `tutoring/chat`、`assessment/generate-questions` |
| Toolkit / ToolResponse | 已用于 ReAct 链路 | tutoring 工具检索课程知识和用户记忆；assessment 工具检索课程知识并校验题目格式 |
| Reader / PDFReader | 已用于知识摄入 | PDF/MD/TXT 到 chunks，再写入 Qdrant |
| Studio init | 最小接入 | FastAPI lifespan best-effort 调用 `agentscope.init(...)` |
| Workflow / multi-agent | 尚未实现 | 下一阶段优先用于 `resources/generate` |

## 接口编排总表

| 接口 | 当前编排 | RAG/Memory | AgentScope 形态 | 后续判断 |
|---|---|---|---|---|
| `GET /agent/v1/health` | 确定性探针 | Qdrant 探针 | 无 LLM | 不做 Agent 化 |
| `POST /agent/v1/tutoring/chat` | ReActAgent -> structured/chat JSON -> rule-based | 课程知识 + 用户记忆 | ReActAgent + Toolkit + structured_model | 保持主 Agent 链路，后续可强化 Studio trace |
| `POST /agent/v1/profile/generate` | structured_model enrichment -> rule-based | 无 | structured_model | 不做多 Agent，保持规则保护 |
| `POST /agent/v1/evaluation/generate` | structured_model enrichment -> rule-based | 无 | structured_model | 不做多 Agent，保持表格白名单 |
| `POST /agent/v1/assessment/evaluate` | 规则判分 + structured_model 诊断增强 -> rule-based | 无 | structured_model | 不做 ReAct，判分必须规则确定 |
| `POST /agent/v1/assessment/generate-questions` | ReActAgent -> structured_model -> skeleton fallback | 课程知识 | ReActAgent + Toolkit + structured_model | 已是多步 Agent 链路，后续只做质量修正 |
| `POST /agent/v1/learning-path/generate` | structured_model -> rule-based | 无 | structured_model | 不做多 Agent，核心是节点白名单和排序 |
| `POST /agent/v1/resources/generate` | 后台任务 + LLM/RAG 并行生成 -> skeleton fallback -> webhook | 课程知识 | 普通 LLM + RAG | 下一阶段多智能体主目标 |
| `POST /agent/v1/memory/compress` | structured_model fact/summary -> rule-based -> Qdrant best-effort | 写入用户记忆 | structured_model | 暂不迁移 AgentScope Memory，保留产品边界 |

## 多智能体升级原则

1. **先用 AgentScope 能稳定实现的能力**：ReActAgent、Toolkit、structured_model、workflow/planning、Studio/observability。
2. **不修改 OpenAPI 表达 Agent 内部结构**：多智能体只是服务内部实现，返回结构保持契约一致。
3. **只在任务天然可分解时使用 multi-agent**：资源生成、复杂辅导、出题自检适合；统计转画像不适合。
4. **所有 Agent 链路必须有降级链**：AgentScope workflow/ReAct 失败后回落到当前 LLM 或规则版路径。
5. **Backend 结构化输入优先于 Qdrant 旧记忆**：Qdrant 是语义增强，不是 SQL 当前态来源。

## 下一阶段主线：resources/generate Workflow

`resources/generate` 是最适合升级为多智能体 workflow 的接口，因为它天然拆成四类产物：

- `document`
- `mindmap`
- `reading`
- `code`

建议目标架构：

```text
ResourceWorkflowOrchestrator
  -> Planner: 解析请求、课程上下文、目标资源类型
  -> DocumentAgent: 生成讲义/总结文档
  -> MindmapAgent: 生成导图文本或 Mermaid
  -> ReadingAgent: 生成延伸阅读材料
  -> CodeAgent: 生成代码示例
  -> Aggregator: 校验字段、排序、去重、统一 fallback
```

第一阶段不要求一次接入复杂 AgentScope workflow API。可先在 `agents/resources.py` 内建立稳定的内部编排边界，再用本地安装包 introspection 和官方文档确认 AgentScope workflow 能力后替换实现。

## 当前不建议继续做的事

- 不把 `profile/generate`、`evaluation/generate`、`learning-path/generate` 强行改成多 Agent。
- 不把 AgentScope 内部对象泄漏到 `schemas/` 或 OpenAPI。
- 不继续维护过时的历史问题清单作为当前待办。
- 不围绕 Qdrant local 文件锁做大范围补丁；部署侧应优先考虑 server 模式。

