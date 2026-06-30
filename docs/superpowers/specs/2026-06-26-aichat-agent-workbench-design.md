# AIChat Agent 工作台 v1 设计

> 日期：2026-06-26  
> 状态：待评审  
> 目标：将学生端 AIChat 从单纯问答页改造成依靠 Agents 的个性化学习主入口。

## 一、背景与目标

比赛主线应是“依靠 Agents 的个性化智能学习系统”。现有学生端已有画像、路径、资源、练习、学习效果、个性化资源等页面，但 AIChat 尚未承担统一 Agent 入口职责。下一阶段不优先新增学生首页，而是改造 AIChat，让学生通过对话直接理解自己的学习状态、看到 Agent 调用工具、获得跳转或自动动作。

v1 目标：

- AIChat 支持真实流式输出或明确修复当前非流式问题。
- 前端能展示 tool 调用过程，而不是只显示最终文本。
- 页面结构调整为左侧会话记录、中间 Agent 工作区、右侧 AI 对话区。
- tool 调用能体现审查状态、来源摘要、fallback 和可执行动作。
- 首批工具不只做页面跳转，还要能在中间工作区生成可读、可操作、可保存的学习产物。
- 后端和 Agent Service 补齐日志与审查记录，为后续多 Agent 展示打基础。

## 二、范围

### v1 做什么

1. AIChat 前端展示：
   - 流式文本输出。
   - tool 调用卡片。
   - 审查状态卡片。
   - 来源/依据摘要。
   - 左侧会话记录、中间 Agent 工作区、右侧 AI 对话区。
   - 中间工作区展示学习路径片段、推荐资源、薄弱点分析、练习题预览、HTML 类 PPT、代码实操任务、学习计划、审查报告等 Agent 产物。
   - 操作按钮：查看完整页面、开始练习、生成个性化题目、生成讲解材料、生成 HTML 类 PPT、保存为学习资源、刷新画像/路径/评估、打开资源详情。

2. 首批 Agent 工具：
   - 查询学生画像摘要。
   - 查询学习路径当前位置和下一步建议。
   - 查询薄弱知识点。
   - 查询推荐资源。
   - 查询学习效果摘要。

3. 后端 / Agent 日志：
   - 记录 conversation_id、message_id、tool_name、status、started_at、finished_at。
   - 记录输入摘要、输出摘要、来源命中摘要。
   - 记录 critic / review 结果。
   - 记录 fallback 原因。

4. Agent memory / content 能力边界：
   - 明确 user memory 是 Agent 长期上下文，不替代原始聊天记录。
   - 明确 content 产物用于后续 HTML 类 PPT、实时问题、项目任务等内容生成。
   - v1 可先设计接口边界，不一次性实现所有内容生成工具。

### v1 不做什么

- 不重做教师端；教师端只保留现状并后续优化展示。
- 不把管理员端作为主线；管理员端后续只做合并和 UI 优化。
- 不优先做真实视频生成；视频后续考虑爬虫、自建链接视频库或外部视频库。
- 不一次性实现完整 OpenClaw 类通用 Agent 平台；先围绕学习状态和学习动作做垂直 Agent 工作台。
- 不把提交材料作为当前开发主线，仅在审计和文档中轻量提及。

## 三、用户体验

AIChat 页面应从当前聊天页升级为“学习 Agent 工作台”。目标布局：

```text
┌──────────────┬────────────────────────────────┬──────────────────┐
│ 左侧          │ 中间                            │ 右侧              │
│ 对话记录      │ Agent 工作区 / 内容展示区         │ AI 对话区          │
│ sessions     │ tool outputs / html / cards     │ chat stream       │
│ history      │ resources / path / ppt / quiz   │ user input        │
└──────────────┴────────────────────────────────┴──────────────────┘
```

分区职责：

- 左侧：保留会话历史、创建新会话、切换课程相关对话。
- 中间：展示 Agent 工具结果和生成产物，不把所有内容都塞进聊天气泡。
- 右侧：保留 AI 对话、流式文本、用户输入、简短工具调用进度。

中间工作区应支持的内容类型：

