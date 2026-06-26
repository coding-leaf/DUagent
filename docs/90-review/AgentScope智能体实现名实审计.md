# AgentScope 智能体实现名实审计

> 审计日期：2026-06-26
> 审计范围：`agent_service/` 智能体相关实现、AgentScope 使用边界、智能体命名与真实实现差异。
> 审计目的：为后续重新设计 Agent 编排与 AgentScope 化改造提供事实底稿，不直接给出完整重构方案。

---

## 1. 总结论

当前 `agent_service` 不是纯手写 Python，也不是完整 AgentScope 原生多智能体系统。更准确的定位是：

```text
稳定 FastAPI 契约
  + 手写业务编排 / fallback
  + 局部 AgentScope ReActAgent / Toolkit / fanout_pipeline / Reader / QdrantStore
  + 大量普通 structured output 调用
```

因此，当前代码中“Agent”一词存在明显名实不一致：

- 有些是真实 AgentScope Agent，例如 `TutorReActAgent`、`QuestionGeneratorReActAgent` 内部封装了 `agentscope.agent.ReActAgent`。
- 有些是 AgentScope pipeline 的适配包装，例如 `resources_workflow._PipelineResourceAgent` 继承 `AgentBase`，但实际工作仍委托给项目自定义 `DocumentAgent` / `CodeAgent` / `ReadingAgent` / `MindmapAgent`。
- 有些只是项目内部角色名或规则函数，例如 `tutoring_strategy.py` 的 StrategyAgent 实际是纯规则选择器。
- 有些只是普通 LLM structured output 调用，例如 `profile`、`evaluation`、`learning_path`、`memory` 等链路。
- 有些能力虽然本地 AgentScope 1.0.20 已支持，但当前未系统使用，例如 `KnowledgeBase`、long-term memory、PlanNotebook、parallel tool calls、compression config、完整 Studio trace。

后续重设计时，应先把“是否是 AgentScope 原生能力”与“是否是业务角色命名”分开。否则容易把手写 workflow、规则 guard、普通 LLM 调用误认为已完成多智能体架构。

---

## 2. 审计口径

本文按以下类型标注当前实现：

| 类型 | 含义 |
|---|---|
| 真实 AgentScope Agent | 直接构造并调用 AgentScope agent，例如 `ReActAgent` |
| AgentScope 包装层 | 使用 AgentScope pipeline / base class 包装项目自定义逻辑 |
| 手写 workflow | 由普通 Python 函数、dataclass、asyncio、fallback 链完成流程控制 |
| 普通 structured output | 通过 `chat_provider.complete(... structured_model=...)` 约束输出，但不是 Agent 编排 |
| 纯规则伪 Agent | 文件名或注释称为 Agent，但实现是规则函数，无 LLM、无 AgentScope |
| 基础设施适配 | AgentScope model、formatter、reader、QdrantStore 等底层封装 |

---

## 3. 关键入口地图

### 3.1 API 入口

| 文件 | 入口 | 当前职责 | 审计结论 |
|---|---|---|---|
| `agent_service/api/v1/tutoring.py` | `tutoring_chat()` | 返回 SSE，委托 `generate_tutoring_sse_events()` | 主接口较薄；`retrieval_probe()` 是调试探针，直接接触 provider / vector store |
| `agent_service/api/v1/assessment.py` | `generate_questions()` / `evaluate_assessment()` | 调用出题和批改 agent 层函数 | API 层较薄 |
| `agent_service/api/v1/resources.py` | `generate_resources()` | 202 接收任务，BackgroundTasks 执行资源生成 | API 层较薄 |
| `agent_service/api/v1/profile.py` | `generate_profile()` | 规则画像 + LLM enrichment | 普通 structured output，不是 Agent 编排 |
| `agent_service/api/v1/evaluation.py` | `generate_evaluation()` | 规则评价 + LLM enrichment | 普通 structured output，不是 Agent 编排 |
| `agent_service/api/v1/learning_path.py` | `generate_learning_path()` | LLM 路径生成 + 规则 fallback | 普通 structured output，不是 Agent 编排 |
| `agent_service/api/v1/memory.py` | `compress_memory()` | 记忆压缩与 Qdrant best-effort 写入 | 普通 structured output + 手写 memory persistence |

