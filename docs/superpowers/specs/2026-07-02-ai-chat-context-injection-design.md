# AIChat Context Injection v1 设计

**日期：** 2026-07-02  
**状态：** 已确认设计，待实施计划  
**目标模块：** `frontend/`、`backend/`、`agent_service_v2/`  
**架构基线：** A+ — Backend 提供可信学习上下文快照，Agent Service v2 使用 AgentScope 2.x 运行时与占位工具边界

---

## 1. 背景与当前链路

当前 AIChat 已经从前端走到 Backend，再由 Backend 代理到 `agent_service_v2`：

```text
Frontend AIChat
  -> POST /api/v1/tutoring/chat
  -> Backend TutoringService / TutoringPayloadBuilder / TutoringStreamAdapter
  -> POST /agent/v2/workbench/chat
  -> agent_service_v2 WorkbenchSession + AgentScope Agent
  -> EDU SSE v2 events
  -> Frontend 渲染回答、工具过程、artifact、审查信息
```

当前已存在的能力：

- Backend 创建/更新 conversation 与 message。
- Backend 会读取课程、catalog、课程 KG 节点预览、用户课程画像、最近消息。
- Backend 将 payload 包进 `context` 发给 `/agent/v2/workbench/chat`。
- `agent_service_v2` 使用 AgentScope 2.0.3 的 `Agent.reply_stream(...)`。
- `agent_service_v2` 已有 planning / artifact / review 占位工具组和 EDU SSE adapter。
- Frontend 已能处理 `text_delta`、`artifact_created`、`content_safety_reviewed`、`debug_log`、`workflow_completed`、`workflow_failed` 等事件。

当前主要缺口：

1. Backend payload 中 `user_profile` 偏扁平，弱点、掌握点、学习偏好、自定义提示词混在一起。
2. `custom_instruction` 只有课程级字段，缺少账号级全局偏好。
3. `agent_service_v2` 把 profile / KG 节点等上下文拼成一条伪 `UserMsg(name="system_context")`，语义边界不清。
4. RAG 与长期记忆尚未设计完成，不应提前实现真实 `RAGMiddleware` / `Mem0Middleware`。
5. 系统不能在 RAG / Memory 未启用时做兜底伪装，不能假装使用课程资料、长期记忆或 source refs。

---

## 2. 已确认范围

### 2.1 本设计要做

本阶段只做 AIChat 个性化上下文注入与 AgentScope v2 工具边界骨架：

- Backend 输出结构化 `context snapshot`。
- 新增账号级 `users.custom_instruction` 作为全局用户偏好。
- 保留课程级 `user_profiles.drive_intent.custom_instruction` 作为 course-local 偏好。
- `agent_service_v2` 按 AgentScope 2.x 边界消费上下文。
- `read_learning_state` 从 Backend snapshot 读取学习状态摘要。
- RAG / Memory 仅作为 placeholder tools 存在。
- placeholder tools 必须显式返回 `not_configured / architecture_pending`。
- Frontend 展示能力未启用、上下文缺失、工具未配置等状态。
- 不产生假 `source_refs`、不产生假长期记忆、不把通用知识伪装成课程资料。

### 2.2 本设计不做

以下能力不属于当前实施范围，后续需要单独设计：

- 真实 `RAGMiddleware`。
- 真实 `Mem0Middleware`。
- 真实 `KnowledgeBase` / `QdrantStore` 接入。
- 真实课程知识库检索。
- 真实长期记忆读写。
- 真实 source refs 生成。
- 多 Agent team。
- Agent Service 反查 Backend 的 C 形态 internal API。

---

## 3. 架构选择：A+ 而不是 C

### 3.1 A+ 架构

```text
Frontend
  -> Backend
       - auth
       - conversation/message persistence
       - learner_context snapshot
       - course_context snapshot
       - user_global + course_local custom instruction
  -> agent_service_v2
       - AgentScope Agent
       - AgentScope Toolkit / ToolGroup / FunctionTool
       - read_learning_state tool
       - search_course_knowledge placeholder tool
       - search_memory placeholder tool
       - add_memory placeholder tool
       - artifact tools
       - EDU SSE adapter
  -> Frontend workbench
       - tool trace
       - placeholder / missing capability display
       - content safety / grounding status
       - artifacts
```

A+ 的职责划分：

- Backend 负责可信业务事实、权限、课程范围、会话落库、上下文快照。
- `agent_service_v2` 负责 AgentScope 2.x runtime、工具边界、事件转换、workspace artifact。
- Frontend 负责用户交互和可视化展示。

