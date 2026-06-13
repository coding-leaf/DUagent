# AI Chat Hybrid Retrieval Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修正 AI Chat Hybrid Retrieval 检索降级逻辑，修复 CLI 探针，并安全注入检索上下文，不涉及 UI 和 Client API 变动。

**Architecture:** 对 `TutoringRetrievalContext` 进行无害扩充（新增 `retrieval_debug` 用于诊断）；重构图谱节点的三级匹配逻辑（Substring去重 -> Reranker -> Embedding降级）；最后调整 `tutoring.py` 等的提示词构建，将匹配到的图谱节点提供给大模型作为回答和生成知识点依据的兜底。

**Tech Stack:** Python 3, FastAPI, Pydantic, pytest.

---

### Task 1: Context Definition & Probe Enhancement

**Files:**
- Modify: `agent_service/memory/tutoring_retrieval.py`
- Modify: `backend/tools/probe_aichat_hybrid_retrieval.py`
- Modify: `agent_service/api/v1/tutoring.py`

- [ ] **Step 1: Modify `TutoringRetrievalContext`**

在 `agent_service/memory/tutoring_retrieval.py` 的 `TutoringRetrievalContext` 类中新增 `retrieval_debug`：

```python
    retrieval_debug: dict | None = Field(None, description="仅供 probe/debug 使用，不保证前端展示，绝不暴露至 Client API/SSE 响应流中")
```

- [ ] **Step 2: Update Probe Response in Agent Service**

在 `agent_service/api/v1/tutoring.py` (如果有针对 Probe 的 endpoint)，确保其文档字符串中标注清楚，且保证正确返回包含了 `retrieval_debug` 的 context。如果目前 `/retrieval_probe` 只是直接 `return context` 则无需额外代码改动，只需添加注释：

```python
@router.post("/retrieval_probe")
async def retrieval_probe(
    # ... args
):
    """
    内部探针端点。仅供 CLI 或 Debug 工具测试 Agent Hybrid Retrieval 质量使用。
    不进 Client API 契约。
    """
    # ...
```

- [ ] **Step 3: Modify CLI Probe tool logic**

在 `backend/tools/probe_aichat_hybrid_retrieval.py` 增加参数，及输出 JSON 功能和过滤，注意警告逻辑。

```python
    parser.add_argument("--catalog-id", help="Optional Catalog ID to override active KG logic")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
```
在组装 payload 时，注意传递给 `_assemble_tutoring_payload` 前记录下如果同时传了 `--course-id` 和 `--catalog-id`，需要有 warning。但是注意 Backend 的 `_assemble_tutoring_payload` 签名可能不接受 `catalog_id`。为保持简单，这里我们在 `probe_aichat_hybrid_retrieval.py` 仅打印 Warning，并在后续 JSON 输出增加摘要。

修改解析探针响应部分：
```python
    retrieval_debug = data.get("retrieval_debug", {})
    summary = {
        "kg_match_count": len(matched_kg_nodes),
        "chunk_count": len(course_knowledge_chunks)
    }
    
    if args.json:
        import json
        output = {
            "course_id": args.course_id,
            "catalog_id": args.catalog_id,
            "question": args.question,
            "matched_kg_nodes": matched_kg_nodes,
            "course_knowledge_chunks": course_knowledge_chunks,
            "retrieval_debug": retrieval_debug,
            "summary": summary
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return
```
并在 Console 模式下读取并打印 `match_method` 和 `score`：
```python
    for i, node in enumerate(matched_kg_nodes):
        print(f"  {i+1}. {node.get('name')} (ID: {node.get('id')}) [Method: {node.get('match_method')} | Score: {node.get('score')}]")
```

- [ ] **Step 4: Commit**
```bash
git add agent_service/memory/tutoring_retrieval.py backend/tools/probe_aichat_hybrid_retrieval.py agent_service/api/v1/tutoring.py
git commit -m "feat: add retrieval_debug context and upgrade CLI probe format"
```

---

### Task 2: Implement Three-Tier Fallback Retrieval (`_match_kg_nodes`)

**Files:**
- Modify: `agent_service/memory/tutoring_retrieval.py`

- [ ] **Step 1: Replace `_rerank_kg_nodes` with `_match_kg_nodes`**

在 `agent_service/memory/tutoring_retrieval.py` 中，完全重写图谱节点的打分逻辑。引入三个阶段：Substring 去重 -> Reranker 打分 -> Embedding 降级。