API 层整体没有泄漏 AgentScope 对象到 public schema，这一点符合边界要求。但 API 名义上的“智能体能力”主要来自 `agents/` 层，不能只看接口名判断 Agent 化程度。

---

## 4. `agents/` 逐文件代码地图

### 4.1 Tutoring 链路

#### `agents/tutoring.py`

类型：手写 workflow + ReAct 适配调用 + SSE 事件包装

关键职责：

- `generate_tutoring_sse_events()` 是 tutoring 主链路入口。
- 内部完成 provider 初始化、retrieval context 构建、策略选择、ReAct 调用、重试、fallback、SSE 事件输出。
- `parse_tutoring_model_response()` 仍保留 JSON、markdown JSON、`<agent_result>` tag 和 raw text 解析链。

名实判断：

- 这是 tutoring 的真实业务编排入口，但它本身不是 AgentScope Agent。
- 它调用 AgentScope ReAct 适配层，但大量控制流仍是手写 Python。
- 解析链存在历史兼容逻辑，说明 structured output 尚未完全替代 prompt/tag 约定。

对后续设计的影响：

- 适合保留为 API 到内部 Agent 编排的稳定 adapter。
- 若后续 C 设计要重构，应先定义 tutoring 内部结果对象和 agent graph，再逐步替换当前手写流程。

#### `agents/tutoring_react.py`

类型：真实 AgentScope Agent 适配器

关键职责：

- `TutorReActAgent` 内部构造 `agentscope.agent.ReActAgent`。
- 使用 `InMemoryMemory`、`Msg`、`Toolkit`、可选 `knowledge`。
- 尝试传入 `TutoringStructuredOutput` 作为 `structured_model`。

名实判断：

- 这是当前 tutoring 链路中最明确的 AgentScope Agent 实现。
- 但当前调用处没有实际传入 AgentScope `KnowledgeBase`。
- `long_term_memory`、`plan_notebook`、`parallel_tool_calls`、`compression_config` 等 AgentScope 1.0.20 能力未使用。

对后续设计的影响：

- 可以作为后续 AgentScope 化的保留起点。
- 需要区分 short-term memory、Backend 画像、Qdrant user memory，避免状态来源混乱。

#### `agents/tutoring_react_flow.py`

类型：手写胶水层

关键职责：

- 把 `TutoringChatRequest` 和 `TutoringRetrievalContext` 拼成 ReAct user message。
- 条件性构建 tutoring toolkit。
- 调用 `TutorReActAgent.generate()`，再把 metadata / text 转回项目内部 `TutoringModelResponse`。

名实判断：

- 它不是 AgentScope workflow，只是项目侧输入输出转换层。
- 当前 RAG 上下文仍主要由项目手写检索提前注入，AgentScope `knowledge` 没有成为主路径。

对后续设计的影响：

- 可演进为正式的 `TutoringAgentAdapter`。
- 若使用 AgentScope Knowledge，应在这里或新的 adapter 中完成 request → Msg / Knowledge / Tool 的转换。

#### `agents/tutoring_tools.py`

类型：AgentScope Toolkit

关键职责：

- 构建 `Toolkit`。
- 注册 `retrieve_course_knowledge` 和 `retrieve_user_memory`。
- 工具内部仍调用项目 embedding provider / vector store / user memory store。

名实判断：

- 这是 AgentScope tool 能力的真实使用。
- 但 retrieval 逻辑不是 AgentScope Knowledge，而是项目自定义 Qdrant 检索封装。

对后续设计的影响：

- 如果后续采用 Agentic RAG，可以继续扩展 Toolkit。
- 如果采用 Generic RAG，应评估 `knowledge` 参数而不是只依赖工具。

#### `agents/tutoring_strategy.py`

类型：纯规则伪 Agent

关键职责：

- `select_tutoring_strategy_by_rule()` 根据 guidance level 和短消息规则选择策略。

名实判断：

- 文件注释称 `Tutoring StrategyAgent`，但没有 LLM 调用、没有 AgentScope、没有 tool use。
- 它是 rule selector，不应在架构文档里称为已实现 AgentScope StrategyAgent。

对后续设计的影响：

