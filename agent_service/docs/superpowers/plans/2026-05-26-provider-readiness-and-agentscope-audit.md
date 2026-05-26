# Provider Readiness And AgentScope Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deploy-time provider readiness check that validates AI/Qdrant configuration safely, then document which EDUagent chains should or should not adopt more AgentScope framework features next.

**Architecture:** Add a new `core/readiness.py` module that reads settings, checks config completeness, attempts provider construction without live model calls by default, and supports explicit live probes through injected providers. Add a CLI under `tools/readiness_check.py` that emits JSON for deployment scripts. Keep API routes, schemas, OpenAPI, and business agents unchanged.

**Tech Stack:** Python stdlib CLI (`argparse`, `json`), existing `core.ai` provider protocols, existing Qdrant store probe pattern, pytest with fakes.

---

## Problem Analysis

The service now has complete business paths, but production startup still lacks a focused readiness command. `GET /health` reports coarse settings state, but deployment needs a command that can answer:

- Are LLM/embedding/reranker settings complete?
- Can configured providers be constructed?
- Can optional live provider calls succeed when explicitly requested?
- Can Qdrant be reached?

The command must not default to real network/model calls because local tests and CI should remain hermetic.

---

## Planned Files

- Create: `core/readiness.py`
  - Owns readiness checks and returns serializable dictionaries.
  - Reads settings and optionally receives injected providers/probe functions for tests.
  - Does not import FastAPI or business agents.

- Create: `tools/readiness_check.py`
  - CLI entrypoint.
  - Default mode: configuration + provider construction only.
  - `--live`: run explicit live probes.
  - Prints JSON and exits `0` if ready, `1` if degraded.

- Create: `tests/test_readiness.py`
  - Unit tests for unconfigured, configured, build failure, non-live behavior, live fake provider success/failure, and Qdrant degraded cases.

- Modify: `WORKFLOW.md`
  - Record readiness tool status and verification commands.

No changes to `api/`, `schemas/`, or `../docs`.

---

## Design

### Readiness Result Shape

`build_readiness_report(live: bool = False, ...) -> dict` returns:

```json
{
  "status": "ready",
  "live": false,
  "checks": {
    "llm": {
      "configured": true,
      "provider_built": true,
      "live_checked": false,
      "ok": true,
      "error": null
    },
    "embedding": {
      "configured": true,
      "provider_built": true,
      "live_checked": false,
      "ok": true,
      "error": null
    },
    "reranker": {
      "configured": false,
      "provider_built": false,
      "live_checked": false,
      "ok": true,
      "error": null
    },
    "qdrant": {
      "configured": true,
      "provider_built": true,
      "live_checked": true,
      "ok": true,
      "error": null
    }
  }
}
```

Status rules:

- `ready`: every configured component builds, and every requested live check passes.
- `degraded`: a configured component cannot build, or requested live check fails.
- Unconfigured optional AI components are `ok: true` with `configured: false`; this matches existing fallback behavior.
- Qdrant is always checked because current health already treats it as service infrastructure.

### Live Probe Behavior

Default mode never calls `complete()`, `embed_texts()`, or `score()`.

`--live` calls:

- LLM: `complete([ChatMessage(role="user", content="ping")])`
- Embedding: `embed_texts(["ping"])`
- Reranker: `score("ping", ["ping document"])`
- Qdrant: existing store/client probe

Tests inject fake providers and fake Qdrant probes so no test performs network I/O.

---

## AgentScope Audit

Current confirmed AgentScope usage:

- `core.ai.AgentScopeChatProvider` wraps AgentScope `OpenAIChatModel` + formatter.
- `core.ai.AgentScopeEmbeddingProvider` wraps AgentScope embedding model.
- `agents/tutoring_react.py` uses AgentScope `ReActAgent`, `Msg`, and `InMemoryMemory`.
- `agents/tutoring_tools.py` uses AgentScope `Toolkit` and `ToolResponse`.
- Course knowledge ingestion has already adopted AgentScope Reader patterns per `WORKFLOW.md`.

Available AgentScope framework areas that are not fully used yet:

- AgentScope structured output instead of prompt-only JSON parsing.
- AgentScope `Knowledge` / generic RAG passed directly into `ReActAgent`.
- AgentScope planning / multi-step agent orchestration.
- AgentScope memory compression/session/state.
- AgentScope observability/evaluation hooks.

Recommended chain for next AgentScope adoption:

1. `tutoring/chat`
   - Best fit because it already uses ReActAgent and tools.
   - Next useful upgrade: replace tag/JSON prompt parsing with verified structured output adapter, or pass course `Knowledge` into ReActAgent for generic RAG.
   - Keep existing SSE/result conversion and rule fallback.

2. `resources/generate`
   - Good fit for AgentScope workflow/planning later because it is multi-step and generates four resource types.
   - Do not start here before readiness is in place; async worker + webhook makes debugging harder.

3. `assessment/generate-questions`
   - Good fit for structured output, not necessarily ReActAgent.
   - Current RAG + LLM path is adequate; structured output would reduce parser fragility.

Chains where AgentScope is not the right next move:

- `health` / readiness: deterministic infra checks, no agent needed.
- `assessment/evaluate`: rule scoring must remain deterministic; LLM only enriches diagnosis.
- `profile/generate` and `evaluation/generate`: guarded schema enrichment is clearer as direct provider calls unless structured-output support is verified.
- `memory/compress`: could use AgentScope memory later, but current fact schema is still product-specific; keep existing Qdrant memory boundary for now.

Conclusion: after readiness, the most suitable AgentScope follow-up is `tutoring/chat` structured output or generic `Knowledge` integration, not provider readiness and not deterministic rule endpoints.

---

### Task 1: Add Readiness Tests

**Files:**
- Create: `tests/test_readiness.py`

- [ ] **Step 1: Add fake providers and settings**

Create test fakes:

```python
import asyncio

from agent_service.core import readiness


class FakeChatProvider:
    def __init__(self, should_raise: bool = False) -> None:
        self.calls = []
        self.should_raise = should_raise

    async def complete(self, messages):
        self.calls.append(messages)
        if self.should_raise:
            raise RuntimeError("chat failed")
        return "pong"


class FakeEmbeddingProvider:
    def __init__(self, should_raise: bool = False) -> None:
        self.calls = []
        self.should_raise = should_raise

    async def embed_texts(self, texts):
        self.calls.append(texts)
        if self.should_raise:
            raise RuntimeError("embedding failed")
        return [[0.1, 0.2]]


class FakeRerankerProvider:
    def __init__(self, should_raise: bool = False) -> None:
        self.calls = []
        self.should_raise = should_raise

    async def score(self, query, documents):
        self.calls.append((query, documents))
        if self.should_raise:
            raise RuntimeError("reranker failed")
        return [0.9]


class FakeSettings:
    LLM_PROVIDER = "none"
    LLM_BASE_URL = None
    LLM_API_KEY = None
    LLM_MODEL = None
    EMBEDDING_PROVIDER = "none"
    EMBEDDING_BASE_URL = None
    EMBEDDING_API_KEY = None
    EMBEDDING_MODEL = None
    RERANKER_PROVIDER = "none"
    RERANKER_BASE_URL = None
    RERANKER_API_KEY = None
    RERANKER_MODEL = None
    QDRANT_USER_MEMORY_COLLECTION = "user_memory_v1_1024"
```

- [ ] **Step 2: Test default mode does not call live providers**

```python
def test_readiness_default_mode_does_not_call_live_providers() -> None:
    chat = FakeChatProvider()
    embedding = FakeEmbeddingProvider()
    reranker = FakeRerankerProvider()

    report = asyncio.run(readiness.build_readiness_report(
        settings_obj=FakeSettings(),
        live=False,
        chat_provider=chat,
        embedding_provider=embedding,
        reranker_provider=reranker,
        qdrant_probe=lambda: True,
    ))

    assert report["status"] == "ready"
    assert chat.calls == []
    assert embedding.calls == []
    assert reranker.calls == []
    assert report["checks"]["qdrant"]["ok"] is True
```

- [ ] **Step 3: Test live mode calls fake providers**