- 学习路径片段：当前节点、下一步、推荐顺序和理由。
- 推荐资源列表：资源类型、知识点、推荐理由、来源/审查状态。
- 薄弱点分析：错误率、关联知识点、建议练习。
- 练习题预览：题目摘要、难度、知识点、开始练习入口。
- HTML 类 PPT / 讲解页：Agent 生成的可阅读教学内容。
- 代码实操任务：任务目标、步骤、参考材料、提交/练习入口。
- 学习计划：今日任务、预计用时、优先级。
- 审查报告：来源命中、可信度、fallback、critic 结论。

右侧对话区里的 tool 调用卡片用于表达“Agent 正在做什么”；中间工作区用于展示“Agent 做出来了什么”。

示例流程：

```text
学生：我今天应该先学什么？
Agent：调用 get_learning_state
Agent：调用 get_weak_points
Agent：调用 get_recommended_resources
Agent：审查建议是否基于真实课程数据
中间工作区：展示今日学习计划、薄弱点、推荐资源和开始练习按钮
右侧对话区：输出简短建议和后续可选动作
```

## 四、前端设计

### 页面层

`frontend/src/pages/AIChat.jsx` 保持容器职责，只组装：

- `SidebarHistory`
- `AgentWorkspace`
- `ChatArea`

### 组件层

新增或改造组件：

- `ToolCallCard`：展示工具调用状态、工具名、结果摘要。
- `ReviewCard`：展示审查状态、是否通过、原因、fallback。
- `ActionButtonGroup`：展示跳转或触发动作。
- `AgentWorkspace`：中间工作区容器，展示当前 Agent 产物。
- `WorkspaceArtifactCard`：统一承载路径、资源、题目、HTML 类 PPT、项目任务、审查报告等产物。
- `WorkspaceToolbar`：保存、刷新、打开详情、开始练习等动作入口。

### 状态层

`ChatContext` 需要支持 SSE 事件类型：

- `chunk`：文本增量。
- `tool_start`：工具开始。
- `tool_result`：工具完成。
- `review`：审查结果。
- `action`：可执行动作。
- `artifact`：中间工作区产物。
- `artifact_update`：产物增量更新。
- `done`：完成。
- `error`：错误。

若当前后端已经发出部分事件但前端没有正确处理，应先修复事件解析和渲染，不先新增复杂协议。

## 五、Backend 设计

Backend 仍作为前端与 Agent Service 的唯一 HTTP 边界，前端不直连 Agent Service。

### 职责

- 保存原始会话消息。
- 代理 Agent Service SSE。
- 将 Agent 事件转为前端稳定事件。
- 记录 tool 调用日志和审查日志。
- 保存或转发 Agent 工作区产物。
- 提供学生状态查询工具所需的 Backend 内部数据。

### 建议新增或完善的服务

- `tutoring_stream_adapter`：统一 Agent SSE 到前端 SSE 的事件转换。
- `agent_tool_log_service`：记录工具调用、审查、fallback、来源摘要。
- `student_learning_context_service`：聚合画像、路径、薄弱点、推荐资源、学习效果，供 Agent 工具调用。
- `agent_artifact_service`：管理 AIChat 中间工作区产物，短期可先落会话 meta，后续再演进到独立 content 表。

### 日志字段

建议最小字段：

- `id`
- `user_id`
- `course_id`
- `conversation_id`
- `message_id`
- `tool_name`
- `phase`
- `status`
- `input_summary`
- `output_summary`
- `source_summary`
- `review_status`
- `review_reason`
- `fallback_reason`
- `started_at`
- `finished_at`

## 六、Agent Service 设计

### 首批工具

- `get_profile_summary`
- `get_learning_path_summary`
- `get_weak_points`
- `get_recommended_resources`
- `get_learning_effects_summary`
- `draft_learning_plan`
- `draft_quiz_preview`
- `draft_html_lesson`

工具应只返回结构化摘要，不直接写 MySQL。需要持久化的动作仍通过 Backend 接口或 webhook。

首批工具分两类：