```python
async def _match_kg_nodes(
    query: str,
    nodes: list[dict],
    reranker_provider: RerankerProvider | None,
    embedding_provider: EmbeddingProvider | None,
    query_vector: list[float] | None,
    limit: int = 3,
) -> list[dict]:
    if not nodes:
        return []
        
    matched = []
    seen_ids = set()
    query_lower = query.lower()

    # 1. Substring 高精匹配
    for node in nodes:
        node_name = node.get("name", "")
        if node_name and (node_name.lower() in query_lower or query_lower in node_name.lower()):
            matched_node = dict(node)
            matched_node["score"] = 1.0
            matched_node["match_method"] = "substring"
            matched.append(matched_node)
            seen_ids.add(node.get("id"))
            
    remaining_nodes = [n for n in nodes if n.get("id") not in seen_ids]

    # 2. Reranker 匹配 (若可用)
    if reranker_provider and remaining_nodes:
        documents = [n.get("name", "") for n in remaining_nodes]
        try:
            scores = await reranker_provider.score(query, documents)
            for node, score in zip(remaining_nodes, scores, strict=True):
                if score >= 0.35:
                    matched_node = dict(node)
                    matched_node["score"] = score
                    matched_node["match_method"] = "reranker"
                    matched.append(matched_node)
                    seen_ids.add(node.get("id"))
            remaining_nodes = [n for n in remaining_nodes if n.get("id") not in seen_ids]
        except Exception as exc:
            logger.warning("Tutoring KG nodes rerank failed: error=%s", exc)
            reranker_provider = None # 标记失败，允许进入降级

    # 3. Embedding 降级 (仅当无 Reranker 或 Reranker 失败时)
    if not reranker_provider and embedding_provider and query_vector and remaining_nodes:
        from agent_service.core.ai.embedding import cosine_similarity # Assuming utility exists, else inline
        
        # We need an inline cosine similarity if it's not exposed
        def _cos_sim(v1, v2):
            import math
            dot = sum(a * b for a, b in zip(v1, v2))
            norm_v1 = math.sqrt(sum(a * a for a in v1))
            norm_v2 = math.sqrt(sum(b * b for b in v2))
            return dot / (norm_v1 * norm_v2) if norm_v1 and norm_v2 else 0.0

        texts_to_embed = [f"{n.get('name', '')} {n.get('chapter', '')}" for n in remaining_nodes]
        try:
            node_vectors = await embedding_provider.embed_texts(texts_to_embed)
            for node, vector in zip(remaining_nodes, node_vectors, strict=True):
                score = _cos_sim(query_vector, vector)
                if score >= 0.55:
                    matched_node = dict(node)
                    matched_node["score"] = score
                    matched_node["match_method"] = "embedding"
                    matched.append(matched_node)
        except Exception as exc:
            logger.warning("Tutoring KG nodes embedding fallback failed: error=%s", exc)

    # 排序分组: 先按 method 优先级，同 method 内按 score
    def sort_key(n):
        method_weight = {"substring": 3, "reranker": 2, "embedding": 1}.get(n.get("match_method"), 0)
        return (method_weight, n.get("score", 0.0))
        
    matched.sort(key=sort_key, reverse=True)
    return matched[:limit]
```

- [ ] **Step 2: Update `build_tutoring_retrieval_context_with_ai`**

更新调用点，并组装 `retrieval_debug` 中的白名单 metadata。
```python
    matched_nodes = []
    if request.active_kg_nodes:
        matched_nodes = await _match_kg_nodes(
            query=request.message,
            nodes=request.active_kg_nodes,
            reranker_provider=reranker_provider,
            embedding_provider=embedding_provider,
            query_vector=query_vector,
            limit=limit,
        )
```
修改 Qdrant Chunk 返回部分，只针对 `course_results` 做安全提取：
```python
    retrieved_chunk_details = []
    for r in course_results:
        safe_meta = {}
        if hasattr(r, "metadata") and isinstance(r.metadata, dict):
             for k in ["chapter", "knowledge_point", "source", "material_id", "chunk_index"]:
                 if k in r.metadata:
                     safe_meta[k] = r.metadata[k]
        retrieved_chunk_details.append({
             "text": r.text,
             "score": getattr(r, "score", 0.0),
             "metadata": safe_meta
        })
    
    return context.model_copy(
        update={
            "user_memory_facts": user_texts,
            "course_knowledge_chunks": course_texts,
            "matched_kg_nodes": matched_nodes,
            "retrieval_debug": {"retrieved_chunk_details": retrieved_chunk_details}
        }
    )
```

- [ ] **Step 3: Commit**
```bash
git add agent_service/memory/tutoring_retrieval.py
git commit -m "feat: implement 3-tier fallback for KG nodes matching"
```

---

### Task 3: Inject KG Match into Prompt & Knowledge Points Fallback

**Files:**
- Modify: `agent_service/prompts/tutoring.py`
- Modify: `agent_service/agents/tutoring.py`
- Modify: `agent_service/agents/tutoring_react_flow.py`

- [ ] **Step 1: Update Prompts**

在 `agent_service/prompts/tutoring.py`，更新 `System Prompt` 并将图谱节点加入 Context：
```python
# 修改 `build_tutoring_messages` 内部 System Prompt 增加约束
        "如果提供了图谱节点，knowledge_points 应优先从这些节点名称中选择；回答应围绕最相关节点展开，不要机械覆盖所有节点。\n"

# 在 context_content 数组末尾增加
            f"图谱节点：{_join_or_none([f\"{n.get('chapter', '')} - {n.get('name', '')}\" for n in retrieval_context.matched_kg_nodes])}",
```
同样在 `build_strategy_selection_messages` 的 `user_content` 数组中也加上同样的“图谱节点”行。

