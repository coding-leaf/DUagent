# AIChat Learning Progress Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let AIChat use AgentScope read-only tools to query real Backend learning progress and recent answer evidence before giving next-step learning advice.

**Architecture:** Backend owns MySQL access and exposes service-token-protected internal APIs. `agent_service_v2` registers AgentScope `FunctionTool(is_read_only=True)` tools in a `learning_progress` ToolGroup; tool closures inject the current run's `user_id/course_id` and call Backend over HTTP. Frontend remains unchanged except consuming existing tool trace/artifact events.

**Tech Stack:** FastAPI, SQLAlchemy 2.x async, Pydantic, pytest, httpx, AgentScope 2.0.3 `Agent` / `FunctionTool` / `ToolGroup` / `Toolkit`, EDU SSE v2.

## Global Constraints

- Frontend must not call Agent Service or Backend internal APIs directly.
- Agent Service must not read or write MySQL.
- Backend must not import `agent_service_v2`.
- Internal learning APIs are Backend-only service APIs under `/internal/ai-chat/*`.
- Internal API authentication uses `X-Internal-Agent-Token`.
- Tool functions are read-only and must be registered through `FunctionTool(..., is_read_only=True)`.
- `user_id` and `course_id` are injected by `WorkbenchAgentFactory.create_agent()` and are not model-provided tool parameters.
- Recent answer queries return at most 10 records.
- No new Client API endpoint and no new SSE event type.
- Do not add undeclared third-party dependencies.
- Keep old `agent_service/` runnable.

---

## File Structure

### Backend

- Modify: `backend/app/core/config.py`  
  Add `INTERNAL_AGENT_TOKEN: str = ""`.

- Create: `backend/app/schemas/internal_ai_chat.py`  
  Pydantic request models for learning progress and recent answer queries.

- Create: `backend/app/services/ai_chat_learning_context.py`  
  Service layer for progress overview, recent answer query, node resolution, and option normalization.

- Create: `backend/app/api/v1/internal_ai_chat.py`  
  Thin FastAPI router for `/internal/ai-chat/learning-progress` and `/internal/ai-chat/recent-answers`.

- Modify: `backend/app/main.py`  
  Include the internal AIChat router.

- Create: `backend/tests/test_ai_chat_learning_context.py`  
  Service-layer tests for node progress, option normalization, recent answers, and limit behavior.

- Create: `backend/tests/test_internal_ai_chat.py`  
  API authentication and response tests.

### agent_service_v2

- Create: `agent_service_v2/src/agent_service_v2/tools/backend_learning_client.py`  
  Async Backend internal API client with timeout and service token headers.

- Create: `agent_service_v2/src/agent_service_v2/tools/learning_progress.py`  
  Build `read_learning_progress` and `read_recent_answers` read-only AgentScope tools.

- Modify: `agent_service_v2/src/agent_service_v2/agents/model_provider.py`  
  Extend settings with `BACKEND_INTERNAL_BASE_URL`, `BACKEND_INTERNAL_AGENT_TOKEN`, and `BACKEND_INTERNAL_TIMEOUT`.

- Modify: `agent_service_v2/src/agent_service_v2/tools/workbench_toolkit.py`  
  Accept and register `learning_progress_tools` before artifact/review tools.

- Modify: `agent_service_v2/src/agent_service_v2/agents/workbench_factory.py`  
  Build learning progress tools with current `user_id/course_id`.

- Modify: `agent_service_v2/src/agent_service_v2/agents/permissions.py`  
  Allow `read_learning_progress` and `read_recent_answers`.

- Modify: `agent_service_v2/src/agent_service_v2/agents/prompts.py`  
  Add tool-use rules for progress and recent-answer evidence.

- Modify: `agent_service_v2/src/agent_service_v2/runtime/protocol_adapter.py`  
  Pass structured tool result summaries through `tool_completed.payload`.

- Create: `agent_service_v2/tests/test_backend_learning_client.py`

- Create: `agent_service_v2/tests/test_learning_progress_tools.py`

- Modify: `agent_service_v2/tests/test_workbench_toolkit.py`

- Modify: `agent_service_v2/tests/test_workbench_factory.py`

- Modify: `agent_service_v2/tests/test_protocol_adapter.py`

### Docs

- Modify: `WorkLine.md`  
  Record implemented files, tests, and internal interface drift after all tasks pass.

---

## Task 1: Backend Learning Context Service

**Files:**
- Create: `backend/app/services/ai_chat_learning_context.py`
- Create: `backend/tests/test_ai_chat_learning_context.py`

**Interfaces:**
- Consumes: `LearningPathService.get_learning_path(user_id: str, course_id: str) -> dict`, `build_node_progress_rows(user_id: str, course_id: str, db: AsyncSession) -> list[dict]`, `LearningActivity`, `QuizQuestion`, `QuizSession`, `QuizAnswer`.
- Produces:
  - `normalize_question_options(options: object) -> list[dict[str, str]]`
  - `resolve_node_knowledge_point(db: AsyncSession, course_id: str, node_id: str) -> str | None`
  - `build_learning_progress_overview(db: AsyncSession, user_id: str, course_id: str, limit_nodes: int = 50) -> dict`
  - `query_recent_answers(db: AsyncSession, user_id: str, course_id: str, node_id: str | None = None, knowledge_point: str | None = None, limit: int = 10, only_wrong: bool = True) -> dict`

- [ ] **Step 1: Write failing service tests**

Create `backend/tests/test_ai_chat_learning_context.py`:

```python
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///./test_ai_chat_learning_context.db",
)

from app.db.session import async_session_factory, init_db
from app.models.course import Course
from app.models.others import CourseKnowledgeGraph, LearningActivity
from app.models.quiz import QuizAnswer, QuizQuestion, QuizSession
from app.models.user import User
from app.services.ai_chat_learning_context import (
    build_learning_progress_overview,
    normalize_question_options,
    query_recent_answers,
    resolve_node_knowledge_point,
)


@pytest.fixture(scope="module", autouse=True)
def _init_db():
    import asyncio
    asyncio.run(init_db())


async def _seed_context():
    suffix = uuid.uuid4().hex[:8]
    user = User(
        id=f"user_{suffix}",
        username=f"student_{suffix}",
        email=f"student_{suffix}@test.local",
        password_hash="x",
        role="student",
    )
    course = Course(
        id=f"course_{suffix}",
        name="数据结构",
        course_code=f"DS{suffix}",
        teacher_id=user.id,
    )
    kg = CourseKnowledgeGraph(
        id=f"kg_{suffix}",
        course_id=course.id,
        version=1,
        is_active=True,
        nodes=[
            {"id": "n-avl", "name": "AVL 树旋转", "chapter": "树"},
            {"id": "n-hash", "name": "散列冲突", "chapter": "散列"},
        ],
        edges=[],
    )
    now = datetime.now(timezone.utc)
    q1 = QuizQuestion(
        id=f"q1_{suffix}",
        course_id=course.id,
        chapter="树",
        knowledge_point="AVL 树旋转",
        type="single_choice",
        source="baseline",
        personalized=False,
        difficulty="medium",
        content="插入后应进行哪种旋转？",
        options=[{"key": "A", "text": "左旋"}, {"key": "B", "text": "右旋"}],
        correct_answer="B",
        explanation="根据失衡类型判断旋转方向。",
    )
    q2 = QuizQuestion(
        id=f"q2_{suffix}",
        course_id=course.id,
        chapter="树",
        knowledge_point="AVL 树旋转",
        type="multi_choice",
        source="baseline",
        personalized=False,
        difficulty="medium",
        content="哪些情况需要双旋？",
        options=["LR", "LL", "RL", "RR"],
        correct_answer="A,C",
        explanation="LR 和 RL 需要双旋。",
    )
    q3 = QuizQuestion(
        id=f"q3_{suffix}",
        course_id=course.id,
        chapter="散列",
        knowledge_point="散列冲突",
        type="single_choice",
        source="baseline",
        personalized=False,
        difficulty="easy",
        content="开放定址法用于什么？",
        options=["解决冲突", "排序"],
        correct_answer="A",
        explanation="开放定址法用于解决散列冲突。",
    )
    session = QuizSession(
        id=f"quiz_{suffix}",
        user_id=user.id,
        course_id=course.id,
        chapter="树",
        score=50,
        correct_count=1,
        total_count=2,
        time_spent=300,
    )
    db_objects = [
        user,
        course,
        kg,
        q1,
        q2,
        q3,
        session,
        QuizAnswer(
            quiz_id=session.id,
            question_id=q1.id,
            user_answer="A",
            is_correct=False,
            correct_answer="B",
            explanation="根据失衡类型判断旋转方向。",
            create_time=now - timedelta(minutes=2),
        ),
        QuizAnswer(
            quiz_id=session.id,
            question_id=q2.id,
            user_answer="A",
            is_correct=True,
            correct_answer="A,C",
            explanation="LR 和 RL 需要双旋。",
            create_time=now - timedelta(minutes=1),
        ),
        QuizAnswer(
            quiz_id=session.id,
            question_id=q3.id,
            user_answer="B",
            is_correct=False,
            correct_answer="A",
            explanation="开放定址法用于解决散列冲突。",
            create_time=now,
        ),
        LearningActivity(
            user_id=user.id,
            course_id=course.id,
            node_id="n-avl",
            node_name="AVL 树旋转",
            activity_type="node_practice_submit",
            duration_seconds=300,
            occurred_at=now,
        ),
    ]
    async with async_session_factory() as db:
        db.add_all(db_objects)
        await db.commit()
    return user.id, course.id


def test_normalize_question_options_supports_strings_and_objects():
    assert normalize_question_options(["左旋", "右旋"]) == [
        {"key": "A", "text": "左旋"},
        {"key": "B", "text": "右旋"},
    ]
    assert normalize_question_options([{"key": "T", "text": "正确"}]) == [
        {"key": "T", "text": "正确"}
    ]


@pytest.mark.asyncio
async def test_resolve_node_knowledge_point_uses_active_kg_node_name():
    _user_id, course_id = await _seed_context()
    async with async_session_factory() as db:
        resolved = await resolve_node_knowledge_point(db, course_id, "n-avl")
    assert resolved == "AVL 树旋转"


@pytest.mark.asyncio
async def test_query_recent_answers_filters_by_node_and_wrong_only():
    user_id, course_id = await _seed_context()
    async with async_session_factory() as db:
        result = await query_recent_answers(
            db,
            user_id=user_id,
            course_id=course_id,
            node_id="n-avl",
            limit=10,
            only_wrong=True,
        )

    assert result["status"] == "available"
    assert result["scope"] == "knowledge_point"
    assert result["query"]["resolved_knowledge_point"] == "AVL 树旋转"
    assert result["summary"]["returned_count"] == 1
    item = result["items"][0]
    assert item["knowledge_point"] == "AVL 树旋转"
    assert item["is_correct"] is False
    assert item["user_answer"] == "A"
    assert item["correct_answer"] == "B"
    assert item["options"] == [
        {"key": "A", "text": "左旋"},
        {"key": "B", "text": "右旋"},
    ]


@pytest.mark.asyncio
async def test_query_recent_answers_can_include_correct_answers_and_caps_limit():
    user_id, course_id = await _seed_context()
    async with async_session_factory() as db:
        result = await query_recent_answers(
            db,
            user_id=user_id,
            course_id=course_id,
            knowledge_point="AVL 树旋转",
            limit=99,
            only_wrong=False,
        )

    assert result["query"]["limit"] == 10
    assert result["summary"]["returned_count"] == 2
    assert {item["is_correct"] for item in result["items"]} == {True, False}


@pytest.mark.asyncio
async def test_build_learning_progress_overview_returns_node_metrics():
    user_id, course_id = await _seed_context()
    async with async_session_factory() as db:
        result = await build_learning_progress_overview(
            db,
            user_id=user_id,
            course_id=course_id,
            limit_nodes=50,
        )

    assert result["status"] == "available"
    assert result["course_id"] == course_id
    assert result["summary"]["total_nodes"] >= 2
    node = next(item for item in result["nodes"] if item["node_id"] == "n-avl")
    assert node["node_name"] == "AVL 树旋转"
    assert node["attempt_count"] >= 2
    assert node["wrong_count"] >= 1
    assert result["recent_activity"][0]["activity_type"] == "node_practice_submit"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd backend && ../.venv/bin/python -m pytest tests/test_ai_chat_learning_context.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.ai_chat_learning_context'`.

- [ ] **Step 3: Implement Backend service**

Create `backend/app/services/ai_chat_learning_context.py`:

