# Agent Service Apifox Real AI Debug Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Apifox testing reflect the real AI/Agent execution path instead of silently falling back because of config, Qdrant local locking, fragile LLM JSON parsing, invalid Qdrant IDs, or unclear Studio expectations.

**Architecture:** Fix root causes at their boundaries: config loading in `core`, Qdrant local-mode behavior in `memory`, LLM resource parsing in `agents/resources_agents.py`, memory point IDs in the memory write path, and testing/Studio expectations in docs. Keep OpenAPI, schemas, and API routes unchanged unless a test proves a contract mismatch.

**Tech Stack:** FastAPI, Pydantic Settings, AgentScope, Qdrant local/client, pytest, Apifox, Markdown docs.

---

## Current Evidence

- `agent_service/.env` contains working model settings:
  - `LLM_PROVIDER=agentscope_openai`
  - `LLM_MODEL=deepseek-v4-flash`
  - `LLM_BASE_URL=https://api.deepseek.com`
- From `agent_service/`, settings load correctly.
- From repo root, settings fall back to defaults because `core/config.py` uses `env_file=".env"` relative to current working directory.
- Health currently can show:
  - `model_loaded=false`
  - `model_name=""`
- Resources can fall back because `get_ai_providers()` sees `chat=None`.
- Qdrant local mode can fail with:
  - `Storage folder ./qdrant_data is already accessed by another instance of Qdrant client`
- Resources LLM output can fail with:
  - `json.decoder.JSONDecodeError: Invalid control character`
- DeepSeek structured output can warn:
  - `This response_format type is unavailable now`
- Memory compression can log:
  - `Point id ... is not a valid UUID`
- AgentScope Studio visibility is expected only for actual AgentScope Agent paths:
  - visible: `tutoring/chat`, `assessment/generate-questions`
  - not visible as Agent flow: `profile/generate`, `evaluation/generate`, `assessment/evaluate`, `learning-path/generate`, `memory/compress`
  - partial/implementation-dependent: `resources/generate` via `fanout_pipeline`

## File Map

- Modify: `core/config.py`
  - Resolve service-local `.env` by absolute path derived from the package location.
- Modify: `tests/test_core_config.py`
  - Prove settings can load `agent_service/.env` regardless of process cwd.
- Modify: `docs/Agent-Service_本地启动与运维.md`
  - Document cwd-independent `.env` loading and how to verify `model_loaded`.
- Modify: `docs/supplemental/Apifox_Agent_Service_全接口测试指南.md`
  - Add Studio visibility / non-Agent interface table.
- Modify: `agents/resources_agents.py`
  - Harden `_parse_resource_json()` against control characters and common LLM JSON failures.
- Modify: `tests/test_resources_workflow.py`
  - Add regression tests for LLM JSON with embedded newlines/control characters.
- Modify: memory write module after discovery, likely one of:
  - `agents/memory.py`
  - `memory/user_memory_store.py`
  - `memory/vector_store.py`
  - `memory/qdrant_store.py`
- Add or modify: memory tests after discovery, likely:
  - `tests/test_memory*.py`
- Optional docs-only change:
  - `docs/supplemental/Apifox_Agent_Service_全接口测试指南.md`
  - `docs/Agent-Service_本地启动与运维.md`

Do not modify:

- `../docs/20-agent-api/Agent-Service.openapi.json`
- `../docs/20-agent-api/API_Agent内部接口规范.md`
- `schemas/`
- `api/`

## Task 1: Fix Service-Local Env Loading

**Files:**
- Modify: `core/config.py`
- Modify: `tests/test_core_config.py`
- Modify: `docs/Agent-Service_本地启动与运维.md`

- [ ] **Step 1: Write failing config path test**

Append to `tests/test_core_config.py`:

```python
def test_settings_default_env_file_is_service_local() -> None:
    from pathlib import Path

    from agent_service.core.config import _SERVICE_ENV_FILE

    assert _SERVICE_ENV_FILE == Path(__file__).resolve().parents[1] / ".env"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
./.venv/bin/pytest tests/test_core_config.py::test_settings_default_env_file_is_service_local -q
```

Expected:

```text
FAILED ... cannot import name '_SERVICE_ENV_FILE'
```

- [ ] **Step 3: Implement service-local env path**

In `core/config.py`, replace the current top of file with:

```python
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


_SERVICE_ROOT = Path(__file__).resolve().parents[1]
_SERVICE_ENV_FILE = _SERVICE_ROOT / ".env"
```

Then change:

```python
model_config = SettingsConfigDict(env_file=".env", extra="ignore")
```

to:

```python
model_config = SettingsConfigDict(env_file=_SERVICE_ENV_FILE, extra="ignore")
```

- [ ] **Step 4: Run config tests**

Run:

```bash
./.venv/bin/pytest tests/test_core_config.py -q
```

