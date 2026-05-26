# Backend Agent Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect the updated FastAPI backend to `agent_service` through the documented `/agent/v1/*` contract, replacing selected mock AI paths with real Agent Service calls while preserving backend SQL ownership.

**Architecture:** Backend owns users, courses, SQL persistence, task records, and public client API responses. Agent Service owns LLM/RAG/AgentScope behavior and returns structured results or SSE events. Integration should add one backend Agent client boundary first, then migrate one endpoint at a time from mock completion to Agent-backed behavior.

**Tech Stack:** FastAPI, SQLAlchemy async, httpx, sse-starlette, Pydantic, existing backend `AsyncTask`, existing `agent_service` OpenAPI contract, pytest or backend `test_api.py` smoke runner.

---

## Current Backend Analysis

### Confirmed Backend State

- `../backend/app/core/config.py` already exposes `AGENT_SERVICE_URL = "http://localhost:8002"`.
- `../backend/requirements.txt` includes `httpx` through current test usage and can support an async Agent client.
- `../backend/app/models/others.py` has durable tables for:
  - `AsyncTask`
  - `UserProfile`
  - `Evaluation`
  - `LearningPath`
  - `Resource`
  - `AgentLog`
- `../backend/app/api/v1/webhooks.py` has `POST /api/v1/webhooks/agent`, but currently it only updates `AsyncTask`; it does not persist `result.resources` into `resources`.
- `../backend/app/api/v1/tutoring.py` already saves user and assistant message rows and returns SSE through `EventSourceResponse`, but the streamed content is still local mock text.
- `../backend/app/api/v1/profile.py`, `evaluation.py`, `learning_path.py`, `resources.py`, and `quiz.py` still create mock results locally and mark tasks completed without calling Agent Service.
- `../backend/app/schemas/operations.py` already has request fields close to Agent needs for tutoring, quiz generation, and resource generation.

### Key Gap

There is still no backend service/client layer that calls `/agent/v1/*`. The next work should not modify `agent_service` first; the integration gap is in `../backend`.

### Contract Boundary

Use these Agent Service contracts as source of truth:

- `../docs/20-agent-api/Agent-Service.openapi.json`
- `../docs/20-agent-api/API_Agent内部接口规范.md`

Backend must continue to own SQL writes. Agent Service must not write backend DB.

---

## Recommended Execution Order

### Batch 1: Agent Client + Profile Refresh

Smallest useful vertical integration. Replaces `POST /api/v1/profile/refresh` mock completion with:

1. Backend creates `AsyncTask`.
2. Backend collects minimal SQL-derived input.
3. Backend calls `POST /agent/v1/profile/generate`.
4. Backend validates `data`.
5. Backend upserts `UserProfile`.
6. Backend marks task completed or failed.

Estimated backend files: 4-6.

### Batch 2: Tutoring SSE Proxy

Connect `POST /api/v1/tutoring/chat` to `POST /agent/v1/tutoring/chat`.

1. Backend still creates/validates conversation.
2. Backend saves user message.
3. Backend builds Agent request with user profile, summary placeholder, and recent messages.
4. Backend proxies Agent SSE events to frontend.
5. Backend accumulates chunks and updates assistant message on done.

Estimated backend files: 3-5.

### Batch 3: Async Generation + Webhook Persistence

Connect async workflows:

- `POST /api/v1/resources/generate` -> `/agent/v1/resources/generate`
- `POST /api/v1/quiz/generate` -> `/agent/v1/assessment/generate-questions`
- Optional later: `POST /api/v1/evaluation/refresh`, `POST /api/v1/learning-path/refresh`

This batch needs webhook persistence for `result.resources`.

Estimated backend files: 5-8.

---

## File Map

### Backend Files To Create

- `../backend/app/services/agent_client.py`
  - Single boundary for HTTP calls to Agent Service.
  - Handles base URL, timeout, JSON wrapper validation, HTTP errors, SSE streaming.

- `../backend/app/services/__init__.py`
  - Marks service package if it does not already exist.

### Backend Files To Modify

- `../backend/app/core/config.py`
  - Add `AGENT_SERVICE_TIMEOUT_SECONDS`.
  - Add optional `BACKEND_PUBLIC_URL` only if webhook URLs need absolute construction.

- `../backend/app/api/v1/profile.py`
  - Replace mock profile refresh completion with Agent call and `UserProfile` persistence.