### 3.2 为什么当前不采用 C

C 形态是：Backend 极薄，Agent Service 通过 tools 反查 Backend 获取学习画像、弱点、学习路径等。

C 的优势是 Agent 自治性更强，但当前会引入：

- service-to-service auth；
- internal API；
- tool timeout/retry；
- 权限泄漏风险；
- 更大的测试面。

当前阶段优先完成 A+，未来可以把 snapshot 中的部分字段逐步演进为 Agent tools，例如：

```text
get_learner_context
get_weak_points
get_learning_path
get_recent_activity
```

---

## 4. 外部参考架构

本设计参考了成熟的 agentic RAG / memory / citation 架构，但只吸收边界思想，不照搬实现。

- Curiosity Workspace RAG and agent architecture：权限感知工具、citation registry、audit log。
- Knowledge Stack Agent：Agent 主动 search/read/browse 知识库并输出 inline citations。
- Azure AI Search + Foundry Agent Service：Agent 通过 knowledge base / MCP tool 获取检索结果和 citation metadata。
- LlamaIndex Agents：Agent = LLM + memory + tools + chat history；工具结果进入 agent loop。
- LangGraph Memory：short-term thread memory 与 long-term user/application memory 分层。
- NVIDIA Agentic RAG Blueprint：query decomposition、retry、verification、observability 是后续 RAG 优化方向。

对 EDUagent 的映射：

```text
permission-aware enterprise RAG agent pattern
  + learner profile
  + user/course context snapshot
  + placeholder RAG / Memory tool boundary
  + future user-course memory
  + future course KG / resource grounding
```

---

## 5. Backend Context Snapshot Schema

### 5.1 设计目标

Backend 不再只是输出扁平 `user_profile`，而是输出结构化、可审计、可裁剪的上下文快照：

```json
{
  "context_version": "ai_chat_context_v1",
  "learner_context": {},
  "custom_instructions": {},
  "course_context": {},
  "conversation_context": {},
  "runtime_policy": {}
}
```

结构化 JSON 是 Backend 到 Agent Service 的中间契约，不是无脑原样塞给模型的 prompt。

`agent_service_v2` 应按用途分流：

- 一部分摘要进入 system prompt。
- 一部分供 `read_learning_state` tool 返回。
- 一部分进入 debug/event meta。
- 一部分只用于 runtime policy，不给模型。

### 5.2 `learner_context`

示例：

```json
{
  "user_id": "u_xxx",
  "display_name": "张三",
  "guidance_level": "L2",
  "modal_preference": {
    "visual": 0.7,
    "text": 0.5,
    "practice": 0.8
  },
  "weak_points": [
    {
      "name": "AVL 树旋转",
      "chapter": "树与二叉树",
      "mastery": 0.42,
      "evidence": "最近测评中旋转题错误率较高",
      "source": "user_profile.knowledge_coordinates"
    }
  ],
  "mastered_points": [
    {
      "name": "二叉树遍历",
      "chapter": "树与二叉树",
      "mastery": 0.86,
      "source": "user_profile.knowledge_coordinates"
    }
  ],
  "cognitive_blindspots": [
    {
      "label": "概念迁移困难",
      "evidence": "多次把 AVL 左旋和右旋条件混淆",
      "source": "user_profile.cognitive_blindspots"
    }
  ],
  "learning_goal": "期末复习",
  "discipline_badge": {
    "label": "连续学习型",
    "confidence": 0.74
  }
}
```

第一阶段来源：

- `users`；
- `user_profiles.guidance_level_current`；
- `user_profiles.modal_preference`；
- `user_profiles.knowledge_coordinates`；
- `user_profiles.cognitive_blindspots`；
- `user_profiles.drive_intent`；
- `user_profiles.discipline_badge`。

### 5.3 `custom_instructions`

双层设计：

```json
{
  "user_global": "讲解时先给直觉，再给公式。",
  "course_local": "这门课请多给数据结构代码例子。",
  "effective_order": ["user_global", "course_local"]
}
```

规则：

- `user_global` 来源于新增 `users.custom_instruction`。
- `course_local` 来源于 `user_profiles.drive_intent.custom_instruction`。
- 两者均低于系统安全规则和运行时策略。
- 如冲突，course-local 作为更具体约束优先，但不得覆盖安全和真实性约束。

### 5.4 `course_context`

示例：

```json
{
  "scope": "course",
  "course_id": "course_xxx",
  "catalog_id": "catalog_xxx",
  "course_title": "数据结构",
  "kg_host_course_id": "catalog_host_xxx",
  "active_kg_nodes_preview": [
    {
      "id": "kg_node_1",
      "name": "AVL 树",
      "chapter": "树"
    }
  ]
}
```

