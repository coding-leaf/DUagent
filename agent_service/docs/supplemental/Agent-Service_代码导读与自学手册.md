# Agent Service 代码导读与自学手册

本文不是接口契约，也不是单纯的架构概览。

它的目标更直接：

1. 帮你快速看懂 `agent_service` 的代码结构。
2. 帮你建立“一个请求在项目里怎么流动”的具体感知。
3. 帮你知道后续要改需求时，应该先看哪里、改哪里、测哪里。
4. 帮你从“能读懂”逐步过渡到“能自己稳定改代码”。

正式接口字段和协议，仍然以以下文档为准：

- `../docs/20-agent-api/Agent-Service.openapi.json`
- `../docs/20-agent-api/API_Agent内部接口规范.md`

当前实现进度和最近测试结果，以 `WORKFLOW.md` 为准。

---

## 1. 先建立一个正确心智模型

先不要把这个项目理解成“一个普通的聊天服务”。

更准确地说，`agent_service` 是一个面向教育业务的 AI 计算服务。它做的事是：

- 接收 Backend 传来的结构化学习数据
- 结合 prompt、规则、LLM、RAG、Qdrant 做推理和生成
- 输出结构化结果，或按 SSE / webhook 协议返回

它**不负责**：

- 用户鉴权
- SQL 持久化
- 课程、用户、对话主业务表
- 前端接口整合

它**负责**：

- 智能辅导
- 用户画像生成
- 学习效果评估
- 题目生成
- 学习路径生成
- 学习资源生成
- 记忆压缩
- Qdrant 中课程知识和用户长期记忆的检索与写入

一句话总结：

`agent_service` = `FastAPI 协议层` + `Agent 编排层` + `Prompt/RAG/Memory/LLM 基础设施`

---

## 2. 阅读顺序建议

如果你第一次看这个项目，不要从某个大文件一头扎进去。推荐按这个顺序读：

1. `AGENTS.md`
   - 看开发约束、改代码边界、测试要求。
2. `WORKFLOW.md`
   - 看当前哪些接口已经完成，哪些是 fallback，哪些是 AgentScope 主链。
3. `../docs/30-dev-guide/Agent-Service_开发导读.md`
   - 建立业务职责和前后端边界。
4. `docs/supplemental/Agent-AI编排审计.md`
   - 看每个接口的 AI 输入、prompt、RAG、fallback 链。
5. `main.py`
   - 看服务是怎么启动、怎么挂路由、怎么初始化 observability 的。
6. `api/v1/router.py`
   - 看有哪些接口模块。
7. `api/v1/*.py`
   - 先看 API 层都做了什么，记住它应该很薄。
8. `schemas/*.py`
   - 对照接口，理解每个请求/响应结构。
9. `agents/*.py`
   - 这是核心业务层，真正的逻辑基本都在这里。
10. `prompts/*.py`、`memory/*.py`、`core/ai.py`
   - 看 AI 具体吃什么、检索怎么做、provider 怎么封装。
11. `tests/*.py`
   - 用测试反推设计意图和边界条件。

推荐阅读原则：

- 先看边界，再看实现。
- 先看“对外承诺的输入输出”，再看“内部怎么算出来的”。
- 先看一条完整链路，再扩展到其他接口。

---

## 3. 目录结构怎么理解

项目根目录下最关键的目录和文件如下：

| 路径 | 作用 | 阅读优先级 |
|---|---|---:|
| `main.py` | FastAPI 启动入口 | 高 |
| `api/` | HTTP 路由与协议适配 | 高 |
| `schemas/` | Pydantic 请求/响应模型 | 高 |
| `agents/` | 业务编排核心 | 最高 |
| `prompts/` | 系统提示词与消息构造 | 高 |
| `memory/` | RAG、Qdrant、知识库、用户记忆 | 高 |
| `core/` | 配置、AI provider、readiness、日志 | 高 |
| `tools/` | 本地运维、smoke、知识入库工具 | 中 |
| `tests/` | 测试与行为样例 | 最高 |
| `docs/` | 本地开发导读、审计文档、操作文档 | 中 |
| `WORKFLOW.md` | 当前状态、最近验证、下一步 | 高 |

你可以把它看成下面这张关系图：

