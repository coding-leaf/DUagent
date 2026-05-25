# resources/generate LLM 接入

**Date**: 2026-05-26
**Status**: draft

## Constraints

1. **暂不接 Qdrant/RAG**。本轮 LLM 仅使用请求中的 `course_id`/`chapter`/`knowledge_point` 元数据生成课程级资料。接口规范要求从 course_knowledge 检索课程资料，但 Qdrant local 模式存在已知并发限制，RAG 接入推迟到 Qdrant server 改造后。Spec 在此明确边界。

2. **v1 仅处理四类资源**：`document` / `mindmap` / `reading` / `code`。`video` 是预留类型，v1 默认不生成。如果请求包含 `video` 或未知类型，LLM 路径整体 fallback 到规则版骨架（与现有行为一致——规则版也会为未知类型生成占位内容）。

3. **Webhook payload shape 不变**：`task_id` 原样带回，`content` 始终为字符串（即使 mindmap/code 内部有结构也序列化），不生成个性化题目（题目归 assessment/generate-questions）。

Replace placeholder resource content ("规则版资源占位内容") with LLM-generated educational content for each resource type (document, mindmap, reading, code). No API contract changes; webhook payload shape unchanged.

## Architecture

```
POST /resources/generate → 202 Accepted
  → background task: run_resource_generation_task(request)
    → get_ai_providers().chat
    → normalize_resource_types(request) → 校验是否全部属于 v1 四类
      否则整体 fallback 到 skeleton
    → generate_resources_with_llm(request, chat_provider)
        │ 对每个 resource_type 并行调 LLM（asyncio.gather）
        │ 每个 LLM 调用: prompt → complete → JSON parse → coerce
        │ 任一失败 → 整体返回 None
    → None? fallback to build_resource_generation_result(request)  ← 现有骨架
    → webhook callback (completed/failed payload)
```

API 层不变。LLM 路径在 `run_resource_generation_task()` 内部优先尝试。
LLM 仅使用请求元数据（course_id/chapter/knowledge_point），暂不接 Qdrant/RAG。

## File Changes

### New: `prompts/resources.py`

- `build_resource_system_prompt(resource_type: str)` → `str`
- `build_resource_user_message(request, resource_type: str)` → `str`

System prompt 按类型差异化：document（长文 markdown）、mindmap（结构化节点）、reading（拓展阅读）、code（可运行代码）。LLM 输出统一为 JSON object `{title, description, content}`。`type/chapter/knowledge_point/tags` 由 coerce 从请求回填。

### Modify: `agents/resources.py`

**New function**:

```python
async def generate_resources_with_llm(
    request: ResourceGenerateRequest,
    chat_provider,
) -> list[dict] | None:
```

1. `chat_provider is None` → return None
2. `normalize_resource_types(request)` → 如果包含非 v1 四类（`video` 或其他），返回 None（整体 fallback）
3. For each resource type: build prompt → `chat_provider.complete()` → strip fences → `json.loads()` → coerce
4. `asyncio.gather(*tasks)` — 任一失败即返回 None
5. Coerce 回填 `type/chapter/knowledge_point/tags`，LLM 只提供 `title/description/content`。`content` 始终为字符串。

**Modify `run_resource_generation_task()`**: 内部获取 providers，先调 LLM，失败走 `result_builder(request)`（保留现有注入语义）。`result_builder` 抛异常时仍按现有逻辑发 failed webhook payload。webhook retry 逻辑不变。

### Tests

In `tests/test_resources_agent.py`:

1. LLM 生成 2 个资源类型 → completed payload，webhook shape 不变
2. 某资源 LLM 失败 → 整体 fallback skeleton
3. LLM 返回无效 JSON → fallback skeleton
4. `chat_provider is None` → fallback skeleton
5. 请求包含 `video`（非 v1 类型）→ 整体 fallback skeleton
6. 并行生成覆盖所有 requested resource_types

## Dependencies

| Dependency | Required? | Fallback |
|------------|-----------|----------|
| `LLM_PROVIDER` | Optional | `build_resource_generation_result()` skeleton |

## Scope

**In**: `generate_resources_with_llm()`, prompt templates, parallel LLM calls, coerce with field backfill, `run_resource_generation_task()` wiring, unit tests.

**Out**: Real webhook call testing, async worker changes, new resource types.

## Verification

```bash
./.venv/bin/pytest tests/test_resources_agent.py -q
```