`course_context` 只表示课程边界和元信息，不表示真实 RAG 结果。

### 5.5 `conversation_context`

示例：

```json
{
  "conversation_id": "conv_xxx",
  "summary": "学生之前询问过二叉查找树和 AVL 树区别。",
  "recent_messages": [
    {
      "role": "user",
      "content": "AVL 树为什么要旋转？",
      "meta": {}
    },
    {
      "role": "assistant",
      "content": "可以把旋转理解为局部重排……",
      "meta": {}
    }
  ]
}
```

约束：

- recent messages 有数量上限。
- 不包含当前空 assistant placeholder。
- 空消息和失败消息需要明确过滤规则。
- conversation summary 是短期会话摘要，不等于长期记忆。

### 5.6 `runtime_policy`

当前阶段 RAG / Memory 均未启用：

```json
{
  "rag": {
    "enabled": false,
    "status": "placeholder",
    "reason": "rag_architecture_pending",
    "course_scoped": true,
    "require_source_refs_for_course_facts": false
  },
  "memory": {
    "enabled": false,
    "status": "placeholder",
    "scope_plan": "user_global_and_user_course",
    "reason": "memory_architecture_pending",
    "search_order": ["user_course", "user_global"],
    "write_policy": "whitelist_pending"
  },
  "safety": {
    "content_safety_review": true,
    "grounding_review": "not_applicable_until_rag_enabled"
  }
}
```

---

## 6. AgentScope 2.x Runtime 边界

### 6.1 已验证 AgentScope 2.0.3 能力

已通过项目虚拟环境 introspection 确认存在：

- `agentscope.agent.Agent`
- `agentscope.tool.Toolkit`
- `agentscope.tool.ToolGroup`
- `agentscope.tool.FunctionTool`
- `agentscope.middleware.RAGMiddleware`
- `agentscope.middleware.Mem0Middleware`
- `agentscope.rag.KnowledgeBase`
- `agentscope.rag.QdrantStore`
- `agentscope.workspace.LocalWorkspace`
- `Agent.reply_stream(...)`

当前阶段只使用 Agent / Toolkit / ToolGroup / FunctionTool / workspace / reply_stream 等边界，不启用真实 RAGMiddleware / Mem0Middleware。

### 6.2 输入分流

Backend snapshot 进入 `agent_service_v2` 后分为：

```text
custom_instructions / learner summary / runtime policy
  -> system prompt augmentation

recent_messages
  -> UserMsg / AssistantMsg

current message
  -> UserMsg(name="student")

learner_context
  -> read_learning_state tool

RAG / Memory
  -> placeholder tools
```

禁止继续把所有 context 拼成一条伪 `UserMsg(name="system_context")`。

### 6.3 System Prompt 约束

system prompt augmentation 应包含：

- 用户全局偏好。
- 课程内偏好。
- 指导等级。
- 当前课程范围。
- RAG 未启用。
- 长期记忆未启用。
- 能力未启用时必须报告。
- 禁止伪造课程来源。
- 禁止声称读取长期记忆。

---

## 7. Placeholder Tools

### 7.1 `read_learning_state`

`read_learning_state` 不再返回无意义占位，而是读取本轮 Backend snapshot 摘要。

返回示例：

```json
{
  "status": "available",
  "source": "backend_context_snapshot",
  "guidance_level": "L2",
  "weak_points_count": 3,
  "mastered_points_count": 5,
  "has_user_global_instruction": true,
  "has_course_local_instruction": true,
  "rag_enabled": false,
  "memory_enabled": false
}
```

### 7.2 `search_course_knowledge`

当前阶段只做 placeholder：

```json
{
  "status": "not_configured",
  "kind": "rag",
  "reason": "rag_architecture_pending",
  "message": "课程 RAG 架构尚未启用，当前不能检索课程知识库。"
}
```

行为约束：

- 不访问 Qdrant。
- 不返回假 chunks。
- 不生成 `source_refs`。
- 不允许回答中写“根据课程资料”。
- 前端展示“课程 RAG 尚未启用”。

### 7.3 `search_memory`

当前阶段只做 placeholder：

```json
{
  "status": "not_configured",
  "kind": "memory",
  "reason": "memory_architecture_pending",
  "scope_plan": "user_global_and_user_course",
  "message": "长期记忆架构尚未启用，当前不能读取用户长期记忆。"
}
```

### 7.4 `add_memory`

当前阶段只做 placeholder：

