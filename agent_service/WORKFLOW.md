# WORKFLOW.md

## 文件用途

本文件只记录 `agent_service` 跨窗口恢复开发所需的最小状态。
接口契约以 `../docs/20-agent-api/Agent-Service.openapi.json` 和 `../docs/20-agent-api/API_Agent内部接口规范.md` 为准，本文件不是接口契约来源。

## 当前方向

- 当前不继续打磨旧 `tutoring/chat` 主链路；后续 tutoring 计划切换到 AgentScope ReActAgent / ReAct 编排。
- 非主线能力以简洁可用为准，避免为了本地 smoke 继续扩大 Qdrant、ID、并发 client 等实现细节。
- AgentScope 仍是后续 AI 编排主框架，但接入应落在 `agents/`、`memory/`、`tools/` 边界内，不泄漏到 OpenAPI/schema。
- `WORKFLOW.md` 不再记录长流水日志，只保留当前状态、最近验证和下一步。

## 接口进度

| 接口 | 状态 | 备注 |
|------|------|------|
| `GET /agent/v1/health` | 已完成基础版 | Qdrant 探针 + uptime；模型状态后续统一定义 |
| `POST /agent/v1/tutoring/chat` | 旧规则版/AI 骨架存在，暂停继续收口 | 后续改为 AgentScope ReActAgent 编排，不再围绕旧链路新增复杂逻辑 |
| `POST /agent/v1/profile/generate` | 规则版已完成 | 基于练习历史、资源使用、近期活跃度生成画像 |
| `POST /agent/v1/evaluation/generate` | 规则版已完成 | 基于学习进度、练习结果、资源使用生成评估 |
| `POST /agent/v1/assessment/evaluate` | 规则版已完成 | 基于标准答案和用户答案生成判分与诊断 |
| `POST /agent/v1/assessment/generate-questions` | 规则版骨架已完成 | 生成结构化占位题目 |
| `POST /agent/v1/learning-path/generate` | 规则版骨架已完成 | 生成结构化学习路径 |
| `POST /agent/v1/resources/generate` | 规则版闭环骨架已完成 | 202 + 后台任务 + webhook payload + retry/backoff |
| `POST /agent/v1/memory/compress` | 规则版闭环已完成 | 生成摘要和 facts；Qdrant 写入保持 best-effort |

## 当前已确认能力

- FastAPI API 骨架、Pydantic schemas、OpenAPI 对齐测试体系已建立。
- 多个非 tutoring 接口已有规则版实现和测试覆盖，可作为后续 AI 替换的稳定外壳。
- AgentScope 依赖已进入项目，后续可用于 ReActAgent、Reader、Embedding、QdrantStore。
- 本地课程资料目录已建立：`knowledge_base/data_structures/`。
- 放入的《数据结构（C语言版）》PDF 可被 AgentScope `PDFReader` 读取，当前解析约 `760` 个 chunks。
- embedding provider 已验证可返回 `1024` 维向量。

## 当前不继续推进的事项

- 不继续修旧 `tutoring/chat` 的单路径 JSON mode / fallback 细节。
- 不继续围绕 Qdrant local 文件锁、UUID point id、shared client 做扩大修补。
- 不继续执行耗时的全量 PDF 入库 smoke；如需验证，优先小样本或正式 ReAct 方案中统一处理。

## 最近测试/验证

- `./.venv/bin/pytest tests/test_openapi_alignment.py -q`：15 passed（上一轮已验证）。
- `./.venv/bin/pytest -q`：140 passed（上一轮旧收口后已验证；本轮清理后仍需按需复跑）。
- PDF 解析检查：`knowledge_base/data_structures/` 下 PDF 可解析，约 `760` chunks。
- 小样本 embedding：前 10 个 chunks 可生成 `10` 条 `1024` 维向量。

## 下一步建议

1. 先清理当前工作区，把旧 tutoring 收口、UUIDv5、未完成 Qdrant shared-client 相关改动撤掉或隔离。
2. 为 AgentScope ReActAgent 版 tutoring 写一个小设计，只定义请求数据如何转成 ReAct 输入、工具/知识如何挂载、输出如何映射回现有 SSE。
3. PDF 入库暂时作为 RAG 输入准备，不把本地 Qdrant 细节作为当前主要开发目标。
