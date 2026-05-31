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

### 3.2 Tutoring 多 Agent 深化

推荐优先级：P1

当前 tutoring 已经有 ReActAgent，不建议短期重写主链路。可升级点在“专业分工”：

| 候选 Agent | 作用 | 价值 | 风险 |
|---|---|---|---|
| `StrategyAgent` | 判断是否需要图解、追问、练习建议 | 提升教学策略感 | 需要控制不要输出不稳定 |
| `RetrievalAgent` | 统一课程知识和用户记忆检索策略 | 让 RAG 更可解释 | 可能和现有 toolkit 重复 |
| `ResponseCritic` | 检查是否超出课程范围、是否过早给答案 | 提升教学质量 | 会增加延迟 |

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

### 3.4 Observability / Studio Trace

推荐优先级：P1

这是多 Agent 化后的必要配套，不是单独业务接口。

可升级点：

- 记录每个 Agent 命中、失败、fallback path。
- 记录 RAG chunk 数量和工具调用结果。
- 验证 AgentScope Studio 能观察 tutoring、assessment、resources workflow。
- smoke 工具输出关键 Agent path，不只看接口返回成功。

价值：能证明多 Agent 不是“文档上存在”，而是可观测、可解释。

### 3.5 Knowledge / AgentScope RAG

推荐优先级：P2

当前已有手写 Qdrant 检索和 toolkit。后续可评估 AgentScope Knowledge / Generic RAG：

- 对 tutoring 和 assessment 与现有 `retrieve_course_knowledge` 做 A/B。
- 对 resources workflow 提供统一课程知识上下文。
- 保留当前 Qdrant 检索 fallback。

风险：如果 AgentScope Knowledge API 与当前版本不完全匹配，不应强行迁移。

### 3.6 Memory 策略 Agent

推荐优先级：P2/P3

可考虑但不优先：

- 从 conversation 中提取更稳定的长期事实。
- 判断哪些 fact 应写入 Qdrant、哪些只留在短期摘要。
- 处理旧事实与 Backend 当前画像冲突。

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
| tutoring 策略/审稿 Agent | 4 | 4 | 4 | 3 | 4 | P1 |
| assessment 出题质量 Agent | 4 | 4 | 3 | 2 | 4 | P1/P2 |
| observability / Studio trace | 4 | 5 | 3 | 1 | 5 | P1 |
| AgentScope Knowledge / RAG | 3 | 3 | 4 | 2 | 3 | P2 |
| Memory 策略 Agent | 3 | 3 | 4 | 3 | 3 | P2/P3 |
| profile/evaluation 多 Agent | 1 | 2 | 3 | 3 | 2 | 不做 |

## 6. 当前推荐路线

### 第一优先级：resources/generate workflow

先写单独 design，再写 implementation plan。目标是建立：

- Planner
- 多 Resource Agent
- Aggregator
- fallback 链
- tests

第一阶段先不强依赖 AgentScope workflow API，先建立内部边界；第二阶段再 AgentScope 原生化。

### 第二优先级：observability / Studio trace

多 Agent 链路没有可观测性会很难证明价值。resources workflow 第一阶段完成后，应立即补日志和 trace 验证。

### 第三优先级：tutoring / assessment 局部深化

只做局部 Agent 能力增强，不重写已有主链路：

- tutoring 增加策略或审稿 Agent。
- assessment 增加质量审查或难度平衡。

### 暂缓

- AgentScope Memory 全迁移。
- profile/evaluation/learning-path 多 Agent 化。
- 改 OpenAPI 表达内部 Agent 结构。

## 7. 待讨论问题

1. `resources/generate` 的 Planner 是否需要 LLM，还是先用规则拆分资源任务？
2. 每个 ResourceAgent 是独立 LLM 调用，还是 AgentScope workflow 节点？
3. Mindmap 资源是否统一输出 Mermaid，还是保持 markdown 树形结构？
4. 单个资源 Agent 失败时，是局部 fallback，还是整体 fallback？
5. Studio trace 是作为开发验证能力，还是作为展示能力写进验收标准？
6. tutoring 是否需要 `StrategyAgent`，还是继续让 ReActAgent 自己判断 diagram / suggestion？
7. assessment 是否需要独立 `QuestionCriticAgent`，还是继续依赖 toolkit 的格式校验？
8. AgentScope Knowledge 是否能替代当前手写 Qdrant retrieval，还是只做对照实验？
9. 多 Agent 产生的中间结果是否需要进入日志、metadata 或只在内部使用？
10. Backend 联调和 resources workflow 哪个先进入实现阶段？

## 8. 更新规则

- 本文用于讨论和决策，不能替代具体 implementation plan。
- 当某个方向被批准进入实现时，必须新建单独 plan。
- 每次完成一个阶段后，同步更新 `WORKFLOW.md`。
- 如果 AgentScope 官方文档、本地安装版本和本文设想冲突，以官方文档和本地 introspection 为准。
