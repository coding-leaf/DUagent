## agent_service暂行开发流程

1. 契约层
  先把所有接口补成“可启动、可出 OpenAPI、可过 schema 测试”。
  范围是 api/ + schemas/。
  你这次已经完成了其中一部分：tutoring/profile/evaluation。

  2. 智能辅导主流程
  按 POST /agent/v1/tutoring/chat 单独推进。
  这是主链路，涉及：

  - 请求解析
  - SQL 画像注入
  - Qdrant 检索
  - Prompt 组装
  - SSE 事件输出
  - done 元数据回传

  这条链路最复杂，建议单独作为一阶段。

  3. 评估与画像流程
  把这两个接口串成一个业务链：

  - POST /agent/v1/evaluation/generate
  - POST /agent/v1/profile/generate

  原因是画像生成天然依赖评估结果和学习统计，这两个接口耦合度高，适合一起做。
  这一阶段重点是结构化输入转结构化输出，不一定先依赖复杂流式能力。

  4. 测验/学习路径/资源生成流程
  按文档再拆成 3 组：

  - assessment：测验评估、题目生成
  - learning-path：学习路径生成
  - resources：异步任务 + webhook

  这里面 resources 又是单独一类，因为它有 202 + task_id + webhook 异步模式，和普通同步接口不同。

  5. 记忆与基础设施流程
  最后补公共底座，而不是一开始就过度设计：

  - memory/compress
  - Qdrant 读写封装
  - retriever
  - prompts
  - agents 层公共编排
  - tools

## 项目进度
> 以下为当前项目的接口等开发进度,仅供参考

| 接口 | 契约层 | API骨架 | Agent承接层 | 业务实现 | 测试状态 | 备注 |
|------|--------|---------|-------------|----------|----------|------|
| `GET /agent/v1/health` | 已完成 | 已完成 | 不适用 | 占位 | 已覆盖 | 后续可补真实健康检查 |
| `POST /agent/v1/tutoring/chat` | 已完成 | 已完成 | 未开始 | SSE占位 | 已覆盖 | 后续接 RAG / 事件流 |
| `POST /agent/v1/profile/generate` | 已完成 | 已完成 | 已完成 | 规则版已完成 | 已覆盖 | 基于练习历史、资源使用、近期活跃度生成基础画像 |
| `POST /agent/v1/evaluation/generate` | 已完成 | 已完成 | 已完成 | 规则版已完成 | 已覆盖 | 基于学习进度、练习结果、资源使用生成表格和摘要 |
| `POST /agent/v1/assessment/evaluate` | 已完成 | 已完成 | 已完成 | 规则版已完成 | 已覆盖 | 基于标准答案和用户答案生成判分与诊断 |
| `POST /agent/v1/assessment/generate-questions` | 已完成 | 已完成 | 已完成 | 规则版骨架已完成 | 已覆盖 | 根据题型、数量、章节、知识点生成结构化占位题目 |
| `POST /agent/v1/learning-path/generate` | 已完成 | 已完成 | 已完成 | 规则版骨架已完成 | 已覆盖 | 基于知识图谱、薄弱点和掌握度生成结构化学习路径 |
| `POST /agent/v1/resources/generate` | 已完成 | 已完成 | 已完成 | 规则版骨架已完成 | 已覆盖 | 202 异步任务承接层已接入，暂不发 webhook |
| `POST /agent/v1/memory/compress` | 已完成 | 已完成 | 已完成 | 规则版骨架已完成 | 已覆盖 | 生成对话摘要并提取基础薄弱点事实 |

## 当前上下文

- `POST /agent/v1/assessment/generate-questions` 已从 API 占位改为调用 `agents.assessment.generate_questions_data`。
- 当前规则版生成器只负责结构化题目骨架：按 `count` 生成题目，按 `question_types` 循环选择题型，保留 `chapter` / `knowledge_point` / `difficulty`。
- 当请求未传 `knowledge_point` 时，会优先从 `personalization_context.wrong_points` 提取第一个可用薄弱点，否则回退为“综合知识点”。
- `POST /agent/v1/learning-path/generate` 已从 API 占位改为调用 `agents.learning_path.generate_learning_path_data`。
- 当前学习路径规则版生成器会按 `knowledge_graph.nodes` 生成路径节点，按 `knowledge_graph.edges` 返回依赖边；命中画像薄弱点的节点标记为 `recommended`，掌握度高的节点标记为 `completed`。
- `POST /agent/v1/memory/compress` 已从 API 占位改为调用 `agents.memory.compress_memory_data`。
- 当前记忆压缩规则版会合并旧摘要与本轮消息，并从用户消息中提取基础 `blind_spot` 事实；暂不写 Qdrant。
- `POST /agent/v1/resources/generate` 已从 API 固定响应改为调用 `agents.resources.accept_resource_generation`。
- 当前资源生成规则版只负责异步任务承接：原样返回 Backend 传入的 `task_id`，按资源类型数量估算 `estimated_duration`；未传 `resource_types` 时默认使用 `document / mindmap / reading / code`，不默认生成预留的 `video`。
- 该阶段不接 LLM、不写 SQL、不检索 Qdrant；后续可替换为 RAG/LLM 和长期记忆写入实现。
- 资源生成阶段同样不写 SQL、不调用 LLM/Qdrant、不实际 POST webhook；后续可在该承接层后接入后台 worker、AgentScope/RAG 和 webhook 重试。

## 最近测试结果

- `./.venv/bin/pytest tests/test_assessment_agent.py`：6 passed
- `./.venv/bin/pytest tests/test_learning_path_agent.py`：3 passed
- `./.venv/bin/pytest tests/test_memory_agent.py`：3 passed
- `./.venv/bin/pytest tests/test_resources_agent.py`：3 passed
- `./.venv/bin/pytest tests/test_schema_contracts.py`：17 passed
- `./.venv/bin/pytest tests/test_openapi_alignment.py`：14 passed，存在既有 Pydantic v2 deprecation warning
- `./.venv/bin/pytest`：54 passed，存在既有 Pydantic v2 deprecation warning

## 下一步建议

- 继续按小步推进 `POST /agent/v1/resources/generate` 的后台 worker/webhook payload 骨架，或回到主链路 `POST /agent/v1/tutoring/chat` 做 SSE 规则版事件生成。
