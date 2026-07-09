# AIChat 学习进度与最近答题查询工具设计

**日期：** 2026-07-09  
**状态：** 已确认方向，待实施计划  
**目标模块：** `backend/`、`agent_service_v2/`、`frontend/`  
**架构基线：** Backend 持有学习事实与权限；Agent Service v2 使用 AgentScope 2.x tool 按需查询；Frontend 继续只连 Backend。

## 1. 背景

当前 AIChat 已经打通 Frontend -> Backend -> `agent_service_v2` 的 AgentScope v2 主链路，但 AIChat 对学生学习状态的理解仍偏粗：

- Backend payload 只传入扁平 `user_profile`，主要包含引导等级、薄弱知识点清单、已掌握知识点清单和课程级自定义提示。
- `agent_service_v2` 当前把这些上下文拼成 `UserMsg(name="system_context")`，还没有通过工具按需读取学习事实。
- 系统已有真实学习进度数据：`LearningActivity`、`LearningPath`、`Evaluation`、`QuizSession`、`QuizAnswer`、`QuizQuestion`。
- AIChat 目前没有直接消费最近答题和错题，因此无法可靠回答“我错在哪”“下一步怎么学”。

本设计目标是让 AIChat 通过只读 tool 真正查询学习进度和最近答题证据，再给出下一步学习建议。第一阶段不写回学习路径，不修改学习状态，不接真实 RAG / Memory。

## 2. 当前可用数据事实

### 2.1 学习活动

`LearningActivity` 已记录：

- `user_id`
- `course_id`
- `node_id`
- `node_name`
- `resource_id`
- `activity_type`
- `duration_seconds`
- `occurred_at`
- `metadata_json`

前端当前已有埋点：

- 学习路径节点切换：`node_view`
- 练习开始：`node_practice_start`
- 练习提交：`node_practice_submit`
- 资源查看：`resource_view`
- 资源学习时长：`resource_study`

### 2.2 节点实时进度

`build_node_progress_rows(user_id, course_id, db)` 已按 active KG 节点聚合：

- `node_id`
- `node_name`
- `assessment_state`
- `status`
- `study_duration_seconds`
- `mastery_score`
- `mastery_label`
- `question_count`
- `attempt_count`
- `wrong_count`
- `resource_visit_count`
- `last_activity_at`

`LearningPathService.get_learning_path()` 已将实时进度合并进学习路径节点，并能返回 `current_position`。

### 2.3 题目与答题

当前题目和答题由三张表表示：

- `quiz_questions`
- `quiz_sessions`
- `quiz_answers`

`quiz_questions` 关键字段：

- `id`
- `course_id`
- `catalog_id`
- `chapter`
- `knowledge_point`
- `type`
- `source`
- `personalized`
- `owner_user_id`
- `difficulty`
- `content`
- `options`
- `correct_answer`
- `explanation`

`options` 实际存在两种形态：

```json
["A", "B", "C", "D"]
```

```json
[
  { "key": "A", "text": "正确" }
]
```

Tool 输出必须统一成：

```json
[
  { "key": "A", "text": "正确" }
]
```

`quiz_sessions` 保存一次练习整体表现：`score`、`correct_count`、`total_count`、`time_spent`、`diagnosis_json`。

`quiz_answers` 保存单题答题事实：`user_answer`、`is_correct`、`correct_answer`、`explanation`。

`QuizAnswer` 本身没有 `user_id/course_id/node_id`，查询必须 join `QuizSession` 与 `QuizQuestion`。

## 3. 用户确认的产品目标

第一阶段选择：**AI 能根据真实学习进度和最近答题给出下一步建议，但不写回学习路径或进度状态。**

用户确认：

- 使用真实查询，不只依赖 prompt snapshot。
- Tool 可返回最多 10 道题，长度可接受。
- 最近答题应绑定到指定节点或知识点。
- AI 流程应先查有哪些知识点和进度，再按弱点或用户指定知识点查询最近答题。

## 4. 方案选择

### 4.1 备选方案

**方案 A：Backend 预聚合 snapshot，Agent 本地查询 snapshot**

Backend 每轮把进度和最近错题一起塞进 `context`。Agent tool 只查本轮 snapshot。

优点：实现简单，不需要 internal API。  
缺点：每轮都带大量数据，不能真正按需查；上下文容易膨胀；错题详情选择不灵活。

**方案 B：AgentScope tool 通过 Backend internal API 真查询**

Agent Service v2 注册只读工具。工具通过 Backend internal API 查询当前用户和课程的学习进度、节点详情和最近答题。

