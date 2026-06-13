# AI Chat Hybrid Retrieval Correction Design

**Date:** 2026-06-14
**Status:** Approved

## 1. 核心目标与范围

本轮设计的核心目标是修复 AI Chat Hybrid Retrieval 存在的检索逻辑缺陷与过度承诺问题。
**最终口径**：不改前端 UI、不改 Client API；本轮只修正 Hybrid retrieval 后端/探针可验证性，撤回过度完成状态。

## 2. 检索上下文改造 (Context & Debug)

- **保持核心链路纯净**：`TutoringRetrievalContext.course_knowledge_chunks` 保持 `list[str]` 不变，以免污染现有 `prompts/tutoring.py` 等链路。
- **新增调试诊断字段**：在 `TutoringRetrievalContext` 中新增 `retrieval_debug: dict | None = None`，专门用来存储 Qdrant Chunk 和图谱打分详情（供探针使用）。
  - 注释明确：该字段仅供 probe/debug 使用，不保证前端展示，绝不暴露至 Client API/SSE 响应流中，LLM Prompt 构建函数也不会去引用它。
- **Metadata 白名单机制**：
  为避免把内部路径、过长 payload 暴露进 probe，组装 `retrieval_debug` 中的 `retrieved_chunk_details` 时对 metadata 做白名单过滤。只保留安全字段，例如：`chapter`、`knowledge_point`、`source`、`material_id`、`chunk_index`。

## 3. 三级检索降级策略 (`_match_kg_nodes`)

重构 `agent_service/memory/tutoring_retrieval.py`，取消原本在无 Reranker 时盲目返回前 3 个节点的假检索逻辑，改为带有溯源 `match_method` 的高精度组合匹配，排序时统一合并去重：

1. **Substring 高精前置去重**：始终优先执行。将 Query 与 Node Name 进行精确/包含匹配。有命中则直接保留（`match_method="substring"`, `score=1.0`）。
2. **Reranker 匹配**：
   - 如果 `reranker_provider` 存在且调用成功，作为主力检索策略。
   - 过滤条件：`score >= 0.35` (KG_RERANK_MIN_SCORE)，不达标则丢弃。
   - `match_method="reranker"`。
3. **Embedding 相似度降级**：
   - 触发条件：仅当 `reranker_provider` 不存在或调用失败时，才进入 Embedding 降级逻辑（绝不在 Reranker 低分时使用 Embedding 把垃圾数据捞回来）。
   - 实现：复用已有的 `query_vector`。对 `node.name + " " + node.chapter` 计算 cosine similarity。
   - 过滤条件：`score >= 0.55` (KG_EMBEDDING_MIN_SCORE)，不达标则丢弃。
   - `match_method="embedding"`。

*返回值结构约定：*
```json
{
  "id": "...",
  "name": "...",
  "chapter": "...",
  "score": 0.82,
  "match_method": "reranker | embedding | substring"
}
```

## 4. LLM Prompt 注入与兜底

消除“匹配的图谱节点毫无作用”的断层问题，将其编织进正式的生成链路：

- **Prompt 内容注入**：
  在 `build_tutoring_messages`、`_build_react_user_message`、`build_strategy_selection_messages` 三处的上下文中补充：
  `图谱节点：{node.chapter} - {node.name}`
  *(ResponseCriticAgent 如果要加，必须配置 trusted terms 以防误判，但非强制必须)*
- **System Prompt 约束**：
  改为相对软性的约束：“如果提供了图谱节点，knowledge_points 应优先从这些节点名称中选择；回答应围绕最相关节点展开，不要机械覆盖所有节点。”
- **Knowledge Points 兜底**：
  重构 `_build_knowledge_points()`，生成 `knowledge_points` 数组的优先级：
  1. 模型解析出的 `knowledge_point_names`；
  2. `context.matched_kg_nodes`（在此取值时，必须使用 `node.name` 并将 `KnowledgePoint.chapter` 赋为图谱带出的 `node.chapter`，而非粗暴的 `course_id`）；
  3. `Profile` 中的 `weak_points`/`mastered_points`；
  4. 截取用户当前问题字面。

## 5. CLI 探针增强 (`probe_aichat_hybrid_retrieval.py`)

- **参数拓展**：
  - 支持 `--catalog-id`。若同时传入 course 和 catalog，优先使用 `catalog_id` 寻找 active KG，并给出 warning 如果发现它们不匹配；`course_id` 继续用于权限与 Qdrant 检索。只传 course 时走教学班绑定的默认路径。
  - 支持 `--json` 输出结构化数据。
- **输出格式**：
  在 Console 或 JSON 输出中打印出检索的详细溯源分数，如 `match_method`、`score` 以及 Qdrant 过滤后的 `metadata`。JSON 输出模式下需要携带顶层的 `summary`（记录 hit count）。
- **取消 Answer Preview**：删除原有 Spec 承诺。本次探针不测试大模型生成的质量。

## 6. 测试与文档修正

- **负例覆盖**：
  在 `test_aichat_hybrid_retrieval.py` 增加必过的负例断言：无论是存在 reranker 但低分，还是无 reranker 时 substring 不命中，都必须返回空数组（断绝 Top 3 问题复发）。
- **正例覆盖**：
  明确编写 substring 正例（query="请解释 malloc/free", 断言 method=="substring" 且 score=1.0）。Mock Embedding 并断言其 Fallback 能起效。
- **验证命令书写**：
  所有地方（代码库文档、PR记录）都使用项目根目录下的特定虚拟环境命令：
  `cd EDUagent && ./.venv/bin/python -m pytest agent_service/tests/test_aichat_hybrid_retrieval.py -q -p no:cacheprovider`
- **状态降级**：
  必须将 `WORKFLOW.md` 和 `docs/feature-ledger.md` 中所有“✅ 后端闭环”全部撤回并正式提交至 Git。状态修改为：“**探针与 mock 回归已完成，真实 Hybrid 闭环待验证**”。