```python
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.others import LearningActivity
from app.models.quiz import QuizAnswer, QuizQuestion, QuizSession
from app.services.course_knowledge_graphs import get_active_knowledge_graph
from app.services.knowledge_progress import build_node_progress_rows
from app.services.learning_path_service import LearningPathService

MAX_RECENT_ANSWERS = 10
MAX_PROGRESS_NODES = 100


def _bounded_limit(value: int, *, default: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(parsed, maximum))


def normalize_question_options(options: object) -> list[dict[str, str]]:
    if not isinstance(options, list):
        return []
    normalized: list[dict[str, str]] = []
    for index, option in enumerate(options):
        fallback_key = chr(65 + index)
        if isinstance(option, dict):
            key = str(option.get("key") or fallback_key)
            text = str(option.get("text") or option.get("label") or option.get("key") or "")
            normalized.append({"key": key, "text": text})
        else:
            normalized.append({"key": fallback_key, "text": str(option or "")})
    return normalized


async def resolve_node_knowledge_point(
    db: AsyncSession,
    course_id: str,
    node_id: str,
) -> str | None:
    kg = await get_active_knowledge_graph(db, course_id)
    nodes = kg.nodes if kg and isinstance(kg.nodes, list) else []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        current_id = str(node.get("id") or node.get("node_id") or "")
        if current_id == node_id:
            name = str(node.get("name") or "").strip()
            return name or None
    return None


def _progress_summary(nodes: list[dict[str, Any]]) -> dict[str, int]:
    completed = sum(1 for node in nodes if node.get("status") == "completed")
    in_progress = sum(1 for node in nodes if node.get("status") == "in_progress")
    weak = sum(1 for node in nodes if node.get("assessment_state") == "weak" or node.get("status") == "recommended")
    pending = sum(1 for node in nodes if node.get("status") == "pending")
    total = len(nodes)
    mastery_rate = int((completed / total) * 100) if total else 0
    return {
        "total_nodes": total,
        "completed_count": completed,
        "in_progress_count": in_progress,
        "weak_count": weak,
        "pending_count": pending,
        "mastery_rate": mastery_rate,
    }


async def build_learning_progress_overview(
    db: AsyncSession,
    *,
    user_id: str,
    course_id: str,
    limit_nodes: int = 50,
) -> dict:
    limit = _bounded_limit(limit_nodes, default=50, maximum=MAX_PROGRESS_NODES)
    path = await LearningPathService(db).get_learning_path(user_id, course_id)
    progress_rows = await build_node_progress_rows(user_id, course_id, db)
    progress_by_id = {str(row.get("node_id") or ""): row for row in progress_rows}

    nodes: list[dict[str, Any]] = []
    for node in (path.get("nodes") or [])[:limit]:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id") or node.get("node_id") or "")
        progress = progress_by_id.get(node_id, {})
        nodes.append(
            {
                "node_id": node_id,
                "node_name": str(node.get("name") or progress.get("node_name") or ""),
                "status": node.get("status") or "pending",
                "assessment_state": progress.get("assessment_state") or "",
                "mastery_score": progress.get("mastery_score"),
                "mastery_label": progress.get("mastery_label") or "",
                "attempt_count": int(progress.get("attempt_count") or 0),
                "wrong_count": int(progress.get("wrong_count") or 0),
                "question_count": int(progress.get("question_count") or 0),
                "study_duration_seconds": progress.get("study_duration_seconds"),
                "resource_visit_count": progress.get("resource_visit_count"),
                "last_activity_at": progress.get("last_activity_at"),
            }
        )

    activity_result = await db.execute(
        select(LearningActivity)
        .where(
            LearningActivity.user_id == user_id,
            LearningActivity.course_id == course_id,
            LearningActivity.is_deleted == False,
        )
        .order_by(LearningActivity.occurred_at.desc())
        .limit(10)
    )
    recent_activity = [
        {
            "activity_type": item.activity_type,
            "node_id": item.node_id,
            "node_name": item.node_name,
            "resource_id": item.resource_id,
            "duration_seconds": item.duration_seconds,
            "occurred_at": item.occurred_at.isoformat() if item.occurred_at else None,
        }
        for item in activity_result.scalars().all()
    ]

    return {
        "status": "available",
        "course_id": course_id,
        "current_position": path.get("current_position"),
        "summary": _progress_summary(nodes),
        "nodes": nodes,
        "recent_activity": recent_activity,
        "source": "backend.learning_progress",
    }


async def query_recent_answers(
    db: AsyncSession,
    *,
    user_id: str,
    course_id: str,
    node_id: str | None = None,
    knowledge_point: str | None = None,
    limit: int = 10,
    only_wrong: bool = True,
) -> dict:
    bounded_limit = _bounded_limit(limit, default=10, maximum=MAX_RECENT_ANSWERS)
    warnings: list[str] = []
    resolved_knowledge_point = str(knowledge_point or "").strip() or None
    scope = "course_recent"

    if node_id:
        node_knowledge_point = await resolve_node_knowledge_point(db, course_id, node_id)
        if node_knowledge_point is None:
            return {
                "status": "not_found",
                "scope": "node",
                "query": {
                    "node_id": node_id,
                    "resolved_knowledge_point": None,
                    "only_wrong": only_wrong,
                    "limit": bounded_limit,
                },
                "items": [],
                "summary": {"returned_count": 0, "has_more": False},
                "warnings": ["node_not_found"],
            }
        if resolved_knowledge_point and resolved_knowledge_point != node_knowledge_point:
            warnings.append("node_id resolved knowledge_point overrides provided knowledge_point")
        resolved_knowledge_point = node_knowledge_point
        scope = "knowledge_point"
    elif resolved_knowledge_point:
        scope = "knowledge_point"

    stmt = (
        select(QuizAnswer, QuizSession, QuizQuestion)
        .join(QuizSession, QuizAnswer.quiz_id == QuizSession.id)
        .join(QuizQuestion, QuizAnswer.question_id == QuizQuestion.id)
        .where(
            QuizSession.user_id == user_id,
            QuizSession.course_id == course_id,
            QuizAnswer.is_deleted == False,
            QuizSession.is_deleted == False,
            QuizQuestion.is_deleted == False,
        )
        .order_by(QuizAnswer.create_time.desc())
        .limit(bounded_limit + 1)
    )
    if resolved_knowledge_point:
        stmt = stmt.where(QuizQuestion.knowledge_point == resolved_knowledge_point)
    if only_wrong:
        stmt = stmt.where(QuizAnswer.is_correct == False)

    rows = (await db.execute(stmt)).all()
    visible_rows = rows[:bounded_limit]
    items = [
        {
            "quiz_id": session.id,
            "question_id": question.id,
            "answered_at": answer.create_time.isoformat() if answer.create_time else None,
            "chapter": question.chapter,
            "knowledge_point": question.knowledge_point,
            "type": question.type,
            "difficulty": question.difficulty,
            "source": question.source,
            "personalized": bool(question.personalized),
            "content": question.content,
            "options": normalize_question_options(question.options),
            "user_answer": answer.user_answer,
            "correct_answer": answer.correct_answer,
            "is_correct": bool(answer.is_correct),
            "explanation": answer.explanation or "",
        }
        for answer, session, question in visible_rows
    ]

    return {
        "status": "available" if items else "empty",
        "scope": scope,
        "query": {
            "node_id": node_id,
            "resolved_knowledge_point": resolved_knowledge_point,
            "only_wrong": only_wrong,
            "limit": bounded_limit,
        },
        "items": items,
        "summary": {"returned_count": len(items), "has_more": len(rows) > bounded_limit},
        "warnings": warnings,
    }
```

- [ ] **Step 4: Run service tests to verify pass**

Run:

