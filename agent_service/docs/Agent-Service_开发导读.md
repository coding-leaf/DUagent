# Agent Service 开发导读

> 用途：这是一份面向后续开发的内部阅读文档，不替代正式接口规范。它基于 `agent_service/docs/`、根目录 `docs/`、当前 `agent_service/` 代码，以及 `agent_service/AGENTS.md` 整理而成，目标是让开发时先分清“项目想做什么”“当前做到哪一步”“接下来该按什么顺序落地”。

---

## 1. 这份文档的使用方式

开发 `agent_service` 时，建议按下面的优先级理解信息：

1. `agent_service/AGENTS.md`
   - 约束当前协作方式：先分析、再说明方案、最小改动、避免大范围重构。
2. `docs/README.md`
   - 这是当前仓库里最接近“总设计说明/README”的文件。
   - 根目录没有单独的 `README.md`，因此项目意图应以这里为准。
3. `agent_service/docs/API_Agent内部接口规范.md`
   - Backend 与 Agent Service 的接口契约。
4. `agent_service/docs/Agent-Service.openapi.json`
   - 契约的机器可读版本，适合后续对接、Mock、校验。
5. `docs/superpowers/specs/2026-05-09-agent-service-design.md`
   - 更偏实现思路和目录建议，不是最终代码现状。
6. 当前 `agent_service/` 代码
   - 这是唯一代表“已经实现了什么”的来源。

一句话总结：`docs/` 决定目标，`agent_service/` 当前代码决定现状，开发时不能把两者混为一谈。

---

## 2. 项目意图

EduAgent 是一个面向教育场景的多智能体系统，整体拆成两个后端：

- `backend`：负责用户、SQL、鉴权、对话持久化、任务管理、前端接口。
- `agent_service`：负责大模型推理、Qdrant 检索、画像生成、测验评估、资源生成、记忆压缩。

关键边界非常明确：

- Agent Service 不碰 SQL。
- Backend 不直接碰大模型。
- Agent Service 只依赖 Backend 传入的结构化数据，以及自己维护的 Qdrant 非结构化语义数据。

这意味着 `agent_service` 的职责不是“做一个普通聊天接口”，而是做一个教育业务 AI 计算服务。

---

## 3. Agent Service 的目标职责

根据 `docs/README.md` 和内部接口规范，`agent_service` 最终要提供 9 类能力：

| 能力 | 接口 | 形态 |
|------|------|------|
| 健康检查 | `GET /agent/v1/health` | 同步 JSON |
| 智能辅导 | `POST /agent/v1/tutoring/chat` | SSE |
| 冷启动画像引导 | `POST /agent/v1/profile/initialize` | SSE |
| 用户画像生成/刷新 | `POST /agent/v1/profile/generate` | 同步 JSON |
| 学习效果评估 | `POST /agent/v1/evaluation/generate` | 同步 JSON |
| 测验评估 | `POST /agent/v1/assessment/evaluate` | 同步 JSON |
| 学习路径生成 | `POST /agent/v1/learning-path/generate` | 同步 JSON |
| 资源生成 | `POST /agent/v1/resources/generate` | 202 + webhook |
| 记忆压缩 | `POST /agent/v1/memory/compress` | 同步 JSON |

其中最核心的业务骨架是：

- `tutoring/chat`：对话主入口，包含 RAG、工具调用、多模态输出。
- `assessment/evaluate`：把学习行为转成诊断结果。
- `profile/generate`：把诊断与统计转成稳定画像。
- `memory/compress`：支撑长对话与长期记忆。
- `resources/generate`：异步生成讲解、导图、习题、拓展、代码等资源。

---

---

## 5. 当前最可信的架构理解

结合文档和代码，`agent_service` 应理解为一个“FastAPI 外壳 + AgentScope 业务内核”的服务。

### 建议的分层

1. API 层
   - 接收 HTTP 请求
   - 做参数校验
   - 组织统一返回格式
   - 对 SSE/异步任务做协议适配

2. Schema 层
   - 管理请求/响应模型
   - 保持与 OpenAPI 一致

3. Agent / Workflow 层
   - 单 Agent 对话
   - Pipeline 状态机
   - Manager-Worker 并发生成

4. Tool / Retrieval 层
   - 课程知识检索
   - 用户长期记忆检索
   - 画图工具
   - 代码执行工具

5. Prompt / Policy 层
   - 集中维护系统提示词
   - 明确 SQL 画像优先于 Qdrant 历史事实

6. Storage Adapter 层
   - 只面向 Qdrant
   - 不承担 SQL 职责

---

## 6. 关键数据边界

这是后续实现最容易混乱的部分。

### Backend 传给 Agent 的数据

属于结构化、可信、当前态数据：

- `user_profile`
- `conversation_summary`
- `recent_messages`
- 学习进度/资源使用统计/练习结果

这些数据应视为权威输入，尤其是画像中的掌握度、引导粒度、学习阶段。

### Agent Service 自己管理的数据

属于非结构化、语义增强数据：

- `course_knowledge`
- `user_memory`

这部分用于：

- 课程知识 RAG
- 长期行为记忆召回
- 对话事实提取后的语义存储

### 一个必须坚持的规则

当 Qdrant 里的旧事实与 Backend 传入的当前画像冲突时，以 Backend 传入的结构化画像为准。

---

## 7. Qdrant 的角色

当前实现已经初始化了两个 collection：

| collection | 用途 |
|------------|------|
| `course_knowledge` | 课程知识库切片 |
| `user_memory` | 用户长期语义记忆 |

文档给出的意图是：

- `course_knowledge`
  - 用于课程概念、章节、知识点检索
  - 需要配合 metadata 做章节/知识点过滤
