# Agent-API 内部接口规范

> Backend (FastAPI, Port 8001) ↔ Agent Service (FastAPI + AgentScope, Port 8002)
> 版本: v5.0 | 日期: 2026-05-17

---

## 通用约定

### 返回格式

所有同步接口统一返回 JSON：

```json
{ "code": 200, "message": "success", "data": {} }
```

### 认证方式

服务间调用，Header: `X-API-Key: <internal_key>`

### 流式响应 (SSE)

`Content-Type: text/event-stream`，每条消息格式：

```
data: {"type": "chunk", "content": "..."}
data: {"type": "tool_call", "tool": "diagram", "data": "..."}
data: {"type": "done", ...}
```

### 异步任务

资源生成类接口：Agent 立即返回 202 `{task_id}`，完成后 POST webhook_url 回调 Backend。

---

## 一、智能辅导 `/agent/v1/tutoring`

### 1.1 对话

```
POST /agent/v1/tutoring/chat
```

**Content-Type:** `text/event-stream` (SSE)

**请求体 `application/json`：**

> **Qdrant 检索由 Agent Service 自行完成。** Agent 收到请求后，自行将用户消息向量化 → Qdrant 混合检索 → Rerank → 注入 Prompt。Backend 仅传入 SQL 数据（user_profile、conversation_summary、recent_messages）。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| user_id | string | 是 | 用户 ID |
| course_id | string | 是 | 课程 ID |
| conversation_id | string | 否 | 对话 ID（继续已有对话时传入） |
| message | string | 是 | 用户当前消息 |
| user_profile | object | 是 | 用户画像（由 Backend 从 SQL 组装） |
| user_profile.guidance_level | string | 是 | 引导粒度：L1 / L2 / L3 |
| user_profile.modal_preference | object | 否 | 模态偏好 |
| user_profile.knowledge_mastered | array | 否 | 已掌握知识点名称列表 |
| user_profile.knowledge_weak | array | 否 | 薄弱知识点名称列表 |
| conversation_summary | string | 否 | 全局对话摘要（记忆压缩后生成） |
| recent_messages | array | 否 | 最近 N 轮缓冲消息 |
| recent_messages[].role | string | 是 | user / assistant |
| recent_messages[].content | string | 是 | 消息内容 |

**SSE 事件类型：**

| type | 说明 |
|------|------|
| chunk | 文本片段 |
| diagram | 图解（Mermaid 语法或图表 JSON） |
| knowledge_points | 引用的知识点 [{name, chapter, mastery}] |
| suggestion | 补充学习建议 + 相似例题 |
| done | 本轮回答完成 |

**`done` 事件 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| message_id | string | 本条回复的消息 ID |
| knowledge_points_used | array | 回答中引用的知识点 |
| suggested_exercises | array | 推送的相似例题 |

---

## 二、用户画像 `/agent/v1/profile`

### 2.1 冷启动引导对话

```
POST /agent/v1/profile/initialize
```

**Content-Type:** `text/event-stream` (SSE)

**请求体 `application/json`：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| user_id | string | 是 | 用户 ID |
| course_id | string | 是 | 课程 ID |
| user_basic_info | object | 是 | 用户基础信息 |
| user_basic_info.major | string | 否 | 专业 |
| user_basic_info.grade | string | 否 | 年级 |

**SSE 事件类型：**

| type | 说明 |
|------|------|
| message | Agent 提问（了解用户基础水平和偏好） |
| chunk | 流式文本片段 |
| done | 引导完成，携带初始画像 |

**`done` 事件 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| initial_profile | object | 初始画像数据，结构同 `/profile/generate` 响应 |

### 2.2 生成/刷新画像

```
POST /agent/v1/profile/generate
```