```bash
cd backend && ../.venv/bin/python -m pytest tests/test_ai_chat_learning_context.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai_chat_learning_context.py backend/tests/test_ai_chat_learning_context.py
git commit -m "feat: 新增AIChat学习进度查询服务"
```

---

## Task 2: Backend Internal AIChat API

**Files:**
- Modify: `backend/app/core/config.py`
- Create: `backend/app/schemas/internal_ai_chat.py`
- Create: `backend/app/api/v1/internal_ai_chat.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_internal_ai_chat.py`

**Interfaces:**
- Consumes: Task 1 service functions.
- Produces:
  - `POST /internal/ai-chat/learning-progress`
  - `POST /internal/ai-chat/recent-answers`
  - Header auth through `X-Internal-Agent-Token`
  - `Settings.INTERNAL_AGENT_TOKEN: str`

- [ ] **Step 1: Write failing internal API tests**

Create `backend/tests/test_internal_ai_chat.py`:

```python
import os
import sys
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///./test_internal_ai_chat.db",
)

from app.db.session import init_db
from app.main import app


@pytest.fixture(scope="module", autouse=True)
def _init_db():
    import asyncio
    asyncio.run(init_db())


@pytest.mark.asyncio
async def test_internal_learning_progress_requires_token():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/internal/ai-chat/learning-progress",
            json={"user_id": "u1", "course_id": "c1"},
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_internal_learning_progress_returns_service_result():
    with patch("app.api.v1.internal_ai_chat.settings.INTERNAL_AGENT_TOKEN", "secret"):
        with patch(
            "app.api.v1.internal_ai_chat.build_learning_progress_overview",
            new_callable=AsyncMock,
        ) as mock_service:
            mock_service.return_value = {
                "status": "available",
                "course_id": "c1",
                "current_position": None,
                "summary": {"total_nodes": 0},
                "nodes": [],
                "recent_activity": [],
                "source": "backend.learning_progress",
            }
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/internal/ai-chat/learning-progress",
                    headers={"X-Internal-Agent-Token": "secret"},
                    json={"user_id": "u1", "course_id": "c1", "limit_nodes": 20},
                )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "available"
    mock_service.assert_awaited_once()


@pytest.mark.asyncio
async def test_internal_recent_answers_caps_request_schema_limit():
    with patch("app.api.v1.internal_ai_chat.settings.INTERNAL_AGENT_TOKEN", "secret"):
        with patch(
            "app.api.v1.internal_ai_chat.query_recent_answers",
            new_callable=AsyncMock,
        ) as mock_service:
            mock_service.return_value = {
                "status": "empty",
                "scope": "knowledge_point",
                "query": {"limit": 10},
                "items": [],
                "summary": {"returned_count": 0, "has_more": False},
                "warnings": [],
            }
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/internal/ai-chat/recent-answers",
                    headers={"X-Internal-Agent-Token": "secret"},
                    json={
                        "user_id": "u1",
                        "course_id": "c1",
                        "knowledge_point": "AVL 树旋转",
                        "limit": 99,
                        "only_wrong": True,
                    },
                )

    assert response.status_code == 200
    kwargs = mock_service.await_args.kwargs
    assert kwargs["limit"] == 10
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd backend && ../.venv/bin/python -m pytest tests/test_internal_ai_chat.py -q
```

Expected: FAIL with import error for `app.api.v1.internal_ai_chat` or 404 for `/internal/ai-chat/learning-progress`.

- [ ] **Step 3: Add internal token setting**

Modify `backend/app/core/config.py` under `WEBHOOK_SECRET`:

```python
    # Internal AIChat tool auth — shared with Agent Service v2
    INTERNAL_AGENT_TOKEN: str = ""
```

- [ ] **Step 4: Add internal request schemas**

Create `backend/app/schemas/internal_ai_chat.py`:

```python
from pydantic import BaseModel, Field


class LearningProgressRequest(BaseModel):
    user_id: str
    course_id: str
    limit_nodes: int = Field(default=50, ge=1, le=100)


class RecentAnswersRequest(BaseModel):
    user_id: str
    course_id: str
    node_id: str | None = None
    knowledge_point: str | None = None
    limit: int = Field(default=10, ge=1, le=10)
    only_wrong: bool = True
```

- [ ] **Step 5: Add internal router**

Create `backend/app/api/v1/internal_ai_chat.py`:

```python
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings
from app.schemas.internal_ai_chat import LearningProgressRequest, RecentAnswersRequest
from app.services.ai_chat_learning_context import (
    build_learning_progress_overview,
    query_recent_answers,
)

router = APIRouter(prefix="/internal/ai-chat", tags=["internal-ai-chat"])


def verify_internal_agent_token(
    x_internal_agent_token: str | None = Header(default=None, alias="X-Internal-Agent-Token"),
) -> None:
    expected = settings.INTERNAL_AGENT_TOKEN
    if not expected or x_internal_agent_token != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": 40300, "message": "internal agent token invalid", "data": None},
        )


@router.post("/learning-progress")
async def read_learning_progress(
    req: LearningProgressRequest,
    _auth: None = Depends(verify_internal_agent_token),
    db: AsyncSession = Depends(get_db),
):
    data = await build_learning_progress_overview(
        db,
        user_id=req.user_id,
        course_id=req.course_id,
        limit_nodes=req.limit_nodes,
    )
    return {"code": 200, "message": "success", "data": data}


@router.post("/recent-answers")
async def read_recent_answers(
    req: RecentAnswersRequest,
    _auth: None = Depends(verify_internal_agent_token),
    db: AsyncSession = Depends(get_db),
):
    data = await query_recent_answers(
        db,
        user_id=req.user_id,
        course_id=req.course_id,
        node_id=req.node_id,
        knowledge_point=req.knowledge_point,
        limit=req.limit,
        only_wrong=req.only_wrong,
    )
    return {"code": 200, "message": "success", "data": data}
```

- [ ] **Step 6: Register router**

Modify imports in `backend/app/main.py`:

```python
from app.api.v1 import (
    admin, auth, catalogs, courses, evaluation, internal_ai_chat,
    learning_path, learning_activities, personalized_resources, profile,
    quiz, resources, tasks, teaching, tutoring, users, webhooks,
)
```

Add include before public routers or near other routers:

```python
app.include_router(internal_ai_chat.router)
```

- [ ] **Step 7: Run API tests**

Run:

```bash
cd backend && ../.venv/bin/python -m pytest tests/test_internal_ai_chat.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/core/config.py backend/app/schemas/internal_ai_chat.py backend/app/api/v1/internal_ai_chat.py backend/app/main.py backend/tests/test_internal_ai_chat.py
git commit -m "feat: 新增AIChat内部学习查询接口"
```

---

## Task 3: Agent Service Backend Learning Client

