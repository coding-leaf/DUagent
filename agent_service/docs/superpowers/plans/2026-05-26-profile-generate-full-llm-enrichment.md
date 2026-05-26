# profile/generate Full LLM Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `POST /agent/v1/profile/generate` from "rule result + reason rewrite" to a guarded LLM enrichment path that can improve the full `ProfileData` structure while preserving API schema and deterministic fallback.

**Architecture:** Keep `generate_profile_data()` as the complete rule fallback and base result. Let `generate_profile_with_llm()` request a full `ProfileData` JSON object, then coerce each field through schema-aware allowlists, numeric clamps, and observed-data guards. Missing or invalid LLM fields fall back to the rule result, so the endpoint remains stable when LLM output is partial, invalid, or unavailable.

**Tech Stack:** FastAPI route already in `api/v1/profile.py`, Pydantic schemas in `schemas/profile.py`, LLM boundary via `core.ai.ChatProvider`, tests with `pytest`.

---

## File Structure

- Modify: `prompts/profile.py`
  - Change the system prompt from "only rewrite reason" to "return full ProfileData".
  - Add explicit JSON shape, enum values, numeric ranges, and anti-fabrication rules.
  - Add richer user-message summaries from quiz history, resource usage, recent activity, and current rule result.

- Modify: `agents/profile.py`
  - Replace reason-only merge with full-field guarded enrichment.
  - Add helpers for clamping scores, validating enum fields, filtering observed chapter names, and filling missing fields from `rule_result`.
  - Keep `generate_profile_data()` unchanged.

- Modify: `tests/test_profile_agent.py`
  - Update old reason-only tests to assert full enrichment behavior.
  - Add tests for field coercion, fabricated-name rejection, partial-output fallback, markdown JSON, invalid JSON, exception fallback, no mutation, and API fallback.

- Modify: `WORKFLOW.md`
  - Update `profile/generate` status after tests pass.
  - Record exact verification commands and results.

- Do not modify: `api/v1/profile.py`, `schemas/profile.py`, or OpenAPI docs.

---

### Task 1: Add Tests For Full Profile Enrichment

**Files:**
- Modify: `tests/test_profile_agent.py`

- [ ] **Step 1: Replace the reason-only success test with full enrichment coverage**

Replace `test_generate_profile_with_llm_enriches_reason_text` with:

```python
def test_generate_profile_with_llm_enriches_full_profile_data() -> None:
    import json as _json
    from agent_service.agents.profile import generate_profile_with_llm

    request = _build_request()
    rule_result = generate_profile_data(request)
    llm_output = _json.dumps({
        "modal_preference": {
            "video_animation": 60.0,
            "chart_logic": 35.0,
            "text_analysis": 90.0,
            "code_practice": 45.0,
            "formula_derivation": 20.0,
        },
        "guidance_level_suggestion": {
            "recommended": "L1",
            "reason": "导数最近只有60%，且资源使用偏文档，建议用更细的步骤和例题拆解极限到导数的过渡。",
        },
        "knowledge_coordinates": [
            {"name": "函数", "status": "mastered"},
            {"name": "导数", "status": "learning"},
        ],
        "cognitive_blindspots": [
            {"name": "导数", "error_count": 2, "severity": "high"},
        ],
        "drive_intent": {"type": "exam_sprint", "intensity": 82.0},
        "discipline_badge": {"subject": "course-1", "level": "sprint", "streak_days": 5},
    })
    provider = FakeChatProvider(output=llm_output)

    result = asyncio.run(generate_profile_with_llm(request, rule_result, provider))

    assert result is not None
    assert result.modal_preference.video_animation == 60.0
    assert result.modal_preference.text_analysis == 90.0
    assert result.guidance_level_suggestion.recommended == "L1"
    assert "导数最近只有60%" in (result.guidance_level_suggestion.reason or "")
    assert [(item.name, item.status) for item in result.knowledge_coordinates] == [
        ("函数", "mastered"),
        ("导数", "learning"),
    ]
    assert [(item.name, item.error_count, item.severity) for item in result.cognitive_blindspots] == [
        ("导数", 2, "high"),
    ]
    assert result.drive_intent.type == "exam_sprint"
    assert result.drive_intent.intensity == 82.0
    assert result.discipline_badge.subject == "course-1"
    assert result.discipline_badge.level == "sprint"
    assert result.discipline_badge.streak_days == 5
```

- [ ] **Step 2: Replace the structured-field rejection test with guarded coercion coverage**

Replace `test_generate_profile_with_llm_rejects_llm_structured_fields` with:

