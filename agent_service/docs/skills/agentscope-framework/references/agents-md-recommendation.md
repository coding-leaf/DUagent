# AGENTS.md Recommendation

Suggested addition to `AGENTS.md`. Do not apply automatically unless the user confirms modifying project instructions.

```markdown
## AgentScope Development Guide

- 涉及 AgentScope API、RAG、Memory、Tool、MCP、ReActAgent、Embedding、部署或评测时，先阅读 `docs/skills/agentscope-framework/SKILL.md`，再按任务读取对应 `references/` 文件。
- AgentScope 官方文档索引以 `https://docs.agentscope.io/llms.txt` 为准；本仓库 `docs/skills/agentscope-framework/` 只保存项目适配指南，不是官方文档镜像。
- 不允许凭记忆编造 AgentScope 类名、方法、参数或依赖 extra；无法确认时必须查官方文档或用本地 `./.venv/bin/python` introspection 验证。
- 课程知识库与用户长期记忆必须分开：课程 PDF/MD/TXT 入 `course_knowledge`，学生画像、薄弱点、偏好入 `user_memory`。
- 引入 AgentScope 时优先做适配层和 fallback，不要一次性替换现有 API 契约、SSE 契约或规则版 agent。
- 本地资料入库优先使用 CLI/离线任务，不要把大文件解析、embedding、Qdrant upsert 放进同步请求路径。
```

Recommended insertion point: after the existing `## AgentScope Boundary` section.
