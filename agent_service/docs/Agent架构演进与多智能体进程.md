# Agent 架构演进与多智能体进程

本文用于承接 EduAgent 后续 Agent 架构讨论、候选升级评估和阶段推进记录。

本文不是接口契约来源，也不是具体实现计划。接口契约以以下文件为准：

- `../docs/20-agent-api/Agent-Service.openapi.json`
- `../docs/20-agent-api/API_Agent内部接口规范.md`

具体实现前仍需单独写 design / plan，并按 `AGENTS.md` 要求小步推进。

## 1. 当前架构目标

EduAgent 后续以 **多智能体架构优先** 为方向，同时坚持 **AgentScope 可落地能力优先**。

核心目标：

1. 让 Agent Service 从“LLM 调用集合”演进成“教育场景多 Agent 协作系统”。
2. 优先使用 AgentScope 已有能力，而不是自造不必要框架。
3. 保持 Backend / Frontend 契约稳定，多 Agent 只作为 Agent Service 内部实现。
4. 每条 Agent 链路必须保留 fallback，不能因为追求架构展示降低可用性。

## 2. 当前 Agent 化现状

| 能力 | 当前状态 | 说明 |
|---|---|---|
| `tutoring/chat` | 已 Agent 化 | ReActAgent + Toolkit + RAG + structured output + rule-based fallback |
| `assessment/generate-questions` | 已 Agent 化 | ReActAgent + 课程知识检索 + 题目格式校验 + structured output fallback |
| `profile/generate` | structured output | 统计数据转画像，不适合强行拆多 Agent |
| `evaluation/generate` | structured output | 表格和 summary 生成，重点是白名单与范围保护 |
| `assessment/evaluate` | 规则判分 + LLM 增强 | 判分必须规则确定，LLM 只做诊断解释 |
| `learning-path/generate` | structured output + 白名单 | 核心是图谱节点约束和排序 |
| `resources/generate` | Multi-Agent Workflow 已完成 | Planner → AgentScope fanout pipeline → ResourceAgent 并行生成 → Aggregator；保留旧 LLM / skeleton fallback |
| `memory/compress` | structured output + Qdrant 写入 | 暂不迁移 AgentScope Memory，先保留产品边界 |

## 3. 可升级架构候选

### 3.1 `resources/generate` Workflow / Multi-Agent

当前状态：P0 已完成第一阶段

理由：

- 资源类型天然拆分为 `document`、`mindmap`、`reading`、`code`。
- 当前已是异步任务，适合后台 workflow。
- 对竞赛/展示有明显架构价值：Planner + 多资源 Agent + Aggregator。
- 可保持现有 202 + webhook 契约不变。

已落地形态：

```text
ResourceWorkflowOrchestrator
  -> LLM Planner / rule-based planner fallback
  -> AgentScope fanout_pipeline
     -> DocumentAgent
     -> MindmapAgent
     -> ReadingAgent
     -> CodeAgent
  -> Aggregator
  -> webhook payload
```

第一阶段已完成：本地 workflow 边界已经建立，并通过 AgentScope `fanout_pipeline` 做并行 ResourceAgent 调度。它还不是完整 AgentScope Studio 可视化 workflow，也未接 PlanNotebook / 更复杂 planning API。

已落地能力：

- Planner 使用 LLM，并保留规则版 planner fallback。
- 单个 ResourceAgent 失败时做局部 fallback，不让一个资源失败拖垮整批资源。
- `mindmap` 资源统一优先输出 Mermaid，Mermaid 无效时局部回退到 markdown 树或 skeleton mindmap。
- Aggregator 使用 `is_skeleton` 判断资源是否可合并，避免把 `fallback_mermaid` 误判为全员失败。
- webhook payload 保持原有契约，不泄漏 `generated_by`、`fallback_reason`、`is_skeleton` 等内部字段。
- 降级链为：multi-agent → 旧 LLM parallel 资源生成 → skeleton → failed webhook。
- ResourceAgent JSON parser 已补强，可处理真实 LLM 输出中 `content` / `description` 字段的未转义换行。