```python
def test_readiness_live_mode_calls_fake_providers() -> None:
    configured = type("Configured", (FakeSettings,), {
        "LLM_PROVIDER": "agentscope_openai",
        "LLM_BASE_URL": "http://llm",
        "LLM_API_KEY": "key",
        "LLM_MODEL": "model",
        "EMBEDDING_PROVIDER": "agentscope_openai",
        "EMBEDDING_BASE_URL": "http://embedding",
        "EMBEDDING_API_KEY": "key",
        "EMBEDDING_MODEL": "embedding",
        "RERANKER_PROVIDER": "openai_compatible",
        "RERANKER_BASE_URL": "http://reranker",
        "RERANKER_API_KEY": "key",
        "RERANKER_MODEL": "reranker",
    })()
    chat = FakeChatProvider()
    embedding = FakeEmbeddingProvider()
    reranker = FakeRerankerProvider()

    report = asyncio.run(readiness.build_readiness_report(
        settings_obj=configured,
        live=True,
        chat_provider=chat,
        embedding_provider=embedding,
        reranker_provider=reranker,
        qdrant_probe=lambda: True,
    ))

    assert report["status"] == "ready"
    assert len(chat.calls) == 1
    assert embedding.calls == [["ping"]]
    assert reranker.calls == [("ping", ["ping document"])]
    assert report["checks"]["llm"]["live_checked"] is True
```

- [ ] **Step 4: Test live failure degrades**

```python
def test_readiness_live_failure_marks_degraded() -> None:
    configured = type("Configured", (FakeSettings,), {
        "LLM_PROVIDER": "agentscope_openai",
        "LLM_BASE_URL": "http://llm",
        "LLM_API_KEY": "key",
        "LLM_MODEL": "model",
    })()

    report = asyncio.run(readiness.build_readiness_report(
        settings_obj=configured,
        live=True,
        chat_provider=FakeChatProvider(should_raise=True),
        qdrant_probe=lambda: True,
    ))

    assert report["status"] == "degraded"
    assert report["checks"]["llm"]["ok"] is False
    assert "chat failed" in report["checks"]["llm"]["error"]
```

- [ ] **Step 5: Test qdrant failure degrades**

```python
def test_readiness_qdrant_failure_marks_degraded() -> None:
    def failing_probe():
        raise RuntimeError("qdrant down")

    report = asyncio.run(readiness.build_readiness_report(
        settings_obj=FakeSettings(),
        live=False,
        qdrant_probe=failing_probe,
    ))

    assert report["status"] == "degraded"
    assert report["checks"]["qdrant"]["ok"] is False
    assert "qdrant down" in report["checks"]["qdrant"]["error"]
```

- [ ] **Step 6: Run failing tests**

```bash
./.venv/bin/pytest tests/test_readiness.py -v
```

Expected: fail because `core/readiness.py` does not exist yet.

---

### Task 2: Implement `core/readiness.py`

**Files:**
- Create: `core/readiness.py`

- [ ] **Step 1: Add readiness implementation**