Expected:

```text
6 passed
```

- [ ] **Step 5: Verify from repo root**

Run:

```bash
cd /home/yezisama/workspace/workflow/EDUagent
./.venv/bin/python -c "from agent_service.core.config import settings; print(settings.LLM_PROVIDER, settings.LLM_MODEL)"
```

Expected:

```text
agentscope_openai deepseek-v4-flash
```

- [ ] **Step 6: Update local operations doc**

In `docs/Agent-Service_本地启动与运维.md`, add a short note under the startup/config section:

```markdown
Agent Service 默认读取 `agent_service/.env`，不依赖当前启动目录。若 health 返回 `model_loaded=false` 且 `model_name=""`，先运行：

```bash
./.venv/bin/python -c "from agent_service.core.config import settings; print(settings.LLM_PROVIDER, settings.LLM_MODEL)"
```

期望输出当前 LLM provider 和 model，例如 `agentscope_openai deepseek-v4-flash`。
```

- [ ] **Step 7: Commit**

```bash
git add core/config.py tests/test_core_config.py docs/Agent-Service_本地启动与运维.md
git commit -m "fix(core): load service env independent of cwd"
```

## Task 2: Document and Contain Qdrant Local Lock Behavior

**Files:**
- Modify: `docs/Agent-Service_本地启动与运维.md`
- Modify: `docs/supplemental/Apifox_Agent_Service_全接口测试指南.md`

- [ ] **Step 1: Add Qdrant local lock section to operations doc**

Add this exact section to `docs/Agent-Service_本地启动与运维.md`:

```markdown
### Qdrant local 文件锁

当前 `QDRANT_PATH=./qdrant_data` 使用 Qdrant local 文件模式。该模式不支持多个 Python 进程同时访问同一个目录。

如果看到：

```text
Storage folder ./qdrant_data is already accessed by another instance of Qdrant client
```

处理顺序：

1. 停掉重复的 `uvicorn`、`smoke_all`、`readiness --live`、知识入库脚本。
2. 确保只保留一个 Agent Service 进程访问 `./qdrant_data`。
3. 再重新测试 Apifox。

如果需要并发测试，后续应切换到 Qdrant server 模式，而不是继续使用 local 文件模式。
```

- [ ] **Step 2: Add Apifox warning**

In `docs/supplemental/Apifox_Agent_Service_全接口测试指南.md`, under resources or common failures, add:

```markdown
- Qdrant local lock：如果日志出现 `Storage folder ./qdrant_data is already accessed by another instance`，停止其他正在运行的 Agent Service/smoke/ingest/readiness 进程后重试。该问题不是 Apifox 请求体错误。
```

- [ ] **Step 3: Verify docs contain key phrase**

Run:

```bash
rg -n "Qdrant local|Storage folder ./qdrant_data|QDRANT_PATH" docs/Agent-Service_本地启动与运维.md docs/supplemental/Apifox_Agent_Service_全接口测试指南.md
```

Expected:

```text
docs/Agent-Service_本地启动与运维.md:...
docs/supplemental/Apifox_Agent_Service_全接口测试指南.md:...
```

- [ ] **Step 4: Commit**

```bash
git add docs/Agent-Service_本地启动与运维.md docs/supplemental/Apifox_Agent_Service_全接口测试指南.md
git commit -m "docs(agent): document qdrant local lock behavior"
```

## Task 3: Harden ResourceAgent JSON Parsing

**Files:**
- Modify: `agents/resources_agents.py`
- Modify: `tests/test_resources_workflow.py`

- [ ] **Step 1: Inspect current parser and tests**

Run:

```bash
rg -n "_parse_resource_json|TestPhase2|Invalid control" agents/resources_agents.py tests/test_resources_workflow.py
```

Expected: locate `_parse_resource_json()` and Phase 2 tests.

- [ ] **Step 2: Add failing test for unescaped newlines in content**

In `tests/test_resources_workflow.py`, add a Phase 2 test near existing parser tests:

```python
def test_phase2_parse_resource_json_repairs_unescaped_content_newlines(self):
    from agent_service.agents.resources_agents import _parse_resource_json

    raw = '''{
      "title": "一次函数讲义",
      "description": "测试",
      "content": "第一行
第二行
第三行",
      "tags": ["函数", "一次函数"]
    }'''

    data = _parse_resource_json(raw)

    self.assertEqual(data["title"], "一次函数讲义")
    self.assertIn("第二行", data["content"])
```

- [ ] **Step 3: Run test to verify it fails**

Run:

```bash
./.venv/bin/pytest tests/test_resources_workflow.py -k "parse_resource_json_repairs_unescaped_content_newlines" -q
```

Expected:

```text
FAILED ... JSONDecodeError
```

- [ ] **Step 4: Implement minimal repair path**