**Files:**
- Modify: `agent_service_v2/src/agent_service_v2/agents/model_provider.py`
- Create: `agent_service_v2/src/agent_service_v2/tools/backend_learning_client.py`
- Create: `agent_service_v2/tests/test_backend_learning_client.py`

**Interfaces:**
- Consumes: Backend internal APIs from Task 2.
- Produces:
  - `BackendLearningClient(base_url: str, token: str, timeout: float = 10.0)`
  - `BackendLearningClient.post_json(path: str, payload: dict) -> dict`
  - `BackendLearningClientError(reason: str, status_code: int | None = None)`
  - `build_backend_learning_client_from_settings(settings: AgentModelSettings | None = None) -> BackendLearningClient | None`
  - `AgentModelSettings.BACKEND_INTERNAL_BASE_URL`
  - `AgentModelSettings.BACKEND_INTERNAL_AGENT_TOKEN`
  - `AgentModelSettings.BACKEND_INTERNAL_TIMEOUT`

- [ ] **Step 1: Write failing client tests**

Create `agent_service_v2/tests/test_backend_learning_client.py`:

```python
import httpx
import pytest

from agent_service_v2.agents.model_provider import AgentModelSettings
from agent_service_v2.tools.backend_learning_client import (
    BackendLearningClient,
    BackendLearningClientError,
    build_backend_learning_client_from_settings,
)


class StubTransport(httpx.AsyncBaseTransport):
    def __init__(self):
        self.requests = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(
            200,
            json={"code": 200, "message": "success", "data": {"status": "available"}},
            request=request,
        )


@pytest.mark.asyncio
async def test_backend_learning_client_posts_token_and_returns_data():
    transport = StubTransport()
    client = BackendLearningClient(
        base_url="http://backend",
        token="secret",
        timeout=5.0,
        transport=transport,
    )

    data = await client.post_json("/internal/ai-chat/learning-progress", {"user_id": "u1"})

    assert data == {"status": "available"}
    request = transport.requests[0]
    assert request.headers["X-Internal-Agent-Token"] == "secret"
    assert str(request.url) == "http://backend/internal/ai-chat/learning-progress"


@pytest.mark.asyncio
async def test_backend_learning_client_raises_structured_error_on_http_error():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"message": "forbidden"}, request=request)

    client = BackendLearningClient(
        base_url="http://backend",
        token="secret",
        timeout=5.0,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(BackendLearningClientError) as exc:
        await client.post_json("/internal/ai-chat/learning-progress", {})

    assert exc.value.reason == "backend_http_error"
    assert exc.value.status_code == 403


def test_build_backend_learning_client_from_settings_requires_base_url_and_token():
    missing = AgentModelSettings(
        BACKEND_INTERNAL_BASE_URL="",
        BACKEND_INTERNAL_AGENT_TOKEN="",
    )
    assert build_backend_learning_client_from_settings(missing) is None

    configured = AgentModelSettings(
        BACKEND_INTERNAL_BASE_URL="http://backend",
        BACKEND_INTERNAL_AGENT_TOKEN="secret",
        BACKEND_INTERNAL_TIMEOUT=3.0,
    )
    client = build_backend_learning_client_from_settings(configured)
    assert isinstance(client, BackendLearningClient)
    assert client.base_url == "http://backend"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/pytest tests/test_backend_learning_client.py -q
```

Expected: FAIL with `ModuleNotFoundError: agent_service_v2.tools.backend_learning_client`.

- [ ] **Step 3: Extend settings**

Modify `agent_service_v2/src/agent_service_v2/agents/model_provider.py` in `AgentModelSettings`:

```python
    BACKEND_INTERNAL_BASE_URL: str | None = None
    BACKEND_INTERNAL_AGENT_TOKEN: str | None = None
    BACKEND_INTERNAL_TIMEOUT: float = 10.0
```

- [ ] **Step 4: Implement Backend learning client**

Create `agent_service_v2/src/agent_service_v2/tools/backend_learning_client.py`:

```python
from __future__ import annotations

from typing import Any

import httpx

from agent_service_v2.agents.model_provider import AgentModelSettings


class BackendLearningClientError(RuntimeError):
    def __init__(self, reason: str, status_code: int | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status_code = status_code


class BackendLearningClient:
    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout
        self._transport = transport

    async def post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = {"X-Internal-Agent-Token": self._token}
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                response = await client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise BackendLearningClientError("backend_timeout") from exc
        except httpx.ConnectError as exc:
            raise BackendLearningClientError("backend_unavailable") from exc
        if response.status_code >= 400:
            raise BackendLearningClientError("backend_http_error", status_code=response.status_code)
        body = response.json()
        data = body.get("data") if isinstance(body, dict) else None
        return data if isinstance(data, dict) else {}


def build_backend_learning_client_from_settings(
    settings: AgentModelSettings | None = None,
) -> BackendLearningClient | None:
    settings = settings or AgentModelSettings()
    if not settings.BACKEND_INTERNAL_BASE_URL or not settings.BACKEND_INTERNAL_AGENT_TOKEN:
        return None
    return BackendLearningClient(
        base_url=settings.BACKEND_INTERNAL_BASE_URL,
        token=settings.BACKEND_INTERNAL_AGENT_TOKEN,
        timeout=settings.BACKEND_INTERNAL_TIMEOUT,
    )
```

- [ ] **Step 5: Run client tests**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/pytest tests/test_backend_learning_client.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add agent_service_v2/src/agent_service_v2/agents/model_provider.py agent_service_v2/src/agent_service_v2/tools/backend_learning_client.py agent_service_v2/tests/test_backend_learning_client.py
git commit -m "feat: 新增Backend学习查询客户端"
```

---

## Task 4: AgentScope Learning Progress Tools

**Files:**
- Create: `agent_service_v2/src/agent_service_v2/tools/learning_progress.py`
- Create: `agent_service_v2/tests/test_learning_progress_tools.py`

**Interfaces:**
- Consumes: `BackendLearningClient`.
- Produces:
  - `build_learning_progress_tools(client: BackendLearningClient | None, user_id: str, course_id: str | None) -> list[FunctionTool]`
  - Tool name `read_learning_progress`
  - Tool name `read_recent_answers`

- [ ] **Step 1: Write failing tool tests**

Create `agent_service_v2/tests/test_learning_progress_tools.py`:

```python
import pytest

from agent_service_v2.tools.learning_progress import build_learning_progress_tools


class FakeClient:
    def __init__(self):
        self.calls = []

    async def post_json(self, path, payload):
        self.calls.append((path, payload))
        return {"status": "available", "path": path, "payload": payload}


@pytest.mark.asyncio
async def test_read_learning_progress_tool_injects_user_and_course():
    client = FakeClient()
    tools = build_learning_progress_tools(client=client, user_id="u1", course_id="c1")
    tool = next(item for item in tools if item.name == "read_learning_progress")

    result = await tool.call({"limit_nodes": 20})

    assert result.content[0]["text"]
    assert client.calls == [
        ("/internal/ai-chat/learning-progress", {"user_id": "u1", "course_id": "c1", "limit_nodes": 20})
    ]