```text
HTTP Request
  -> api/
  -> schemas/
  -> agents/
      -> prompts/
      -> core/ai.py
      -> memory/
      -> tools/（少量运维型场景）
  -> schemas/
  -> HTTP Response / SSE / webhook
```

---

## 4. 每一层到底负责什么

这一节非常重要。你以后改代码，首先就是判断该改哪一层。

### 4.1 `api/`：协议适配层

`api/v1/*.py` 主要做这些事：

- 接收 FastAPI 请求
- 参数校验
- 调用 `agents/` 层
- 包装统一响应结构
- 对 SSE / 202 / webhook 协议做适配

这层**不应该**做：

- prompt 拼接
- 业务规则推理
- LLM 输出解析
- Qdrant 检索细节

你可以把 API 层理解为“薄路由”。

典型文件：

- `api/v1/health.py`
- `api/v1/tutoring.py`
- `api/v1/profile.py`
- `api/v1/resources.py`

如果你发现 API 文件开始出现大量业务 if/else，通常就是分层开始偏了。

### 4.2 `schemas/`：契约层

`schemas/*.py` 是项目最接近 OpenAPI 的代码。

这里定义：

- request model
- response model
- 嵌套结构
- 枚举/字段含义

它的核心价值不是“少写字”，而是把接口约束固化成代码。

你改 schema 时，要有两个警惕：

1. 这是不是接口契约变更？
2. 这会不会导致 OpenAPI 对齐测试失败？

典型文件：

- `schemas/tutoring.py`
- `schemas/profile.py`
- `schemas/assessment.py`

### 4.3 `agents/`：业务编排层

这是项目最核心的目录。

这里放的是：

- 规则版逻辑
- LLM 调用流程
- ReActAgent 胶水层
- fallback 链
- 输出保护与结果合并

一个经验判断：

如果某段逻辑回答的是“这个接口到底怎么生成结果”，它大概率属于 `agents/`。

典型文件：

- `agents/profile.py`
- `agents/evaluation.py`
- `agents/assessment.py`
- `agents/resources.py`
- `agents/tutoring.py`
- `agents/tutoring_react.py`
- `agents/tutoring_react_flow.py`

### 4.4 `prompts/`：AI 输入构造层

这层负责：

- system prompt
- user message 拼接
- AI 消息列表构造

不要把 prompt 当成“随手写一段字符串”。在这个项目里，prompt 是业务策略的一部分。

例如它会决定：

- 输出 JSON 结构要求
- 能不能发明字段
- 回答风格是否符合教育场景
- 是否允许使用检索上下文

### 4.5 `memory/`：RAG 与记忆层

这层负责：

- 课程知识切片与入库
- 用户长期记忆写入与检索
- Qdrant 检索封装
- 向量搜索与可选重排
- tutoring 场景下的检索上下文拼接

这层不要掺杂接口协议，不要直接做 HTTP 语义。

### 4.6 `core/`：基础设施层

主要包括：

- `core/config.py`：环境变量和配置
- `core/ai.py`：chat / embedding / reranker provider 封装
- `core/readiness.py`：provider readiness 检查
- `core/logging.py`：日志基础设施

这层回答的是：“AI 和基础能力怎么接进来，而不是业务上怎么使用它。”

### 4.7 `tools/`：开发与运维辅助层

当前 `tools/` 不是业务 Tool Calling 主目录，而是偏开发运维辅助：

- `tools/ingest_knowledge.py`
- `tools/readiness_check.py`
- `tools/smoke_all.py`
- `tools/smoke_react.py`

它们主要用于：

- 知识入库
- 本地 readiness 验证
- 全接口 smoke 验收
- AgentScope/ReAct 冒烟验证

---

## 5. 从启动入口开始看

### 5.1 `main.py`

建议先看 `main.py`，因为它会告诉你整个服务怎么被组起来。

你重点关注这些问题：

1. FastAPI app 在哪里创建？
2. v1 router 在哪里挂载？
3. startup / lifespan 做了什么？
4. AgentScope Studio 是什么时候初始化的？

当前你应该能观察到：

- 路由通过 `api/v1/router.py` 聚合
- 启动时会做 best-effort 的 AgentScope Studio 初始化
- 这部分是基础设施初始化，不属于某个接口的业务逻辑

这会帮助你区分：

