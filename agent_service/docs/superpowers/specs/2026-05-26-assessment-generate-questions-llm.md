# assessment/generate-questions LLM 接入

**Date**: 2026-05-26
**Status**: draft

## Purpose

Upgrade `POST /agent/v1/assessment/generate-questions` from placeholder skeleton to LLM-powered question generation, with rule-based skeleton as fallback.

## Architecture

```
POST /assessment/generate-questions
  → generate_questions(request)
    → get_ai_providers()
    → generate_questions_with_llm(request, chat_provider)
        │ 成功: return list[GeneratedQuestion]
        │ 失败: return None
    → None? fallback to generate_questions_data(request)  ← 现有骨架
  → QuestionGenerateResponse(questions=...)
```

Same pattern as tutoring: try LLM, degrade to rule-based.

## File Changes

### New: `prompts/assessment.py`

Two functions:

- `build_question_generation_system_prompt()` → `str`
- `build_question_generation_user_message(request: QuestionGenerateRequest)` → `str`

System prompt constraints:
- Output ONLY a JSON array, no markdown fences, no extra text
- Each element matches GeneratedQuestion schema: type, content, options, answer, explanation, chapter, knowledge_point, difficulty
- Questions pedagogically sound for the given difficulty
- Options for single_choice/multi_choice have plausible distractors

User message fills: knowledge_point, question_types, count, difficulty, chapter, personalization_context.

### Modify: `agents/assessment.py`

New function:

```python
async def generate_questions_with_llm(
    request: QuestionGenerateRequest,
    chat_provider: ChatProvider | None,
) -> list[GeneratedQuestion] | None:
```

Logic:
1. `chat_provider is None` → return None
2. Build messages from `prompts/assessment.py`
3. `chat_provider.complete(messages)` → raw text
4. Strip markdown fences if present, `json.loads()` → verify list
5. Coerce each dict into `GeneratedQuestion`, skip items with empty `content`
6. Any exception → return None

### Modify: `api/v1/assessment.py`

`generate_questions()` becomes async, tries LLM first, falls back to skeleton:

```python
async def generate_questions(request):
    providers = get_ai_providers()
    questions = await generate_questions_with_llm(request, getattr(providers, "chat", None))
    if questions is None:
        questions = generate_questions_data(request).questions
    return QuestionGenerateResponse(code=200, message="success",
        data=QuestionGenerateResult(questions=questions))
```

### Tests for `generate_questions_with_llm`

In `tests/test_assessment_agent.py`:

1. Valid JSON array → parsed correctly
2. JSON with markdown fences → stripped and parsed
3. Invalid JSON → returns None
4. `chat_provider is None` → returns None
5. LLM raises → returns None

## Dependencies

| Dependency | Required? | Fallback |
|------------|-----------|----------|
| `LLM_PROVIDER=agentscope_openai` | Optional | Skeleton `generate_questions_data()` |
| `LLM_MODEL/BASE_URL/API_KEY` | Optional | Skeleton |

No embedding, no Qdrant, no vector store. Pure LLM text generation.

## Scope

**In**: `generate_questions_with_llm()`, prompt templates, API handler wiring, unit tests.

**Out**: Embedding-based retrieval, multi-agent generation, quality evaluation, Qdrant.

## Verification

```bash
./.venv/bin/pytest tests/test_assessment_agent.py -q
```
