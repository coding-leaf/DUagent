# learning-path/generate LLM 接入

**Date**: 2026-05-26
**Status**: draft

## Purpose

Upgrade `POST /agent/v1/learning-path/generate` with LLM-enhanced planning judgment. The rule-based implementation already produces valid output; the LLM layer improves status/mastery/reason/order/current_position quality.

## Core Constraint

LLM MUST NOT invent new nodes or names. `node.id` and `node.name` come from `request.knowledge_graph.nodes`. LLM only provides planning annotations (status, mastery, order, reason). This ensures Backend can match returned nodes to its knowledge graph, tests can validate by whitelist membership, and rule-based fallback has consistent output.

## Architecture

```
POST /learning-path/generate
  → generate_learning_path(request)
    → get_ai_providers()
    → generate_learning_path_with_llm(request, chat_provider)
        │ 成功: return LearningPathData
        │ 失败: return None
    → None? fallback to generate_learning_path_data(request)  ← 现有规则版
  → LearningPathGenerateResponse(data=...)
```

## File Changes

### New: `prompts/learning_path.py`

- `build_learning_path_system_prompt()` → `str`
- `build_learning_path_user_message(request)` → `str` — serializes nodes, edges, profile, evaluation

Key prompt constraints:
- Output ONLY a JSON object `{"nodes": [...], "current_position": {...}}`, no markdown fences
- Each node has `{id, status, mastery, order, reason}` — `id` must be from input nodes list
- `current_position` is `{node_id}` — `node_id` must be in the output nodes
- Do NOT output `name` field for nodes or `node_name` for current_position — these are backfilled from input

### Modify: `agents/learning_path.py`

```python
async def generate_learning_path_with_llm(
    request: LearningPathGenerateRequest,
    chat_provider,
) -> LearningPathData | None:
```

Logic:
1. `chat_provider is None` → return None
2. Build `nodes_by_id`: `{node.id: node for node in request.knowledge_graph.nodes if node.id}`
3. Build messages → `chat_provider.complete(messages)` → raw text
4. Strip fences, `json.loads()` → dict with `nodes` array and optional `current_position`
5. `_coerce_path_nodes(llm_nodes, nodes_by_id)` — for each LLM node:
   - Discard if `id` not in `nodes_by_id`
   - Backfill `name` from `nodes_by_id[id].name`
   - Backfill `chapter` from `nodes_by_id[id].chapter`
   - Validate `status` is one of `completed/in_progress/pending/recommended`, else default `pending`
   - Clamp `mastery` to 0-100, default 0
   - Cast `order` to int, default based on position in array
   - Use LLM `reason` or default to empty string
6. `_coerce_current_position(llm_cp, valid_ids, nodes_by_id)`:
   - If `node_id` is in `valid_ids`, create `CurrentPosition(node_id=node_id, node_name=nodes_by_id[node_id].name)`
   - Otherwise find first `recommended/in_progress/pending` node by order; if none, return None
7. Combine: `LearningPathData(nodes=coerced_nodes, edges=copy(input edges), current_position=...)`
8. Any exception → return None

### Modify: `api/v1/learning_path.py`

Handler becomes async, tries LLM first, falls back to existing rule-based.

### Tests

In `tests/test_learning_path_agent.py`:

1. Valid LLM output with known IDs → nodes have backfilled `name`, edges preserved, unknown IDs discarded
2. LLM returns node with unknown id → discarded, not in output
3. `current_position.node_id` references unknown node → falls back to first recommended/in_progress/pending
4. `name` field in LLM output is ignored, backfilled from input
5. Invalid JSON → returns None
6. `chat_provider is None` → returns None
7. LLM raises → returns None

In `tests/test_learning_path_api.py` (new or append to existing):

8. Mock LLM success → API returns LLM-generated data
9. Mock LLM returns None → API falls back to rule-based data (skeleton `generate_learning_path_data`)

## Dependencies

| Dependency | Required? | Fallback |
|------------|-----------|----------|
| `LLM_PROVIDER` | Optional | Existing `generate_learning_path_data()` |

## Scope

**In**: `generate_learning_path_with_llm()`, prompt templates, `_coerce_path_nodes()` with ID whitelist + name backfill, API wiring, agent + API tests.

**Out**: LLM generating new nodes, LLM generating edges, embedding/Qdrant.

## Verification

```bash
./.venv/bin/pytest tests/test_learning_path_agent.py tests/test_learning_path_api.py -q
./.venv/bin/pytest tests/test_openapi_alignment.py -q
```
