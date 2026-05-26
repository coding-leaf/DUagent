# evaluation/generate Full LLM Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `POST /agent/v1/evaluation/generate` from "rule tables + LLM summary" to guarded full `EvaluationData` enrichment without changing API schema.

**Architecture:** Keep `generate_evaluation_data()` as deterministic fallback. Let `generate_evaluation_with_llm()` request full `EvaluationData`, then coerce `progress_table`, `mastery_table`, `resource_usage_table`, and `summary_text` through fixed column contracts, observed chapter/resource allowlists, numeric clamps, and partial-output fallback. API route remains unchanged.

**Tech Stack:** FastAPI route in `api/v1/evaluation.py`, Pydantic schemas in `schemas/evaluation.py`, LLM boundary through `core.ai.ChatProvider`, tests with `pytest`.

---

## File Structure

- Modify: `prompts/evaluation.py`
  - Change prompt from summary-only to full `EvaluationData` JSON.
  - Define exact table column contracts.
  - Instruct LLM not to invent chapters/resource types and to fall back to rule table values when evidence is insufficient.

- Modify: `agents/evaluation.py`
  - Replace summary-only `_enrich_evaluation_result()` with full guarded enrichment.
  - Add table coercion helpers for progress, mastery, resource usage, score clamps, observed names, and fallback.
  - Keep `generate_evaluation_data()` unchanged.

- Modify: `tests/test_evaluation_agent.py`
  - Update success test to assert LLM can enrich all tables and summary.
  - Add invalid/fabricated field rejection test.
  - Keep provider-none, invalid JSON, exception, markdown, no-mutation, and API fallback tests.

- Modify: `WORKFLOW.md`
  - Mark `evaluation/generate` as full LLM enrichment + rule fallback.
  - Record targeted, OpenAPI, and full-suite verification.

- Do not modify: `api/v1/evaluation.py`, `schemas/evaluation.py`, or OpenAPI docs.

---

### Task 1: Add Failing Tests For Full Evaluation Enrichment

**Files:**
- Modify: `tests/test_evaluation_agent.py`

- [ ] **Step 1: Replace summary-only success test**

Replace `test_generate_evaluation_with_llm_enriches_summary_text` with a test that sends full `EvaluationData` JSON from `FakeChatProvider`:

```python
def test_generate_evaluation_with_llm_enriches_full_evaluation_data() -> None:
    import json as _json
    from agent_service.agents.evaluation import generate_evaluation_with_llm

    request = _build_request()
    rule_result = generate_evaluation_data(request)
    llm_output = _json.dumps({
        "progress_table": {
            "columns": [
                {"key": "chapter", "title": "章节"},
                {"key": "completion_rate", "title": "完成率"},
                {"key": "time_spent", "title": "学习时长（分钟）"},
                {"key": "progress_insight", "title": "进度分析"},
            ],
            "rows": [
                {"chapter": "函数", "completion_rate": 80.0, "time_spent": 120, "progress_insight": "进度稳定"},
                {"chapter": "导数", "completion_rate": 40.0, "time_spent": 60, "progress_insight": "进度偏慢"},
            ],
        },
        "mastery_table": {
            "columns": [
                {"key": "chapter", "title": "章节"},
                {"key": "average_score", "title": "平均正确率"},
                {"key": "quiz_count", "title": "练习次数"},
                {"key": "mastery_level", "title": "掌握水平"},
                {"key": "root_cause", "title": "薄弱根因"},
            ],
            "rows": [
                {"chapter": "函数", "average_score": 90.0, "quiz_count": 1, "mastery_level": "strong", "root_cause": "基础稳定"},
                {"chapter": "导数", "average_score": 55.0, "quiz_count": 1, "mastery_level": "weak", "root_cause": "极限概念不牢"},
            ],
        },
        "resource_usage_table": {
            "columns": [
                {"key": "resource_type", "title": "资源类型"},
                {"key": "count", "title": "使用次数"},
                {"key": "effectiveness_hint", "title": "效果提示"},
            ],
            "rows": [
                {"resource_type": "document", "count": 3, "effectiveness_hint": "文档偏多但导数仍弱"},
                {"resource_type": "video", "count": 1, "effectiveness_hint": "可增加视频辅助理解"},
            ],
        },
        "summary_text": "导数正确率55%，较函数90%明显偏低，建议增加视频讲解和代码练习。",
    })
    provider = FakeChatProvider(output=llm_output)

    result = asyncio.run(generate_evaluation_with_llm(request, rule_result, provider))

    assert result is not None
    assert result.progress_table.rows[1]["progress_insight"] == "进度偏慢"
    assert result.mastery_table.rows[1]["root_cause"] == "极限概念不牢"
    assert result.resource_usage_table.rows[1]["effectiveness_hint"] == "可增加视频辅助理解"
    assert "导数正确率55%" in (result.summary_text or "")
```