In `agents/resources_agents.py`, update `_parse_resource_json()` to follow this order:

```python
def _parse_resource_json(raw: str) -> dict:
    text = _strip_outer_json_fence(raw.strip())
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        repaired = _repair_multiline_json_string_fields(text, fields=("content", "description"))
        data = json.loads(repaired)
    if not isinstance(data, dict):
        raise ValueError("LLM output is not a JSON object")
    return data
```

Add helpers:

```python
def _strip_outer_json_fence(text: str) -> str:
    if text.startswith("```"):
        lines = text.splitlines()
        fence_lines = [idx for idx, line in enumerate(lines) if line.strip().startswith("```")]
        if len(fence_lines) >= 2:
            return "\n".join(lines[fence_lines[0] + 1:fence_lines[-1]]).strip()
    return text


def _repair_multiline_json_string_fields(text: str, fields: tuple[str, ...]) -> str:
    repaired = text
    for field in fields:
        repaired = _escape_raw_newlines_inside_json_field(repaired, field)
    return repaired


def _escape_raw_newlines_inside_json_field(text: str, field: str) -> str:
    marker = f'"{field}"'
    start = text.find(marker)
    if start == -1:
        return text
    colon = text.find(":", start + len(marker))
    if colon == -1:
        return text
    first_quote = text.find('"', colon + 1)
    if first_quote == -1:
        return text
    index = first_quote + 1
    escaped = False
    while index < len(text):
        char = text[index]
        if char == "\\" and not escaped:
            escaped = True
            index += 1
            continue
        if char == '"' and not escaped:
            value = text[first_quote + 1:index]
            safe_value = value.replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")
            return text[:first_quote + 1] + safe_value + text[index:]
        escaped = False
        index += 1
    return text
```

If existing helper names already exist, reuse them instead of duplicating.

- [ ] **Step 5: Run resources workflow tests**

Run:

```bash
./.venv/bin/pytest tests/test_resources_workflow.py -q
```

Expected:

```text
passed
```

- [ ] **Step 6: Commit**

```bash
git add agents/resources_agents.py tests/test_resources_workflow.py
git commit -m "fix(resources): repair multiline llm json content"
```

## Task 4: Fix Memory Qdrant Point IDs

**Files:**
- Discover with `rg`
- Modify memory write module
- Add/modify memory tests

- [ ] **Step 1: Locate point id generation**

Run:

```bash
rg -n "point_id|PointStruct|upsert|uuid|sha|hash|Memory persistence failed" agents memory tests -S
```

Expected: find the function that writes memory facts to Qdrant.

- [ ] **Step 2: Add failing UUID test**

In the relevant memory test file, add:

```python
def test_memory_point_id_is_valid_uuid() -> None:
    import uuid

    from agent_service.memory.user_memory_store import build_memory_point_id

    point_id = build_memory_point_id("user_001", "conv_001", "blind_spot", "栈和队列")

    uuid.UUID(point_id)
    assert point_id == build_memory_point_id("user_001", "conv_001", "blind_spot", "栈和队列")
```

If `user_memory_store.py` does not exist, put `build_memory_point_id()` in the module that currently generates the invalid hash point id.

- [ ] **Step 3: Run failing test**

Run the narrow memory test:

```bash
./.venv/bin/pytest tests -k "memory_point_id_is_valid_uuid" -q
```

Expected:

```text
FAILED ... cannot import name 'build_memory_point_id'
```

- [ ] **Step 4: Implement deterministic UUIDv5**

In the memory write module, add:

```python
import uuid


_MEMORY_POINT_NAMESPACE = uuid.UUID("b9cf7a5f-0f29-4bd1-9232-6d7ef79bb6c1")


def build_memory_point_id(user_id: str, conversation_id: str, fact_type: str, content: str) -> str:
    raw = f"{user_id}|{conversation_id}|{fact_type}|{content}"
    return str(uuid.uuid5(_MEMORY_POINT_NAMESPACE, raw))
```

Replace the invalid hash id assignment with:

```python
point_id = build_memory_point_id(
    user_id=user_id,
    conversation_id=conversation_id,
    fact_type=fact.fact_type or "",
    content=fact.content or "",
)
```

- [ ] **Step 5: Run memory tests**

Run:

```bash
./.venv/bin/pytest tests -k "memory" -q
```

Expected: all selected memory tests pass.

- [ ] **Step 6: Commit**

```bash
git add <memory-module> <memory-test-file>
git commit -m "fix(memory): use uuid point ids for qdrant"
```

## Task 5: Add Studio Visibility and Real-AI Testing Matrix

**Files:**
- Modify: `docs/supplemental/Apifox_Agent_Service_全接口测试指南.md`

- [ ] **Step 1: Add Studio visibility table**

Add this section near the end of `docs/supplemental/Apifox_Agent_Service_全接口测试指南.md`:

```markdown
## Studio 可见性矩阵