@pytest.mark.asyncio
async def test_read_recent_answers_tool_does_not_accept_user_id_from_model():
    client = FakeClient()
    tools = build_learning_progress_tools(client=client, user_id="u1", course_id="c1")
    tool = next(item for item in tools if item.name == "read_recent_answers")

    await tool.call({"node_id": "n-avl", "user_id": "attacker", "limit": 99})

    path, payload = client.calls[0]
    assert path == "/internal/ai-chat/recent-answers"
    assert payload["user_id"] == "u1"
    assert payload["course_id"] == "c1"
    assert payload["node_id"] == "n-avl"
    assert payload["limit"] == 10
    assert "attacker" not in payload.values()


@pytest.mark.asyncio
async def test_learning_tools_return_unavailable_when_client_missing():
    tools = build_learning_progress_tools(client=None, user_id="u1", course_id="c1")
    tool = next(item for item in tools if item.name == "read_learning_progress")

    result = await tool.call({})

    assert "backend_learning_client_not_configured" in result.content[0]["text"]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/pytest tests/test_learning_progress_tools.py -q
```

Expected: FAIL with `ModuleNotFoundError: agent_service_v2.tools.learning_progress`.

- [ ] **Step 3: Implement tools**

Create `agent_service_v2/src/agent_service_v2/tools/learning_progress.py`:

```python
from __future__ import annotations

from typing import Any

from agentscope.tool import FunctionTool

from agent_service_v2.tools.backend_learning_client import (
    BackendLearningClient,
    BackendLearningClientError,
)


def _bounded_recent_limit(limit: int) -> int:
    try:
        parsed = int(limit)
    except (TypeError, ValueError):
        return 10
    return max(1, min(parsed, 10))


def _bounded_node_limit(limit: int) -> int:
    try:
        parsed = int(limit)
    except (TypeError, ValueError):
        return 50
    return max(1, min(parsed, 100))


def _error_result(reason: str, status_code: int | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"status": "unavailable", "reason": reason}
    if status_code is not None:
        result["status_code"] = status_code
    return result


def build_learning_progress_tools(
    *,
    client: BackendLearningClient | None,
    user_id: str,
    course_id: str | None,
) -> list[FunctionTool]:
    async def read_learning_progress(limit_nodes: int = 50) -> dict[str, Any]:
        if client is None:
            return _error_result("backend_learning_client_not_configured")
        if not course_id:
            return _error_result("course_context_missing")
        try:
            return await client.post_json(
                "/internal/ai-chat/learning-progress",
                {
                    "user_id": user_id,
                    "course_id": course_id,
                    "limit_nodes": _bounded_node_limit(limit_nodes),
                },
            )
        except BackendLearningClientError as exc:
            return _error_result(exc.reason, exc.status_code)

    async def read_recent_answers(
        node_id: str | None = None,
        knowledge_point: str | None = None,
        limit: int = 10,
        only_wrong: bool = True,
    ) -> dict[str, Any]:
        if client is None:
            return _error_result("backend_learning_client_not_configured")
        if not course_id:
            return _error_result("course_context_missing")
        try:
            return await client.post_json(
                "/internal/ai-chat/recent-answers",
                {
                    "user_id": user_id,
                    "course_id": course_id,
                    "node_id": node_id,
                    "knowledge_point": knowledge_point,
                    "limit": _bounded_recent_limit(limit),
                    "only_wrong": bool(only_wrong),
                },
            )
        except BackendLearningClientError as exc:
            return _error_result(exc.reason, exc.status_code)

    return [
        FunctionTool(
            read_learning_progress,
            name="read_learning_progress",
            description="Read the current learner's course progress overview before giving next-step learning advice.",
            is_read_only=True,
        ),
        FunctionTool(
            read_recent_answers,
            name="read_recent_answers",
            description="Read up to 10 recent answer records for a node or knowledge point before explaining mistakes.",
            is_read_only=True,
        ),
    ]
```

- [ ] **Step 4: Run tool tests**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/pytest tests/test_learning_progress_tools.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent_service_v2/src/agent_service_v2/tools/learning_progress.py agent_service_v2/tests/test_learning_progress_tools.py
git commit -m "feat: 新增AIChat学习进度只读工具"
```

---

## Task 5: Workbench Toolkit Integration

**Files:**
- Modify: `agent_service_v2/src/agent_service_v2/tools/workbench_toolkit.py`
- Modify: `agent_service_v2/src/agent_service_v2/agents/workbench_factory.py`
- Modify: `agent_service_v2/src/agent_service_v2/agents/permissions.py`
- Modify: `agent_service_v2/src/agent_service_v2/agents/prompts.py`
- Modify: `agent_service_v2/tests/test_workbench_toolkit.py`
- Modify: `agent_service_v2/tests/test_workbench_factory.py`

**Interfaces:**
- Consumes: `build_learning_progress_tools()`.
- Produces: Workbench Agent has `learning_progress` ToolGroup with `read_learning_progress` and `read_recent_answers`, and permission allow rules for both tools.

- [ ] **Step 1: Update failing toolkit test**

Modify `agent_service_v2/tests/test_workbench_toolkit.py` expected group order:

```python
def test_workbench_tool_groups_include_expected_boundaries():
    groups = build_workbench_tool_groups(
        memory_tools=[],
        rag_tools=[],
        learning_progress_tools=[],
        workspace=LocalWorkspace(workdir="/tmp/eduagent-test-workspace", workspace_id="ws"),
        run_id="run-1",
    )

    assert [group.name for group in groups] == [
        "planning",
        "learning_state",
        "artifact",
        "review",
    ]
```

Append a new test:

```python
def test_workbench_tool_groups_include_learning_progress_group_when_tools_exist():
    class FakeTool:
        name = "read_learning_progress"

    groups = build_workbench_tool_groups(
        memory_tools=[],
        rag_tools=[],
        learning_progress_tools=[FakeTool()],
        workspace=LocalWorkspace(workdir="/tmp/eduagent-test-workspace", workspace_id="ws"),
        run_id="run-1",
    )

    assert [group.name for group in groups] == [
        "planning",
        "learning_progress",
        "learning_state",
        "artifact",
        "review",
    ]
```

- [ ] **Step 2: Update failing factory permission test**

Modify `agent_service_v2/tests/test_workbench_factory.py` permission assertions:

```python
    assert "read_learning_progress" in allow_rules
    assert "read_recent_answers" in allow_rules
```

Append:

```python
def test_factory_prompt_mentions_learning_progress_tools(tmp_path: Path):
    class FakeModel:
        pass

    workspace = WorkbenchWorkspaceManager(root_dir=tmp_path).get_workspace(
        user_id="u1",
        course_id="c1",
        conversation_id="conv1",
    )
    factory = WorkbenchAgentFactory(model_provider=lambda: FakeModel())

    agent = factory.create_agent(
        user_id="u1",
        course_id="c1",
        workspace=workspace,
        run_id="run-1",
    )

    assert "read_learning_progress" in agent.system_prompt
    assert "read_recent_answers" in agent.system_prompt
    assert "do not fabricate" in agent.system_prompt.lower()
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/pytest tests/test_workbench_toolkit.py tests/test_workbench_factory.py -q
```

Expected: FAIL because `build_workbench_tool_groups()` does not accept `learning_progress_tools`, permissions do not allow new tools, and prompt lacks tool rules.

- [ ] **Step 4: Integrate tools into toolkit**

Modify signature in `agent_service_v2/src/agent_service_v2/tools/workbench_toolkit.py`:

```python
def build_workbench_tool_groups(
    *,
    memory_tools: list[ToolBase] | None,
    rag_tools: list[ToolBase] | None,
    learning_progress_tools: list[ToolBase] | None,
    workspace: LocalWorkspace,
    run_id: str,
) -> list[ToolGroup]:
```

Insert after planning group:

```python
    if learning_progress_tools:
        groups.append(
            ToolGroup(
                name="learning_progress",
                description="Read real learner progress and recent answer evidence from Backend.",
                instructions=(
                    "Use read_learning_progress before giving overall next-step learning advice. "
                    "Use read_recent_answers before explaining specific mistakes. "
                    "If the tools return empty or unavailable data, say evidence is insufficient."
                ),
                tools=learning_progress_tools,
            )
        )
```

- [ ] **Step 5: Integrate tools into factory**

Modify imports in `agent_service_v2/src/agent_service_v2/agents/workbench_factory.py`:

```python
from agent_service_v2.tools.backend_learning_client import build_backend_learning_client_from_settings
from agent_service_v2.tools.learning_progress import build_learning_progress_tools
```

In `create_agent()`, before `Toolkit(...)`:

```python
        learning_client = build_backend_learning_client_from_settings()
        learning_progress_tools = build_learning_progress_tools(
            client=learning_client,
            user_id=user_id,
            course_id=course_id,
        )
```

Pass to toolkit:

```python
                learning_progress_tools=learning_progress_tools,
```

- [ ] **Step 6: Allow new tools**

Modify `SAFE_WORKBENCH_TOOLS` in `agent_service_v2/src/agent_service_v2/agents/permissions.py`:

```python
    "read_learning_progress",
    "read_recent_answers",
```

- [ ] **Step 7: Add prompt rules**

Append to `WORKBENCH_SYSTEM_PROMPT` in `agent_service_v2/src/agent_service_v2/agents/prompts.py`:

```text

Learning progress tool rules:
- When the user asks for next-step learning advice, call read_learning_progress first.
- When the user asks what they got wrong or why a knowledge point is weak, call read_recent_answers for the relevant node_id or knowledge_point.
- If no answer evidence is available, do not fabricate mistake causes; say the current records are insufficient.
- These tools are read-only. Do not claim that you updated learning paths, mastery status, or long-term memory.
```

- [ ] **Step 8: Run integration tests**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/pytest tests/test_workbench_toolkit.py tests/test_workbench_factory.py tests/test_learning_progress_tools.py tests/test_backend_learning_client.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add agent_service_v2/src/agent_service_v2/tools/workbench_toolkit.py agent_service_v2/src/agent_service_v2/agents/workbench_factory.py agent_service_v2/src/agent_service_v2/agents/permissions.py agent_service_v2/src/agent_service_v2/agents/prompts.py agent_service_v2/tests/test_workbench_toolkit.py agent_service_v2/tests/test_workbench_factory.py
git commit -m "feat: Workbench接入学习进度查询工具"
```

---

## Task 6: Tool Result Summaries in EDU Events

**Files:**
- Modify: `agent_service_v2/src/agent_service_v2/runtime/protocol_adapter.py`
- Modify: `agent_service_v2/tests/test_protocol_adapter.py`

**Interfaces:**
- Consumes: Tool result text captured from `ToolResultTextDeltaEvent`.
- Produces: `tool_completed.payload` may include `status`, `reason`, `output_summary`, and `returned_count` when tool result JSON contains those fields.

- [ ] **Step 1: Write failing adapter test**

Append to `agent_service_v2/tests/test_protocol_adapter.py`:

```python
import json

from agentscope.event import ToolCallStartEvent, ToolResultEndEvent, ToolResultTextDeltaEvent


def test_protocol_adapter_passes_learning_tool_result_summary():
    adapter = EDUProtocolAdapter(run_id="run-1", conversation_id="conv-1")
    start = ToolCallStartEvent(
        name="agent",
        reply_id="reply-1",
        tool_call_id="tool-1",
        tool_call_name="read_recent_answers",
    )
    result_text = json.dumps({
        "status": "available",
        "summary": {"returned_count": 3, "has_more": False},
    })
    delta = ToolResultTextDeltaEvent(
        name="agent",
        reply_id="reply-1",
        tool_call_id="tool-1",
        delta=result_text,
    )
    end = ToolResultEndEvent(
        name="agent",
        reply_id="reply-1",
        tool_call_id="tool-1",
        state="success",
    )

    assert adapter.adapt(start).type.value == "tool_started"
    assert adapter.adapt(delta) is None
    event = adapter.adapt(end)

    assert event.type.value == "tool_completed"
    assert event.payload["tool_name"] == "read_recent_answers"
    assert event.payload["status"] == "available"
    assert event.payload["returned_count"] == 3
    assert "3" in event.payload["output_summary"]
```

If existing tests import these event classes already, merge imports instead of duplicating them.

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/pytest tests/test_protocol_adapter.py -q
```

Expected: FAIL because `tool_completed.payload` lacks `tool_name`, `status`, `returned_count`, or `output_summary`.

- [ ] **Step 3: Add summary extraction**

Modify `ToolResultEndEvent` branch in `agent_service_v2/src/agent_service_v2/runtime/protocol_adapter.py`:

```python
        if isinstance(event, ToolResultEndEvent):
            payload: dict[str, Any] = {
                "tool_call_id": event.tool_call_id,
                "tool_name": self._tool_names.get(event.tool_call_id),
                "state": getattr(event.state, "value", event.state),
            }
            parsed = _parse_json_object(self._tool_result_text.get(event.tool_call_id, ""))
            if parsed:
                if "status" in parsed:
                    payload["status"] = parsed["status"]
                if "reason" in parsed:
                    payload["reason"] = parsed["reason"]
                summary = parsed.get("summary") if isinstance(parsed.get("summary"), dict) else {}
                returned_count = summary.get("returned_count")
                if returned_count is not None:
                    payload["returned_count"] = returned_count
                    payload["output_summary"] = f"返回 {returned_count} 条学习记录"
                elif parsed.get("status"):
                    payload["output_summary"] = f"工具状态：{parsed['status']}"
            return EduEventType.TOOL_COMPLETED, payload
```