- “服务启动行为”
- “单个接口业务行为”

这是两个不同层次的问题。

---

## 6. 先用一条完整链路理解项目

第一次读代码，推荐先挑一个接口打穿。

最推荐的有两个：

1. `POST /agent/v1/profile/generate`
   - 相对稳定
   - 没有 SSE
   - 没有复杂工具调用
   - 能代表“规则版 + LLM enrichment + schema merge”的典型模式

2. `POST /agent/v1/tutoring/chat`
   - 最复杂
   - 能体现 SSE、RAG、ReActAgent、fallback
   - 适合第二阶段再看

### 6.1 以 `profile/generate` 为例

建议阅读顺序：

1. `api/v1/profile.py`
2. `schemas/profile.py`
3. `agents/profile.py`
4. `prompts/profile.py`
5. `tests/test_profile_agent.py`

你要回答这几个问题：

1. API 层接收到什么 request model？
2. API 层调用了哪个 agent 函数？
3. agent 先做规则版还是先调 LLM？
4. LLM 的输出是完整接管，还是只做 enrichment？
5. 最终返回的对象是否仍然受 schema/规则保护？

如果你能把这 5 个问题说清楚，你已经开始真正理解这个项目。

### 6.2 以 `tutoring/chat` 为例

建议阅读顺序：

1. `api/v1/tutoring.py`
2. `schemas/tutoring.py`
3. `agents/tutoring.py`
4. `agents/tutoring_react_flow.py`
5. `agents/tutoring_react.py`
6. `agents/tutoring_tools.py`
7. `memory/tutoring_retrieval.py`
8. `prompts/tutoring.py`
9. `tests/test_tutoring_api.py`
10. `tests/test_tutoring_react.py`
11. `tests/test_tutoring_react_flow.py`

这一条链路能帮你看懂：

- SSE 是怎么组织事件的
- 为什么先发 fallback chunk
- 检索上下文是怎么注入 prompt 的
- ReActAgent 和普通 chat JSON 路径是什么关系
- 为什么项目里同时保留规则版和 LLM 路径

---

## 7. 九个接口和主要文件的对应关系

下面这张表非常适合你读代码时对照。

| 接口 | API 文件 | 主要 agent 文件 | 相关 prompt | 相关 memory / 其他 |
|---|---|---|---|---|
| `GET /agent/v1/health` | `api/v1/health.py` | `agents/health.py` | 无 | `core/readiness.py` |
| `POST /agent/v1/tutoring/chat` | `api/v1/tutoring.py` | `agents/tutoring.py`, `agents/tutoring_react.py`, `agents/tutoring_react_flow.py`, `agents/tutoring_tools.py` | `prompts/tutoring.py` | `memory/tutoring_retrieval.py`, `memory/vector_store.py` |
| `POST /agent/v1/profile/generate` | `api/v1/profile.py` | `agents/profile.py` | `prompts/profile.py` | `core/ai.py` |
| `POST /agent/v1/evaluation/generate` | `api/v1/evaluation.py` | `agents/evaluation.py` | `prompts/evaluation.py` | `core/ai.py` |
| `POST /agent/v1/assessment/evaluate` | `api/v1/assessment.py` | `agents/assessment.py` | `prompts/assessment.py` | `core/ai.py` |
| `POST /agent/v1/assessment/generate-questions` | `api/v1/assessment.py` | `agents/assessment.py` | `prompts/assessment.py` | `memory/course_knowledge_store.py` |
| `POST /agent/v1/learning-path/generate` | `api/v1/learning_path.py` | `agents/learning_path.py` | `prompts/learning_path.py` | `core/ai.py` |
| `POST /agent/v1/resources/generate` | `api/v1/resources.py` | `agents/resources.py` | `prompts/resources.py` | `memory/course_knowledge_store.py` |
| `POST /agent/v1/memory/compress` | `api/v1/memory.py` | `agents/memory.py` | `prompts/memory.py` | `memory/user_memory_store.py` |

---

## 8. 这个项目里最常见的实现模式

项目虽然接口多，但实现套路并不杂。你真正需要掌握的是几个“重复出现的模式”。

### 8.1 模式一：薄 API + 厚 agent

表现为：

- API 文件很短
- 主要逻辑在 `agents/*.py`
- schema 明确，协议包装统一