```json
{
  "status": "not_configured",
  "kind": "memory",
  "reason": "memory_architecture_pending",
  "message": "长期记忆写入尚未启用，本轮不会写入用户记忆。"
}
```

行为约束：

- 不接 Mem0。
- 不写 Qdrant。
- 不写 MySQL。
- 不产生真实 memory item。
- 不声称“已保存到长期记忆”。

---

## 8. 禁止兜底与显式报告原则

本设计禁止所谓“兜底伪装”。

### 禁止模式

```text
RAG 未启用 -> 用通用知识假装课程资料
Memory 未启用 -> 用 recent messages 假装长期记忆
Profile 缺失 -> 编造学生弱点
Source 缺失 -> 生成假 source_refs
Grounding 未执行 -> 显示“已通过”
```

### 正确模式

```text
能力未启用 -> 报告未启用
上下文缺失 -> 报告缺失
来源不足 -> 标注无课程来源
记忆不可用 -> 只使用当前会话和 Backend snapshot
```

示例：

```text
当前课程 RAG 检索尚未启用，我不能引用课程资料原文。
我可以基于通用知识解释 AVL 树，但这不会标记为课程资料依据。
```

```text
长期记忆尚未启用，我无法读取跨会话学习记录。
我只能基于当前会话和后端传入的学习画像回答。
```

---

## 9. EDU SSE 事件策略

现有 EDU v2 事件类型已足够，当前阶段不新增事件名。重点是复用 payload：

```text
workflow_started
debug_log
tool_started
tool_completed
tool_failed
source_refs
critic_completed
artifact_created
text_delta
content_safety_reviewed
workflow_completed
workflow_failed
```

### 9.1 Context attached

```json
{
  "type": "debug_log",
  "payload": {
    "event": "context.attached",
    "level": "info",
    "message": "已装载学习画像和运行策略",
    "attributes": {
      "context_version": "ai_chat_context_v1",
      "has_user_global_instruction": true,
      "has_course_local_instruction": true,
      "weak_points_count": 3,
      "recent_messages_count": 8,
      "rag_enabled": false,
      "memory_enabled": false
    }
  }
}
```

### 9.2 Placeholder RAG tool

```json
{
  "type": "tool_completed",
  "payload": {
    "tool_name": "search_course_knowledge",
    "display_name": "课程 RAG 尚未启用",
    "kind": "rag",
    "status": "not_configured",
    "reason": "rag_architecture_pending",
    "output_summary": "课程 RAG 架构尚未启用，未执行检索。"
  }
}
```

### 9.3 Placeholder Memory tool

```json
{
  "type": "tool_completed",
  "payload": {
    "tool_name": "search_memory",
    "display_name": "长期记忆尚未启用",
    "kind": "memory",
    "status": "not_configured",
    "reason": "memory_architecture_pending",
    "output_summary": "长期记忆架构尚未启用，未读取跨会话记忆。"
  }
}
```

### 9.4 Grounding 状态

如果 RAG 未启用，不能发送“grounding passed”。可以发送：

```json
{
  "type": "critic_completed",
  "payload": {
    "critic_type": "grounding",
    "status": "not_applicable",
    "reason": "rag_not_enabled",
    "message": "课程 RAG 未启用，本轮未进行基于课程来源的 grounding 审查。"
  }
}
```

### 9.5 Source refs

当前阶段不生成真实 `source_refs`。

如果没有真实 RAG 结果：

- 不发送 `source_refs`；
- 不保存假 sources；
- 不显示空引用区。

---

## 10. Frontend 展示策略

Frontend 最小改动：

1. Tool card 支持 `payload.status = "not_configured"`。
2. RAG tool 展示“课程 RAG 尚未启用”。
3. Memory tool 展示“长期记忆尚未启用”。
4. `critic_completed.status = "not_applicable"` 展示为“未进行课程来源 grounding 审查”。
5. 没有真实 `source_refs` 时不展示引用卡。
6. Developer console 保留完整 `debug_log`。

不要把 placeholder 工具显示成：

```text
检索完成
命中 0 条
记忆检索完成
防幻觉审查通过
```

这些都会误导用户以为真实能力已运行。

---

## 11. 分阶段实施计划

### Phase 0：AgentScope 2.x 边界核验

- 核验当前用到的 AgentScope 2.x API。
- 不启用真实 RAG/Mem0。
- 记录 placeholder 工具使用的 ToolGroup / FunctionTool 形态。

### Phase 1：Backend Context Snapshot

