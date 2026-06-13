# AI Chat Hybrid Retrieval Design

## 1. Overview
Currently, AI Chat's course knowledge retrieval (`tutoring_retrieval.py`) relies exclusively on semantic vector search over raw Qdrant chunks. It lacks the ability to align user queries with the structural Knowledge Graph (Active KG), causing inconsistencies when attempting to map answers back to official `knowledge_points` for resource recommendation.

This design introduces a **Hybrid Retrieval Architecture** (KG Match + Qdrant Chunks) and dictates a strict verification path (CLI -> Pytest) before any UI integration, strictly adhering to the project ledger constraint.

## 2. Architecture & Data Flow
The new retrieval pipeline executes when `scope=course`:

1. **KG Match**: Align the user's question with nodes in the current Active KG. This provides the primary structural context and ensures stable `knowledge_points`.
2. **Qdrant Chunk Search**: Semantic search in Qdrant for detailed course fragments (chunks) to ground the LLM's answer with actual course material.
3. **Prompt Assembly & LLM Synthesis**: Both matched nodes and text chunks are injected into the agent's context. 
4. **Structured Output**: The LLM generates the final answer and outputs a discrete list of `knowledge_points` that strongly prefer the matched KG node names. Subsequent resource recommendations will query against these points.

## 3. Implementation Verification Path

Following the ledger rule: *"后续 Chat spec 必须从’先验证 Agent 检索能力’开始，不先加 UI"*。

### Phase 1: CLI Probe Tool (`tools/probe_aichat_hybrid_retrieval.py`)
A standalone CLI tool to expose and debug the intermediate hybrid steps.
- **Inputs**: `course_id`, `catalog_id`, `question`
- **Outputs**:
  - `[KG Match]`: Matched nodes with relevance scores.
  - `[Qdrant Chunks]`: Retrieved text chunks and scores.
  - `[Knowledge Points]`: Final extracted stable concepts.
  - `[Answer Preview]`: The generated LLM response.
- **Feature**: Supports `--json` for exporting outputs into reusable test cases.

### Phase 2: Pytest Regression Suite (`tests/test_aichat_hybrid_retrieval.py`)
Once the CLI probe demonstrates stable behavior, 6-8 high-value C-language samples will be codified into integration tests.
- **Sample Types**: Concepts (pointers, arrays), Code Debugging (wild pointers, bounds), Long-tail details, and Out-of-bounds questions.
- **Assertions**:
  - `matched_kg_nodes` contains expected structural concepts.
  - `retrieved_chunks` is non-empty and bounded to the correct catalog.
  - `knowledge_points` is a stable string list.
  - `answer` is non-empty.
  - Out-of-scope questions yield low confidence or empty structural matches.

### Phase 3: Frontend UI Integration (Deferred)
Only after Phase 1 and Phase 2 pass will the frontend `AIChat.jsx` be updated to:
- Render actual ToolCalls (`[KG Match]`, `[Qdrant Chunks]`).
- Extract the verified `knowledge_points` and dynamically query the `/resources` endpoint for right-sidebar recommendations.

## 4. Impacted Components
- **Agent Memory**: `agent_service/memory/tutoring_retrieval.py` (Upgrade `build_tutoring_retrieval_context_with_ai` to incorporate KG queries).
- **Tooling**: `tools/probe_aichat_hybrid_retrieval.py`
- **Testing**: `tests/test_aichat_hybrid_retrieval.py`