这是当前项目最值得保持的模式。

### 8.2 模式二：规则版作为基础，LLM 做增强

很多接口不是“全靠 LLM 生成”，而是：

1. 先有一个规则版结果
2. 再让 LLM 做 enrichment
3. 最终由代码保护关键结构和字段

这样做的好处是：

- 稳定
- 可测试
- 不容易被模型乱输出破坏结构

典型场景：

- `profile/generate`
- `evaluation/generate`
- `assessment/evaluate`

### 8.3 模式三：LLM 主生成 + fallback 兜底

当接口天然更偏生成式任务时，会走：

1. LLM 主路径
2. 失败时回落到 skeleton / rule-based

典型场景：

- `assessment/generate-questions`
- `resources/generate`
- `tutoring/chat`

### 8.4 模式四：Prompt、RAG、schema 三方共同约束

不要误以为 prompt 一写就完了。

在这个项目里，稳定性来自三层：

1. prompt 告诉模型“应该怎么说”
2. RAG 告诉模型“基于什么上下文说”
3. schema / 代码守卫告诉系统“哪些结果能接收，哪些不能接收”

这也是你以后改 AI 功能时必须守住的结构。

---

## 9. Prompt 应该怎么读

读 `prompts/*.py` 时，不要只看文字内容。重点看它在回答哪些工程问题。

每个 prompt 至少要观察：

1. 它有没有明确角色定义？
2. 它有没有约束输出格式？
3. 它有没有禁止模型发明事实？
4. 它有没有说明如何使用检索上下文？
5. 它有没有体现教育业务语气和边界？

推荐你读：

- `prompts/tutoring.py`
- `prompts/assessment.py`
- `prompts/resources.py`

读法建议：

- 先读 system prompt
- 再看 user message 是如何拼接字段的
- 再对照测试，观察哪些字段是被刻意保护的

---

## 10. RAG 和 Memory 应该怎么读

这部分是很多人一开始最容易混乱的地方。

### 10.1 两类语义数据

项目里主要有两种语义数据：

1. `course_knowledge`
   - 课程知识
   - 用于概念、章节、知识点检索

2. `user_memory`
   - 用户长期记忆
   - 用于召回历史事实、偏好、盲点、掌握情况

### 10.2 读代码时先找这几个文件

- `memory/vector_store.py`
- `memory/course_knowledge_store.py`
- `memory/user_memory_store.py`
- `memory/tutoring_retrieval.py`
- `memory/course_knowledge_ingestion.py`

### 10.3 你要特别理解的边界

Backend 传进来的结构化画像，是当前权威状态。

Qdrant 里的用户记忆，不应覆盖 Backend 当前画像，它更像补充上下文。

所以你以后如果改 tutoring、profile、memory 压缩，一定要守住这个优先级：

`Backend 结构化当前态 > Qdrant 历史语义事实`

这是业务正确性的关键。

---

## 11. AgentScope 在这个项目里怎么用

不要把 AgentScope 想成“整个项目都交给它”。

当前项目对 AgentScope 的使用是有边界的。

### 11.1 已经落地的部分

- `core/ai.py`
  - 封装 chat / embedding provider
- `agents/tutoring_react.py`
  - ReActAgent 适配
- `agents/tutoring_tools.py`
  - 挂载可调用工具
- `tools/ingest_knowledge.py`
  - 借助 Reader / PDFReader 路径做知识摄入

### 11.2 还没有把 AgentScope 变成总框架

多数接口仍然是：

- 规则逻辑
- prompt
- LLM completion
- schema merge

而不是全量 agentic workflow。

这是刻意的，不是落后。

原因很实际：

- 很多接口结构化约束比“智能自主性”更重要
- 先保住契约和可测性，再逐步加 agentic 能力

---

## 12. 测试目录应该怎么读

如果你真的想成长到能自己稳定改代码，测试不是附属品，而是主教材。

### 12.1 先看哪些测试

推荐顺序：

1. `tests/test_openapi_alignment.py`
   - 看哪些 schema / 路由被 OpenAPI 守住
2. `tests/test_schema_contracts.py`
   - 看结构约束