- 查询工具：读取画像、路径、薄弱点、资源、学习效果。
- 产物草稿工具：生成学习计划、题目预览、HTML 类讲解页等中间区内容。

### 记忆能力

当前缺口是 user memory 没有形成完整产品能力。v1 建议明确三层：

- 原始聊天记录：Backend 保存。
- 长期记忆事实：Agent Service 负责压缩、检索、返回摘要。
- 当前工具上下文：单次对话内的 tool 调用结果，不一定长期保存。

后续可新增或完善：

- memory 写入接口。
- memory 检索接口。
- memory 审查 / 去重 / 过期策略。

### 个性化学习路径推荐

当前学习路径更接近基于课程知识图谱的排序和状态展示。后续需要演进为真正的个性化学习路径推荐，而不是固定路径换状态。

后续需求：

- 路径推荐应综合画像、长期记忆、薄弱点、练习结果、资源使用、学习目标和可用时间。
- Agent 应能给出多个候选路径或下一步策略，例如“补弱优先”“项目实践优先”“考试冲刺优先”。
- 路径节点需要强化推荐理由、触发依据、预期收益和资源绑定关系。
- AIChat 工作区应能展示推荐路径片段，并允许用户追问“为什么先学这个”。
- 本设计只记录该方向，v1 不实现完整路径推荐算法。

### 审查能力

每次 Agent 输出学习建议前，应能产生审查事件：

- 是否基于真实课程数据。
- 是否使用不存在的知识点或资源。
- 是否触发 fallback。
- 是否缺少来源支撑。

审查结果先作为事件展示，不要求 v1 阻断所有输出。

## 七、接口与契约

v1 优先复用 `/api/v1/tutoring/chat` 的 SSE 通道。若现有 SSE 事件不足，可扩展事件类型，但必须同步更新：

- Backend SSE adapter。
- 前端 ChatContext。
- 文档中的事件说明。
- 相关测试。

工具查询尽量由 Agent Service 通过 Backend 已有接口或 Backend 聚合上下文提供，不允许前端直连 Agent Service，不允许 Agent Service 直接写 MySQL。

工作区产物可先作为 SSE `artifact` 事件返回给前端；需要保存时再通过 Backend 落到会话 meta、个性化资源或后续 content 表。

## 八、验证策略

前端：

- ChatContext 能正确处理 `chunk`、`tool_start`、`tool_result`、`review`、`action`、`done`。
- AIChat 能渲染左侧会话记录、中间 Agent 工作区、右侧对话区。
- AIChat 能渲染 tool 调用卡片、审查卡片、工作区产物和 action 按钮。
- 流式输出不退化成一次性整块输出。

Backend：

- SSE adapter 单测覆盖事件转换。
- 日志 service 单测覆盖 tool、review、fallback 记录。
- 学生学习上下文聚合 service 单测覆盖画像、路径、薄弱点、推荐资源、学习效果缺失场景。

Agent Service：

- 工具返回结构化摘要。
- 审查事件可输出。
- memory 检索缺失时不阻断课程 RAG 和正常答复。

## 九、实施顺序建议

1. 复核并修复 AIChat 当前非流式输出问题。
2. 调整 AIChat 页面结构为左记录 / 中工作区 / 右对话。
3. 定义 SSE 事件和前端渲染模型。
4. 增加 Backend 学生学习上下文聚合能力。
5. 增加 tool 调用卡片、审查卡片和工作区产物卡片。
6. 接入首批查询工具和轻量产物草稿工具。
7. 增加 tool / review / fallback 日志。
8. 再考虑动作型工具、持久化 content 和完整个性化路径推荐。

## 十、开放问题

- v1 是否需要真实持久化 tool 调用日志，还是先在会话 meta 中记录。
- 首批工具由 Backend 聚合后一次性传给 Agent，还是由 Agent 按需调用。
- content 产物是否先落在个性化资源体系，还是单独建立 Agent content 表。
- 中间工作区产物是按会话保存，还是允许跨会话固定到学生学习档案。
- 个性化学习路径推荐后续应优先做规则版，还是直接进入 Agent 推荐多候选路径。