在 `agent_service/agents/tutoring_react_flow.py` (如果有 `_build_react_user_message` 类似逻辑)，同样补充：
```python
            f"图谱节点：{_join_or_none([f\"{n.get('chapter', '')} - {n.get('name', '')}\" for n in retrieval_context.matched_kg_nodes])}",
```

- [ ] **Step 2: Update `_build_knowledge_points` fallback logic**

在 `agent_service/agents/tutoring.py`，让 `matched_kg_nodes` 成为第二顺位的兜底：
```python
def _build_knowledge_points(
    request: TutoringChatRequest,
    context: TutoringRetrievalContext,
    knowledge_point_names: list[str] | None = None,
) -> list[KnowledgePoint]:
    # 1. 优先使用模型生成的 names
    if knowledge_point_names:
        return [
            KnowledgePoint(
                name=name,
                chapter=request.course_id if request.scope == "course" else None,
            )
            for name in knowledge_point_names[:3]
            if name
        ]
        
    # 2. 兜底 1: 真实图谱命中节点
    if context.matched_kg_nodes:
        return [
            KnowledgePoint(
                name=node.get("name", "未知节点"),
                chapter=node.get("chapter") or request.course_id if request.scope == "course" else None,
            )
            for node in context.matched_kg_nodes[:3]
        ]
        
    # 3. 兜底 2: Context 里自带的 Knowledge Points (旧逻辑兼容)
    if context.knowledge_points:
        return context.knowledge_points
        
    # 4. 兜底 3: Profile 薄弱/掌握项，或字面截断
    weak_points = request.user_profile.knowledge_weak
    mastered_points = request.user_profile.knowledge_mastered
    names = weak_points or mastered_points or [request.message[:20] or "当前问题"]
    mastery = 40.0 if weak_points else 70.0 if mastered_points else None
    return [
        KnowledgePoint(
            name=name,
            chapter=request.course_id if request.scope == "course" else None,
            mastery=mastery,
        )
        for name in names[:3]
        if name
    ]
```

- [ ] **Step 3: Commit**
```bash
git add agent_service/prompts/tutoring.py agent_service/agents/tutoring.py agent_service/agents/tutoring_react_flow.py
git commit -m "feat: inject matched_kg_nodes into tutoring prompts and fallback chain"
```

---

### Task 4: Fix Tests and Feature Ledger

**Files:**
- Modify: `agent_service/tests/test_aichat_hybrid_retrieval.py`
- Modify: `frontend/docs/feature-ledger.md`
- Modify: `frontend/WORKFLOW.md`

- [ ] **Step 1: Write Negative and Substring Tests**

在 `test_aichat_hybrid_retrieval.py` 添加：
```python
@pytest.mark.asyncio
async def test_kg_nodes_no_match_returns_empty():
    # 有 Reranker 但是打分低 (例如 < 0.35)
    # 断言 matched_kg_nodes == []
    pass

@pytest.mark.asyncio
async def test_kg_nodes_substring_match_high_confidence():
    # 没有 Reranker 时，Substring 匹配 (Query: "解释 malloc/free", Node: "malloc/free")
    # 断言 len(matched) > 0, match_method == 'substring', score == 1.0
    pass
    
@pytest.mark.asyncio
async def test_kg_nodes_embedding_fallback():
    # 没有 Reranker，且 substring 不中时，mock embedding 算相似度 > 0.55
    # 断言 match_method == 'embedding'
    pass
```
*注：具体实现依据项目现有 mock fixtures，重点是增加这三项的覆盖。*

- [ ] **Step 2: Run Tests using root venv**

执行命令验证测试是否通过：
```bash
cd /home/yezisama/workspace/workflow/EDUagent && ./.venv/bin/python -m pytest agent_service/tests/test_aichat_hybrid_retrieval.py -q -p no:cacheprovider
```

- [ ] **Step 3: Update `feature-ledger.md` and `WORKFLOW.md`**

修改 `frontend/docs/feature-ledger.md` 第 174 行（以及任何残留的错误承诺）：
```markdown
- 2026-06-13 AI Chat Hybrid Retrieval 验证完成：按设计只验证后端和探针（不接 UI）。后端已将 `active_kg_nodes` 透传给 Agent Service 的 `TutoringChatRequest`，Agent 内实现了 KG 节点与 User Message 语义匹配打分的 Hybrid Context Logic，新增了直接吐出匹配上下文的探针端点 `/retrieval_probe` 和 CLI 工具，并补充了 C 语言专属查询回归测试（`test_aichat_hybrid_retrieval.py`）。当前已进入「探针与 mock 回归已完成，真实 Hybrid 闭环待验证」状态。
```

在 `WORKFLOW.md` 中记录本次 Correction 设计及对应的实现降级状态。

- [ ] **Step 4: Commit**
```bash
git add agent_service/tests/test_aichat_hybrid_retrieval.py frontend/docs/feature-ledger.md frontend/WORKFLOW.md
git commit -m "test: upgrade retrieval tests and downgrade feature ledger status"
```