优点：按需查询，事实来源清晰，能返回指定节点或知识点的最近答题证据。  
缺点：需要新增 Backend internal API、service-to-service 鉴权、超时和错误处理。

**方案 C：直接将最近错题完整塞进 system prompt**

Backend 每轮传最近全课程错题。

优点：最快。  
缺点：不绑定意图，token 浪费，AI 容易误用全课程错题回答单个知识点问题。

### 4.2 选择

选择 **方案 B**。

原因：

- 当前需求明确要求“真正查询”。
- AI 需要先看学习进度地图，再按弱点或用户指定知识点钻取最近答题。
- Backend 仍是 MySQL 权威访问边界；Agent Service 不直接访问 MySQL。
- Tool 调用轨迹能在 AIChat 中可观察，便于调试与验收。

## 5. 架构

```text
Frontend AIChat
  -> Backend /api/v1/tutoring/chat
  -> Backend TutoringPayloadBuilder supplies lightweight context
  -> Backend TutoringStreamAdapter proxies /agent/v2/workbench/chat
  -> agent_service_v2 Workbench Agent
       - read_learning_progress tool
       - read_recent_answers tool
       -> Backend internal API
  -> Agent uses queried facts to answer and optionally write Markdown artifact
```

边界规则：

- Frontend 不直连 Agent Service。
- Agent Service 不写 MySQL。
- Backend 不导入 `agent_service_v2`。
- Backend internal API 只服务 Agent Service tool，不暴露给前端页面。
- Tool 第一阶段只读。

## 6. Backend Internal API

### 6.1 鉴权

新增 internal API 必须有 service-to-service 鉴权，不复用学生 access token。

建议第一阶段使用内部共享 token：

- Header：`X-Internal-Agent-Token`
- Backend 从 settings 读取 token。
- Agent Service 从 settings/env 读取 token。
- token 不写日志。

鉴权失败返回 401 或 403。

### 6.2 进度总览接口

```text
POST /internal/ai-chat/learning-progress
```

请求：

```json
{
  "user_id": "u1",
  "course_id": "course1",
  "limit_nodes": 50
}
```

响应：

```json
{
  "status": "available",
  "course_id": "course1",
  "current_position": {
    "node_id": "n-avl",
    "node_name": "AVL 树旋转"
  },
  "summary": {
    "total_nodes": 20,
    "completed_count": 4,
    "in_progress_count": 2,
    "weak_count": 3,
    "pending_count": 11,
    "mastery_rate": 20
  },
  "nodes": [
    {
      "node_id": "n-avl",
      "node_name": "AVL 树旋转",
      "status": "recommended",
      "assessment_state": "weak",
      "mastery_score": 52.0,
      "attempt_count": 8,
      "wrong_count": 4,
      "question_count": 10,
      "study_duration_seconds": 600,
      "resource_visit_count": 2,
      "last_activity_at": "2026-07-09T10:00:00"
    }
  ],
  "recent_activity": [
    {
      "activity_type": "node_practice_submit",
      "node_id": "n-avl",
      "node_name": "AVL 树旋转",
      "duration_seconds": 300,
      "occurred_at": "2026-07-09T10:00:00"
    }
  ],
  "source": "backend.learning_progress"
}
```

实现来源：

- `LearningPathService.get_learning_path()`
- `build_node_progress_rows()`
- `LearningActivity`

节点状态映射沿用当前 `learning_path_service.map_assessment_to_status()`：

- `mastered -> completed`
- `learning -> in_progress`
- `weak -> recommended`
- `pending_practice -> pending`
- `unstarted -> pending`

### 6.3 最近答题接口

```text
POST /internal/ai-chat/recent-answers
```

请求：

```json
{
  "user_id": "u1",
  "course_id": "course1",
  "node_id": "n-avl",
  "knowledge_point": null,
  "limit": 10,
  "only_wrong": true
}
```

查询范围规则：

1. 如果传 `node_id`，Backend 查询 active KG，将 `node_id` 解析为 `node.name`，用该名称作为 `knowledge_point`。
2. 如果没有 `node_id`，但传了 `knowledge_point`，直接使用 `knowledge_point`。
3. 如果两者都没有，允许返回课程最近答题，响应中标记 `scope="course_recent"`。
4. 如果 `node_id` 和 `knowledge_point` 都传且不一致，以 `node_id` 解析出的节点名为准，并返回 warning。

默认查询：

```text
current user + current course + specified knowledge_point + wrong answers only
order by QuizAnswer.create_time desc
limit 10
```