后续只做增强，不再把 resources 作为“待启动主线”：

- 真实 Backend webhook 联调。
- 更完整的 AgentScope Studio trace 展示。
- 真实 LLM 输出质量评估和 prompt 迭代。
- 可选评估 PlanNotebook / 更复杂 planning API，前提是收益明确。

### 3.2 Tutoring 多 Agent 深化

推荐优先级：P1

当前 tutoring 已经有 ReActAgent，不建议短期重写主链路。可升级点在“专业分工”：

| 候选 Agent | 作用 | 价值 | 风险 |
|---|---|---|---|
| `StrategyAgent` | 判断是否需要图解、追问、练习建议 | 提升教学策略感 | 需要控制不要输出不稳定 |
| `RetrievalAgent` | 统一课程知识和用户记忆检索策略 | 让 RAG 更可解释 | 可能和现有 toolkit 重复 |
| `ResponseCritic` | 检查是否超出课程范围、是否过早给答案 | 提升教学质量 | 会增加延迟 |

已确认方向：

1. `StrategyAgent` 优先：先判断教学策略，包括是否图解、是否追问、是否推荐练习、讲解深度。
2. `ResponseCritic` 第二：检查回答是否越界、是否过早给答案、是否没有贴合用户画像。
3. `RetrievalAgent` 暂缓：当前已有 RAG 和 toolkit，等检索质量成为主要瓶颈时再做。

建议：等 resources workflow 稳定后，再考虑 tutoring 的策略/审稿 Agent。不要在当前已可用主链路上做大改。

### 3.3 Assessment 出题质量 Agent

推荐优先级：P1/P2

当前 `assessment/generate-questions` 已有 ReActAgent + 格式校验工具。进一步升级可以围绕质量闭环：

| 候选能力 | 作用 |
|---|---|
| `QuestionCriticAgent` | 检查题目是否重复、是否过于模板化、是否贴合知识点 |
| `DifficultyBalancer` | 控制简单/中等/困难比例 |
| `KnowledgePointGuard` | 强制 knowledge_point 来自请求或课程知识白名单 |

注意：如果 Backend 暂时没有真实题库索引，就不要做“真实题目去重/推荐”的复杂承诺。

已确认方向：

1. `QuestionCriticAgent` 优先：生成后审查题目质量，检查重复、模板化、选项质量和解析质量。
2. `KnowledgePointGuard` 第二：强制 knowledge_point 来自请求或课程知识白名单，避免 LLM 发明新名称。
3. `DifficultyBalancer` 第三：在题目质量稳定后，再控制题组难度分布。

### 3.4 Observability / Studio Trace

推荐优先级：P1

这是多 Agent 化后的必要配套，不是单独业务接口。

可升级点：

- 记录每个 Agent 命中、失败、fallback path。
- 记录 RAG chunk 数量和工具调用结果。
- 验证 AgentScope Studio 能观察 tutoring、assessment、resources workflow。
- smoke 工具输出关键 Agent path，不只看接口返回成功。

价值：能证明多 Agent 不是“文档上存在”，而是可观测、可解释。

当前进展：

- 已补结构化日志和 smoke 输出，resources smoke 可显示 multi-agent path / fallback 信息。
- Apifox 全接口测试指南已补充 Studio 可见性矩阵：不是所有 AI 接口都会出现在 Studio Agent 流里。
- Apifox 指南已补真实 AI 命中证据 checklist：health、日志、fallback、webhook body 需要一起看。
- Studio trace 仍是后续能力：`tutoring/chat`、`assessment/generate-questions` 更容易看到 ReActAgent 流；`resources/generate` 当前主要依赖日志和 webhook 验证。

后续方向：

- 第一阶段继续强化结构化日志、smoke 输出、Apifox 验证路径。
- 第二阶段再接 AgentScope Studio trace，用于展示 Planner、Worker、Critic、Aggregator 等链路。
- Studio trace 既是开发验证能力，也可作为竞赛/展示验收能力。

### 3.5 Knowledge / AgentScope RAG

推荐优先级：P2