- 建议后续重命名为 `tutoring_strategy_rules.py` 或明确标注为 rule fallback。
- 若设计真正 `StrategyAgent`，应定义策略输出 schema 和 fallback 关系。

#### `agents/tutoring_response_critic.py`

类型：纯规则 guard / critic

关键职责：

- `evaluate_tutoring_response_by_rule()` 检查空回答、澄清问题、相关性。

名实判断：

- 这是规则 critic，不是 AgentScope critic agent。
- 当前测试文件说明 fast path 中 “Guard 已从链路移除”，因此不能把它视为 tutoring 主链路已启用的 ResponseCriticAgent。

对后续设计的影响：

- 可作为未来 `ResponseCriticAgent` 的规则 fallback。
- 后续应先确认它是否重新进入主链路，再决定是否 AgentScope 化。

### 4.2 Assessment 链路

#### `agents/assessment.py`

类型：手写 workflow + structured output + ReAct 适配调用 + 规则 fallback

关键职责：

- `evaluate_assessment_data()` 负责确定性判分。
- `evaluate_assessment_with_llm()` 用 structured output 增强解释和诊断。
- `generate_questions_with_llm()` 普通 LLM structured output 出题。
- `generate_questions_with_agent()` 是出题主编排：RAG context → ReActAgent → quality review → LLM fallback → skeleton fallback。

名实判断：

- 出题主链路确实优先尝试 ReActAgent。
- 但质量门禁、fallback、题目 coercion、知识上下文构造仍是手写 Python。
- 批改链路不是 Agent 编排，且不应为了多 Agent 化改变规则判分真值。

对后续设计的影响：

- 出题适合作为多 Agent 进一步演进候选。
- 批改应保留 deterministic 主体，只允许 LLM / Agent 做解释增强。

#### `agents/assessment_react.py`

类型：真实 AgentScope Agent 适配器

关键职责：

- `QuestionGeneratorReActAgent` 内部构造 `ReActAgent`。
- 接收 toolkit、memory、formatter、chat model。
- 输出 raw text 后仍调用 `_parse_question_payload()`。

名实判断：

- 这是 assessment 出题链路中的真实 AgentScope Agent。
- 但未使用 AgentScope structured output；输出仍走项目 JSON parser。

对后续设计的影响：

- 后续可优先把出题 ReAct 输出改为可靠 structured output。
- 可引入 QuestionCritic / KnowledgeGuard / DifficultyBalancer，但需要区分规则版与真实 AgentScope agent。

#### `agents/assessment_tools.py`

类型：AgentScope Toolkit

关键职责：

- 注册 `retrieve_course_knowledge`。
- 注册 `validate_question_format`。

名实判断：

- 真实使用 AgentScope Toolkit。
- 工具内检索仍是项目自定义 vector store，不是 AgentScope Knowledge。

#### `agents/assessment_quality.py`

类型：手写 quality workflow + 普通 LLM judge + 规则 gate

关键职责：

- `review_generated_questions()` 执行基础质量、答案一致性、知识点检查、LLM critic 等。

名实判断：

- 这是出题质量门禁，但不是 AgentScope Agent。
- 如果文档称 QuestionCriticAgent 已实现，需要注明它目前是规则/LLM 函数，不是 ReActAgent 或 AgentScope workflow。

对后续设计的影响：

- 适合作为未来 QuestionCriticAgent 的业务规则来源。
- 需要先定义 critic 输出、repair 策略和 fallback 规则。

### 4.3 Resources 链路

#### `agents/resources.py`

类型：异步任务 workflow 入口 + fallback 链

关键职责：

- `accept_resource_generation()` 返回 202 任务响应。
- `run_resource_generation_task()` 执行后台任务并 webhook 回调。
- `_try_multi_agent_workflow()` 优先尝试 resources workflow。
- `generate_resources_with_llm()` 保留旧普通 LLM 资源生成 fallback。

名实判断：

- 这是 resources 的真实任务编排入口，但不是 AgentScope workflow 本体。
- 它决定降级链：multi-agent workflow → 旧 LLM 生成 → skeleton → failed webhook。

对后续设计的影响：

- 应保留异步协议和 webhook 边界。
- 重构时不要把 AgentScope 内部字段泄漏到 webhook payload。

#### `agents/resources_workflow.py`

类型：手写 workflow + AgentScope fanout pipeline 包装