- `../backend/app/api/v1/tutoring.py`
  - Replace mock SSE generator with Agent SSE proxy.

- `../backend/app/api/v1/resources.py`
  - Replace local resource mock generation with Agent async task submission.

- `../backend/app/api/v1/webhooks.py`
  - Persist `result.resources` into SQL for `resource_generation`.

- `../backend/app/api/v1/quiz.py`
  - Replace mock question generation with Agent question generation and SQL insert.
  - Optional later: call `/agent/v1/assessment/evaluate` after local deterministic scoring.

- `../backend/test_api.py`
  - Extend smoke coverage with monkeypatched Agent client or local Agent Service integration mode.

### Agent Service Files To Modify

- None expected for the first integration pass.
- Only update `agent_service/WORKFLOW.md` after each completed batch.

---

## Task 1: Add Backend Agent Client Boundary

**Files:**
- Create: `../backend/app/services/agent_client.py`
- Create: `../backend/app/services/__init__.py`
- Modify: `../backend/app/core/config.py`

- [ ] **Step 1: Add failing tests or smoke harness for client wrapper**

If backend has no pytest suite, add a small import-level check in `../backend/test_api.py` before full smoke:

```python
from app.services.agent_client import AgentServiceClient

client = AgentServiceClient(base_url="http://agent.test", timeout=1.0)
chk("Agent client base url", str(client.base_url).rstrip("/") == "http://agent.test")
```

Run:

```bash
cd ../backend
python test_api.py
```

Expected before implementation:

```text
ModuleNotFoundError: No module named 'app.services'
```

- [ ] **Step 2: Create service package**

Create `../backend/app/services/__init__.py`:

```python
"""Backend service boundaries for external/internal service integrations."""
```

- [ ] **Step 3: Implement minimal JSON/SSE Agent client**

Create `../backend/app/services/agent_client.py`:

```python
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings


class AgentServiceError(RuntimeError):
    """Raised when Agent Service is unavailable or returns an invalid response."""


@dataclass
class AgentServiceClient:
    """HTTP boundary for Backend -> Agent Service calls.

    Input: Agent API path plus JSON payload.
    Output: unwrapped Agent `data` dict, accepted task payload, or raw SSE lines.
    """

    base_url: str = settings.AGENT_SERVICE_URL
    timeout: float = 30.0

    async def post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                body = response.json()
        except Exception as exc:
            raise AgentServiceError(f"Agent Service request failed: {path}") from exc

        if not isinstance(body, dict) or "code" not in body:
            raise AgentServiceError(f"Agent Service returned invalid wrapper: {path}")
        if body.get("code") not in (200, 202):
            raise AgentServiceError(f"Agent Service returned code={body.get('code')}: {path}")
        data = body.get("data")
        return data if isinstance(data, dict) else {}

    async def stream_sse(self, path: str, payload: dict[str, Any]) -> AsyncIterator[str]:
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", url, json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line:
                            yield line
        except Exception as exc:
            raise AgentServiceError(f"Agent Service SSE request failed: {path}") from exc


def get_agent_client() -> AgentServiceClient:
    """FastAPI dependency factory for Agent Service calls."""

    return AgentServiceClient(timeout=30.0)
```

- [ ] **Step 4: Add timeout config**

Modify `../backend/app/core/config.py`:

```python
# Agent service (internal)
AGENT_SERVICE_URL: str = "http://localhost:8002"
AGENT_SERVICE_TIMEOUT_SECONDS: float = 30.0
```

Then update `get_agent_client()`:

```python
def get_agent_client() -> AgentServiceClient:
    """FastAPI dependency factory for Agent Service calls."""

    return AgentServiceClient(timeout=settings.AGENT_SERVICE_TIMEOUT_SECONDS)
```

- [ ] **Step 5: Verify and commit**

Run:

```bash
cd ../backend
python test_api.py
```

Expected:

```text
ALL TESTS PASSED!
```

Commit:

```bash
git add backend/app/services backend/app/core/config.py backend/test_api.py
git commit -m "feat(backend): add agent service client boundary"
```

---

## Task 2: Integrate `POST /api/v1/profile/refresh`

**Files:**
- Modify: `../backend/app/api/v1/profile.py`
- Modify: `../backend/test_api.py`

- [ ] **Step 1: Write failing refresh expectation**

Patch the profile refresh section in `../backend/test_api.py` so it verifies that the task completes and profile data changes after refresh.

