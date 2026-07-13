# Agent API 内部接口规范

> Backend（8001）↔ Agent Service v2（8002）
>
> 当前运行时只支持 `/agent/v2/*`。精确字段、响应模型和校验规则以同目录 `Agent-Service.openapi.json` 为准。

## 边界

- Frontend 不直连 Agent Service。
- Backend 只通过 HTTP 调用 Agent Service，不导入其 Python 模块。
- Agent Service 不访问 MySQL；业务落库通过 Backend 内部 API 或 webhook。
- Qdrant 检索和 AgentScope Workspace 由 Agent Service 管理。
- Backend 创建的业务 `task_id` 必须由 Agent 原样传递。
- AgentScope 原始事件不得泄漏到公开协议。

## 通用响应

同步 JSON 接口使用：

```json
{"code": 200, "message": "success", "data": {}}
```

异步接收可返回 HTTP 202。Workbench 和个性化资源事件使用 SSE；其事件模型由 OpenAPI schema 和当前协议适配器共同约束。

## 当前接口

### Workbench

- `POST /agent/v2/workbench/chat`：AgentScope 工作台对话与工具事件流。
- `GET /agent/v2/workbench/artifacts`：在可信 user/course/conversation 边界内读取产物。

Workbench 保持 AgentScope 2.x `Agent.reply_stream + Toolkit + ToolGroup` 的自主工具调用。EDU 协议适配器将工具结果统一为：

```json
{
  "outcome": "success | neutral | warning | failure",
  "status": "published",
  "reason": null,
  "summary": {},
  "retryable": false,
  "data": {},
  "artifact": {},
  "sources": []
}
```

- `available/published/ok/success` → `success`，`empty/not_found` → `neutral`，`degraded` → `warning`，`rejected/unavailable/delivery_incomplete/error` → `failure`。
- AgentScope `ToolResultState.ERROR` 直接映射为 `tool_failed`。`tool_started` 携带 `tool_title/tool_category/read_only`。
- RAG 引用只使用 `payload.sources[]`，每项为 `source_file/snippet/score`；不再交叉使用 `citations`。
- 联网检索按需使用固定版 `open-websearch@2.1.11` MCP，只注册 `search`，不开放网页正文抓取工具。内部工具名 `mcp__web_search__search` 在 EDU 事件中稳定映射为 `web_search`，标题为“联网检索最新资料”。
- 联网成功结果复用 `source_refs`，最多 5 项，每项为 `title/url/snippet/source/engine`。失败或超时只产生友好的 `tool_failed`，不得产生来源或把模型记忆冒充实时结果。
- 长期记忆只保存用户明确表达的长期偏好、目标和稳定事实；禁止保存推断掌握度、诊断、答案、敏感内容或工具原文。写入前去重，工具卡可见，审计日志不记忆正文。
- `artifact_created` 支持 `PersonalizedResourceCard`：已有推荐使用 `props.resources[]`，异步生成使用 `props.task_id/course_id/resource_type/goal`。任务卡只表示已启动，不表示已审核或发布。
- AI Chat 输入先使用本地 UTF-8 高风险短语词表召回候选；只有候选输入复用非流式聊天模型做结构化语义复核，普通输入不增加模型调用。语义审核超时、不可用或输出无效时回退到本地硬词阻断。
- AI 输出使用滚动窗口进行跨分片检测，命中后立即关闭 AgentScope 回复流，不再等待语义模型。阻断时依次发送 `content_safety_reviewed(action=block)`、统一拒答 `text_delta` 和 `workflow_completed`；`match_count` 可见但不泄露命中原词。该能力不是事实防幻觉审查。

### AI Chat 画像与精准资源内部工具

- `read_learner_profile` / `update_learner_profile_from_dialogue` 通过 Backend internal API 读取六维画像并更新用户明确表达的稳定事实；可信身份不暴露给模型。
- `recommend_personalized_resources` 最多推荐 3 个课程权限内已有资源；`generate_personalized_resource` 仅在无有效推荐时启动一个非视频资源任务。
- 每个 Workbench run 最多启动一个资源任务；任务 ID 由 user/course/conversation/run/goal/resource_type 稳定派生。

### AI Chat 联网检索运行配置

- 代码默认 `WEB_SEARCH_ENABLED=false`；根目录 `start_all.sh` 默认注入 `true`。
- `WEB_SEARCH_PACKAGE` 默认固定为 `open-websearch@2.1.11`。
- `WEB_SEARCH_DEFAULT_ENGINE` 默认 `baidu`；`WEB_SEARCH_ALLOWED_ENGINES` 默认 `baidu,sogou,bing,csdn,juejin`。
- `WEB_SEARCH_TIMEOUT` 默认 12 秒；`WEB_SEARCH_USE_PROXY/WEB_SEARCH_PROXY_URL` 控制显式代理，默认不使用。
- STDIO MCP 启动和工具发现总超时 30 秒。启动失败时不注册搜索工具，Workbench 原有 SSE 主链路继续可用。
- MCP 子进程仅接收进程启动和搜索所需环境变量，不接收 LLM 密钥、Backend Token、用户或会话标识。

### AI Chat 互动练习内部发布

Agent Service 通过 Backend 内部 HTTP 链路发布 QuizCard 和 CodeSandboxCard：

1. `POST /internal/ai-chat/personal-practices/prepare`：验证可信上下文与 draft，以稳定幂等键保存 `delivery_pending` generation，不创建用户可见题目。
2. `POST /internal/ai-chat/personal-practices/finalize`：锁定 generation，在同一 MySQL 事务中创建业务记录、关联和 artifact descriptor，然后标记 `published`。
3. `POST /internal/ai-chat/personal-practices/resume`：按 `generation_id` 幂等恢复 `delivery_failed` 或响应丢失的发布。

`idempotency_key` 由规范化 draft、user、conversation、run 和工具类型稳定派生。互动卡片由 Backend 作为唯一权威；Agent Workspace 只保留 Markdown/Mermaid 等文件型产物。旧 `/internal/ai-chat/code-problem-validations` 和 `/internal/ai-chat/choice-quizzes` 已删除。

### Knowledge

- `POST /agent/v2/knowledge/ingestions`：课程资料切片并写入 Qdrant。
- `POST /agent/v2/knowledge/knowledge-graphs/generations`：根据课程切片或文本生成知识图谱。
- `POST /agent/v2/knowledge/quiz/generations`：生成课程或个性化题目。
- `POST /agent/v2/knowledge/resources/generations`：异步生成公共学习资源。

### Evaluation

- `POST /agent/v2/evaluation/generations`：生成结构化学情评估。
- `POST /agent/v2/evaluation/quiz/diagnose`：根据作答事实生成诊断。

### Personalized Resources

- `POST /agent/v2/personalized-resources/generations`：启动个性化资源 Agent Team。
- `GET /agent/v2/personalized-resources/generations/{session_id}/events`：订阅生成事件。

### Team Runtime

- `/agent/v2/team-runtime`：AgentScope 团队运行时挂载点，不作为 Frontend 直连接口。

## 已退役能力

- 全部 `/agent/v1/*` 已删除，不提供兼容代理。
- 画像生成与刷新由 Backend 规则服务负责。
- 学习路径由 Backend 根据 active KG 和实时学习进度计算，不再调用 Agent 生成。
- 旧记忆压缩接口由 v2 Workbench 的记忆生命周期替代。

## 本地验证

```bash
cd agent_service_v2
./.venv/bin/uvicorn agent_service_v2.main:app --host 127.0.0.1 --port 8002
curl -fsS http://127.0.0.1:8002/openapi.json >/dev/null
```
