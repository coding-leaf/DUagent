# WORKFLOW.md

## 文件用途

本文件用于记录 `agent_service` 当前开发进度、阶段目标、测试结果和跨窗口恢复上下文。
本文件不是接口契约来源，接口契约以 `../docs/20-agent-api` 下的 OpenAPI 与接口规范为准。

## 本文件修改注意事项

- 只记录跨窗口恢复开发所需的最小状态。
- 保留接口进度、当前焦点、近期完成摘要、最近测试结果和下一步建议。
- 不记录完整对话过程、详细推理过程、冗长历史背景。
- 每次完成小阶段后更新本文件，但应优先压缩为状态摘要。
- 不以更新本文件为理由扩大业务代码修改范围。

## 项目进度

> 以下为当前项目的接口开发进度，仅供恢复上下文使用。

| 接口 | 契约层 | API骨架 | Agent承接层 | 业务实现 | 测试状态 | 备注 |
|------|--------|---------|-------------|----------|----------|------|
| `GET /agent/v1/health` | 已完成 | 已完成 | 不适用 | 占位 | 已覆盖 | 后续可补真实健康检查 |
| `POST /agent/v1/tutoring/chat` | 已完成 | 已完成 | 未开始 | SSE占位 | 已覆盖 | 后续接 RAG / 事件流 |
| `POST /agent/v1/profile/generate` | 已完成 | 已完成 | 已完成 | 规则版已完成 | 已覆盖 | 基于练习历史、资源使用、近期活跃度生成基础画像 |
| `POST /agent/v1/evaluation/generate` | 已完成 | 已完成 | 已完成 | 规则版已完成 | 已覆盖 | 基于学习进度、练习结果、资源使用生成表格和摘要 |
| `POST /agent/v1/assessment/evaluate` | 已完成 | 已完成 | 已完成 | 规则版已完成 | 已覆盖 | 基于标准答案和用户答案生成判分与诊断 |
| `POST /agent/v1/assessment/generate-questions` | 已完成 | 已完成 | 已完成 | 规则版骨架已完成 | 已覆盖 | 根据题型、数量、章节、知识点生成结构化占位题目 |
| `POST /agent/v1/learning-path/generate` | 已完成 | 已完成 | 已完成 | 规则版骨架已完成 | 已覆盖 | 基于知识图谱、薄弱点和掌握度生成结构化学习路径 |
| `POST /agent/v1/resources/generate` | 已完成 | 已完成 | 已完成 | 规则版闭环骨架已完成 | 已覆盖 | 202 + 后台任务 + webhook payload 骨架，暂不接 LLM/Qdrant |
| `POST /agent/v1/memory/compress` | 已完成 | 已完成 | 已完成 | 规则版骨架已完成 | 已覆盖 | 生成对话摘要并提取基础薄弱点事实 |

## 当前焦点

- 下一步推荐优先推进 `POST /agent/v1/tutoring/chat`：把当前 SSE 占位改为规则版事件流，先形成主链路可演示闭环。
- 备选焦点是继续增强 `POST /agent/v1/resources/generate`：补 webhook 重试、超时和资源内容生成替换点。

## 近期完成摘要

- `POST /agent/v1/assessment/generate-questions`：已接入 `agents.assessment.generate_questions_data`，可生成规则版结构化占位题目。
- `POST /agent/v1/learning-path/generate`：已接入 `agents.learning_path.generate_learning_path_data`，可基于知识图谱、薄弱点和掌握度生成规则版学习路径。
- `POST /agent/v1/memory/compress`：已接入 `agents.memory.compress_memory_data`，可生成对话摘要并提取基础 `blind_spot` 事实，暂不写 Qdrant。
- `POST /agent/v1/resources/generate`：已接入 `agents.resources`，支持 202 接收、后台任务和 completed/failed webhook payload。

## 历史完成详情

- `POST /agent/v1/profile/generate`：规则版已完成，基于练习历史、资源使用和近期活跃度生成基础画像。
- `POST /agent/v1/evaluation/generate`：规则版已完成，基于学习进度、练习结果和资源使用生成评估摘要。
- `POST /agent/v1/assessment/evaluate`：规则版已完成，基于标准答案和用户答案生成判分与诊断。
- `GET /agent/v1/health`：健康检查接口已完成基础占位。
- 当前所有规则版实现均不接 LLM、不写 SQL、不检索 Qdrant；后续可按接口逐步替换为 AgentScope / RAG / LLM 实现。

## 最近测试结果

- `./.venv/bin/pytest tests/test_assessment_agent.py`：6 passed
- `./.venv/bin/pytest tests/test_learning_path_agent.py`：3 passed
- `./.venv/bin/pytest tests/test_memory_agent.py`：3 passed
- `./.venv/bin/pytest tests/test_resources_agent.py`：6 passed
- `./.venv/bin/pytest tests/test_schema_contracts.py`：17 passed
- `./.venv/bin/pytest tests/test_openapi_alignment.py`：14 passed，存在既有 Pydantic v2 deprecation warning
- `./.venv/bin/pytest`：57 passed，存在既有 Pydantic v2 deprecation warning

## 下一步建议

- 首选：推进 `POST /agent/v1/tutoring/chat` 的 SSE 规则版事件流。
- 次选：补 `POST /agent/v1/resources/generate` 的 webhook retry / timeout / backoff 策略。