```python
def test_generate_profile_with_llm_rejects_invalid_or_fabricated_fields() -> None:
    import json as _json
    from agent_service.agents.profile import generate_profile_with_llm

    request = _build_request()
    rule_result = generate_profile_data(request)
    llm_output = _json.dumps({
        "modal_preference": {
            "video_animation": 999.0,
            "text_analysis": -20.0,
        },
        "guidance_level_suggestion": {
            "recommended": "L9",
            "reason": "保留这个有效理由。",
        },
        "knowledge_coordinates": [
            {"name": "fabricated", "status": "mastered"},
            {"name": "函数", "status": "invalid"},
            {"name": "导数", "status": "learning"},
        ],
        "cognitive_blindspots": [
            {"name": "fabricated", "error_count": 99, "severity": "high"},
            {"name": "导数", "error_count": -3, "severity": "invalid"},
        ],
        "drive_intent": {"type": "invalid", "intensity": 500.0},
        "discipline_badge": {"subject": "hacked", "level": "advanced", "streak_days": -1},
    })
    provider = FakeChatProvider(output=llm_output)

    result = asyncio.run(generate_profile_with_llm(request, rule_result, provider))

    assert result is not None
    assert result.modal_preference.video_animation == 100.0
    assert result.modal_preference.text_analysis == 0.0
    assert result.guidance_level_suggestion.recommended == rule_result.guidance_level_suggestion.recommended
    assert result.guidance_level_suggestion.reason == "保留这个有效理由。"
    assert [(item.name, item.status) for item in result.knowledge_coordinates] == [("导数", "learning")]
    assert [(item.name, item.error_count, item.severity) for item in result.cognitive_blindspots] == [("导数", 0, "medium")]
    assert result.drive_intent == rule_result.drive_intent
    assert result.discipline_badge.subject == "course-1"
    assert result.discipline_badge.level == "advanced"
    assert result.discipline_badge.streak_days == rule_result.discipline_badge.streak_days
```

- [ ] **Step 3: Add partial-output fallback test**

Append:

```python
def test_generate_profile_with_llm_fills_missing_fields_from_rule_result() -> None:
    import json as _json
    from agent_service.agents.profile import generate_profile_with_llm

    request = _build_request()
    rule_result = generate_profile_data(request)
    provider = FakeChatProvider(output=_json.dumps({
        "guidance_level_suggestion": {
            "reason": "只增强理由，其余字段沿用规则结果。",
        },
    }))

    result = asyncio.run(generate_profile_with_llm(request, rule_result, provider))

    assert result is not None
    assert result.guidance_level_suggestion.reason == "只增强理由，其余字段沿用规则结果。"
    assert result.guidance_level_suggestion.recommended == rule_result.guidance_level_suggestion.recommended
    assert result.modal_preference == rule_result.modal_preference
    assert result.knowledge_coordinates == rule_result.knowledge_coordinates
    assert result.cognitive_blindspots == rule_result.cognitive_blindspots
    assert result.drive_intent == rule_result.drive_intent
    assert result.discipline_badge == rule_result.discipline_badge
```

- [ ] **Step 4: Run targeted tests and verify new tests fail**

Run:

```bash
./.venv/bin/pytest tests/test_profile_agent.py -v
```

Expected: at least the new full enrichment and invalid-field tests fail because `_enrich_profile_result()` only updates `guidance_level_suggestion.reason`.

---

### Task 2: Strengthen The Profile Prompt

**Files:**
- Modify: `prompts/profile.py`

- [ ] **Step 1: Replace `build_profile_system_prompt()`**

Use this implementation:

```python
def build_profile_system_prompt() -> str:
    return (
        "你是 EDUagent 的学习画像分析助手。你需要根据用户练习历史、资源使用、近期学习强度和系统规则画像，"
        "生成完整 ProfileData JSON 对象。\n\n"
        "输出字段必须完整：\n"
        "- modal_preference: {video_animation, chart_logic, text_analysis, code_practice, formula_derivation}，每项 0-100\n"
        "- guidance_level_suggestion: {recommended, reason}，recommended 只能是 L1/L2/L3\n"
        "- knowledge_coordinates: [{name, status}]，status 只能是 mastered/learning\n"
        "- cognitive_blindspots: [{name, error_count, severity}]，severity 只能是 high/medium/low\n"
        "- drive_intent: {type, intensity}，type 只能是 exam_sprint/daily_homework/casual，intensity 为 0-100\n"
        "- discipline_badge: {subject, level, streak_days}\n\n"
        "约束：\n"
        "- 不要编造输入中没有出现的章节、知识点或课程 ID\n"
        "- 结构字段可以基于证据修正，但必须与输入数据一致\n"
        "- 分数、强度和偏好值必须在 0-100 范围内\n"
        "- reason 要引用具体章节、正确率、资源使用或学习频率，避免泛泛而谈\n"
        "- 如果证据不足，沿用系统规则画像中的对应字段\n"
        "- 只输出 JSON 对象，不要加 markdown 代码块标记，不要加任何其他文字"
    )
```