3. `tests/test_profile_agent.py`
4. `tests/test_evaluation_agent.py`
5. `tests/test_assessment_agent.py`
6. `tests/test_learning_path_agent.py`
7. `tests/test_resources_agent.py`
8. `tests/test_tutoring_*`

### 12.2 测试在这个项目里有三种价值

#### 第一种：守契约

例如：

- schema 字段是否和 OpenAPI 一致
- 路由输出是否还符合对外协议

#### 第二种：守 fallback 行为

例如：

- LLM 失败时是否回落到规则版
- structured output 失败时是否还能解析文本
- Qdrant 不可用时系统是否仍有最小行为

#### 第三种：守实现意图

有时光看代码你不知道设计者为什么这么写，但看测试你会立刻知道：

- 这里不能发明字段
- 那里必须保留原有排序
- 某个响应必须带固定元数据

这就是测试作为“活文档”的价值。

---

## 13. 想自己改代码时，应该怎么下手

这是最实用的一节。

你以后拿到一个需求，建议按这个顺序执行。

### 13.1 第一步：判断需求属于哪一层

先问自己：

- 是接口协议变了吗？那先看 `schemas/` 和 OpenAPI。
- 是生成逻辑变了吗？那大概率改 `agents/`。
- 是模型输入话术变了吗？那改 `prompts/`。
- 是检索逻辑变了吗？那改 `memory/`。
- 是启动配置 / provider 变了吗？那改 `core/`。

### 13.2 第二步：先找现有模式，不要发明新套路

例如你要加一个“LLM enrichment 但保留规则版兜底”的接口，不要自己设计新框架，先去看：

- `agents/profile.py`
- `agents/evaluation.py`

如果你要加“RAG + 生成”的能力，先看：

- `agents/assessment.py`
- `agents/resources.py`

如果你要调 tutoring 主链，先看：

- `agents/tutoring.py`
- `agents/tutoring_react_flow.py`

### 13.3 第三步：先补或先找测试

改之前先问：

- 现有测试覆盖了吗？
- 没覆盖的话，应该补哪一类测试？

推荐习惯：

1. 先写或补失败测试
2. 再做最小改动
3. 跑相关测试
4. 再决定要不要扩大范围

### 13.4 第四步：改动尽量沿着现有调用链走

不要跨层乱写。

例如你要调 `profile/generate` 的 AI 输出：

- 正常路径：`api/v1/profile.py` -> `agents/profile.py` -> `prompts/profile.py`
- 不正常路径：直接在 API 层拼 prompt，或者在 schema 里塞业务逻辑

### 13.5 第五步：最后再看是否要更新 `WORKFLOW.md`

如果是已确认任务的一部分，应同步：

- 当前实现状态
- 跑了哪些测试
- 下一步建议

---

## 14. 常见误区

### 14.1 误区一：把业务逻辑写进 API 层

这是最常见的坏味道。

表现：

- API 文件很长
- 路由函数里充满条件分支
- API 层开始直接处理 LLM 输出

改法：

- 下沉到 `agents/`

### 14.2 误区二：把 Qdrant 当成权威业务状态

Qdrant 是语义补充，不是业务真相源。

结构化当前状态应该优先来自 Backend。

### 14.3 误区三：过度相信 prompt

prompt 很重要，但单靠 prompt 不够。

必须和：

- schema
- 代码守卫
- fallback

一起看。

### 14.4 误区四：一上来就想大重构

这个项目当前最值钱的是：

- 契约稳定
- 测试覆盖
- 边界逐渐清晰

不是“抽象得更漂亮”。

所以你后续改代码，优先原则仍然应该是：

`minimal diff + 贴近现有模式 + 守住测试`

### 14.5 误区五：只看实现，不看测试

很多 AI 相关代码表面看起来都“差不多能跑”，但真正决定可维护性的，是测试里锁住了哪些关键行为。

---

## 15. 从会读到会写的成长路线

你可以按下面四个阶段推进。

### 阶段一：能看懂

目标：

- 知道目录分层
- 知道 9 个接口各自对应哪些文件
- 知道请求如何流经 API -> agent -> prompt/memory -> schema

标志：

- 你能口头讲清 `profile/generate` 和 `tutoring/chat` 的主链

### 阶段二：能做小改动

目标：

- 能改 prompt
- 能调小范围规则逻辑
- 能补一两个 agent 层测试