响应：

```json
{
  "status": "available",
  "scope": "knowledge_point",
  "query": {
    "node_id": "n-avl",
    "resolved_knowledge_point": "AVL 树旋转",
    "only_wrong": true,
    "limit": 10
  },
  "items": [
    {
      "quiz_id": "qs1",
      "question_id": "q1",
      "answered_at": "2026-07-09T10:00:00",
      "chapter": "树与二叉树",
      "knowledge_point": "AVL 树旋转",
      "type": "single_choice",
      "difficulty": "medium",
      "source": "baseline",
      "personalized": false,
      "content": "插入节点后应进行哪种旋转？",
      "options": [
        { "key": "A", "text": "左旋" },
        { "key": "B", "text": "右旋" }
      ],
      "user_answer": "A",
      "correct_answer": "B",
      "is_correct": false,
      "explanation": "此处属于 RR 型失衡，应进行左旋修正。"
    }
  ],
  "summary": {
    "returned_count": 1,
    "has_more": false
  },
  "warnings": []
}
```

SQL 逻辑：

```sql
SELECT
  qs.id AS quiz_id,
  qq.id AS question_id,
  qa.create_time AS answered_at,
  qq.chapter,
  qq.knowledge_point,
  qq.type,
  qq.difficulty,
  qq.source,
  qq.personalized,
  qq.content,
  qq.options,
  qa.user_answer,
  qa.correct_answer,
  qa.is_correct,
  qa.explanation
FROM quiz_answers qa
JOIN quiz_sessions qs ON qa.quiz_id = qs.id
JOIN quiz_questions qq ON qa.question_id = qq.id
WHERE qs.user_id = :user_id
  AND qs.course_id = :course_id
  AND qq.knowledge_point = :knowledge_point
  AND qa.is_correct = false
  AND qa.is_deleted = false
  AND qs.is_deleted = false
  AND qq.is_deleted = false
ORDER BY qa.create_time DESC
LIMIT :limit
```

`limit` 最大值为 10。

## 7. Backend Service 设计

新增 service 层，避免 internal router 里写查询逻辑：

```text
backend/app/services/ai_chat_learning_context.py
```

职责：

- `build_learning_progress_overview(db, user_id, course_id, limit_nodes)`
- `query_recent_answers(db, user_id, course_id, node_id, knowledge_point, limit, only_wrong)`
- `resolve_node_knowledge_point(db, course_id, node_id)`
- `normalize_question_options(options)`

Router 只做：

- internal token 校验
- request schema 校验
- 调 service
- 包装响应

## 8. Agent Service v2 Tool 设计

新增 tool 模块：

```text
agent_service_v2/src/agent_service_v2/tools/learning_progress.py
```

注册到 Workbench Toolkit：

```text
ToolGroup name="learning_progress"
  - read_learning_progress
  - read_recent_answers
```

AgentScope 注册方式：

- 使用当前已验证的 `agentscope.tool.FunctionTool` 包装 Python 函数。
- 两个工具都必须设置 `is_read_only=True`。
- 使用当前已验证的 `ToolGroup` 加入 Workbench `Toolkit`，分组名固定为 `learning_progress`。
- `user_id` 与 `course_id` 不暴露为模型可填写参数，由 `WorkbenchAgentFactory.create_agent()` 在构造工具闭包时注入当前 run 的用户和课程上下文。
- LLM 只能提供 `node_id`、`knowledge_point`、`limit`、`only_wrong` 等查询意图参数。

Tool 行为：

### 8.1 `read_learning_progress`

入参：

```json
{
  "limit_nodes": 50
}
```

实际调用 Backend：

```json
{
  "user_id": "<current user>",
  "course_id": "<current course>",
  "limit_nodes": 50
}
```

返回 Backend 响应原结构。

### 8.2 `read_recent_answers`

入参：

```json
{
  "node_id": "n-avl",
  "knowledge_point": null,
  "limit": 10,
  "only_wrong": true
}
```

Tool 自动补 `user_id/course_id`，并调用 internal API。

错误策略：

- Backend 401/403：返回 `status="error"`、`reason="internal_auth_failed"`，不暴露 token。
- Backend 404 node：返回 `status="not_found"`、`reason="node_not_found"`。
- 超时：返回 `status="unavailable"`、`reason="backend_timeout"`。
- 没有答题：返回 `status="empty"`，`items=[]`。

## 9. Agent 行为规则

Workbench system prompt 和 tool description 需要约束：

