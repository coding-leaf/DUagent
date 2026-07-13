# 对话画像、精准资源推送与敏感内容过滤设计

## 目标

AI Chat 自动保存用户明确表达的稳定课程画像事实，优先推荐匹配画像和学情的已有资源；没有有效资源时，幂等启动一个 Resource Team 生成任务。同时用本地版本化词表过滤 AI 输出和发布前学生可见内容。

不包含视频、图片识题、音频或其他多模态，也不把敏感词过滤描述为事实防幻觉审查。

## 架构选择

- 画像与推荐采用 Backend Service：需要课程权限、MySQL 画像、学习行为和任务事实，Router 仅做内部鉴权与参数转发。
- Agent 使用 AgentScope `FunctionTool + ToolGroup`：模型在约束内自主决定读取、更新、推荐或生成，不引入手写推理循环。
- 横切输出安全采用流式过滤器：在 AgentScope 事件进入 EDU SSE 适配、日志和 Workspace 前处理；发布门禁由 Backend 读取同一词表独立执行，保持微服务边界。
- 不新增表或依赖：复用 `UserProfile` JSON、`AsyncTask`、`UserPersonalizedResource`、Resource Team 和现有 SWR 接口。

## 数据与协议

画像工具的 user/course/conversation/run 由闭包注入。可写字段仅包括目标、四类资源偏好、L1-L3 引导强度、自定义教学要求和稳定习惯。重复值返回 `neutral/unchanged`，审计只保存字段名、run_id 和结果。

推荐最多返回 3 条资源，理由来自目标/知识点、画像偏好、薄弱或推荐节点及近期行为的确定性排序。生成支持 `personal_lesson|diagram|practice|reading`，每 run 最多一个任务。

`PersonalizedResourceCard` 支持两种 props：

```json
{"course_id":"course-1","resources":[{"id":"r1","title":"...","type":"diagram","summary":"...","reason":"..."}]}
```

```json
{"course_id":"course-1","task_id":"task-1","resource_type":"reading","goal":"..."}
```

生成卡的出现只代表任务启动。前端通过既有任务/个性化资源接口轮询，发布完成后显示可打开资源。

## 敏感内容过滤

`config/sensitive_words.txt` 是唯一词表来源。Agent 流式过滤器保留最长词长度减一的滚动窗口，支持跨分片替换为 `[内容已屏蔽]`。`content_safety_reviewed` 使用 `reviewer=local_wordlist`、`action=flag` 和 `match_count`，不返回命中原词。

Backend 在普通资源、选择题和编程题学生可见内容发布前执行同一词表检查；命中即拒绝发布。该功能只处理敏感短语，不评价事实正确性。