```python
r = await client.post(f"/api/v1/profile/refresh?course_id={course_id}", headers=s_h)
chk("Profile refresh 202", r.status_code == 202)
profile_task_id = r.json()["data"]["task_id"]

r = await client.get(f"/api/v1/tasks/{profile_task_id}", headers=s_h)
chk("Profile task completed", r.json()["data"]["status"] == "completed")

r = await client.get(f"/api/v1/profile?course_id={course_id}", headers=s_h)
pd = r.json()["data"]
chk("Profile refreshed profile", "knowledge_coordinates" in pd and "drive_intent" in pd)
```

Run:

```bash
cd ../backend
python test_api.py
```

Expected before implementation against real Agent:

```text
FAIL Profile refreshed profile
```

- [ ] **Step 2: Add Agent client dependency and mapper**

In `../backend/app/api/v1/profile.py`, add imports:

```python
from app.services.agent_client import AgentServiceClient, AgentServiceError, get_agent_client
```

Change function signature:

```python
async def refresh_profile(
    course_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    agent_client: AgentServiceClient = Depends(get_agent_client),
):
```

Add helper near `_profile_data()`:

```python
def _apply_agent_profile(profile: UserProfile, data: dict, course_id: str) -> None:
    """Map Agent profile result into Backend UserProfile columns."""

    guidance = data.get("guidance_level_suggestion") or {}
    profile.modal_preference = data.get("modal_preference") or {}
    profile.guidance_level_current = guidance.get("recommended") or profile.guidance_level_current or "L2"
    profile.guidance_level_updated_at = datetime.now(timezone.utc)
    profile.knowledge_coordinates = data.get("knowledge_coordinates") or []
    profile.cognitive_blindspots = data.get("cognitive_blindspots") or []
    profile.drive_intent = data.get("drive_intent") or {}
    profile.discipline_badge = data.get("discipline_badge") or {"subject": course_id, "level": "", "streak_days": 0}
    profile.generated_at = datetime.now(timezone.utc)
```

- [ ] **Step 3: Replace mock completion with Agent call**

Inside `refresh_profile()`, after creating and refreshing `task`, replace the mock completion block:

```python
try:
    agent_data = await agent_client.post_json(
        "/agent/v1/profile/generate",
        {
            "user_id": current_user.id,
            "course_id": course_id,
            "evaluation_data": None,
            "quiz_history": [],
            "resource_usage_stats": {},
            "drive_intent_data": {},
        },
    )

    existing_result = await db.execute(
        select(UserProfile).where(
            UserProfile.user_id == current_user.id,
            UserProfile.course_id == course_id,
            UserProfile.is_deleted == False,
        )
    )
    profile = existing_result.scalar_one_or_none()
    if profile is None:
        profile = UserProfile(user_id=current_user.id, course_id=course_id)
        db.add(profile)

    _apply_agent_profile(profile, agent_data, course_id)
    task.status = "completed"
    task.progress = 100
    task.result = {"updated_at": datetime.now(timezone.utc).isoformat()}
    task.completed_at = datetime.now(timezone.utc)
except AgentServiceError as exc:
    task.status = "failed"
    task.error_code = "AGENT_SERVICE_ERROR"
    task.error_message = str(exc)
    task.completed_at = datetime.now(timezone.utc)

await db.flush()
```

Return remains HTTP 202 with task id.

- [ ] **Step 4: Verify profile path**

Run with Agent Service on port 8002:

```bash
cd agent_service
./.venv/bin/uvicorn agent_service.main:app --host 127.0.0.1 --port 8002
```

In another shell:

```bash
cd backend
python test_api.py
```

Expected:

```text
Profile refresh 202
Profile task completed
Profile refreshed profile
ALL TESTS PASSED!
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/profile.py backend/test_api.py
git commit -m "feat(backend): connect profile refresh to agent service"
```

---

## Task 3: Integrate Tutoring SSE Proxy

**Files:**
- Modify: `../backend/app/api/v1/tutoring.py`
- Modify: `../backend/test_api.py`

- [ ] **Step 1: Add smoke coverage for tutoring chat**

Add a tutoring chat call in `../backend/test_api.py`:

```python
r = await client.post("/api/v1/tutoring/chat", headers=s_h, json={
    "scope": "course",
    "course_id": course_id,
    "message": "请解释一下数组和链表的区别",
})
chk("Tutoring chat SSE", r.status_code == 200)
chk("Tutoring chat content type", "text/event-stream" in r.headers.get("content-type", ""))
```