| 接口 | 当前 AI 实现 | AgentScope Studio 预期 |
|------|------|------|
| `tutoring/chat` | `TutorReActAgent` + tools + memory | 应能看到 Agent 流 |
| `assessment/generate-questions` | `QuestionGeneratorReActAgent` + `retrieve_course_knowledge` + `validate_question_format` | 应能看到 `QuestionGenerator` |
| `resources/generate` | Planner + AgentScope `fanout_pipeline` + ResourceAgent adapter + Aggregator | 可能不像 ReAct 聊天流一样完整展示，主要看日志和 webhook |
| `profile/generate` | 规则结果 + LLM structured output 增强 | 不会显示 Agent 流 |
| `evaluation/generate` | 规则表格 + LLM structured output 增强 | 不会显示 Agent 流 |
| `assessment/evaluate` | 规则判分 + LLM 解释增强 | 不会显示 Agent 流 |
| `learning-path/generate` | LLM structured output + 规则 fallback | 不会显示 Agent 流 |
| `memory/compress` | LLM 提取 + 规则 fallback + Qdrant best-effort 写入 | 不会显示 Agent 流 |
```

- [ ] **Step 2: Add real AI evidence checklist**

Add:

```markdown
## 真实 AI 命中证据

仅 HTTP 200 / 202 不能证明真实 AI 路径命中。需要同时检查：

- health: `model_loaded=true` 且 `model_name` 为当前模型。
- 日志出现 `LLM ... succeeded` 或 `ReActAgent ... succeeded`。
- 日志没有 `chat_provider=None`。
- 日志没有关键路径 `falling back`。
- resources webhook body 中 `result.resources[].content` 不是空内容或规则占位内容。
```

- [ ] **Step 3: Verify doc text**

Run:

```bash
rg -n "Studio 可见性矩阵|真实 AI 命中证据|QuestionGenerator|fanout_pipeline|chat_provider=None" docs/supplemental/Apifox_Agent_Service_全接口测试指南.md
```

Expected: all phrases found.

- [ ] **Step 4: Commit**

```bash
git add docs/supplemental/Apifox_Agent_Service_全接口测试指南.md
git commit -m "docs(agent): clarify studio visibility for apifox tests"
```

## Task 6: Final Verification

**Files:**
- No code changes unless previous tasks require follow-up.

- [ ] **Step 1: Run targeted tests**

Run:

```bash
./.venv/bin/pytest tests/test_core_config.py tests/test_resources_workflow.py -q
```

Expected: all pass.

- [ ] **Step 2: Run memory tests**

Run:

```bash
./.venv/bin/pytest tests -k "memory" -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Run OpenAPI alignment if API/schema changed**

This plan should not modify API/schema. If any task accidentally modified `api/`, `schemas/`, or `../docs/20-agent-api`, run:

```bash
./.venv/bin/pytest tests/test_openapi_alignment.py -q
```

Expected: pass.

- [ ] **Step 4: Manual Apifox smoke**

Start service from either repo root or `agent_service/`:

```bash
./.venv/bin/uvicorn agent_service.main:app --host 127.0.0.1 --port 8002
```

Check health:

```text
model_loaded=true
model_name=deepseek-v4-flash
```

Run `resources/generate` with:

```text
webhook_url=https://m1.apifoxmock.com/m1/8182577-7941807-7764192/api/v1/webhooks/agent
```

Expected:

- API returns 202.
- Apifox Mock receives webhook request.
- `Request Body.result.resources` exists.
- Logs show resources workflow or LLM success, not only fallback.

- [ ] **Step 5: Commit workflow/docs status if changed**

If `WORKFLOW.md` is edited during execution, commit it with the relevant task commit. Do not stage unrelated dirty changes.

## Risks and Notes

- Qdrant local lock cannot be fully solved for multi-process access without moving to Qdrant server mode. This plan documents and contains the local-mode limitation; a later plan can migrate to server mode.
- DeepSeek structured output may not support `response_format`. AgentScope already falls back to tool-call based structured output. Do not remove that fallback unless a live test proves a better provider-specific setting.
- Studio visibility is not equivalent to AI usage. Interfaces using plain `chat_provider.complete()` are AI-backed but not AgentScope Agent flows.
- Do not treat HTTP 200/202 alone as proof of real LLM success; check health, logs, and output content.

## Self-Review

- Spec coverage: covers env loading, Qdrant local lock, resources parser failure, memory UUID failure, Studio visibility, and final Apifox verification.
- Placeholder scan: no TODO/TBD placeholders remain.
- Type consistency: uses existing `Settings`, `ResourceGenerateRequest`, `ResourceResult`, and memory point ID concepts; memory module path is explicitly discovery-based because current failing stack does not identify the write function.