关键职责：

- `run_multi_agent_resource_workflow()` 编排 Planner、ResourceAgents、Aggregator。
- `_run_resource_agents_with_agentscope_pipeline()` 使用 `agentscope.pipeline.fanout_pipeline`。
- `_PipelineResourceAgent(AgentBase)` 把项目自定义 `ResourceAgent` 包装为 AgentScope pipeline 可调用对象。

名实判断：

- 这是当前 resources “多智能体”最核心的位置。
- 但 AgentScope 只承担 fanout 调度；Planner、Worker 实际生成、Critic、Aggregator 都是项目手写逻辑。
- `_PipelineResourceAgent` 继承 `AgentBase`，但 `reply()` 内部只是调用 `_run_single_agent_with_fallback()`，再把 dataclass JSON 化成 `Msg`。
- 这应表述为“本地 workflow 已建立，并局部接入 AgentScope fanout pipeline”，不应表述为完整 AgentScope 原生 workflow。

对后续设计的影响：

- 后续 C 设计如果重构 resources，应优先决定：保留当前本地 orchestrator，还是引入 AgentScope planning / PlanNotebook / 更完整 trace。
- 当前文件 322 行，已经接近项目建议上限，继续堆新能力前应拆分。

#### `agents/resources_agents.py`

类型：项目自定义 ResourceAgent Protocol + 普通 LLM 生成类

关键职责：

- 定义 `ResourceAgent` Protocol 和 `ResourceResult`。
- 实现 `DocumentAgent`、`CodeAgent`、`ReadingAgent`、`MindmapAgent`。
- 每个 agent 基本通过 `chat_provider.complete()` 生成 JSON，再手写解析和 fallback。

名实判断：

- 类名叫 Agent，但不是 AgentScope Agent。
- 它们是业务 worker 类，当前通过 `_PipelineResourceAgent` 才进入 AgentScope fanout。
- JSON parser 和 fallback 逻辑较重，说明资源生成仍强依赖手写稳态保护。

对后续设计的影响：

- 可保留业务能力，但建议在后续设计中改称 `ResourceWorker` 或明确区分 `ResourceAgentAdapter`。
- 若改为真实 AgentScope Agent，应重新定义每个资源 agent 的 Msg 输入、structured output 和 tool/knowledge 边界。

#### `agents/resources_plan.py`

类型：手写 planner 数据结构 + 普通 LLM planner + 规则 fallback

关键职责：

- 定义 `ResourcePlan`、`ResourceTaskSpec`。
- `generate_plan_with_llm()` 通过 `chat_provider.complete()` 生成计划。
- `build_rule_based_plan()` 兜底。

名实判断：

- 这是 Planner 角色，但不是 AgentScope planning / PlanNotebook。
- 当前计划生成仍是普通 LLM JSON 解析。

对后续设计的影响：

- 是未来 AgentScope planning 的主要替换候选。
- 重构前应先确定 ResourcePlan 是否作为项目内部稳定契约保留。

#### `agents/resources_critic.py`

类型：规则 critic + 普通 LLM critic

关键职责：

- `ResourceCriticAgent.review()` 先规则审查，再可选 LLM 审查。

名实判断：

- 类名叫 Agent，但不是 AgentScope Agent。
- 当前 critic 是本地类，不参与 AgentScope pipeline，也没有 tool/memory/state。

对后续设计的影响：

- 可作为未来 AgentScope critic agent 的业务逻辑来源。
- 当前命名容易造成“CriticAgent 已 AgentScope 化”的误解。

#### `agents/resources_aggregator.py`

类型：手写 aggregator

关键职责：

- 合并 ResourceResult。
- 过滤 skeleton fallback。
- 保证 webhook payload 不泄漏内部字段。

名实判断：

- Aggregator 是手写函数，不是 AgentScope agent。
- 这类确定性聚合逻辑未必需要 AgentScope 化，但名称和架构图应明确它是 deterministic aggregator。

#### `agents/resources_mermaid.py`

类型：普通 LLM helper + 手写 Mermaid 校验 / fallback

关键职责：

- 生成 Mermaid。
- Mermaid 无效时退到 markdown tree 或 skeleton。

名实判断：