- [ ] **Step 4: Run adapter tests**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/pytest tests/test_protocol_adapter.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent_service_v2/src/agent_service_v2/runtime/protocol_adapter.py agent_service_v2/tests/test_protocol_adapter.py
git commit -m "feat: 透传学习工具结果摘要"
```

---

## Task 7: Final Verification and WorkLine

**Files:**
- Modify: `WorkLine.md`

**Interfaces:**
- Consumes: All previous tasks.
- Produces: Project record of implemented files, verification results, and interface drift.

- [ ] **Step 1: Run Backend targeted tests**

Run:

```bash
cd backend && ../.venv/bin/python -m pytest tests/test_ai_chat_learning_context.py tests/test_internal_ai_chat.py tests/test_learning_activities.py tests/test_learning_path_realtime.py -q
```

Expected: PASS.

- [ ] **Step 2: Run Backend syntax checks**

Run:

```bash
cd backend && ../.venv/bin/python -m py_compile app/services/ai_chat_learning_context.py app/api/v1/internal_ai_chat.py app/schemas/internal_ai_chat.py app/core/config.py app/main.py
```

Expected: PASS with no output.

- [ ] **Step 3: Run Agent Service targeted tests**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/pytest tests/test_backend_learning_client.py tests/test_learning_progress_tools.py tests/test_workbench_toolkit.py tests/test_workbench_factory.py tests/test_protocol_adapter.py -q
```

Expected: PASS.

- [ ] **Step 4: Run Agent Service syntax checks**

Run:

```bash
cd agent_service_v2 && ./.venv/bin/python -m py_compile src/agent_service_v2/tools/backend_learning_client.py src/agent_service_v2/tools/learning_progress.py src/agent_service_v2/tools/workbench_toolkit.py src/agent_service_v2/agents/workbench_factory.py src/agent_service_v2/agents/permissions.py src/agent_service_v2/agents/prompts.py src/agent_service_v2/runtime/protocol_adapter.py
```

Expected: PASS with no output.

- [ ] **Step 5: Run existing frontend-free AIChat regressions**

Run:

```bash
cd backend && ../.venv/bin/python -m pytest tests/test_tutoring_stream_adapter.py -q
cd agent_service_v2 && ./.venv/bin/pytest tests/test_workbench_session.py tests/test_workbench_api.py -q
```

Expected: PASS.

- [ ] **Step 6: Append WorkLine record**

Append to `WorkLine.md`:

```markdown
### 2026-07-09 — AIChat 接入学习进度与最近答题查询工具

**涉及文件：**
- `backend/app/core/config.py`
- `backend/app/schemas/internal_ai_chat.py`
- `backend/app/services/ai_chat_learning_context.py`
- `backend/app/api/v1/internal_ai_chat.py`
- `backend/app/main.py`
- `backend/tests/test_ai_chat_learning_context.py`
- `backend/tests/test_internal_ai_chat.py`
- `agent_service_v2/src/agent_service_v2/tools/backend_learning_client.py`
- `agent_service_v2/src/agent_service_v2/tools/learning_progress.py`
- `agent_service_v2/src/agent_service_v2/tools/workbench_toolkit.py`
- `agent_service_v2/src/agent_service_v2/agents/workbench_factory.py`
- `agent_service_v2/src/agent_service_v2/agents/permissions.py`
- `agent_service_v2/src/agent_service_v2/agents/prompts.py`
- `agent_service_v2/src/agent_service_v2/runtime/protocol_adapter.py`
- `agent_service_v2/tests/test_backend_learning_client.py`
- `agent_service_v2/tests/test_learning_progress_tools.py`
- `agent_service_v2/tests/test_workbench_toolkit.py`
- `agent_service_v2/tests/test_workbench_factory.py`
- `agent_service_v2/tests/test_protocol_adapter.py`

**核心改动：**
Backend 新增 service-token 保护的 internal AIChat 学习查询接口，支持读取课程学习进度总览和按节点/知识点查询最近最多 10 条答题记录。Agent Service v2 新增 `read_learning_progress` 与 `read_recent_answers` 只读 AgentScope tools，通过 Backend internal API 真查询学习事实，Workbench prompt 要求给出下一步建议前先查询进度、分析错因前先查询最近答题，查不到数据时不得编造错因。

**验证结果：**
- Backend targeted：记录 Step 1/2 实际运行的 pytest 命令和 PASS/FAIL 结果
- Backend py_compile：记录 Step 2 实际运行的 py_compile 命令和 PASS/FAIL 结果
- Agent targeted：记录 Step 3/4/5/6 实际运行的 pytest 命令和 PASS/FAIL 结果
- Agent py_compile：记录 Step 3/4/5/6 实际运行的 py_compile 命令和 PASS/FAIL 结果
- AIChat regressions：记录 Step 5 实际运行的 Workbench API/session 回归命令和 PASS/FAIL 结果

**接口漂移：**
有。新增 Backend internal API：`POST /internal/ai-chat/learning-progress`、`POST /internal/ai-chat/recent-answers`，仅供 Agent Service 通过 `X-Internal-Agent-Token` 调用；新增 Agent v2 只读工具 `read_learning_progress` 与 `read_recent_answers`。Client API 与 SSE event type 无漂移。
```

Before committing, replace the five `记录 ... 实际运行` verification bullets with the exact command text and observed result.

- [ ] **Step 7: Commit WorkLine**

```bash
git add WorkLine.md
git commit -m "docs: 记录AIChat学习查询工具落地"
```

---

## Self-Review

**Spec coverage:**
- Backend internal APIs from spec sections 6.2 and 6.3 are covered by Tasks 1 and 2.
- Internal token auth from section 6.1 is covered by Task 2.
- Backend service separation from section 7 is covered by Task 1.
- AgentScope `FunctionTool` / `ToolGroup` / `Toolkit` registration from section 8 is covered by Tasks 4 and 5.
- Agent behavior rules from section 9 are covered by Task 5 prompt updates.
- No Client API / no SSE event type drift from section 11 is preserved; Task 6 only enriches existing `tool_completed.payload`.
- Security rules from section 12 are covered by Tasks 2, 4, and 5.
- Testing requirements from section 13 are mapped to Tasks 1 through 7.

**Placeholder scan:**
- Red-flag terms from the No Placeholders section were searched and removed. The WorkLine task requires exact observed command results before commit.

**Type consistency:**
- Backend service function names match router and tests.
- Agent tool names match permission rules, prompt rules, and toolkit tests.
- Internal API paths match Backend client calls and spec.
