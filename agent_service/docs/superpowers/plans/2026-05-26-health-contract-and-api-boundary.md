# Health Contract And API Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `GET /agent/v1/health` strictly match OpenAPI and move health probing logic out of the API layer.

**Architecture:** Keep `api/v1/health.py` as a thin FastAPI route that wraps `agents.health.build_health_data()`. The new `agents/health.py` owns Qdrant probing, uptime calculation, status selection, and logging. `HealthData` follows the current OpenAPI contract and does not expose readiness-only provider fields.

**Tech Stack:** FastAPI, Pydantic, pytest, existing `agent_service.core.config.settings`, existing Qdrant store builder.

---

## Scope

### Modify

- `schemas/common.py`
- `api/v1/health.py`
- `tests/test_health.py`
- `tests/test_openapi_alignment.py`
- `WORKFLOW.md`

### Create

- `agents/health.py`

### Do Not Modify

- `../docs/20-agent-api/Agent-Service.openapi.json`
- `api/v1/tutoring.py`
- backend files

---

## Contract Decision

Use the current OpenAPI contract as source of truth. `HealthData` contains only:

```python
status
qdrant_connected
model_loaded
model_name
uptime_seconds
```

Remove these readiness-only fields from the health response:

```python
llm_configured
embedding_configured
reranker_configured
qdrant_collection
```

Detailed provider readiness remains in:

```bash
./.venv/bin/python -m agent_service.tools.readiness_check
```

---

## Task 1: Add A Failing Contract Test For HealthData

**Files:**

- Modify: `tests/test_openapi_alignment.py`

- [ ] **Step 1: Import `HealthData`**

Add this import near the other schema imports:

```python
from agent_service.schemas.common import HealthData
```

- [ ] **Step 2: Add the property-level assertion**

Add this test near the existing wrapper test:

```python
def test_health_data_matches_openapi(self) -> None:
    self.assert_schema_properties_match(HealthData.model_json_schema(), "HealthData")
```

- [ ] **Step 3: Run the failing test**

Run:

```bash
./.venv/bin/pytest tests/test_openapi_alignment.py::OpenAPIAlignmentTests::test_health_data_matches_openapi -q
```

Expected: FAIL because the app schema exposes `llm_configured`, `embedding_configured`, `reranker_configured`, and `qdrant_collection`.

---

## Task 2: Align `HealthData` With OpenAPI

**Files:**

- Modify: `schemas/common.py`

- [ ] **Step 1: Remove readiness-only fields**

Replace `HealthData` with:

```python
class HealthData(BaseModel):
    status: HealthStatus = Field(..., description="healthy / degraded / unhealthy")
    qdrant_connected: bool = Field(..., description="Qdrant 向量库连接状态")
    model_loaded: bool = Field(..., description="大模型加载状态")
    model_name: str = Field(..., description="当前加载的模型名称")
    uptime_seconds: int = Field(..., ge=0, description="服务运行时长（秒）")
```

- [ ] **Step 2: Run the contract test again**

Run:

```bash
./.venv/bin/pytest tests/test_openapi_alignment.py::OpenAPIAlignmentTests::test_health_data_matches_openapi -q
```

Expected: PASS.

---

## Task 3: Move Health Logic Into `agents/health.py`

**Files:**

- Create: `agents/health.py`
- Modify: `api/v1/health.py`

- [ ] **Step 1: Create `agents/health.py`**

Add:

```python
import time
from collections.abc import Callable

from agent_service.core.config import settings
from agent_service.core.logging import get_logger
from agent_service.memory.qdrant_store import build_qdrant_store


STARTED_AT = time.monotonic()
logger = get_logger(__name__)


def build_health_data(
    qdrant_probe: Callable[[], bool] | None = None,
    monotonic_now: Callable[[], float] = time.monotonic,
    started_at: float = STARTED_AT,
) -> dict:
    """构建 health 响应 data；输入探针函数，输出与 OpenAPI HealthData 对齐的字典。"""
    probe = qdrant_probe or _probe_qdrant
    try:
        qdrant_connected = bool(probe())
    except Exception as exc:
        logger.warning("Health probe failed: %s", exc)
        qdrant_connected = False

    model_loaded = settings.LLM_PROVIDER != "none" and bool(settings.LLM_MODEL)
    model_name = settings.LLM_MODEL if model_loaded else ""

    return {
        "status": "healthy" if qdrant_connected else "degraded",
        "qdrant_connected": qdrant_connected,
        "model_loaded": model_loaded,
        "model_name": model_name,
        "uptime_seconds": max(0, int(monotonic_now() - started_at)),
    }


def _probe_qdrant() -> bool:
    store = build_qdrant_store(settings.QDRANT_USER_MEMORY_COLLECTION)
    store.get_client()
    return True
```

- [ ] **Step 2: Thin `api/v1/health.py`**

Replace imports and remove local helper functions so the file is:

```python
from fastapi import APIRouter

from agent_service.agents.health import build_health_data
from agent_service.schemas.common import HealthResponse


router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint for the Agent Service.
    """
    return HealthResponse(
        code=200,
        message="success",
        data=build_health_data(),
    )
```

- [ ] **Step 3: Run health tests to expose import failures**

Run:

```bash
./.venv/bin/pytest tests/test_health.py -q
```

Expected: FAIL until imports in `tests/test_health.py` are updated.

---

## Task 4: Update Health Tests

**Files:**

- Modify: `tests/test_health.py`

- [ ] **Step 1: Change imports**

Replace:

```python
from agent_service.api.v1.health import build_health_data, health_check
```

with:

```python
from agent_service.agents.health import build_health_data
from agent_service.api.v1.health import health_check
```

- [ ] **Step 2: Update expected health payloads**

Ensure tests assert only the OpenAPI fields:

```python
assert data == {
    "status": "healthy",
    "qdrant_connected": True,
    "model_loaded": True,
    "model_name": "deepseek-chat",
    "uptime_seconds": 25,
}
```

When model is not loaded, assert:

```python
assert data["model_name"] == ""
```

- [ ] **Step 3: Run focused tests**

Run:

```bash
./.venv/bin/pytest tests/test_health.py tests/test_openapi_alignment.py -q
```

Expected: PASS.

---

## Task 5: Update Workflow And Commit

**Files:**

- Modify: `WORKFLOW.md`

- [ ] **Step 1: Update current confirmed capability**

Add:

```markdown
- Health 契约与 OpenAPI 对齐：readiness-only 字段不再出现在 `/agent/v1/health` 响应中，health 探针逻辑已下沉到 `agents/health.py`。
```

- [ ] **Step 2: Run full tests**

Run:

```bash
./.venv/bin/pytest -q
```

Expected: `234 passed` or higher.

- [ ] **Step 3: Commit**

Run:

```bash
git add schemas/common.py agents/health.py api/v1/health.py tests/test_health.py tests/test_openapi_alignment.py WORKFLOW.md
git commit -m "fix(agent): align health contract and move probe logic"
```

---

## Acceptance Criteria

- `GET /agent/v1/health` response data has exactly the OpenAPI `HealthData` fields.
- Health probing logic lives in `agents/health.py`, not `api/v1/health.py`.
- `tests/test_openapi_alignment.py` catches future `HealthData` property drift.
- `./.venv/bin/pytest -q` passes.
