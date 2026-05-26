# Tutoring Provider Boundary And Backend Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move tutoring/assessment orchestration out of API internals and prepare agent_service for backend contract testing.

**Architecture:** Keep FastAPI routes thin: routes receive Pydantic requests, call public agent functions, and wrap HTTP/SSE responses. Agent modules own provider lookup, retrieval context construction, ReAct/structured fallback, and event assembly. Backend work in this plan is read-only discovery and a follow-up test plan, not backend code changes.

**Tech Stack:** FastAPI `StreamingResponse`, async generators, existing AgentScope adapters, pytest.

---

## Scope

The user explicitly allowed modifying more than 5 files. Keep this plan focused on API boundary cleanup and backend readiness only.

### Modify

- `api/v1/tutoring.py`
- `agents/tutoring.py`
- `agents/tutoring_react_flow.py`
- `api/v1/assessment.py`
- `agents/assessment.py`
- `tests/test_tutoring_agent.py`
- `tests/test_tutoring_react_flow.py`
- `tests/test_assessment_agent.py`
- `WORKFLOW.md`

### Create

- `docs/superpowers/plans/2026-05-26-backend-agent-service-contract-check.md` as a follow-up plan after read-only backend inspection.

### Do Not Modify

- `../backend` in this plan
- `../docs`
- OpenAPI specs
- prompt files

---

## Task 1: Move Tutoring SSE Event Assembly Into Agents Layer

**Files:**

- Modify: `agents/tutoring.py`
- Modify: `api/v1/tutoring.py`

- [ ] **Step 1: Add a public event builder in `agents/tutoring.py`**

Add imports if missing:

```python
from agent_service.schemas.tutoring import DoneEvent, KnowledgePointsEvent, SuggestionEvent, TutoringChatRequest
```

Add this function:

```python
def build_tutoring_runtime_events(request: TutoringChatRequest, result) -> list[KnowledgePointsEvent | SuggestionEvent | DoneEvent]:
    """把辅导生成结果转换为 SSE 事件实体；输入请求和生成结果，输出 API 可序列化事件列表。"""
    return [
        KnowledgePointsEvent(knowledge_points=result.knowledge_points),
        SuggestionEvent(
            suggestion=result.suggestion_text,
            suggested_exercises=result.suggested_exercises,
        ),
        DoneEvent(
            message_id=f"msg_{request.user_id}_{request.conversation_id or 'new'}",
            knowledge_points_used=result.knowledge_points,
            suggested_exercises=result.suggested_exercises,
        ),
    ]
```

- [ ] **Step 2: Update `api/v1/tutoring.py` to call the public builder**

Replace `_build_runtime_events(...)` usage with:

```python
for event in build_tutoring_runtime_events(request, runtime_result):
    yield f"data: {json.dumps(event.model_dump(), ensure_ascii=False)}\n\n"
```

Remove the local `_build_runtime_events` function and related event schema imports from `api/v1/tutoring.py`.

- [ ] **Step 3: Run tutoring tests**

Run:

```bash
./.venv/bin/pytest tests/test_tutoring_agent.py -q
```

Expected: PASS.

---

## Task 2: Move Tutoring Retrieval And Model Orchestration Into Agents Layer

**Files:**

- Modify: `agents/tutoring.py`
- Modify: `api/v1/tutoring.py`
- Modify: `tests/test_tutoring_agent.py`
- Modify: `tests/test_tutoring_react_flow.py`

- [ ] **Step 1: Add public runtime builder in `agents/tutoring.py`**

Add imports if missing:

```python
from agent_service.agents.tutoring_react_flow import generate_tutoring_react_response
from agent_service.core.ai import get_ai_providers
from agent_service.core.logging import get_logger
from agent_service.memory.tutoring_retrieval import (
    TutoringRetrievalContext,
    build_tutoring_retrieval_context,
    build_tutoring_retrieval_context_with_ai,
)
from agent_service.memory.vector_store import QdrantVectorStore
```

Add:

```python
logger = get_logger(__name__)
```

Add:

```python
async def build_tutoring_runtime_result(request: TutoringChatRequest):
    """执行 tutoring/chat 运行时编排；输入请求，输出包含检索/模型增强后的生成结果。"""
    providers = get_ai_providers()
    embedding = getattr(providers, "embedding", None)
    vector_store = _build_shared_vector_store(embedding)
    retrieval_context = await _build_runtime_retrieval_context(
        request, providers, vector_store=vector_store
    )
    model_response = await _build_model_response(
        request, retrieval_context, providers, vector_store=vector_store
    )
    return build_tutoring_generation_result(
        request,
        retrieval_context=retrieval_context,
        model_response=model_response,
    )
```

Move the existing helper bodies from `api/v1/tutoring.py` into `agents/tutoring.py`:

```python
async def _build_runtime_retrieval_context(request, providers, *, vector_store=None) -> TutoringRetrievalContext:
    reranker_provider = getattr(providers, "reranker", None)
    try:
        if reranker_provider is None:
            return await build_tutoring_retrieval_context_with_ai(
                request,
                embedding_provider=providers.embedding,
                vector_store=vector_store,
            )
        return await build_tutoring_retrieval_context_with_ai(
            request,
            embedding_provider=providers.embedding,
            reranker_provider=reranker_provider,
            vector_store=vector_store,
        )
    except Exception:
        logger.warning("Tutoring retrieval failed, using fallback context", exc_info=True)
        return build_tutoring_retrieval_context(request)
```

```python
async def _build_model_response(request, retrieval_context, providers, *, vector_store=None) -> TutoringModelResponse | None:
    chat_provider = getattr(providers, "chat", None)
    embedding = getattr(providers, "embedding", None)
    react_response = await generate_tutoring_react_response(
        request,
        retrieval_context,
        chat_provider,
        embedding_provider=embedding,
        vector_store=vector_store,
    )
    if react_response is not None:
        return react_response
    return await generate_tutoring_model_response(request, retrieval_context, chat_provider)
```

```python
def _build_shared_vector_store(embedding_provider) -> QdrantVectorStore | None:
    if embedding_provider is None:
        return None
    try:
        return QdrantVectorStore()
    except Exception:
        logger.warning("Failed to create shared QdrantVectorStore", exc_info=True)
        return None
```

- [ ] **Step 2: Thin `api/v1/tutoring.py`**

Keep only route/SSE formatting logic:

```python
async def tutoring_event_stream(request: TutoringChatRequest) -> AsyncIterator[str]:
    fallback_result = build_tutoring_generation_result(request)
    yield f"data: {json.dumps({'type': 'chunk', 'content': fallback_result.chunk_text}, ensure_ascii=False)}\n\n"

    runtime_result = await build_tutoring_runtime_result(request)
    if runtime_result.chunk_text != fallback_result.chunk_text:
        yield f"data: {json.dumps({'type': 'chunk', 'content': runtime_result.chunk_text}, ensure_ascii=False)}\n\n"

    for event in build_tutoring_runtime_events(request, runtime_result):
        yield f"data: {json.dumps(event.model_dump(), ensure_ascii=False)}\n\n"
```

The route remains:

```python
@router.post("/chat", ...)
async def tutoring_chat(request: TutoringChatRequest) -> StreamingResponse:
    return StreamingResponse(tutoring_event_stream(request), media_type="text/event-stream")
```

- [ ] **Step 3: Run focused tutoring tests**

Run:

```bash
./.venv/bin/pytest tests/test_tutoring_agent.py tests/test_tutoring_react_flow.py tests/test_tutoring_tools.py -q
```

Expected: PASS.

---

## Task 3: Remove Assessment API Private Function Import

**Files:**

- Modify: `agents/assessment.py`
- Modify: `api/v1/assessment.py`
- Modify: `tests/test_assessment_agent.py`

- [ ] **Step 1: Add public orchestration function in `agents/assessment.py`**

Add:

```python
async def generate_questions_with_providers(request: QuestionGenerateRequest, providers) -> list[GeneratedQuestion]:
    """生成题目主编排；输入出题请求和 provider 容器，输出题目列表。"""
    course_knowledge_context = await _build_question_generation_knowledge_context(
        request,
        getattr(providers, "embedding", None),
    )
    questions = await generate_questions_with_llm(
        request,
        getattr(providers, "chat", None),
        course_knowledge_context=course_knowledge_context,
    )
    if questions is None:
        return generate_questions_data(request).questions
    return questions
```