- [ ] **Step 2: Enrich `build_profile_user_message()` with compact evidence summaries**

Inside `build_profile_user_message()`, after `parts.append(f"课程ID：{request.course_id}")`, add:

```python
    parts.append("")
    parts.append("画像生成要求：请输出完整 ProfileData JSON。若某字段证据不足，请沿用系统已计算画像。")
```

After the quiz-history loop, add:

```python
    if request.quiz_history:
        scores = [item.score for item in request.quiz_history]
        first = request.quiz_history[0]
        last = request.quiz_history[-1]
        weak = [item for item in request.quiz_history if item.score < 70]
        parts.append(
            f"练习摘要：平均正确率 {sum(scores) / len(scores):.1f}%，"
            f"首次 {first.chapter or '未知'} {first.score}%，"
            f"最近 {last.chapter or '未知'} {last.score}%，"
            f"低于70%的记录 {len(weak)} 条"
        )
    else:
        parts.append("练习摘要：无练习历史")
```

- [ ] **Step 3: Run profile prompt tests**

Run:

```bash
./.venv/bin/pytest tests/test_profile_agent.py -v
```

Expected: prompt-only changes should not make all new enrichment tests pass yet.

---

### Task 3: Implement Guarded Full-Field Enrichment

**Files:**
- Modify: `agents/profile.py`

- [ ] **Step 1: Add constants near `_MARKDOWN_FENCE_PATTERN`**

Add:

```python
_VALID_GUIDANCE_LEVELS = {"L1", "L2", "L3"}
_VALID_KNOWLEDGE_STATUSES = {"mastered", "learning"}
_VALID_BLINDSPOT_SEVERITIES = {"high", "medium", "low"}
_VALID_DRIVE_INTENTS = {"exam_sprint", "daily_homework", "casual"}
```

- [ ] **Step 2: Pass request into enrichment**

Change:

```python
        return _enrich_profile_result(rule_result, data)
```

to:

```python
        return _enrich_profile_result(request, rule_result, data)
```

Change the function signature:

```python
def _enrich_profile_result(request: ProfileGenerateRequest, rule_result: ProfileData, llm_data: dict) -> ProfileData:
```

- [ ] **Step 3: Replace `_enrich_profile_result()`**

Use:

```python
def _enrich_profile_result(request: ProfileGenerateRequest, rule_result: ProfileData, llm_data: dict) -> ProfileData:
    enriched = rule_result.model_copy(deep=True)
    observed_names = _observed_profile_names(request, rule_result)

    enriched.modal_preference = _coerce_modal_preference(
        llm_data.get("modal_preference"),
        rule_result.modal_preference,
    )
    enriched.guidance_level_suggestion = _coerce_guidance_level(
        llm_data.get("guidance_level_suggestion"),
        rule_result.guidance_level_suggestion,
    )
    enriched.knowledge_coordinates = _coerce_knowledge_coordinates(
        llm_data.get("knowledge_coordinates"),
        rule_result.knowledge_coordinates,
        observed_names,
    )
    enriched.cognitive_blindspots = _coerce_cognitive_blindspots(
        llm_data.get("cognitive_blindspots"),
        rule_result.cognitive_blindspots,
        observed_names,
    )
    enriched.drive_intent = _coerce_drive_intent(
        llm_data.get("drive_intent"),
        rule_result.drive_intent,
    )
    enriched.discipline_badge = _coerce_discipline_badge(
        llm_data.get("discipline_badge"),
        rule_result.discipline_badge,
        request.course_id,
    )
    return enriched
```

- [ ] **Step 4: Add coercion helpers below `_extract_llm_reason()`**

Add:

```python
def _coerce_modal_preference(raw, fallback: ModalPreference | None) -> ModalPreference | None:
    if not isinstance(raw, dict):
        return fallback
    base = fallback or ModalPreference()
    return ModalPreference(
        video_animation=_coerce_score(raw.get("video_animation"), base.video_animation),
        chart_logic=_coerce_score(raw.get("chart_logic"), base.chart_logic),
        text_analysis=_coerce_score(raw.get("text_analysis"), base.text_analysis),
        code_practice=_coerce_score(raw.get("code_practice"), base.code_practice),
        formula_derivation=_coerce_score(raw.get("formula_derivation"), base.formula_derivation),
    )


def _coerce_guidance_level(raw, fallback: GuidanceLevelSuggestion | None) -> GuidanceLevelSuggestion | None:
    if not isinstance(raw, dict):
        return fallback
    base = fallback or GuidanceLevelSuggestion()
    recommended = raw.get("recommended")
    if recommended not in _VALID_GUIDANCE_LEVELS:
        recommended = base.recommended
    reason = raw.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        reason = base.reason
    return GuidanceLevelSuggestion(recommended=recommended, reason=reason)


def _coerce_knowledge_coordinates(raw, fallback: list[KnowledgeCoordinate], observed_names: set[str]) -> list[KnowledgeCoordinate]:
    if not isinstance(raw, list):
        return fallback
    result: list[KnowledgeCoordinate] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        status = item.get("status")
        if not isinstance(name, str) or name not in observed_names or name in seen:
            continue
        if status not in _VALID_KNOWLEDGE_STATUSES:
            continue
        result.append(KnowledgeCoordinate(name=name, status=status))
        seen.add(name)
    return result or fallback


def _coerce_cognitive_blindspots(raw, fallback: list[CognitiveBlindspot], observed_names: set[str]) -> list[CognitiveBlindspot]:
    if not isinstance(raw, list):
        return fallback
    result: list[CognitiveBlindspot] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str) or name not in observed_names or name in seen:
            continue
        severity = item.get("severity")
        if severity not in _VALID_BLINDSPOT_SEVERITIES:
            severity = "medium"
        result.append(CognitiveBlindspot(
            name=name,
            error_count=_coerce_non_negative_int(item.get("error_count"), 0),
            severity=severity,
        ))
        seen.add(name)
    return result or fallback


def _coerce_drive_intent(raw, fallback: DriveIntent | None) -> DriveIntent | None:
    if not isinstance(raw, dict):
        return fallback
    intent_type = raw.get("type")
    if intent_type not in _VALID_DRIVE_INTENTS:
        return fallback
    return DriveIntent(
        type=intent_type,
        intensity=_coerce_score(raw.get("intensity"), fallback.intensity if fallback else None),
    )


def _coerce_discipline_badge(raw, fallback: DisciplineBadge | None, course_id: str) -> DisciplineBadge | None:
    if not isinstance(raw, dict):
        return fallback
    base = fallback or DisciplineBadge(subject=course_id, level=None, streak_days=0)
    level = raw.get("level")
    if not isinstance(level, str) or not level.strip():
        level = base.level
    return DisciplineBadge(
        subject=course_id,
        level=level,
        streak_days=_coerce_non_negative_int(raw.get("streak_days"), base.streak_days or 0),
    )


def _observed_profile_names(request: ProfileGenerateRequest, rule_result: ProfileData) -> set[str]:
    names = {item.chapter for item in request.quiz_history if item.chapter}
    names.update(item.name for item in rule_result.knowledge_coordinates)
    names.update(item.name for item in rule_result.cognitive_blindspots)
    return {name for name in names if name}


def _coerce_score(value, fallback: float | None) -> float | None:
    if isinstance(value, int | float):
        return max(0.0, min(100.0, float(value)))
    return fallback


def _coerce_non_negative_int(value, fallback: int) -> int:
    if isinstance(value, int | float):
        return max(0, int(value))
    return fallback
```

- [ ] **Step 5: Run targeted profile tests**

Run:

```bash
./.venv/bin/pytest tests/test_profile_agent.py -v
```

Expected: all profile tests pass.

---

### Task 4: Update Workflow And Verify Contracts

**Files:**
- Modify: `WORKFLOW.md`

- [ ] **Step 1: Update interface progress row**

Change the `profile/generate` row to:

```markdown
| `POST /agent/v1/profile/generate` | LLM full enrichment + 规则版 fallback 已完成 | 降级链：LLM guarded full ProfileData enrichment → 规则版；LLM 输出经 schema/枚举/范围/观测名称保护后合并 |
```

- [ ] **Step 2: Update recent verification**

Update the latest test count after running tests. Expected commands:

```bash
./.venv/bin/pytest tests/test_profile_agent.py -v
./.venv/bin/pytest tests/test_openapi_alignment.py -v
./.venv/bin/pytest -q
```

- [ ] **Step 3: Run OpenAPI alignment**

Run:

```bash
./.venv/bin/pytest tests/test_openapi_alignment.py -v
```

Expected: `15 passed`.

- [ ] **Step 4: Run full suite**

Run:

```bash
./.venv/bin/pytest -q
```

Expected: all tests pass; count should be at least the current `218 passed`.

- [ ] **Step 5: Commit**

Run:

```bash
git add prompts/profile.py agents/profile.py tests/test_profile_agent.py WORKFLOW.md
git commit -m "feat(agent): enable guarded full profile LLM enrichment"
```

---

## Self-Review

- Spec coverage: This plan upgrades the remaining `profile/generate` gap from reason-only enrichment to guarded full `ProfileData` enrichment without changing API schema.
- Placeholder scan: No TBD/TODO placeholders remain; code snippets are concrete.
- Type consistency: Function signatures use existing `ProfileGenerateRequest`, `ProfileData`, and field classes from `schemas/profile.py`; no schema additions are required.
- Scope check: Four implementation files, within the AGENTS.md five-file limit. The plan file itself is not part of runtime implementation.