建议练习：

- 调整 `profile/generate` 的某个 enrichment 字段策略
- 调整 `assessment/evaluate` 的 explanation 生成规则

### 阶段三：能做一条完整能力链

目标：

- 能从 schema 到 agent 到 prompt 到测试做完一个小需求

建议练习：

- 给 `resources/generate` 某类资源增加一条约束
- 给 `memory/compress` 增加一个可控的抽取规则

### 阶段四：能做编排级调整

目标：

- 能判断哪里该用规则版，哪里该用 LLM，哪里适合 AgentScope
- 能修改 fallback 链而不破坏现有契约

建议练习：

- 调整 tutoring 的 RAG 注入策略
- 调整 assessment question generation 的 structured output 策略

---

## 16. 推荐的实战练习题

如果你要真正熟悉这个项目，下面这些练习最有效。

### 练习 1：追踪 `profile/generate` 完整调用链

要求：

- 列出请求 schema
- 找到 API 入口
- 找到规则版生成位置
- 找到 LLM enrichment 位置
- 找到测试覆盖点

目标：

- 训练你建立“单接口完整链路图”

### 练习 2：给 tutoring 画自己的顺序图

要求：

- 从 `api/v1/tutoring.py` 开始
- 画出 SSE、retrieval、ReAct、fallback 的顺序

目标：

- 强迫你真正理解最复杂链路

### 练习 3：挑一个 prompt 做审计

要求：

- 看它要求了什么输出
- 看代码是否真的验证了这些输出
- 找出“仅靠 prompt 保证”的脆弱点

目标：

- 训练你区分“语言约束”和“工程约束”

### 练习 4：只看测试反推实现

要求：

- 先读 `tests/test_assessment_agent.py`
- 不先读实现
- 先写出你推测的处理逻辑，再对照真实代码

目标：

- 训练你从行为约束理解系统

### 练习 5：自己做一次最小需求修改设计

要求：

- 假设要调整 `learning-path/generate` 的节点选择逻辑
- 写出你会改哪些文件、为什么、要补哪些测试

目标：

- 训练你从“读代码”过渡到“设计改动”

---

## 17. 你真正要掌握的，不是文件，而是判断力

最终你需要建立的不是“记住每个函数名”，而是下面这些判断力：

1. 这个需求属于哪一层。
2. 这个逻辑应该由规则保证，还是由 LLM 生成。
3. 这个结果应该靠 prompt 约束，还是靠 schema/代码保护。
4. 这个改动会不会影响 OpenAPI 契约。
5. 这个接口该做 enrichment，还是该做 full generation。
6. 这里是否需要 fallback。
7. 哪些测试必须跟着跑。

只要这些判断力建立起来，你就不只是“看懂这个项目”，而是开始具备独立维护它的能力。

---

## 18. 结合现有文档怎么用

后续建议把几份文档分工使用，不要混着看。

### 看项目职责和前后端边界

读：

- `../docs/30-dev-guide/Agent-Service_开发导读.md`

### 看当前实现状态和最近验证

读：

- `WORKFLOW.md`

### 看每个接口的 AI 实际输入、RAG、fallback 和顺序图

读：

- `docs/supplemental/Agent-AI编排审计.md`

### 看本地启动、smoke、readiness、知识入库操作

读：

- `docs/Agent-Service_本地启动与运维.md`

### 看“如何阅读代码并成长到能自己修改”

读：

- 本文 `docs/supplemental/Agent-Service_代码导读与自学手册.md`

---

## 19. 最后给你的阅读建议

如果你现在时间有限，不要试图一次性看完所有实现。

最有效的路径是：

1. 先读本文第 2、3、4、6、13 节
2. 实际打开 `profile/generate` 的链路读一遍
3. 再读 `tutoring/chat` 的链路
4. 然后挑一个测试文件，用测试反推实现
5. 最后再尝试一个很小的改动

这个顺序比“从头到尾扫代码”有效得多。

当你能自己回答下面这三个问题时，说明你已经开始真正掌握这个项目：

1. 一个接口请求是怎么从 API 流到 agent 再流回 schema 的？
2. 哪些地方是规则逻辑，哪些地方是 LLM 逻辑，为什么这样分？
3. 你想改一个行为时，应该先改哪里、再测哪里？
