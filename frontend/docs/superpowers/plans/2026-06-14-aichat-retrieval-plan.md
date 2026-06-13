# AI Chat Hybrid Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Hybrid Retrieval (KG Match + Qdrant Chunks) for AI Chat, establishing a CLI probe and regression suite to verify retrieval quality before UI integration.

**Architecture:** 
1. **Payload Expansion**: Backend fetches the Active KG for the course's catalog and passes it in `TutoringChatRequest`.
2. **Hybrid Retrieval**: Agent Service's `tutoring_retrieval.py` performs KG Match (semantic/exact match against KG nodes) and Qdrant chunk search.
3. **Probe Tool**: A standalone CLI tool to output intermediate retrieval states (KG matches, chunks) without full chat stream, allowing debugging.
4. **Testing**: Pytest regression suite over the hybrid logic using specific C-language samples.

**Tech Stack:** Python, FastAPI, Qdrant, SQLAlchemy, Pytest

---

### Task 1: Extend TutoringChatRequest with Active KG Nodes

**Files:**
- Modify: `agent_service/schemas/tutoring.py`
- Modify: `app/schemas/operations.py` (Backend)
- Modify: `app/api/v1/tutoring.py` (Backend)

- [ ] **Step 1: Add `active_kg_nodes` to agent schema**

In `agent_service/schemas/tutoring.py` and `backend/app/schemas/operations.py`, add to `TutoringChatRequest`:
```python
    active_kg_nodes: list[dict] = Field(default_factory=list, description="当前课程绑定资源库的 Active KG 节点精简列表")
```

- [ ] **Step 2: Update Backend Chat API to inject Active KG**

In `backend/app/api/v1/tutoring.py`, update `_assemble_tutoring_payload` to query the `course_knowledge_graphs` for the given `course_id` (via `CourseOffering.catalog_id` or `kg_host_course_id`), and append `"active_kg_nodes"` containing id, name, and chapter to the returned payload.

- [ ] **Step 3: Commit**

```bash
git add agent_service/schemas/tutoring.py backend/app/schemas/operations.py backend/app/api/v1/tutoring.py
git commit -m "feat(chat): inject active_kg_nodes into tutoring chat payload"
```

---

### Task 2: Implement Hybrid Retrieval Context Logic

**Files:**
- Modify: `agent_service/memory/tutoring_retrieval.py`
- Test: `agent_service/tests/test_tutoring_retrieval.py` (or create if absent)

- [ ] **Step 1: Update TutoringRetrievalContext schema**

In `agent_service/memory/tutoring_retrieval.py`, add `matched_kg_nodes: list[dict] = Field(default_factory=list)` to `TutoringRetrievalContext`.

- [ ] **Step 2: Implement KG Match in `build_tutoring_retrieval_context_with_ai`**

In `agent_service/memory/tutoring_retrieval.py`, update `build_tutoring_retrieval_context_with_ai`:
1. Use `request.active_kg_nodes` and compute relevance between `request.message` and each node (using `reranker_provider` or embedding similarity).
2. Store the top matched nodes in `matched_kg_nodes`.
3. Existing Qdrant search remains unchanged to populate `course_knowledge_chunks`.

- [ ] **Step 3: Run existing agent tests**

Run: `pytest tests/test_tutoring_retrieval.py -q` (if exists) or other related memory tests to ensure nothing breaks.

- [ ] **Step 4: Commit**

```bash
git add agent_service/memory/tutoring_retrieval.py
git commit -m "feat(agent): implement hybrid KG match in tutoring retrieval"
```

---

### Task 3: Create Hybrid Retrieval Probe API and CLI Tool

**Files:**
- Modify: `agent_service/api/v1/tutoring.py`
- Create: `backend/tools/probe_aichat_hybrid_retrieval.py`

- [ ] **Step 1: Expose Agent Probe Endpoint**

In `agent_service/api/v1/tutoring.py`, add an endpoint `POST /agent/v1/tutoring/retrieval_probe` that accepts `TutoringChatRequest`, calls `build_tutoring_retrieval_context_with_ai`, and returns the context (matched nodes and chunks) as JSON.

- [ ] **Step 2: Create CLI Probe Tool**

Create `backend/tools/probe_aichat_hybrid_retrieval.py` that takes `--course-id`, `--catalog-id`, and `--question`. 
It should:
1. Query MySQL for the active KG of the catalog/course.
2. Build the `TutoringChatRequest` payload.
3. Call the new `/agent/v1/tutoring/retrieval_probe` HTTP endpoint.
4. Print/export `[KG Match]`, `[Qdrant Chunks]`, and `[Knowledge Points]` (extracted from matched nodes).

- [ ] **Step 3: Commit**

```bash
git add agent_service/api/v1/tutoring.py backend/tools/probe_aichat_hybrid_retrieval.py
git commit -m "feat(tools): add hybrid retrieval probe API and CLI tool"
```

---

### Task 4: Write Pytest Regression Suite

**Files:**
- Create: `backend/tests/test_aichat_hybrid_retrieval.py`

- [ ] **Step 1: Write integration tests based on CLI probe logic**

Create `backend/tests/test_aichat_hybrid_retrieval.py` to test high-value C-language samples (e.g., pointers, arrays, wild pointers).
Mock the DB and Qdrant, or use a test DB. Assert that:
- `matched_kg_nodes` contains expected structural concepts.
- `course_knowledge_chunks` is non-empty.

- [ ] **Step 2: Run the test suite**

Run: `pytest tests/test_aichat_hybrid_retrieval.py -q`

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_aichat_hybrid_retrieval.py
git commit -m "test: add hybrid retrieval regression suite"
```