当前已有手写 Qdrant 检索和 toolkit。后续可评估 AgentScope Knowledge / Generic RAG：

- 对 tutoring 和 assessment 与现有 `retrieve_course_knowledge` 做 A/B。
- 对 resources workflow 提供统一课程知识上下文。
- 保留当前 Qdrant 检索 fallback。

风险：如果 AgentScope Knowledge API 与当前版本不完全匹配，不应强行迁移。

已确认方向：

- 不直接迁移全部 RAG。
- 做 A/B 对照实验，保留当前手写 Qdrant retrieval 作为默认稳定路径。
- 优先选择 `resources/generate` workflow 或 tutoring 的局部 retrieval 工具做试验。
- 对比检索命中质量、metadata 过滤能力、代码复杂度、Studio trace 适配度。

### 3.6 Memory 策略 Agent

推荐优先级：P2/P3

可考虑但不优先：

- 从 conversation 中提取更稳定的长期事实。
- 判断哪些 fact 应写入 Qdrant、哪些只留在短期摘要。
- 处理旧事实与 Backend 当前画像冲突。

已确认方向：

- 同一个对话窗口内，主要依赖 `conversation_summary` + recent messages 保持上下文一致。
- 长期 fact 由 AI 定期更新，不每轮实时写入；触发点可为会话结束、达到 N 轮对话或 Backend 定时触发 `memory/compress`。
- fact 记录用户稳定特征，例如学习风格、常见困惑、偏好解释方式、已掌握/薄弱知识点、提问习惯。
- Backend 结构化画像优先；Qdrant / fact 是辅助语义信息。
- 当 fact 与 Backend 当前画像冲突时，tutoring 以 Backend 画像为准，fact 只能作为补充或弱信号。
- tutoring 可以使用 memory fact 参与教学策略决策，例如更倾向 diagram、对比解释、代码示例或降低抽象程度。
- 未来如实现 Memory Agent，先做低频 `MemoryWritePolicyAgent`，只判断“写不写、以什么 fact_type 写”，不接管全部 memory。

当前暂不迁移到 AgentScope Memory，原因是 Backend 结构化画像和 Qdrant 长期语义记忆是产品边界，贸然迁移会让状态来源变复杂。

近期已修复：

- 用户长期记忆写入 Qdrant 时，point id 已从普通 sha256 字符串改为稳定 UUIDv5，避免 Qdrant 报 `Point id ... is not a valid UUID`。
- 该修复只影响 `memory/compress` 的 Qdrant 写入，不改变 API payload 或 Backend 契约。

## 4. 不建议升级的接口

| 接口 | 原因 |
|---|---|
| `profile/generate` | 统计/诊断数据转画像，structured output + 规则保护足够 |
| `evaluation/generate` | 核心是表格白名单、范围保护和 summary，不需要多 Agent |
| `assessment/evaluate` | 判分必须规则确定，多 Agent 不能改正确性 |
| `learning-path/generate` | 核心是图谱节点白名单和排序，不应让 Agent 发明节点 |
| `health` | 确定性探针，无 LLM/Agent 价值 |

## 5. 候选方案评分

评分范围：1 低，5 高。

| 候选方向 | 架构价值 | 展示价值 | 实现复杂度 | 契约风险 | AgentScope 适配度 | 当前优先级 |
|---|---:|---:|---:|---:|---:|---|
| resources workflow / multi-agent | 5 | 5 | 4 | 2 | 5 | P0 已完成第一阶段 |
| tutoring StrategyAgent / ResponseCritic | 4 | 4 | 4 | 3 | 4 | P1 |
| assessment QuestionCriticAgent / Guard | 4 | 4 | 3 | 2 | 4 | P1/P2 |
| observability / Studio trace | 4 | 5 | 3 | 1 | 5 | P1 |
| AgentScope Knowledge / RAG A/B | 3 | 3 | 4 | 2 | 3 | P2 |
| MemoryWritePolicyAgent / memory fact 策略 | 3 | 3 | 4 | 3 | 3 | P2/P3 |
| profile/evaluation 多 Agent | 1 | 2 | 3 | 3 | 2 | 不做 |