- [ ] **Step 2: Build Agent request from backend SQL**

In `../backend/app/api/v1/tutoring.py`, import:

```python
from app.models.others import UserProfile
from app.services.agent_client import AgentServiceClient, get_agent_client
```

Change function signature:

```python
async def tutoring_chat(
    req: TutoringChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    agent_client: AgentServiceClient = Depends(get_agent_client),
):
```

Add helper:

```python
async def _build_agent_tutoring_payload(
    db: AsyncSession,
    req: TutoringChatRequest,
    current_user: User,
    conversation_id: str,
) -> dict:
    """Assemble Backend SQL context for Agent tutoring/chat."""

    profile_result = await db.execute(
        select(UserProfile).where(
            UserProfile.user_id == current_user.id,
            UserProfile.course_id == req.course_id,
            UserProfile.is_deleted == False,
        )
    )
    profile = profile_result.scalar_one_or_none()
    user_profile = {
        "guidance_level": profile.guidance_level_current if profile else "L2",
        "modal_preference": profile.modal_preference if profile else {},
        "knowledge_mastered": [
            item.get("name", "")
            for item in ((profile.knowledge_coordinates if profile else []) or [])
            if item.get("status") == "mastered"
        ],
        "knowledge_weak": [
            item.get("name", "")
            for item in ((profile.cognitive_blindspots if profile else []) or [])
        ],
    }

    recent_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id, Message.is_deleted == False)
        .order_by(Message.create_time.desc())
        .limit(10)
    )
    recent = list(reversed(recent_result.scalars().all()))

    return {
        "user_id": current_user.id,
        "scope": req.scope,
        "course_id": req.course_id,
        "conversation_id": conversation_id,
        "message": req.message,
        "user_profile": user_profile,
        "conversation_summary": None,
        "recent_messages": [
            {"role": m.role, "content": m.content or "", "meta": m.meta_json or {}}
            for m in recent
            if m.role in ("user", "assistant")
        ],
    }
```

- [ ] **Step 3: Replace local mock SSE with proxy**

Inside `event_generator()`, stream from Agent:

```python
    async def event_generator():
        content_parts: list[str] = []
        async for line in agent_client.stream_sse("/agent/v1/tutoring/chat", agent_payload):
            if line.startswith("data: "):
                raw = line[len("data: "):]
                try:
                    event = json.loads(raw)
                    if event.get("type") == "chunk":
                        content_parts.append(event.get("content", ""))
                    elif event.get("type") == "done":
                        assistant_msg.content = "".join(content_parts)
                        await db.flush()
                except json.JSONDecodeError:
                    pass
            yield line
```

Before returning `EventSourceResponse`, build:

```python
    agent_payload = await _build_agent_tutoring_payload(db, req, current_user, conversation_id)
```

- [ ] **Step 4: Verify tutoring path**

Run:

```bash
cd backend
python test_api.py
```

Expected:

```text
Tutoring chat SSE
Tutoring chat content type
ALL TESTS PASSED!
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/tutoring.py backend/test_api.py
git commit -m "feat(backend): proxy tutoring chat to agent service"
```

---

## Task 4: Integrate Resource Generation With Webhook Persistence

**Files:**
- Modify: `../backend/app/api/v1/resources.py`
- Modify: `../backend/app/api/v1/webhooks.py`
- Modify: `../backend/test_api.py`

- [ ] **Step 1: Update webhook expectation**

In `../backend/test_api.py`, after resource generation, call webhook with generated resources and check list endpoint:

```python
r = await client.post("/api/v1/resources/generate", headers=t_h, json={"course_id": course_id})
chk("Resources generate 202", r.status_code == 202)
resource_task_id = r.json()["data"]["task_id"]

r = await client.post("/api/v1/webhooks/agent", json={
    "task_id": resource_task_id,
    "task_type": "resource_generation",
    "status": "completed",
    "result": {
        "resources": [{
            "title": "Agent 生成讲义",
            "type": "document",
            "description": "由 Agent Service 生成",
            "content": "正文",
            "chapter": "第1章",
            "knowledge_point": "数组",
            "tags": ["AI生成"],
        }]
    },
})
chk("Resource webhook", r.json()["code"] == 200)

r = await client.get(f"/api/v1/resources?course_id={course_id}", headers=s_h)
titles = [item["title"] for item in r.json()["data"]["resources"]]
chk("Resource webhook persisted", "Agent 生成讲义" in titles)
```