- `user_memory`
  - 只存从对话中提炼出的事实
  - 必须至少带 `user_id` 过滤
  - 需要考虑时间衰减或按时间排序

当前代码只完成了 collection 初始化，还没有：

- embedding
- upsert
- hybrid search
- rerank
- metadata filtering

所以现在的 Qdrant 只是“空的存储底座”，还不是可用的记忆/RAG 系统。

---

## 8. SSE 与异步任务的协议要求

### SSE

聊天与画像引导是流式接口，事件类型至少包括：

- `chunk`
- `diagram`
- `knowledge_points`
- `suggestion`
- `done`

后续实现时要特别注意：

- 事件格式要和文档保持一致
- 不要只返回纯文本流
- `done` 事件要带补充元数据，供 Backend 持久化

### 异步任务

`/resources/generate` 不是普通同步接口，要求：

- Agent Service 立即返回 `202`
- 返回 `task_id`
- 后台继续执行多 agent 任务
- 完成后向 Backend 的 `webhook_url` 回调

这意味着资源生成不能简单复用普通同步 handler。

---

## 9. 与前后端搭档的 Git 同步边界

当前分工：

- 你负责 `agent_service`：AgentScope、LLM 调用、Qdrant、SSE、画像/评估/路径/资源/记忆压缩逻辑。
- 搭档负责前后端：前端页面、Backend SQL、用户/课程/对话持久化、鉴权、任务管理、对外 API。

通过 Git 同步时，不需要把 Agent 内部实现细节全部同步给搭档，但必须同步会影响 Backend/Frontend 对接的契约变化。

### 每次需要同步的信息

1. 接口契约变化
   - 新增、删除或改名的 endpoint。
   - 请求字段、响应字段、字段是否必填、枚举值变化。
   - HTTP 状态码变化，例如同步 JSON、SSE、`202 + webhook`。

2. SSE 协议变化
   - 事件类型变化，例如 `chunk`、`diagram`、`knowledge_points`、`suggestion`、`done`。
   - `done` 事件里 Backend 需要持久化的元数据变化。
   - 是否仍保持 `data: {...}` 的 SSE 格式。

3. Backend 需要提供的数据
   - `user_profile`
   - `conversation_summary`
   - `recent_messages`
   - 学习进度、练习结果、资源使用统计
   - `webhook_url`

4. Agent Service 回传给 Backend 的数据
   - 画像生成结果
   - 学习效果评估结果
   - 测验诊断结果
   - 学习路径结果
   - 资源生成 webhook payload
   - 记忆压缩后的 `new_summary`

5. 数据边界变化
   - Agent Service 不碰 SQL。
   - Backend 不直接调用大模型。
   - Agent Service 写 Qdrant 的 `course_knowledge` / `user_memory`。
   - Backend 保存 SQL 当前态，且结构化画像优先于 Qdrant 旧事实。

6. 环境和启动方式变化
   - 端口、环境变量、模型配置、Qdrant 配置。
   - `uv` 依赖变更。
   - 本地联调启动命令变化。

### 建议的 Git 同步方式

- 文档契约变更单独提交，commit message 建议使用 `docs(agent): update internal api contract`。
- Agent 实现变更另起提交，commit message 建议使用 `feat(agent): ...` 或 `fix(agent): ...`。
- 每次改接口时，同时更新 `API_Agent内部接口规范.md`；如果影响开发顺序或职责边界，再更新本导读。
- 发给搭档时优先贴 commit hash 或 PR/分支名，并附一句“需要你改 Backend/Frontend 的点”。
- 不要只口头同步字段变化，字段变化必须落到 Git 文档里。

### 同步消息模板

```text
我更新了 Agent Service 对接契约：

分支/commit: <branch-or-commit>
影响接口: <endpoint>
你需要关注:
- Backend 需要新增/调整字段: <fields>
- Frontend 需要监听/展示: <events-or-data>
- 状态码/调用方式变化: <sync-json | sse | 202-webhook>

文档位置:
- agent_service/docs/API_Agent内部接口规范.md
- agent_service/docs/Agent-Service_开发导读.md
```

---

## 10. 开发时应主动防止的误区

### 误区 1：把 Agent 当成 SQL 服务

不要在 `agent_service` 中引入用户关系型数据读写逻辑。文档已经明确，这部分属于 Backend。

### 误区 2：把所有逻辑都塞进 FastAPI 路由

路由只应该做协议适配与调用协调，业务逻辑应下沉到 agent/workflow/tool 层。

### 误区 3：让 Qdrant 替代画像真值

Qdrant 的长期记忆只是辅助上下文，不是用户状态的唯一来源。

### 误区 4：先做复杂多智能体，再做基础协议

当前最缺的不是 fancy orchestration，而是：

- 路由落地
- schema 稳定
- SSE 正确
- Qdrant 检索闭环

### 误区 5：把设计稿中的目录当成必须照搬

设计文档提供的是建议结构。`agent_service/AGENTS.md` 明确要求最小改动和避免过度工程化，因此目录演进应服务于当前实现，而不是为了“看起来完整”一次性铺太大。

---

## 11. 建议把这份文档当成什么

这份文档适合在以下场景先看一遍：

- 新开一个接口前
- 准备重构目录前
- 准备接入 AgentScope / Qdrant / SSE 前
- 对“某个能力是不是该在 agent_service 做”有疑问时

它不适合替代：

- 详细字段说明：看 `API_Agent内部接口规范.md`
- 机器校验：看 `Agent-Service.openapi.json`
- 实际代码现状：看 `agent_service/` 源码

---