**请求体 `application/json`：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| user_id | string | 是 | 用户 ID |
| course_id | string | 是 | 课程 ID |
| evaluation_data | object | 否 | 最新学习效果评估 |
| evaluation_data.progress | object | 否 | 学习进度 |
| evaluation_data.mastery | object | 否 | 掌握程度 |
| evaluation_data.resource_usage | object | 否 | 资源使用统计 |
| quiz_history | array | 否 | 练习历史记录 |
| quiz_history[].score | number | 是 | 正确率 |
| quiz_history[].chapter | string | 否 | 章节 |
| quiz_history[].created_at | string | 是 | 完成时间 |
| resource_usage_stats | object | 否 | 资源类型使用比例 |
| resource_usage_stats.video_count | integer | 否 | 视频使用次数 |
| resource_usage_stats.document_count | integer | 否 | 文档使用次数 |
| resource_usage_stats.code_count | integer | 否 | 代码资源使用次数 |
| resource_usage_stats.exercise_count | integer | 否 | 练习题使用次数 |
| drive_intent_data | object | 否 | 近期学习频率（由 Backend 从 SQL 统计） |
| drive_intent_data.recent_7d_sessions | integer | 否 | 近 7 天学习次数 |
| drive_intent_data.recent_7d_duration | integer | 否 | 近 7 天学习时长（分钟） |

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| modal_preference | object | 模态偏好雷达图 |
| modal_preference.video_animation | number | 视频动画 0-100 |
| modal_preference.chart_logic | number | 图表逻辑 0-100 |
| modal_preference.text_analysis | number | 文字解析 0-100 |
| modal_preference.code_practice | number | 代码实践 0-100 |
| modal_preference.formula_derivation | number | 公式推导 0-100 |
| guidance_level_suggestion | object | 引导粒度建议 |
| guidance_level_suggestion.recommended | string | 建议级别：L1 / L2 / L3 |
| guidance_level_suggestion.reason | string | 建议依据 |
| knowledge_coordinates | array | 知识坐标标签 |
| knowledge_coordinates[].name | string | 知识点名称 |
| knowledge_coordinates[].status | string | mastered / learning |
| cognitive_blindspots | array | 认知盲区标签 |
| cognitive_blindspots[].name | string | 知识点名称 |
| cognitive_blindspots[].error_count | integer | 错误次数 |
| cognitive_blindspots[].severity | string | high / medium / low |
| drive_intent | object | 驱动意图 |
| drive_intent.type | string | exam_sprint / daily_homework / casual |
| drive_intent.intensity | number | 近 7 天学习强度 0-100 |
| discipline_badge | object | 学科底座徽章 |
| discipline_badge.subject | string | 学科名称 |
| discipline_badge.level | string | 徽章等级 |
| discipline_badge.streak_days | integer | 连续学习天数 |

---

## 三、学习效果评估 `/agent/v1/evaluation`

### 3.1 生成学习效果评估

```
POST /agent/v1/evaluation/generate
```

**请求体 `application/json`：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| user_id | string | 是 | 用户 ID |
| course_id | string | 是 | 课程 ID |
| learning_progress | object | 是 | 学习进度数据（由 Backend 从 SQL 统计） |
| learning_progress.chapter_progress | array | 是 | 各章节完成度 |
| learning_progress.chapter_progress[].chapter | string | 是 | 章节名称 |
| learning_progress.chapter_progress[].completion_rate | number | 是 | 完成率 0-100 |
| learning_progress.chapter_progress[].time_spent | integer | 是 | 学习时长（分钟） |
| quiz_results | array | 是 | 各次练习结果汇总 |
| quiz_results[].chapter | string | 是 | 章节 |
| quiz_results[].score | number | 是 | 正确率 |
| quiz_results[].created_at | string | 是 | 完成时间 |
| resource_usage | object | 是 | 资源使用统计 |
| resource_usage.by_type | object | 是 | `{video: N, document: N, code: N, exercise: N}` |
| resource_usage.by_chapter | object | 否 | 各章节资源使用分布 |

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| progress_table | object | 学习进度表 |
| progress_table.columns | array | 表头 [{key, title}] |
| progress_table.rows | array | 数据行 |
| mastery_table | object | 知识点掌握程度表 |
| mastery_table.columns | array | 表头 |
| mastery_table.rows | array | 数据行 |
| resource_usage_table | object | 资源使用习惯记录表 |
| resource_usage_table.columns | array | 表头 |
| resource_usage_table.rows | array | 数据行 |
| summary_text | string | LLM 综合文字总结 |

---

## 四、测验评估 `/agent/v1/assessment`

### 4.1 测验评估

```
POST /agent/v1/assessment/evaluate
```

**请求体 `application/json`：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| user_id | string | 是 | 用户 ID |
| course_id | string | 是 | 课程 ID |
| quiz_id | string | 是 | 练习 ID |
| questions | array | 是 | 题目列表 |
| questions[].id | string | 是 | 题目 ID |
| questions[].type | string | 是 | 题型 |
| questions[].content | string | 是 | 题目内容 |
| questions[].options | array | 否 | 选项列表 |
| questions[].correct_answer | string | 是 | 正确答案 |
| questions[].knowledge_point | string | 是 | 关联知识点 |
| answers | array | 是 | 用户答案 |
| answers[].question_id | string | 是 | 题目 ID |
| answers[].answer | string | 是 | 用户提交的答案 |
| user_mastery | object | 否 | 用户当前知识点掌握度 |

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| per_question_results | array | 每题评估结果 |
| per_question_results[].question_id | string | 题目 ID |
| per_question_results[].is_correct | boolean | 是否正确 |
| per_question_results[].explanation | string | LLM 解析 |
| per_question_results[].related_knowledge_points | array | 关联知识点 |
| diagnosis | object | 综合诊断 |
| diagnosis.summary | string | 诊断总结 |
| diagnosis.weak_points | array | 薄弱知识点 |
| diagnosis.weak_points[].name | string | 知识点名称 |
| diagnosis.weak_points[].error_pattern | string | 错误模式描述 |
| diagnosis.suggestions | array | 复习建议 |