## 6. 最近架构验证与调试修复

本轮围绕“Apifox 能不能证明真实 AI 工作流命中”完成了几项基础修复：

| 问题 | 处理结果 | 影响 |
|---|---|---|
| 从仓库根目录启动时 `.env` 读不到 | 配置加载固定为 service-local `agent_service/.env` | health 可正确显示当前 LLM provider / model |
| Qdrant local 文件锁误判为接口问题 | 运维文档和 Apifox 指南补充 local lock 说明 | 明确这是本地多进程访问限制，不是请求体错误 |
| ResourceAgent 解析真实 LLM JSON 时遇到未转义换行 | parser 增加 `content` / `description` 字段修复路径 | 减少真实模型输出导致的局部 fallback |
| memory 写 Qdrant point id 非 UUID | user memory point id 改为稳定 UUIDv5 | 避免 memory persistence best-effort 写入失败 |
| Studio 看不到所有接口 Agent 流 | Apifox 指南补 Studio 可见性矩阵 | 明确哪些接口是 ReActAgent，哪些只是 structured output |

验证结果：

- `tests/test_core_config.py tests/test_resources_workflow.py`：69 passed。
- `tests -k "memory"`：36 passed。
- `tests/test_openapi_alignment.py`：25 passed。
- 从仓库根目录导入 settings 可读取 `agentscope_openai deepseek-v4-flash`。

## 7. 当前推荐路线

### 第一优先级：真实联调和可观测验证

resources workflow 第一阶段已完成。下一步重点不再是“再拆更多 Agent”，而是证明真实运行质量：

- 用 Apifox / Backend webhook 验证 resources payload。
- 检查 health、日志、webhook body，确认真实 LLM 路径命中。
- 记录 fallback path 和 ResourceAgent 成功/失败比例。

### 第二优先级：observability / Studio trace

多 Agent 链路没有可观测性会很难证明价值。resources workflow 第一阶段完成后，应立即补结构化日志和 smoke 输出；第二阶段接 AgentScope Studio trace。

### 第三优先级：tutoring / assessment 局部深化

只做局部 Agent 能力增强，不重写已有主链路：

- tutoring 增加策略或审稿 Agent。
- assessment 增加质量审查或难度平衡。

### 暂缓

- AgentScope Memory 全迁移。
- profile/evaluation/learning-path 多 Agent 化。
- 改 OpenAPI 表达内部 Agent 结构。

## 8. 待讨论问题

1. resources workflow 是否继续接 PlanNotebook / 更复杂 AgentScope planning API，还是保持当前 fanout pipeline。
2. resources 真实 LLM 输出质量如何验收：人工抽检、rubric、Question/Resource critic，还是离线 eval。
3. resources Backend webhook 联调何时开始；Backend 尚未 ready 时继续用 Apifox Mock 验证。
4. Studio trace 需要展示到什么粒度：Planner / Worker / Aggregator，还是只展示 ReActAgent 主链路。
5. tutoring 已确认 StrategyAgent 优先、ResponseCritic 第二、RetrievalAgent 暂缓；实现前需设计策略输出 schema。
6. assessment 已确认 QuestionCriticAgent 优先、KnowledgePointGuard 第二、DifficultyBalancer 第三；实现前需定义质量评分和 repair/fallback 规则。
7. AgentScope Knowledge 已确认做 A/B 对照实验，不直接替换当前手写 Qdrant retrieval。
8. Memory 已确认 Backend 画像优先、同窗口 summary 保持上下文、AI 定期更新长期 fact、tutoring 使用 fact 参与策略决策。
9. 若后续需要并发本地测试，是否将 Qdrant local 模式切换为 Qdrant server 模式。

## 9. 更新规则

- 本文用于讨论和决策，不能替代具体 implementation plan。
- 当某个方向被批准进入实现时，必须新建单独 plan。
- 每次完成一个阶段后，同步更新 `WORKFLOW.md`。
- 如果 AgentScope 官方文档、本地安装版本和本文设想冲突，以官方文档和本地 introspection 为准。