- 新增 `users.custom_instruction`。
- `/api/v1/users/me` 支持读写 `custom_instruction`。
- `TutoringPayloadBuilder` 输出结构化 context snapshot。
- `runtime_policy.rag.enabled = false`。
- `runtime_policy.memory.enabled = false`。
- 保留旧字段兼容一段时间。

### Phase 2：agent_service_v2 context 输入重构

- 不再把所有 context 拼成伪 `system_context` 用户消息。
- system prompt augmentation 明确能力边界。
- recent messages 转为真实 `UserMsg` / `AssistantMsg`。
- `read_learning_state` 读取 Backend snapshot。

### Phase 3：RAG / Memory Placeholder Tools

- 新增或调整：
  - `search_course_knowledge`
  - `search_memory`
  - `add_memory`
- 全部返回 `not_configured / architecture_pending`。
- 不访问 Qdrant / Mem0 / MySQL。

### Phase 4：Frontend 展示未启用状态

- Tool card 展示 placeholder 状态。
- Message 展示 grounding not applicable。
- 不显示假 source refs。
- Developer console 展示 context attached / partial warning。

### Phase 5：后续单独设计真实 RAG / Memory

- 后续再设计真实 RAG 架构。
- 后续再设计真实 Mem0 / long-term memory 架构。
- 真实接入不属于本设计实施范围。

---

## 12. 测试与验收清单

### 12.1 Backend

- 有课程画像时输出结构化 weak/mastered/blindspot。
- 无课程画像时明确空数组/默认值，不编造弱点。
- `users.custom_instruction` 与 course-local instruction 均进入 `custom_instructions`。
- `scope != course` 时不注入 course-local profile。
- recent messages 不包含当前空 assistant placeholder。
- `runtime_policy.rag.enabled = false`。
- `runtime_policy.memory.enabled = false`。

### 12.2 Agent Service v2

- system prompt 包含用户偏好、课程偏好、能力未启用约束。
- recent messages 正确转为 UserMsg / AssistantMsg。
- `read_learning_state` 返回 Backend snapshot 摘要。
- `search_course_knowledge` 返回 `not_configured`。
- `search_memory` 返回 `not_configured`。
- `add_memory` 返回 `not_configured`。
- 不启用真实 RAGMiddleware / Mem0Middleware。
- 不访问 Qdrant / Mem0 / MySQL。

### 12.3 SSE

- placeholder tools 产生 `tool_completed`，payload 中 `status = not_configured`。
- RAG 未启用时不发送 `source_refs`。
- grounding 未执行时 `critic_completed.status = not_applicable`。
- `workflow_completed` 正常结束。
- 能力未启用不导致 stream 崩溃。

### 12.4 Frontend

- RAG placeholder 显示“课程 RAG 尚未启用”。
- Memory placeholder 显示“长期记忆尚未启用”。
- 不显示空引用卡。
- 不显示“检索完成 / 命中 0 条”来冒充真实检索。
- Grounding not applicable 不显示成“通过防幻觉审查”。

### 12.5 禁止兜底

验收必须覆盖：

```text
用户要求“结合课程资料” -> 系统报告 RAG 未启用，不生成假来源。
用户要求“结合长期记忆” -> 系统报告长期记忆未启用，不伪装成已读取。
用户画像缺失 -> 系统报告画像缺失，不编造弱点。
```

---

## 13. 完成定义

本设计对应的完成定义：

```text
1. Backend 已输出结构化个性化上下文快照。
2. users.custom_instruction 支持读写。
3. agent_service_v2 已按 AgentScope 2.x 边界消费 context。
4. read_learning_state tool 能读取 Backend snapshot。
5. search_course_knowledge/search_memory/add_memory 作为 placeholder tools 存在。
6. 未启用能力通过 tool event 和回答显式报告。
7. 前端展示 placeholder / 未启用状态。
8. 不产生假 source_refs。
9. 不产生假 long-term memory。
10. 不做 fallback 伪装。
```

---

## 14. 后续扩展点

后续单独设计 RAG / Memory 时，应基于本设计保留的边界接入：

```text
search_course_knowledge placeholder
  -> real AgentScope-native course RAG tool / middleware

search_memory / add_memory placeholder
  -> real user-global + user-course memory architecture

runtime_policy.rag.enabled=false
  -> true

runtime_policy.memory.enabled=false
  -> true
```

真实接入前仍需遵守 `agentscope-2x` skill：

- 先核验 AgentScope API 行为。
- 不编造 API。
- 不把旧 `agent_service/` 手写 RAG/Memory 直接搬到 v2 主线。
- EDU SSE 协议继续由 adapter 维护。
- 工具结果必须结构化、可审计、可测试。