- 不是 AgentScope tool 或 Agent。
- 可作为未来 `generate_diagram` tool 的候选。

### 4.4 其他 structured output 链路

#### `agents/profile.py`

类型：规则计算 + 普通 structured output enrichment

名实判断：

- 不是 AgentScope Agent。
- 当前只使用 `chat_provider.complete(... structured_model=...)` 作为增强。
- 适合保持规则保护，不应在现阶段强行称为多 Agent。

#### `agents/evaluation.py`

类型：规则表格生成 + 普通 structured output enrichment

名实判断：

- 不是 AgentScope Agent。
- 白名单和范围保护是主价值。

#### `agents/learning_path.py`

类型：普通 structured output + 图谱节点白名单 + 规则 fallback

名实判断：

- 不是 AgentScope Agent。
- 核心是节点约束，不应让 Agent 发明图谱节点。

#### `agents/memory.py`

类型：普通 structured output + 手写 Qdrant best-effort persistence

名实判断：

- 不是 AgentScope Memory。
- 当前 memory/compress 明确由项目 schema 和 Qdrant user memory collection 管理。
- AgentScope long-term memory 尚未接入。

---

## 5. `memory/` 与 RAG 实现地图

### `memory/course_knowledge_ingestion.py`

类型：AgentScope Reader 基础设施适配

当前使用：

- `agentscope.rag.PDFReader`
- `agentscope.rag.TextReader`

名实判断：

- 这里是真实 AgentScope Reader 使用。
- 但输出被转换为项目自定义 `CourseKnowledgeChunk`，后续写入仍由项目逻辑控制。

### `memory/qdrant_store.py`

类型：AgentScope QdrantStore 基础设施适配

当前使用：

- `agentscope.rag.QdrantStore`

名实判断：

- 这是 AgentScope Store 层使用。
- 但当前没有把 `SimpleKnowledge` / `KnowledgeBase` 作为主要 RAG 抽象接入 ReActAgent。

### `memory/tutoring_retrieval.py`

类型：手写 hybrid retrieval

名实判断：

- 课程知识、用户记忆、KG 节点召回主要由项目代码完成。
- 不是 AgentScope Generic RAG，也不是 Agentic RAG。

### `memory/user_memory_store.py`

类型：手写 user memory vector persistence

名实判断：

- 不是 AgentScope LongTermMemory。
- 当前更像产品级长期事实存储，Backend 画像仍应优先。

---

## 6. `core/ai.py` AgentScope provider 地图

类型：AgentScope model / formatter / embedding 基础设施适配

当前使用：

- `OpenAIChatModel`
- `DeepSeekChatFormatter`
- `OpenAITextEmbedding`
- `Msg`

关键事实：

- `AgentScopeChatProvider.complete()` 支持 `structured_model` 和 json mode。
- 许多业务链路通过这个 provider 获得 structured output，但这不等于它们是 Agent。
- provider 暴露了 `.model` 和 `.formatter`，供 ReActAgent 适配器使用。

本地 introspection 确认：

- AgentScope 版本：`1.0.20`
- `ReActAgent.__init__` 支持 `toolkit`、`memory`、`long_term_memory`、`long_term_memory_mode`、`parallel_tool_calls`、`knowledge`、`plan_notebook`、`compression_config` 等参数。
- 当前代码主要使用了 `toolkit`、`memory`、`knowledge` 参数位，其中 `knowledge` 参数位未实际成为主路径。

---

## 7. AgentScope 能力覆盖表

