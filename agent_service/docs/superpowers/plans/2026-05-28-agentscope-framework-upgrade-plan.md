# AgentScope 多智能体架构升级计划

## 背景

前一版 AgentScope 框架深入计划已经完成主要近期目标：

- structured_model 已迁移到主要 LLM 接口。
- `tutoring/chat` 已接入 ReActAgent + Toolkit。
- `assessment/generate-questions` 已接入 ReActAgent + Toolkit + 格式自检。
- API 边界已收束，核心业务编排下沉到 `agents/`。
- OpenAPI 对齐测试、smoke 工具和 readiness 工具已建立。

因此，当前不再把“补齐 structured_model 覆盖”作为主线。新的架构方向是：

> EduAgent 以多智能体架构优先，优先使用 AgentScope 能稳定落地的方案。

该方向服务两个目标：

1. 符合当前 AI 应用主流趋势：单 Agent 向 Agent 协同、workflow、tool-use、可观测编排演进。
2. 让 EduAgent 不只是“LLM 包装服务”，而是具备清晰 Agent 协作边界的教育智能体系统。

## 当前实现基线

| 能力 | 当前状态 |
|---|---|
| FastAPI + OpenAPI | 已完成，主要 schema 有对齐测试 |
| 规则版 fallback | 所有 LLM 相关接口均保留 |
| AgentScope provider | ChatModel、Formatter、Embedding 已封装 |
| structured_model | 已覆盖 tutoring、profile、evaluation、assessment、learning-path、memory 等主路径 |
| ReActAgent | 已用于 tutoring/chat 和 assessment/generate-questions |
| Toolkit | 已用于课程知识检索、用户记忆检索、题目格式校验 |
| RAG | tutoring、assessment 出题、resources 资源生成已使用课程知识检索 |
| Knowledge ingestion | PDF/MD/TXT 摄入、chunk、embedding、Qdrant 写入已跑通 |
| Workflow / multi-agent | 尚未落地，是下一阶段重点 |

## 架构原则

### 1. 多智能体优先，但不滥用

多智能体只用于天然需要拆分、协作、校验或并行的任务。

适合：

- `resources/generate`：不同资源类型天然可拆分。
- `tutoring/chat`：对话 Agent + 工具检索 + 后续可扩展策略 Agent。
- `assessment/generate-questions`：出题 Agent + 检索工具 + 格式校验工具。

暂不适合：

- `profile/generate`：统计数据转画像，structured output + 规则保护足够。
- `evaluation/generate`：学习统计转表格和总结，关键是白名单和范围保护。
- `assessment/evaluate`：判分必须规则确定，LLM 只做诊断增强。
- `learning-path/generate`：核心是节点 ID 白名单和排序，不是多 Agent 推理。
- `memory/compress`：当前长期记忆是产品边界，先不迁移到 AgentScope Memory。

### 2. AgentScope 优先

涉及 Agent 编排时，优先评估并使用 AgentScope：

- ReActAgent
- Toolkit / ToolResponse
- structured_model
- workflow / planning / pipeline 能力
- Studio / tracing / observability
- Knowledge / RAG 能力

如果官方文档、本地安装版本和历史示例冲突，以官方当前文档和本地 introspection 为准。不凭空编造 AgentScope API。

### 3. 契约稳定

多智能体架构是内部实现，不改变 Backend 调用方式。

- 不改 OpenAPI。
- 不改 `schemas/` 表达 Agent 内部结构。
- 不把 AgentScope 对象暴露到 API 层。
- 保持现有 fallback 链。

### 4. 可验证优先

每个阶段必须能通过测试证明：

- API 响应契约不漂移。
- Agent 失败时可回落。
- 多 Agent 产物能被 Aggregator 校验和统一包装。
- 异步 webhook 语义不变。

## 下一阶段主线：resources/generate Workflow / Multi-Agent

`resources/generate` 是当前最值得升级的接口。它已经是异步任务，并且资源类型天然分工：

- `document`
- `mindmap`
- `reading`
- `code`

### 目标架构

