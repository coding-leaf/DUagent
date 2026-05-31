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
| `resources/generate` | LLM + RAG + 异步 webhook | 当前最适合升级为 workflow / multi-agent |
| `memory/compress` | structured output + Qdrant 写入 | 暂不迁移 AgentScope Memory，先保留产品边界 |

## 3. 可升级架构候选

### 3.1 `resources/generate` Workflow / Multi-Agent

推荐优先级：P0

理由：

- 资源类型天然拆分为 `document`、`mindmap`、`reading`、`code`。
- 当前已是异步任务，适合后台 workflow。
- 对竞赛/展示有明显架构价值：Planner + 多资源 Agent + Aggregator。
- 可保持现有 202 + webhook 契约不变。

候选形态：

```text
ResourceWorkflowOrchestrator
  -> Planner
  -> DocumentResourceAgent
  -> MindmapResourceAgent
  -> ReadingResourceAgent
  -> CodeResourceAgent
  -> Aggregator
```

第一阶段可先做本地 orchestrator 边界；第二阶段再根据 AgentScope 官方文档和本地 introspection 接入原生 workflow / planning API。

已确认方向：

- Planner 使用 LLM，但必须 structured output，并保留规则版 planner fallback。
- 单个 ResourceAgent 失败时做局部 fallback，不让一个资源失败拖垮整批资源。
- `mindmap` 资源统一优先输出 Mermaid，Mermaid 无效时局部回退到 markdown 树或 skeleton mindmap。
- Aggregator 负责合并成功资源和局部 fallback 资源，并保持 webhook payload 契约不变。

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

已确认方向：

- 分阶段推进。
- 第一阶段先做结构化日志和 smoke 输出，记录 Agent path、tool call、fallback、RAG chunk 数。
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
| resources workflow / multi-agent | 5 | 5 | 4 | 2 | 5 | P0 |
| tutoring StrategyAgent / ResponseCritic | 4 | 4 | 4 | 3 | 4 | P1 |
| assessment QuestionCriticAgent / Guard | 4 | 4 | 3 | 2 | 4 | P1/P2 |
| observability / Studio trace | 4 | 5 | 3 | 1 | 5 | P1 |
| AgentScope Knowledge / RAG A/B | 3 | 3 | 4 | 2 | 3 | P2 |
| MemoryWritePolicyAgent / memory fact 策略 | 3 | 3 | 4 | 3 | 3 | P2/P3 |
| profile/evaluation 多 Agent | 1 | 2 | 3 | 3 | 2 | 不做 |

## 6. 当前推荐路线

### 第一优先级：resources/generate workflow

先写单独 design，再写 implementation plan。目标是建立：

- LLM Planner + 规则版 planner fallback
- 多 Resource Agent
- Aggregator
- 局部 fallback 链
- Mermaid mindmap 优先输出
- tests

第一阶段先不强依赖 AgentScope workflow API，先建立内部边界；第二阶段再 AgentScope 原生化。

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

## 7. 待讨论问题

1. resources 已确认 LLM Planner；实现时需决定 planner structured output schema。
2. ResourceAgent 第一阶段可为独立 LLM 调用或本地 workflow 节点；第二阶段再验证 AgentScope workflow API。
3. mindmap 已确认优先 Mermaid；实现时需定义 Mermaid 校验和 fallback 条件。
4. 单资源失败已确认局部 fallback；实现时需定义 webhook payload 中是否标注 fallback 来源。
5. observability 已确认分阶段：先日志/smoke，再 Studio trace。
6. tutoring 已确认 StrategyAgent 优先、ResponseCritic 第二、RetrievalAgent 暂缓；实现前需设计策略输出 schema。
7. assessment 已确认 QuestionCriticAgent 优先、KnowledgePointGuard 第二、DifficultyBalancer 第三；实现前需定义质量评分和 repair/fallback 规则。
8. AgentScope Knowledge 已确认做 A/B 对照实验，不直接替换当前手写 Qdrant retrieval。
9. Memory 已确认 Backend 画像优先、同窗口 summary 保持上下文、AI 定期更新长期 fact、tutoring 使用 fact 参与策略决策。
10. Backend 联调和 resources workflow 哪个先进入实现阶段仍需排期决定。

## 8. 更新规则

- 本文用于讨论和决策，不能替代具体 implementation plan。
- 当某个方向被批准进入实现时，必须新建单独 plan。
- 每次完成一个阶段后，同步更新 `WORKFLOW.md`。
- 如果 AgentScope 官方文档、本地安装版本和本文设想冲突，以官方文档和本地 introspection 为准。