Use the exact existing `GeneratedQuestion` type import already present in the module. If it is not imported, add it from `agent_service.schemas.assessment`.

- [ ] **Step 2: Thin `api/v1/assessment.py`**

Replace private import:

```python
_build_question_generation_knowledge_context,
generate_questions_data,
generate_questions_with_llm,
```

with:

```python
generate_questions_with_providers,
```

Update the route:

```python
@router.post(
    "/generate-questions",
    response_model=QuestionGenerateResponse,
    tags=["Assessment"],
    summary="生成题目",
)
async def generate_questions(request: QuestionGenerateRequest) -> QuestionGenerateResponse:
    providers = get_ai_providers()
    questions = await generate_questions_with_providers(request, providers)
    return QuestionGenerateResponse(
        code=200,
        message="success",
        data=QuestionGenerateResult(questions=questions),
    )
```

- [ ] **Step 3: Update tests that patch private API-layer function**

Find:

```bash
rg "_build_question_generation_knowledge_context|api.v1.assessment" tests/test_assessment_agent.py
```

Replace API-layer private patches with agent-layer behavior tests. A minimal route-level test can patch the public orchestration function:

```python
with patch("agent_service.api.v1.assessment.generate_questions_with_providers", _fake_generate):
    ...
```

- [ ] **Step 4: Run assessment tests**

Run:

```bash
./.venv/bin/pytest tests/test_assessment_agent.py -q
```

Expected: PASS.

---

## Task 4: Backend Read-Only Contract Discovery Plan

**Files:**

- Create: `docs/superpowers/plans/2026-05-26-backend-agent-service-contract-check.md`

- [ ] **Step 1: Write follow-up backend plan**

Create a plan with this goal:

```markdown
# Backend Agent Service Contract Check Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Read backend Agent Service call sites and compare them with `Agent-Service.openapi.json` before modifying backend code.

**Architecture:** This is a read-only discovery pass over `../backend`. It identifies client classes, endpoint paths, payload fields, SSE handling, webhook handling, timeouts, and tests. It produces a concise gap report and a separate implementation plan if backend changes are needed.

**Tech Stack:** ripgrep, existing backend test runner discovered from backend package files.
```

Include read-only commands:

```bash
rg "agent_service|Agent Service|/agent/v1|tutoring/chat|generate-questions|memory/compress|resources/generate" ../backend
find ../backend -maxdepth 2 -type f \( -name "package.json" -o -name "pyproject.toml" -o -name "pom.xml" -o -name "build.gradle" \)
```

Include acceptance criteria:

```markdown
- Every backend call site to `/agent/v1/*` is listed.
- Request/response field mismatches are listed with file paths.
- SSE and webhook handling are explicitly checked.
- No backend files are modified in the discovery pass.
```

- [ ] **Step 2: Commit this follow-up plan with the boundary cleanup**

This plan file should be included in the final commit for this boundary-readiness pass.

---

## Task 5: Update Workflow And Commit

**Files:**

- Modify: `WORKFLOW.md`

- [ ] **Step 1: Update current confirmed capability**

Add:

```markdown
- API 层边界继续收束：tutoring runtime 编排下沉到 agents 层，assessment 出题不再从 API 层导入 agents 私有函数；backend 联调前置只读契约检查计划已准备。
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
git add api/v1/tutoring.py agents/tutoring.py agents/tutoring_react_flow.py api/v1/assessment.py agents/assessment.py tests/test_tutoring_agent.py tests/test_tutoring_react_flow.py tests/test_tutoring_tools.py tests/test_assessment_agent.py WORKFLOW.md docs/superpowers/plans/2026-05-26-backend-agent-service-contract-check.md
git commit -m "refactor(agent): move tutoring and assessment orchestration out of api"
```

Omit any unchanged file from `git add`.

---

## Acceptance Criteria

- `api/v1/tutoring.py` contains route/SSE formatting only and no Qdrant/vector store/retrieval provider orchestration.
- `api/v1/assessment.py` no longer imports `_build_question_generation_knowledge_context`.
- Existing tutoring and assessment fallback chains remain behaviorally unchanged.
- A read-only backend contract check plan exists.
- `./.venv/bin/pytest -q` passes.