```python
import asyncio
from collections.abc import Callable
from typing import Any

from agent_service.core.ai import ChatMessage, get_ai_providers
from agent_service.core.config import settings
from agent_service.memory.qdrant_store import build_qdrant_store


def _configured(settings_obj, provider_name: str, fields: list[str]) -> bool:
    provider = getattr(settings_obj, provider_name, "none")
    if provider == "none":
        return False
    return all(bool(getattr(settings_obj, field, None)) for field in fields)


def _check_template(configured: bool) -> dict[str, Any]:
    return {
        "configured": configured,
        "provider_built": False,
        "live_checked": False,
        "ok": True,
        "error": None,
    }


async def build_readiness_report(
    *,
    settings_obj=settings,
    live: bool = False,
    chat_provider=None,
    embedding_provider=None,
    reranker_provider=None,
    qdrant_probe: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    """Build a deploy-time readiness report from settings and optional live probes."""
    providers = get_ai_providers(
        embedding_provider=embedding_provider,
        reranker_provider=reranker_provider,
        chat_provider=chat_provider,
    )
    checks = {
        "llm": await _check_llm(settings_obj, providers.chat, live),
        "embedding": await _check_embedding(settings_obj, providers.embedding, live),
        "reranker": await _check_reranker(settings_obj, providers.reranker, live),
        "qdrant": _check_qdrant(settings_obj, qdrant_probe),
    }
    status = "ready" if all(item["ok"] for item in checks.values()) else "degraded"
    return {"status": status, "live": live, "checks": checks}


async def _check_llm(settings_obj, provider, live: bool) -> dict[str, Any]:
    check = _check_template(_configured(settings_obj, "LLM_PROVIDER", ["LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"]))
    check["provider_built"] = provider is not None
    if check["configured"] and provider is None:
        check["ok"] = False
        check["error"] = "LLM is configured but provider could not be built"
        return check
    if live and provider is not None:
        check["live_checked"] = True
        try:
            await provider.complete([ChatMessage(role="user", content="ping")])
        except Exception as exc:
            check["ok"] = False
            check["error"] = str(exc)
    return check


async def _check_embedding(settings_obj, provider, live: bool) -> dict[str, Any]:
    check = _check_template(_configured(settings_obj, "EMBEDDING_PROVIDER", ["EMBEDDING_BASE_URL", "EMBEDDING_API_KEY", "EMBEDDING_MODEL"]))
    check["provider_built"] = provider is not None
    if check["configured"] and provider is None:
        check["ok"] = False
        check["error"] = "Embedding is configured but provider could not be built"
        return check
    if live and provider is not None:
        check["live_checked"] = True
        try:
            await provider.embed_texts(["ping"])
        except Exception as exc:
            check["ok"] = False
            check["error"] = str(exc)
    return check


async def _check_reranker(settings_obj, provider, live: bool) -> dict[str, Any]:
    check = _check_template(_configured(settings_obj, "RERANKER_PROVIDER", ["RERANKER_BASE_URL", "RERANKER_API_KEY", "RERANKER_MODEL"]))
    check["provider_built"] = provider is not None
    if check["configured"] and provider is None:
        check["ok"] = False
        check["error"] = "Reranker is configured but provider could not be built"
        return check
    if live and provider is not None:
        check["live_checked"] = True
        try:
            await provider.score("ping", ["ping document"])
        except Exception as exc:
            check["ok"] = False
            check["error"] = str(exc)
    return check


def _check_qdrant(settings_obj, qdrant_probe: Callable[[], bool] | None) -> dict[str, Any]:
    check = {
        "configured": True,
        "provider_built": True,
        "live_checked": True,
        "ok": True,
        "error": None,
        "collection": getattr(settings_obj, "QDRANT_USER_MEMORY_COLLECTION", None),
    }
    try:
        probe = qdrant_probe or _probe_qdrant
        check["ok"] = bool(probe())
    except Exception as exc:
        check["ok"] = False
        check["error"] = str(exc)
    return check


def _probe_qdrant() -> bool:
    store = build_qdrant_store(settings.QDRANT_USER_MEMORY_COLLECTION)
    store.get_client()
    return True
```

- [ ] **Step 2: Run tests**

```bash
./.venv/bin/pytest tests/test_readiness.py -v
```

Expected: tests pass, or expose provider construction issue to fix locally.

---

### Task 3: Add CLI Tool

**Files:**
- Create: `tools/readiness_check.py`
- Modify: `tests/test_readiness.py`

- [ ] **Step 1: Add CLI**

```python
import argparse
import asyncio
import json

from agent_service.core.readiness import build_readiness_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Agent Service readiness checks.")
    parser.add_argument("--live", action="store_true", help="Run live provider probes.")
    args = parser.parse_args()
    report = asyncio.run(build_readiness_report(live=args.live))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Add import smoke test**

Append to `tests/test_readiness.py`:

```python
def test_readiness_cli_imports() -> None:
    from agent_service.tools import readiness_check

    assert callable(readiness_check.main)
```

- [ ] **Step 3: Run tests**

```bash
./.venv/bin/pytest tests/test_readiness.py -v
```

Expected: pass.

---

### Task 4: Update Workflow, Verify, Commit

**Files:**
- Modify: `WORKFLOW.md`

- [ ] **Step 1: Update status**

Add to `当前已确认能力`:

```markdown
- Provider readiness CLI 已完成：默认只检查配置与 provider 构建；`--live` 才发真实 LLM/Embedding/Reranker 探针。
```

Update `下一步`:

```markdown
- 短期：provider readiness CLI ← **已完成**
- 中期：tutoring/chat AgentScope structured output 或 Generic Knowledge 集成
```

- [ ] **Step 2: Verify**

Run:

```bash
./.venv/bin/pytest tests/test_readiness.py -v
./.venv/bin/pytest tests/test_ai_providers.py tests/test_health.py -v
./.venv/bin/pytest -q
```

- [ ] **Step 3: Commit**

```bash
git add core/readiness.py tools/readiness_check.py tests/test_readiness.py WORKFLOW.md
git commit -m "feat(core): add provider readiness check"
```

---

## Self-Review

- Scope fits AGENTS.md: four runtime/test files, no API/schema/OpenAPI changes.
- Tests are hermetic: live provider calls use injected fakes.
- Default readiness mode does not make network/model calls.
- AgentScope audit does not propose using AgentScope for deterministic infra checks.
