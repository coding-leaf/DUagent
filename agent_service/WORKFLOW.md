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
| `POST /agent/v1/tutoring/chat` | ReActAgent 最小垂直链路已完成 | 降级链：ReActAgent → chat JSON → rule-based；第一版无 toolkit |
| `POST /agent/v1/profile/generate` | 规则版已完成 | 基于练习历史、资源使用、近期活跃度生成画像 |
| `POST /agent/v1/evaluation/generate` | 规则版已完成 | 基于学习进度、练习结果、资源使用生成评估 |
| `POST /agent/v1/assessment/evaluate` | 规则版已完成 | 基于标准答案和用户答案生成判分与诊断 |
| `POST /agent/v1/assessment/generate-questions` | 规则版骨架已完成 | 生成结构化占位题目 |
| `POST /agent/v1/learning-path/generate` | 规则版骨架已完成 | 生成结构化学习路径 |
| `POST /agent/v1/resources/generate` | 规则版闭环骨架已完成 | 202 + 后台任务 + webhook payload + retry/backoff |
| `POST /agent/v1/memory/compress` | 规则版闭环已完成 | 生成摘要和 facts；Qdrant 写入保持 best-effort |

## 当前已确认能力

- FastAPI API 骨架、Pydantic schemas、OpenAPI 对齐测试体系已建立。
- 多个非 tutoring 接口已有规则版实现和测试覆盖。
- AgentScope 依赖已进入项目，ReActAgent、Reader、Embedding、QdrantStore 可用。
- 课程知识摄入 CLI 已完成幂等闭环：支持 PDF/MD/TXT，重复执行跳过已摄入源文件。
- `knowledge_base/` 已加入 `.gitignore`，含 `README.md` 说明用法。
- ReActAgent 最小垂直链路已接入 `tutoring/chat`：`agents/tutoring_react_flow.py` 做胶水层，`_build_model_response()` 内部顺序 ReAct → chat JSON → None。
- `retrieve_course_knowledge` toolkit 已挂载：闭包隐藏 course_id/embedding_provider/store/limit，模型只暴露 query。
- 《数据结构（C语言版）》PDF 可被 AgentScope PDFReader 解析，约 760 chunks。
- embedding provider 已验证可返回 1024 维向量。

## 当前不继续推进的事项

- 不继续修旧 `tutoring/chat` 的单路径 JSON mode / fallback 细节。
- 不继续围绕 Qdrant local 文件锁、UUID point id、shared client 做扩大修补。
- 不继续执行耗时的全量 PDF 入库 smoke。

## 最近测试/验证

- `./.venv/bin/pytest -q`：**153 passed**（2026-05-25 API smoke 超时处理补测后验证）
- ReAct LLM smoke **通过**（2026-05-25）：`deepseek-v4-flash`，ReActAgent → JSON parse 主路径验证成功，elapsed 6.50s
- `retrieve_course_knowledge` toolkit 已实现并挂载，新增 5 个测试
- API smoke 脚本已就绪：`./.venv/bin/python -m agent_service.tools.smoke_tutoring_api`
- QdrantVectorStore 改为请求级共享实例，消除 retrieval / ReAct toolkit 双重创建导致的文件锁冲突
- OpenAPI 对齐未变化
- **API smoke 端到端验证通过**（2026-05-25 23:53）：ReAct LLM 主路径完成，SSE 5 事件完整输出（chunk×2 → knowledge_points → suggestion → done），elapsed 6.34s。Qdrant local 锁导致 `_build_shared_vector_store()` 失败属已知限制，retrieval 降级到 fallback context，不阻断请求。toolkit 完整路径待后续 Qdrant server 模式单独验证。

## 下一步

- 后续可选：挂载 `retrieve_user_memory` 工具
- Qdrant toolkit 完整路径验证（需先完成 Qdrant server 模式或 shared client 改造，单独开任务）
- 继续推进其他接口或能力