- [ ] **Step 2: Add invalid/fabricated rejection test**

Append:

```python
def test_generate_evaluation_with_llm_rejects_invalid_or_fabricated_rows() -> None:
    import json as _json
    from agent_service.agents.evaluation import generate_evaluation_with_llm

    request = _build_request()
    rule_result = generate_evaluation_data(request)
    provider = FakeChatProvider(output=_json.dumps({
        "progress_table": {
            "columns": [{"key": "chapter", "title": "章节"}, {"key": "completion_rate", "title": "完成率"}],
            "rows": [
                {"chapter": "fabricated", "completion_rate": 99},
                {"chapter": "导数", "completion_rate": 180, "time_spent": -1, "progress_insight": "保留有效章节"},
            ],
        },
        "mastery_table": {
            "columns": [{"key": "chapter", "title": "章节"}, {"key": "average_score", "title": "平均正确率"}],
            "rows": [
                {"chapter": "fabricated", "average_score": 100},
                {"chapter": "导数", "average_score": -5, "quiz_count": -2, "mastery_level": "invalid"},
            ],
        },
        "resource_usage_table": {
            "columns": [{"key": "resource_type", "title": "资源类型"}, {"key": "count", "title": "使用次数"}],
            "rows": [
                {"resource_type": "unknown", "count": 9},
                {"resource_type": "video", "count": -3, "effectiveness_hint": "保留有效资源"},
            ],
        },
        "summary_text": "有效总结。",
    }))

    result = asyncio.run(generate_evaluation_with_llm(request, rule_result, provider))

    assert result is not None
    assert result.progress_table.rows == [{"chapter": "导数", "completion_rate": 100.0, "time_spent": 0, "progress_insight": "保留有效章节"}]
    assert result.mastery_table.rows == [{"chapter": "导数", "average_score": 0.0, "quiz_count": 0, "mastery_level": "weak"}]
    assert result.resource_usage_table.rows == [{"resource_type": "video", "count": 0, "effectiveness_hint": "保留有效资源"}]
    assert result.summary_text == "有效总结。"
```

- [ ] **Step 3: Run targeted tests and verify expected failure**

Run:

```bash
./.venv/bin/pytest tests/test_evaluation_agent.py -v
```

Expected: new full-table tests fail because current `_enrich_evaluation_result()` only replaces `summary_text`.

---

### Task 2: Strengthen The Evaluation Prompt

**Files:**
- Modify: `prompts/evaluation.py`

- [ ] **Step 1: Replace system prompt**

Change `build_evaluation_system_prompt()` so it asks for complete `EvaluationData`:

```python
def build_evaluation_system_prompt() -> str:
    return (
        "你是 EDUagent 的学习评估助手。根据学习进度、练习结果、资源使用和系统规则评估，"
        "生成完整 EvaluationData JSON 对象。\n\n"
        "输出字段必须完整：progress_table、mastery_table、resource_usage_table、summary_text。\n"
        "每个表格必须包含 columns 和 rows。\n\n"
        "progress_table 固定基础列：chapter、completion_rate、time_spent；可增加 progress_insight。\n"
        "mastery_table 固定基础列：chapter、average_score、quiz_count、mastery_level；可增加 root_cause。\n"
        "resource_usage_table 固定基础列：resource_type、count；可增加 effectiveness_hint。\n\n"
        "约束：\n"
        "- 不要编造输入中没有出现的章节或资源类型\n"
        "- completion_rate、average_score 必须在 0-100\n"
        "- time_spent、quiz_count、count 必须为非负整数\n"
        "- mastery_level 只能是 strong/learning/weak\n"
        "- 如果证据不足，沿用系统规则表格对应行\n"
        "- summary_text 必须包含整体概况、章节对比、趋势、资源关联、可操作建议\n"
        "- 只输出 JSON 对象，不要加 markdown 代码块标记，不要加任何其他文字"
    )
```

- [ ] **Step 2: Update user message label**