```text
api/v1/resources.py
  -> agents.resources.accept_resource_generation()
  -> background task
  -> ResourceWorkflowOrchestrator
       -> ResourcePlanner
       -> DocumentResourceAgent
       -> MindmapResourceAgent
       -> ReadingResourceAgent
       -> CodeResourceAgent
       -> ResourceAggregator
  -> webhook callback
```

### 组件职责

| 组件 | 职责 |
|---|---|
| `ResourceWorkflowOrchestrator` | resources/generate 总编排，负责降级链和 webhook payload 形状 |
| `ResourcePlanner` | 根据请求、课程 ID、资源类型、RAG 上下文生成执行计划 |
| `DocumentResourceAgent` | 生成课程讲义、摘要、知识点解释 |
| `MindmapResourceAgent` | 生成导图内容，优先输出 Mermaid 或结构化导图文本 |
| `ReadingResourceAgent` | 生成延伸阅读、学习建议、阅读路径 |
| `CodeResourceAgent` | 生成代码示例、注释和运行说明 |
| `ResourceAggregator` | 校验字段、去重、排序、补 fallback、保持 OpenAPI 结果形状 |

### 降级链

```text
AgentScope workflow / multi-agent
  -> 当前 generate_resources_with_llm()
  -> skeleton resources fallback
  -> failed webhook payload
```

### 第一阶段实现边界

第一阶段不直接大规模替换异步任务协议，只做内部编排边界：

1. 在 `agents/resources.py` 或相邻新模块建立 workflow orchestrator 函数。
2. 保持 `api/v1/resources.py` 不变或只做薄委托调整。
3. 保持 webhook 202 协议不变。
4. 保留当前 LLM/RAG 和 skeleton fallback。
5. 补 tests 证明 workflow 成功、部分 Agent 失败、全部失败三种路径。

### 第二阶段 AgentScope 原生化

在第一阶段边界稳定后，再根据 AgentScope 官方文档和本地版本 introspection 引入 workflow/planning API：

1. 验证本地安装版本支持的 workflow/pipeline API。
2. 用最小 spike 跑通 Planner -> Worker -> Aggregator。
3. 将第一阶段本地 orchestrator 替换为 AgentScope workflow adapter。
4. 增加 Studio / trace 观测点。

## 次级方向

### Tutoring 多 Agent 深化

当前 tutoring 已有 ReActAgent + Toolkit，不建议短期重写。后续可按需求增加：

- StrategyAgent：判断是否需要 diagram、练习建议、追问。
- RetrievalAgent：统一课程知识和用户记忆检索策略。
- ResponseCritic：检查回答是否超出课程范围或过度直接给答案。

这些应在 `resources/generate` workflow 稳定后再考虑。

### Assessment 出题质量修正

当前出题已是 ReActAgent 链路。后续只做局部质量增强：

- 出题多样性 prompt。
- `answer` 与 `type` 的一致性修正。
- `knowledge_point` 白名单保护。

不再扩大成复杂多 Agent，除非 Backend 提供真实题库索引用于去重/推荐。

### Observability

多 Agent 链路实现后，应补充可观测性：

- 每个 Agent 命中/失败日志。
- fallback path 日志。
- RAG chunk 数量日志。
- Studio trace 接入验证。

## 暂不推进

- 不把所有接口统一套 subagent / multi-agent。
- 不迁移 OpenAPI/schema 来表达 Agent 内部细节。
- 不继续维护旧 Phase 0-3 作为待办。
- 不在没有官方文档或本地 introspection 验证前编造 AgentScope workflow API。
- 不围绕 Qdrant local 文件锁做扩大修复；部署侧优先考虑 Qdrant server 模式。

## 推荐执行顺序

1. 更新文档真相源，移除已过时历史问题清单。
2. 为 `resources/generate` 写单独设计文档：AgentScope workflow / multi-agent。
3. 为设计写实现计划，明确测试与回退。
4. 第一阶段实现本地 orchestrator 边界。
5. 第二阶段根据 AgentScope 文档和本地版本接入原生 workflow。
6. 补充 observability 和 Studio trace 验证。