1. 用户问整体学习建议时，先调用 `read_learning_progress`。
2. 用户问“我错在哪”“为什么不会”“某知识点怎么补”时，先调用 `read_learning_progress` 定位节点，再调用 `read_recent_answers` 查询证据。
3. 用户明确指定知识点时，用该知识点查询最近答题。
4. 用户未指定知识点时，优先选择：
   - weak / recommended 节点
   - current in_progress 节点
   - pending_practice 节点
5. 不能编造错因。没有最近答题时，只能说“当前没有足够答题记录”，并给通用复习建议。
6. Tool 只读。AI 不得声称已修改学习路径、已更新掌握状态、已保存长期记忆。
7. 需要生成可保存建议时，复用现有 `write_artifact_file` 写 Markdown artifact。

## 10. Frontend 展示

第一阶段不新增页面。

复用现有：

- 工具调用卡：展示 `read_learning_progress`、`read_recent_answers`。
- Developer Console：查看 tool/debug 事件。
- 工作区 artifact：AI 可生成 Markdown “下一步学习建议”。

如果后续要更强可视化，可单独新增 `LearningAdvice` artifact plugin；不纳入本阶段。

## 11. API 与协议漂移

有接口漂移：

- 新增 Backend internal API：
  - `POST /internal/ai-chat/learning-progress`
  - `POST /internal/ai-chat/recent-answers`
- Agent v2 Toolkit 新增只读工具：
  - `read_learning_progress`
  - `read_recent_answers`

无 Client API 漂移：

- Frontend 仍使用 `/api/v1/tutoring/chat`。
- 前端不直接调用 internal API。

无 SSE 事件类型漂移：

- 继续使用现有 `tool_started`、`tool_completed`、`debug_log`、`artifact_created`、`text_delta` 等事件。

若需要在工具卡展示更丰富摘要，后续可扩展 `tool_completed.payload.output_summary`，但第一阶段不新增事件名。

## 12. 安全与隐私

- Internal API 必须校验 service token。
- Internal API 只允许查询请求中的 `user_id/course_id`，不得跨用户汇总。
- Agent Service tool 不接收前端传来的任意 user_id；由 Workbench runtime 当前 run context 注入。
- Backend 不返回无关课程的题目或答题。
- 最近答题最多返回 10 条。
- 不返回其他学生数据。
- 不把 internal token 写入日志、debug_log 或 SSE。

## 13. 测试策略

### 13.1 Backend

新增测试：

- `read_learning_progress` 返回 current_position、节点状态、wrong_count、attempt_count。
- `recent_answers` 通过 `node_id` 解析 KG 节点名后查询指定知识点错题。
- `recent_answers` 通过 `knowledge_point` 查询。
- 默认只返回错题。
- `only_wrong=false` 返回正确和错误答题。
- 最多返回 10 条。
- options 被统一为 `{key,text}`。
- `node_id` 与 `knowledge_point` 冲突时，以 `node_id` 为准并返回 warning。
- internal token 缺失或错误时拒绝。

### 13.2 Agent Service v2

新增测试：

- Toolkit 注册 `read_learning_progress` 和 `read_recent_answers`。
- Tool 自动补 `user_id/course_id`。
- Tool 正确调用 Backend internal API。
- Backend empty/error/timeout 被转换为结构化 tool result。
- Workbench prompt 包含“查不到不能编造错因”的规则。

### 13.3 Integration

用 fake Backend internal client 验证：

- 用户问“下一步学什么”时，Agent 可调用 progress tool。
- 用户问“AVL 错在哪”时，Agent 可调用 recent answers tool。
- 没有答题记录时，不生成具体错因。

## 14. 完成定义

本阶段完成后：

1. AIChat 可以通过 tool 查询当前课程学习进度总览。
2. AIChat 可以按节点或知识点查询最近最多 10 条答题记录。
3. 最近答题与知识点强绑定，不是全局随便取最近 10 题。
4. AI 能基于真实答题证据给出下一步学习建议。
5. AI 查不到数据时明确说明证据不足。
6. 不写回学习路径，不修改进度状态。
7. Frontend 不新增 internal API 调用。
8. 所有查询仍由 Backend 持有 MySQL 访问权。

## 15. 后续扩展

后续可以单独设计：

- 将 AI 建议写入学习路径或计划。
- 新增 LearningAdvice 工作区插件。
- 按错因模式聚类 recent mistakes。
- 接入真实课程 RAG，结合资源原文给建议。
- 长期记忆记录跨课程学习偏好与稳定错因。