In `build_evaluation_user_message()`, add after course ID:

```python
    parts.append("")
    parts.append("评估生成要求：请输出完整 EvaluationData JSON。若某表格字段证据不足，请沿用系统规则表格。")
```

- [ ] **Step 3: Run targeted tests**

Run:

```bash
./.venv/bin/pytest tests/test_evaluation_agent.py -v
```

Expected: full-table tests still fail until agent merge logic is implemented.

---

### Task 3: Implement Guarded Full EvaluationData Enrichment

**Files:**
- Modify: `agents/evaluation.py`

- [ ] **Step 1: Pass request into enrichment**

Change:

```python
return _enrich_evaluation_result(rule_result, data)
```

to:

```python
return _enrich_evaluation_result(request, rule_result, data)
```

- [ ] **Step 2: Replace `_enrich_evaluation_result()`**

Implement:

```python
def _enrich_evaluation_result(request: EvaluationGenerateRequest, rule_result: EvaluationData, llm_data: dict) -> EvaluationData:
    enriched = rule_result.model_copy(deep=True)
    observed_chapters = _observed_chapters(request)
    observed_resources = set(request.resource_usage.by_type.keys())
    enriched.progress_table = _coerce_progress_table(llm_data.get("progress_table"), rule_result.progress_table, observed_chapters)
    enriched.mastery_table = _coerce_mastery_table(llm_data.get("mastery_table"), rule_result.mastery_table, observed_chapters)
    enriched.resource_usage_table = _coerce_resource_usage_table(llm_data.get("resource_usage_table"), rule_result.resource_usage_table, observed_resources)
    summary = llm_data.get("summary_text")
    if isinstance(summary, str) and summary.strip():
        enriched.summary_text = summary.strip()
    return enriched
```

- [ ] **Step 3: Add coercion helpers**

Add helpers for:

- `_observed_chapters(request) -> set[str]`
- `_coerce_columns(raw_columns, fallback_columns, allowed_extra_keys)`
- `_coerce_progress_table(raw, fallback, observed_chapters)`
- `_coerce_mastery_table(raw, fallback, observed_chapters)`
- `_coerce_resource_usage_table(raw, fallback, observed_resources)`
- `_coerce_score(value, fallback)`
- `_coerce_non_negative_int(value, fallback)`
- `_coerce_mastery_level(value, fallback_score)`

Rules:

- Drop rows whose `chapter` is not in observed chapters.
- Drop rows whose `resource_type` is not in observed resource types.
- Clamp scores to `0.0..100.0`.
- Convert negative counts/time to `0`.
- Invalid `mastery_level` derives from score: `>=85 strong`, `>=60 learning`, else `weak`.
- If a coerced table has no valid rows, return fallback table.

- [ ] **Step 4: Run targeted tests**

Run:

```bash
./.venv/bin/pytest tests/test_evaluation_agent.py -v
```

Expected: all evaluation tests pass.

---

### Task 4: Update Workflow, Verify, Commit

**Files:**
- Modify: `WORKFLOW.md`

- [ ] **Step 1: Update status**

Change `evaluation/generate` row to:

```markdown
| `POST /agent/v1/evaluation/generate` | LLM full enrichment + 规则版 fallback 已完成 | 降级链：LLM guarded full EvaluationData enrichment → 规则版；表格和 summary 均经列/范围/观测名称保护后合并 |
```

- [ ] **Step 2: Run verification**

Run:

```bash
./.venv/bin/pytest tests/test_evaluation_agent.py -v
./.venv/bin/pytest tests/test_openapi_alignment.py -v
./.venv/bin/pytest -q
```

Expected:

- evaluation tests pass
- OpenAPI alignment stays at `15 passed`
- full suite passes

- [ ] **Step 3: Commit**

Run:

```bash
git add agents/evaluation.py prompts/evaluation.py tests/test_evaluation_agent.py WORKFLOW.md
git commit -m "feat(agent): enable guarded full evaluation LLM enrichment"
```

---

## Self-Review

- Spec coverage: Moves `evaluation/generate` beyond summary-only enrichment into guarded full `EvaluationData`.
- Placeholder scan: No TBD/TODO placeholders remain.
- Type consistency: Uses existing `EvaluationGenerateRequest`, `EvaluationData`, `TableData`, and `TableColumn`; no schema or API changes required.
- Scope check: Four implementation files, within the AGENTS.md five-file limit.
