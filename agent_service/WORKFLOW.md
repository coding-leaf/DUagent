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
| `POST /agent/v1/profile/generate` | LLM + 规则版 fallback 已完成 | 降级链：LLM enrichment → 规则版；LLM 只增强 guidance_level_suggestion.reason |
| `POST /agent/v1/evaluation/generate` | LLM + 规则版 fallback 已完成 | 降级链：LLM enrichment → 规则版；LLM 只增强 summary_text；表格全保持规则版 |
| `POST /agent/v1/assessment/evaluate` | LLM + 规则版 fallback 已完成 | 判分由规则确定；LLM 增强 explanation、diagnosis.summary、weak_points.error_pattern、suggestions；降级链：LLM enrichment → 规则版 |
| `POST /agent/v1/assessment/generate-questions` | LLM + RAG + fallback 已完成 | 降级链：LLM（含 course_knowledge RAG context）→ 骨架占位题；prompt 强化质量约束 |
| `POST /agent/v1/learning-path/generate` | LLM + 规则版 fallback 已完成 | 降级链：LLM（节点 ID 白名单 + name 回填）→ 规则版；LLM 不发明节点 |
| `POST /agent/v1/resources/generate` | LLM + RAG + fallback 已完成 | 202 + 后台任务；LLM 并行生成四类资源 + course_knowledge RAG 检索注入 prompt；skeleton fallback → webhook completed |
| `POST /agent/v1/memory/compress` | LLM + 规则版 fallback 已完成 | 降级链：LLM → 规则版；LLM 提取 3 种 fact 类型 + 生成摘要；Qdrant 写入 best-effort |

## 当前已确认能力

- FastAPI API 骨架、Pydantic schemas、OpenAPI 对齐测试体系已建立。
- 多个非 tutoring 接口已有规则版实现和测试覆盖。
- AgentScope 依赖已进入项目，ReActAgent、Reader、Embedding、QdrantStore 可用。
- 课程知识摄入 CLI 已完成幂等闭环：支持 PDF/MD/TXT，重复执行跳过已摄入源文件。
- `knowledge_base/` 已加入 `.gitignore`，含 `README.md` 说明用法。
- ReActAgent 最小垂直链路已接入 `tutoring/chat`：`agents/tutoring_react_flow.py` 做胶水层，`_build_model_response()` 内部顺序 ReAct → chat JSON → None。
- `retrieve_course_knowledge` + `retrieve_user_memory` toolkit 已挂载：两个工具均闭包隐藏内部参数，模型只暴露 query。user_memory_facts 首轮注入保持不变。
- 《数据结构（C语言版）》PDF 可被 AgentScope PDFReader 解析，约 760 chunks。
- embedding provider 已验证可返回 1024 维向量。

## 当前不继续推进的事项

- 不继续修旧 `tutoring/chat` 的单路径 JSON mode / fallback 细节。
- 不继续围绕 Qdrant local 文件锁、UUID point id、shared client 做扩大修补。
- 不继续执行耗时的全量 PDF 入库 smoke。

## 最近测试/验证

- `./.venv/bin/pytest -q`：**213 passed**（2026-05-26 resources/generate RAG 接入后验证）
- resources/generate RAG：22 个测试（含 5 个新 RAG 用例，覆盖 context 拼接/embedding=None/检索异常/空结果/RAG→LLM集成）
- resources/generate：LLM 并行生成四类资源 + skeleton fallback，webhook shape 不变，新增 8 个测试
- learning-path/generate：LLM + rule-based fallback
- assessment/generate-questions：LLM + skeleton fallback
- tutoring/chat：ReActAgent + 双工具 toolkit + API smoke
- OpenAPI 对齐：15 passed

## 下一步

- 短期：assessment/generate-questions RAG + 质量约束 ← **已完成**
- 中期：memory/compress 规则增强（mastered_point / cognitive_preference 规则提取）
- 远期：Qdrant server 模式 / shared client 改造
- 长期：Qdrant server 模式 / shared client 改造
