# ReActAgent LLM Smoke

**Date**: 2026-05-25
**Status**: approved

## Purpose

Verify that `TutorReActAgent` → `parse_tutoring_model_response()` works end-to-end with a real LLM, before depending on it in the API degradation chain.

## Architecture

```
tools/smoke_react.py (CLI entry, no HTTP, no Qdrant)
  ├── Synthetic TutoringChatRequest (hand-written)
  ├── Synthetic TutoringRetrievalContext (1 synthetic fact + 1 synthetic chunk + hand-written knowledge_points)
  ├── get_ai_providers().chat → model + formatter
  ├── generate_tutoring_react_response(request, context, chat_provider)
  │     ├── duck-typing check: hasattr(model) and hasattr(formatter)
  │     ├── _build_react_user_message(request, context)
  │     ├── TutorReActAgent(chat_model, formatter)
  │     ├── agent.generate(user_message)
  │     └── parse_tutoring_model_response(output)
  └── Console output: model_text, knowledge_points, suggestion, elapsed time
```

## Dependencies

| Dependency | Required? | Notes |
|------------|-----------|-------|
| `LLM_PROVIDER=agentscope_openai` | Yes | |
| `LLM_MODEL` | Yes | |
| `LLM_BASE_URL` | Yes | |
| `LLM_API_KEY` | Yes | |
| `EMBEDDING_*` | No | Smoke does not touch Qdrant or embedding |
| Qdrant | No | Disk or remote |
| FastAPI / uvicorn | No | |

## Success Criteria

| Outcome | Exit Code | Description |
|---------|-----------|-------------|
| **Pass** | 0 | `model_text` non-empty; `knowledge_points` / `suggestion` may be empty (warning only) |
| **Fail: ReAct returned None** | 1 | `agent.generate()` returned None — ReAct path did not execute |
| **Fail: ReAct raised** | 1 | Exception from `agent.generate()` not caught by internal try/except |
| **Fail: empty model_text** | 1 | Parse succeeded but `model_text` is empty string |
| **Fail: unconfigured** | 1 | `LLM_PROVIDER` not set to `agentscope_openai`, or provider has no model/formatter |

Purpose of this smoke is to verify the ReActAgent → JSON parse main path works under a real LLM. Degradation is NOT considered success — if ReAct doesn't produce a valid response, the script must fail loudly so the result is unambiguous.

## Scope

**In**: One-shot CLI smoke script under `tools/smoke_react.py`.

**Out**: HTTP server, SSE streaming, Qdrant retrieval, embedding calls, `_build_model_response()`, API-layer integration test.

## Synthetic Data

```python
request = TutoringChatRequest(
    user_id="smoke-user",
    course_id="data-structures",
    message="线性表和链表有什么区别？",
    user_profile=TutoringUserProfile(
        guidance_level="L2",
        knowledge_weak=["链表"],
        knowledge_mastered=["顺序表"],
    ),
)

context = TutoringRetrievalContext(
    user_id="smoke-user",
    course_id="data-structures",
    query_text="线性表和链表有什么区别？",
    include_course_knowledge=True,
    knowledge_points=["线性表", "链表"],
    user_memory_facts=["用户刚学完顺序表，容易混淆数组和链表。"],
    course_knowledge_chunks=["线性表是相同类型数据元素的有限序列，链表用指针表示逻辑关系。"],
)
```

## Test Output Format

```
=== ReActAgent LLM Smoke ===
Provider: agentscope_openai
Model: deepseek-v3
Elapsed: 2.34s

model_text: 线性表和链表的核心区别在于存储方式...
knowledge_points: ['线性表', '链表', '顺序存储']
suggestion: 建议画图对比数组连续内存和链表指针跳转

OK — ReAct response parsed successfully
```

On failure (any of the exit-1 conditions):
```
=== ReActAgent LLM Smoke ===
Provider: agentscope_openai
Model: deepseek-v3
Elapsed: 1.20s

FAIL: ReActAgent returned None — check LLM configuration and model compatibility
```

## Verification

```bash
./.venv/bin/python -m agent_service.tools.smoke_react
```
