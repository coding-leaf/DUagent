# retrieve_course_knowledge Toolkit

**Date**: 2026-05-25
**Status**: approved

## Purpose

Let ReActAgent actively retrieve course knowledge during tutoring, without expanding into a complex multi-tool system.

## Architecture

```
generate_tutoring_react_response(request, ..., embedding_provider)
  ├── build_tutoring_toolkit(course_id, embedding_provider, vector_store?, limit=3)
  │     └── closure captures: course_id, embedding_provider, vector_store, limit
  │     └── register_tool_function(retrieve_course_knowledge)
  │           model sees: retrieve_course_knowledge(query: str)
  └── TutorReActAgent(..., toolkit=toolkit)
```

Dependencies hidden from model via closure — NOT `preset_kwargs` (which only accepts JSON-serializable values, cannot hold provider/store objects).

## File Changes

### New: `agents/tutoring_tools.py`

Factory function `build_tutoring_toolkit()` creates an AgentScope `Toolkit` with a single tool.

**Closure captures (hidden from model):**

```
course_id: str | None             — from TutoringChatRequest.course_id
embedding_provider                — from get_ai_providers().embedding
vector_store: QdrantVectorStore   — injected or default
limit: int = 3                    — fixed
```

**Tool signature exposed to model:**

```
retrieve_course_knowledge(query: str) -> ToolResponse
```

**Tool behavior:**

| Condition | Return |
|-----------|--------|
| `course_id` is None (global scope) | `ToolResponse(content=[{"text": "当前对话无指定课程知识库。"}])` |
| Embedding + Qdrant search OK | `ToolResponse(content=[{"text": "\n---\n".join(chunk texts)}])` |
| Search returns empty | `ToolResponse(content=[{"text": "未找到相关课程知识。"}])` |
| Any exception (including UnconfiguredEmbeddingProvider) | `ToolResponse(content=[{"text": "课程知识检索暂时不可用。"}])` |

The tool is always registered when `build_tutoring_toolkit()` is called. The embedding provider may be `UnconfiguredEmbeddingProvider` — in that case the exception is caught at call time inside the tool, returning the error message. No `isinstance` check needed.

### Modify: `agents/tutoring_react_flow.py`

`generate_tutoring_react_response()` gains an optional `embedding_provider` parameter:

```python
async def generate_tutoring_react_response(
    request,
    retrieval_context,
    chat_provider,
    embedding_provider=None,
) -> TutoringModelResponse | None:
```

When `embedding_provider` is provided, builds toolkit and passes to `TutorReActAgent`. When absent, toolkit is None — ReAct works as before (no tools).

`_build_model_response()` in `api/v1/tutoring.py` passes `providers.embedding`.

### New: `tests/test_tutoring_tools.py`

1. **Global scope** (course_id=None) → returns no-knowledge ToolResponse, no embedding call
2. **Search returns chunks** → ToolResponse content is joined chunks with separator
3. **Empty search** → returns empty-message ToolResponse
4. **Embedding failure** → returns error-message ToolResponse, no exception raised
5. **Tool schema** — registered function's JSON schema only exposes `query`, not `course_id` / provider / vector_store / limit

### Modify: `tests/test_tutoring_react_flow.py`

Existing tests pass `embedding_provider=None` (no behavior change). Add 1 test for toolkit injection.

## API Boundaries

- **AgentScope `Toolkit.register_tool_function()`** — API confirmed via introspection
- **`ToolResponse(content=[{"text": ...}])`** — confirmed return type
- **Closure, not `preset_kwargs`** — `preset_kwargs` only accepts JSON-serializable values, cannot hold provider/store objects

## Dependencies

| Dependency | Required for toolkit? | Fallback |
|------------|----------------------|----------|
| `LLM_PROVIDER=agentscope_openai` | Yes (for ReAct itself) | ReAct → chat JSON → rule |
| `EMBEDDING_PROVIDER=agentscope_openai` | Yes (for real retrieval) | Tool always registered; exception caught at call time → "检索暂时不可用" |
| Qdrant with course knowledge | Yes (for real results) | Tool returns "检索不可用" or "未找到" |

## Scope

**In**: Single `retrieve_course_knowledge` tool, factory function, wiring in `generate_tutoring_react_response()`, unit tests.

**Out**: `retrieve_user_memory` tool, diagram tool, code execution tool, multi-tool orchestration, smoke script updates, API-level E2E testing.

## Verification

```bash
./.venv/bin/pytest tests/test_tutoring_tools.py tests/test_tutoring_react_flow.py -q
```