---

## 五、学习路径 `/agent/v1/learning-path`

### 5.1 生成学习路径

```
POST /agent/v1/learning-path/generate
```

**请求体 `application/json`：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| user_id | string | 是 | 用户 ID |
| course_id | string | 是 | 课程 ID |
| evaluation | object | 是 | 学习效果评估（来自 `/evaluation/generate` 或 SQL 缓存） |
| profile | object | 是 | 用户画像（来自 `/profile/generate` 或 SQL 缓存） |
| knowledge_graph | object | 是 | 静态课程知识点图谱（JSON 格式的前置依赖关系） |
| knowledge_graph.nodes | array | 是 | 图谱节点 [{id, name, chapter}] |
| knowledge_graph.edges | array | 是 | 前置依赖 [{from, to}] |

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| nodes | array | 路径节点 |
| nodes[].id | string | 节点 ID |
| nodes[].name | string | 知识点名称 |
| nodes[].status | string | completed / in_progress / pending / recommended |
| nodes[].mastery | number | 掌握度 0-100 |
| nodes[].order | integer | 排序序号 |
| nodes[].reason | string | 排在该位置的原因说明 |
| edges | array | 节点间边 |
| edges[].from | string | 前置节点 ID |
| edges[].to | string | 后置节点 ID |
| current_position | object | 当前学习位置 |
| current_position.node_id | string | 当前节点 ID |
| current_position.node_name | string | 当前节点名称 |

---

## 六、资源生成 `/agent/v1/resources`

### 6.1 生成资源库

```
POST /agent/v1/resources/generate
```

**请求体 `application/json`：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| user_id | string | 是 | 触发教师用户 ID |
| course_id | string | 是 | 课程 ID |
| course_materials | array | 是 | 课程原始资料列表（开发时硬编码导入后向量化存储的信息） |
| course_materials[].id | string | 是 | 资料 ID |
| course_materials[].title | string | 是 | 资料标题 |
| course_materials[].content | string | 是 | 资料文本内容 |
| course_materials[].chapter | string | 是 | 所属章节 |
| course_materials[].type | string | 是 | 资料类型 |
| webhook_url | string | 是 | 完成回调 URL（Backend 的 `/api/v1/webhooks/agent`） |

**响应：** HTTP 202

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | string | 异步任务 ID |
| estimated_duration | integer | 预计完成时间（秒） |

**Webhook 回调 payload（Agent → Backend）：**

| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | string | 任务 ID |
| task_type | string | `resource_generation` |
| status | string | completed / failed |
| result | object | 完成时携带 |
| result.resources | array | 生成的资源列表 |
| result.resources[].title | string | 资源标题 |
| result.resources[].type | string | 类型：document / mindmap / exercise / reading / code |
| result.resources[].content | string | 资源内容 |
| result.resources[].chapter | string | 所属章节 |
| result.resources[].tags | array | 标签 |
| error_message | string | 失败时携带 |

---

## 七、记忆压缩 `/agent/v1/memory`

### 7.1 记忆压缩

```
POST /agent/v1/memory/compress
```

**触发条件：** Backend 检测到对话轮数达到阈值（如 20 轮），后台异步调用

**请求体 `application/json`：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| user_id | string | 是 | 用户 ID |
| conversation_id | string | 是 | 对话 ID |
| old_summary | string | 否 | 旧的全局摘要（首次压缩时为空） |
| messages_to_compress | array | 是 | 本轮需要压缩的对话消息（最早的 N 轮） |
| messages_to_compress[].role | string | 是 | user / assistant |
| messages_to_compress[].content | string | 是 | 消息内容 |
| messages_to_compress[].timestamp | string | 是 | 消息时间 |
| existing_facts | array | 否 | 已存储的长期记忆事实 ID 列表（用于去重） |

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| new_summary | string | 融合后的新全局摘要 |
| extracted_facts | array | 提取的语义事实 |
| extracted_facts[].content | string | 事实内容（如"用户在递归概念上卡壳"） |
| extracted_facts[].fact_type | string | 事实类型：blind_spot / mastered_point / cognitive_preference |
| extracted_facts[].knowledge_point | string | 关联知识点名称（如有） |
| extracted_facts[].confidence | number | 置信度 0-1 |

---

## 八、健康检查 `/agent/v1`

### 8.1 健康检查

```
GET /agent/v1/health
```

**响应 `data`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| status | string | `healthy` / `degraded` / `unhealthy` |
| qdrant_connected | boolean | Qdrant 向量库连接状态 |
| model_loaded | boolean | 大模型加载状态 |
| model_name | string | 当前加载的模型名称 |
| uptime_seconds | integer | 服务运行时长（秒） |