- [ ] **Step 2: Submit resource task to Agent**

In `../backend/app/api/v1/resources.py`, import:

```python
from app.core.config import settings
from app.services.agent_client import AgentServiceClient, AgentServiceError, get_agent_client
```

Change signature:

```python
async def generate_resources(
    req: ResourceGenerateRequest,
    current_user: User = Depends(require_role("teacher")),
    db: AsyncSession = Depends(get_db),
    agent_client: AgentServiceClient = Depends(get_agent_client),
):
```

Replace local `Resource(...)` mock creation with:

```python
try:
    await agent_client.post_json(
        "/agent/v1/resources/generate",
        {
            "task_id": task.id,
            "user_id": current_user.id,
            "course_id": req.course_id,
            "webhook_url": f"{settings.AGENT_SERVICE_URL.rsplit(':', 1)[0]}:8001/api/v1/webhooks/agent",
            "chapter": req.chapter,
            "knowledge_point": req.knowledge_point,
            "resource_types": req.resource_types,
        },
    )
except AgentServiceError as exc:
    task.status = "failed"
    task.error_code = "AGENT_SERVICE_ERROR"
    task.error_message = str(exc)
    task.completed_at = datetime.now(timezone.utc)

await db.flush()
```

Note: replace the `webhook_url` construction with `BACKEND_PUBLIC_URL` if backend config adds that field.

- [ ] **Step 3: Persist webhook resources**

In `../backend/app/api/v1/webhooks.py`, import:

```python
from app.models.others import AsyncTask, Resource
```

Inside `if req.status == "completed":`, add:

```python
        if req.task_type == "resource_generation":
            resources = (req.result or {}).get("resources") or []
            for item in resources:
                db.add(Resource(
                    course_id=task.course_id or "",
                    title=item.get("title") or "未命名资源",
                    type=item.get("type") or "document",
                    description=item.get("description") or "",
                    tags=item.get("tags") or [],
                    chapter=item.get("chapter") or "",
                    knowledge_point=item.get("knowledge_point") or "",
                    content=item.get("content") or "",
                    url=item.get("url") or "",
                ))
```

- [ ] **Step 4: Verify async resource path**

Run with Agent Service running:

```bash
cd backend
python test_api.py
```

Expected:

```text
Resources generate 202
Resource webhook
Resource webhook persisted
ALL TESTS PASSED!
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/resources.py backend/app/api/v1/webhooks.py backend/test_api.py
git commit -m "feat(backend): connect resource generation webhook flow"
```

---

## Task 5: Integrate Quiz Question Generation

**Files:**
- Modify: `../backend/app/api/v1/quiz.py`
- Modify: `../backend/test_api.py`

- [ ] **Step 1: Assert generated questions are written**

In `../backend/test_api.py`, after `POST /api/v1/quiz/generate`, call question list again:

```python
r = await client.post("/api/v1/quiz/generate", headers=s_h, json={
    "course_id": course_id, "count": 3, "personalized": True,
})
chk("Quiz generate 202", r.status_code == 202)

r = await client.get(f"/api/v1/quiz/questions?course_id={course_id}&source=personalized&limit=5", headers=s_h)
chk("Quiz generated questions listed", r.json()["data"]["total_count"] >= 1)
```

- [ ] **Step 2: Call Agent question generation**

In `../backend/app/api/v1/quiz.py`, import:

```python
from app.services.agent_client import AgentServiceClient, AgentServiceError, get_agent_client
```

Change signature:

```python
async def generate_questions(
    req: QuizGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    agent_client: AgentServiceClient = Depends(get_agent_client),
):
```

Replace the simulated `new_q` creation with:

