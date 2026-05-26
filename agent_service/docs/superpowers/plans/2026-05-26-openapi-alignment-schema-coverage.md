# OpenAPI Alignment Schema Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand OpenAPI alignment tests so schema drift is caught before backend integration.

**Architecture:** Keep the OpenAPI document unchanged and extend `tests/test_openapi_alignment.py` to assert property and required-field parity for all externally exposed request/response data schemas. Apply only small schema fixes that are directly revealed by those tests.

**Tech Stack:** pytest/unittest, FastAPI generated OpenAPI, Pydantic model JSON schema.

---

## Scope

### Modify

- `tests/test_openapi_alignment.py`
- `schemas/learning_path.py`
- `WORKFLOW.md`

### Conditional Modify

- `schemas/assessment.py` only if the new alignment tests show a concrete OpenAPI mismatch that can be fixed without changing API semantics.

### Do Not Modify

- `../docs/20-agent-api/Agent-Service.openapi.json`
- `api/`
- `agents/`
- backend files

---

## Task 1: Import All Public Schema Models

**Files:**

- Modify: `tests/test_openapi_alignment.py`

- [ ] **Step 1: Add imports**

Replace the current narrow imports with explicit imports for all public schemas:

```python
from agent_service.schemas.assessment import (
    AssessmentEvaluateRequest,
    AssessmentResult,
    QuestionGenerateRequest,
    QuestionGenerateResult,
)
from agent_service.schemas.common import HealthData, ResourceTaskResponse
from agent_service.schemas.evaluation import EvaluationData, EvaluationGenerateRequest
from agent_service.schemas.learning_path import LearningPathData, LearningPathGenerateRequest
from agent_service.schemas.memory import MemoryCompressRequest, MemoryCompressResult
from agent_service.schemas.profile import ProfileData, ProfileGenerateRequest
from agent_service.schemas.resources import ResourceGenerateRequest
from agent_service.schemas.tutoring import TutoringChatRequest
```

- [ ] **Step 2: Run existing tests to verify imports**

Run:

```bash
./.venv/bin/pytest tests/test_openapi_alignment.py -q
```

Expected: existing tests still pass before adding broader assertions.

---

## Task 2: Add Property-Level Tests For Remaining Schemas

**Files:**

- Modify: `tests/test_openapi_alignment.py`

- [ ] **Step 1: Add tests for assessment schemas**

Add:

```python
def test_assessment_evaluate_request_matches_openapi(self) -> None:
    self.assert_schema_properties_match(
        AssessmentEvaluateRequest.model_json_schema(), "AssessmentEvaluateRequest"
    )

def test_assessment_result_matches_openapi(self) -> None:
    self.assert_schema_properties_match(AssessmentResult.model_json_schema(), "AssessmentResult")

def test_question_generate_request_matches_openapi(self) -> None:
    self.assert_schema_properties_match(QuestionGenerateRequest.model_json_schema(), "QuestionGenerateRequest")

def test_question_generate_result_matches_openapi(self) -> None:
    self.assert_schema_properties_match(QuestionGenerateResult.model_json_schema(), "QuestionGenerateResult")
```

- [ ] **Step 2: Add tests for learning path schemas**

Add:

```python
def test_learning_path_generate_request_matches_openapi(self) -> None:
    self.assert_schema_properties_match(
        LearningPathGenerateRequest.model_json_schema(), "LearningPathGenerateRequest"
    )

def test_learning_path_data_matches_openapi(self) -> None:
    self.assert_schema_properties_match(LearningPathData.model_json_schema(), "LearningPathData")
```

- [ ] **Step 3: Add tests for resources and memory schemas**

Add:

```python
def test_resource_generate_request_matches_openapi(self) -> None:
    self.assert_schema_properties_match(ResourceGenerateRequest.model_json_schema(), "ResourceGenerateRequest")

def test_resource_task_response_matches_openapi(self) -> None:
    self.assert_schema_properties_match(ResourceTaskResponse.model_json_schema(), "ResourceTaskResponse")

def test_memory_compress_request_matches_openapi(self) -> None:
    self.assert_schema_properties_match(MemoryCompressRequest.model_json_schema(), "MemoryCompressRequest")

def test_memory_compress_result_matches_openapi(self) -> None:
    self.assert_schema_properties_match(MemoryCompressResult.model_json_schema(), "MemoryCompressResult")
```

- [ ] **Step 4: Run expanded alignment tests**

Run:

```bash
./.venv/bin/pytest tests/test_openapi_alignment.py -q
```

Expected: either PASS or fail with exact schema names that need local schema correction.

---

## Task 3: Add Alias Population Guard For Learning Path Edges

**Files:**

- Modify: `schemas/learning_path.py`

- [ ] **Step 1: Import `ConfigDict`**

Replace:

```python
from pydantic import BaseModel, Field
```

with:

```python
from pydantic import BaseModel, ConfigDict, Field
```

- [ ] **Step 2: Allow Python-side `from_` construction**

Update both edge models:

```python
class KnowledgeGraphEdge(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str | None = Field(None, alias="from", description="前置节点 ID")
    to: str | None = Field(None, description="后置节点 ID")
```

```python
class LearningPathEdge(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str | None = Field(None, alias="from", description="前置节点 ID")
    to: str | None = Field(None, description="后置节点 ID")
```

- [ ] **Step 3: Add or update schema contract test**

If `tests/test_schema_contracts.py` has learning path edge tests, add:

```python
def test_learning_path_edge_accepts_python_field_name() -> None:
    edge = LearningPathEdge(from_="a", to="b")
    assert edge.from_ == "a"
    assert edge.model_dump(by_alias=True) == {"from": "a", "to": "b"}
```

If the file does not import `LearningPathEdge`, add:

```python
from agent_service.schemas.learning_path import LearningPathEdge
```

- [ ] **Step 4: Run schema tests**

Run:

```bash
./.venv/bin/pytest tests/test_openapi_alignment.py tests/test_schema_contracts.py -q
```

Expected: PASS.

---

## Task 4: Update Workflow And Commit

**Files:**

- Modify: `WORKFLOW.md`

- [ ] **Step 1: Update current confirmed capability**

Add:

```markdown
- OpenAPI 对齐测试已扩展到主要 request/response schema，`HealthData`、assessment、learning-path、resources、memory 等 schema 漂移可被测试捕获。
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
git add tests/test_openapi_alignment.py tests/test_schema_contracts.py schemas/learning_path.py WORKFLOW.md
git commit -m "test(agent): expand OpenAPI schema alignment coverage"
```

If `tests/test_schema_contracts.py` was not modified, omit it from `git add`.

---

## Acceptance Criteria

- OpenAPI alignment tests cover all externally exposed core request/result schemas.
- `HealthData` drift is guarded by tests from Plan 1 and remains passing.
- Learning path edge models accept both OpenAPI alias input and Python `from_` construction.
- No OpenAPI document changes.
- `./.venv/bin/pytest -q` passes.