| AgentScope 能力 | 当前状态 | 主要位置 | 名实判断 |
|---|---|---|---|
| ChatModel / Formatter | 已接入 | `core/ai.py` | 基础设施适配，不代表业务 Agent 化 |
| Embedding | 已接入 | `core/ai.py` | 基础设施适配 |
| `structured_model` | 多链路使用 | `profile` / `evaluation` / `assessment` / `learning_path` / `memory` / `tutoring_react` | 是结构化输出能力，不等于多 Agent |
| `ReActAgent` | 局部接入 | `tutoring_react.py`、`assessment_react.py` | 真实 AgentScope Agent |
| `Toolkit` / `ToolResponse` | 局部接入 | `tutoring_tools.py`、`assessment_tools.py` | 真实工具能力，但工具内逻辑仍是项目自定义 |
| `fanout_pipeline` | 局部接入 | `resources_workflow.py` | AgentScope 调度层，worker 仍是本地类 |
| `AgentBase` | 适配包装 | `_PipelineResourceAgent` | 包装本地 ResourceAgent，不是完整原生业务 agent |
| Reader | 已接入 | `course_knowledge_ingestion.py` | 真实 Reader 使用 |
| `QdrantStore` | 已接入 | `qdrant_store.py` | Store 层使用 |
| `KnowledgeBase` / `SimpleKnowledge` | 未成主路径 | 无业务主链路 | 当前 RAG 仍是手写检索 |
| Long-term memory | 未接入 | 无 | 当前 user memory 是项目自定义 Qdrant facts |
| PlanNotebook / planning | 未接入 | 无 | resources planner 是普通 LLM + dataclass |
| parallel tool calls | 未接入 | 无 | ReActAgent 未启用 |
| compression config | 未接入 | 无 | memory/compress 是项目自定义 |
| Studio trace | 最小 init | `main.py` | 只有 best-effort init，缺少系统性 trace 设计 |
| evaluation hooks | 未接入 | 无 | 当前依赖单元测试和规则 critic |

---

## 8. 名实不一致重点清单

| 名称 / 文档说法 | 当前真实实现 | 风险 |
|---|---|---|
| `StrategyAgent` | 纯规则 selector | 容易误认为已实现策略智能体 |
| `ResponseCritic` | 规则 guard，且可能不在主链路 | 容易误认为 tutoring 已有审稿 Agent |
| `ResourceAgent` | Protocol + 本地 worker 类 | 容易误认为 Document/Code/Reading/Mindmap 是 AgentScope Agent |
| `ResourceCriticAgent` | 本地规则 + LLM critic 类 | 容易误认为 AgentScope critic |
| `ResourcePlanner` / LLM Planner | 普通 LLM JSON plan + dataclass | 不是 AgentScope PlanNotebook / planning |
| `resources Multi-Agent Workflow 已完成` | 本地 workflow + AgentScope fanout pipeline | 说法需要补充限定，否则过度宣称 |
| `structured_model 已覆盖` | structured output 能力覆盖 | 不等于 Agent 编排覆盖 |
| `RAG 已接入 AgentScope` | Reader / QdrantStore 接入，retrieval 主链路仍手写 | 容易误判 Knowledge 已接入 |

---

## 9. 后续设计注意事项

本文不直接给出完整 C 方案，但后续重设计建议先处理以下问题：

1. 先定义“真实 Agent”的判定标准
   - 是否直接继承 / 构造 AgentScope Agent。
   - 是否有明确 Msg 输入输出。
   - 是否有 tool / knowledge / memory / planning / trace 边界。
   - 是否能被 Studio 或结构化日志解释。

2. 把业务角色名和 AgentScope 实现名分开
   - `StrategyRuleSelector` 不应叫 `StrategyAgent`。
   - 本地 `ResourceWorker` 和 AgentScope `ResourceAgent` 应区分。
   - deterministic aggregator 不必伪装成 Agent。

3. 优先梳理 tutoring、assessment、resources 三条链路
   - tutoring：已有 ReActAgent，但 strategy / critic / memory / knowledge 需要重新界定。
   - assessment：已有 ReActAgent 和 Toolkit，但 quality gate 不是 AgentScope agent。
   - resources：已有 fanout pipeline，但 planner / worker / critic / aggregator 仍是本地编排。

4. 不把 D 作为当前目标
   - 不是回退到单 Agent 或只做效果调参。
   - 后续方向应以多智能体协作、AgentScope 能力落地、可观测编排为主。

5. 避免一次性全量重写
   - 当前 fallback 和契约保护是系统稳定性的基础。
   - AgentScope 化应以 adapter / internal contract 为边界逐步替换。

---

## 10. 建议的下一步输入

在用户完成 C 的初版设计前，建议先基于本文明确三件事：

1. 哪些现有“Agent”必须改名，避免继续误导。
2. 哪些现有本地 workflow 是稳定资产，应保留为 fallback。
3. 哪些链路要作为第一批 AgentScope 原生化目标。

这份审计建议作为后续设计文档的事实引用，而不是最终架构方案。