```python
try:
    agent_data = await agent_client.post_json(
        "/agent/v1/assessment/generate-questions",
        {
            "user_id": current_user.id,
            "course_id": req.course_id,
            "chapter": req.chapter,
            "knowledge_point": req.knowledge_point,
            "question_types": req.question_types or ["single_choice"],
            "count": req.count,
            "difficulty": req.difficulty,
            "personalized": req.personalized,
            "personalization_context": None,
        },
    )
    question_ids = []
    for item in agent_data.get("questions", []):
        q = QuizQuestion(
            course_id=req.course_id,
            chapter=item.get("chapter") or req.chapter or "",
            knowledge_point=item.get("knowledge_point") or req.knowledge_point or "",
            type=item.get("type") or "single_choice",
            source="personalized" if req.personalized else "common",
            personalized=req.personalized,
            owner_user_id=current_user.id if req.personalized else None,
            difficulty=item.get("difficulty") or req.difficulty or "medium",
            content=item.get("content") or "",
            options=item.get("options") or [],
            correct_answer=str(item.get("answer") or ""),
            explanation=item.get("explanation") or "",
        )
        db.add(q)
        await db.flush()
        question_ids.append(q.id)
    task.status = "completed"
    task.progress = 100
    task.result = {"question_ids": question_ids}
    task.completed_at = datetime.now(timezone.utc)
except AgentServiceError as exc:
    task.status = "failed"
    task.error_code = "AGENT_SERVICE_ERROR"
    task.error_message = str(exc)
    task.completed_at = datetime.now(timezone.utc)

await db.flush()
```

- [ ] **Step 3: Verify quiz generation**

Run:

```bash
cd backend
python test_api.py
```

Expected:

```text
Quiz generate 202
Quiz generated questions listed
ALL TESTS PASSED!
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/v1/quiz.py backend/test_api.py
git commit -m "feat(backend): generate quiz questions through agent service"
```

---

## Task 6: Optional Sync Refreshes For Evaluation And Learning Path

**Files:**
- Modify: `../backend/app/api/v1/evaluation.py`
- Modify: `../backend/app/api/v1/learning_path.py`
- Modify: `../backend/test_api.py`

- [ ] **Step 1: Evaluation refresh**

Call `/agent/v1/evaluation/generate` with minimal SQL-derived payload:

```python
{
    "user_id": current_user.id,
    "course_id": course_id,
    "learning_progress": {"chapter_progress": []},
    "quiz_results": [],
    "resource_usage": {"by_type": {}, "by_chapter": {}},
}
```

Persist returned `progress_table`, `mastery_table`, `resource_usage_table`, and `summary_text` into `Evaluation`.

- [ ] **Step 2: Learning path refresh**

Call `/agent/v1/learning-path/generate` with:

```python
{
    "user_id": current_user.id,
    "course_id": course_id,
    "evaluation": latest_evaluation_dict,
    "profile": latest_profile_dict,
    "knowledge_graph": {"nodes": [], "edges": []},
}
```

Persist returned `nodes`, `edges`, and `current_position` into `LearningPath`.

- [ ] **Step 3: Verify**

Run:

```bash
cd backend
python test_api.py
```

Expected:

```text
Eval refresh 202
LP refresh 202
ALL TESTS PASSED!
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/v1/evaluation.py backend/app/api/v1/learning_path.py backend/test_api.py
git commit -m "feat(backend): connect evaluation and learning path refreshes"
```

---

## Verification Matrix

### Agent Service

Run from `agent_service/`:

```bash
./.venv/bin/pytest -q
./.venv/bin/python -m agent_service.tools.smoke_all
./.venv/bin/uvicorn agent_service.main:app --host 127.0.0.1 --port 8002
```

Expected:

```text
246 passed
9/9 PASS
Application startup complete
```

### Backend

Run from `backend/`:

```bash
python test_api.py
```

Expected:

```text
ALL TESTS PASSED!
```

### Manual Contract Checks

Use these checkpoints after each batch:

- Backend calls only `/agent/v1/*`, not internal `agent_service` Python modules.
- Backend never writes Qdrant.
- Agent Service never writes backend SQL.
- Async endpoints return HTTP 202 with backend-created `task_id`.
- Resource webhook writes SQL only in backend.
- Tutoring SSE response remains `text/event-stream`.
- Public backend response wrapper remains `{code, message, data}`.

---

## Risk Notes

- Webhook URL construction should be moved to an explicit backend config if local LAN, Docker, or remote deployment is used. Do not hard-code `localhost` for production.
- Backend webhook currently has no internal auth. This matches current v5.0 docs, but should be revisited before deployment outside a private network.
- `test_api.py` is a smoke script, not a full isolated pytest suite. Prefer adding real backend tests later, but do not block first integration on test framework migration.
- Keep batch size small. Do not integrate all endpoints in one commit.

---

## Updated Recommendation

Start with **Task 1 + Task 2 only**.

Reason: profile refresh is the least risky real Agent-backed path because it is JSON-in/JSON-out, no SSE, no webhook, no generated SQL fanout. Once it works, the same client boundary can support tutoring, resources, quiz, evaluation, and learning path.
