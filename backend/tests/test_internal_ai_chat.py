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
from app.schemas.internal_ai_chat import PersonalPracticePrepareRequest


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
async def test_internal_recent_answers_validates_explicit_scope_and_limit():
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
                        "scope": "knowledge_point",
                        "knowledge_point": "AVL 树旋转",
                        "limit": 10,
                        "only_wrong": True,
                    },
                )

    assert response.status_code == 200
    kwargs = mock_service.await_args.kwargs
    assert kwargs["limit"] == 10
    assert kwargs["scope"] == "knowledge_point"


def _choice_prepare_payload():
    return {
        "user_id": "u1",
        "course_id": "offering-1",
        "conversation_id": "conv-1",
        "run_id": "run-1",
        "practice_type": "choice_quiz",
        "choice_quiz": {
            "title": "指针练习",
            "chapter": "指针",
            "knowledge_point": "指针基础",
            "questions": [{
                "type": "single_choice",
                "content": "哪个运算符用于取地址？",
                "options": [{"key": "A", "text": "&"}, {"key": "B", "text": "*"}],
                "answer": "A",
                "explanation": "& 是取地址运算符。",
                "difficulty": "easy",
            }],
        },
    }


@pytest.mark.asyncio
async def test_internal_prepare_rejects_unsupported_question_type():
    payload = _choice_prepare_payload()
    payload["choice_quiz"]["questions"][0]["type"] = "code"
    with patch("app.api.v1.internal_ai_chat.settings.INTERNAL_AGENT_TOKEN", "secret"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/internal/ai-chat/personal-practices/prepare",
                headers={"X-Internal-Agent-Token": "secret"},
                json=payload,
            )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_internal_prepare_returns_pending_generation():
    from types import SimpleNamespace

    with patch("app.api.v1.internal_ai_chat.settings.INTERNAL_AGENT_TOKEN", "secret"):
        with patch(
            "app.api.v1.internal_ai_chat.prepare_personal_practice_delivery",
            new_callable=AsyncMock,
            return_value=SimpleNamespace(id="generation-1", status="delivery_pending"),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/internal/ai-chat/personal-practices/prepare",
                    headers={"X-Internal-Agent-Token": "secret"},
                    json=_choice_prepare_payload(),
                )

    assert response.status_code == 200
    assert response.json()["data"] == {
        "generation_id": "generation-1",
        "status": "delivery_pending",
    }


@pytest.mark.asyncio
async def test_internal_finalize_returns_backend_artifact_descriptor():
    result = {
        "generation_id": "generation-1",
        "status": "published",
        "artifact": {
            "id": "generation-1",
            "type": "QuizCard",
            "title": "指针练习",
            "course_id": "offering-1",
            "question_ids": ["question-1"],
        },
        "delivery_attempts": 1,
    }
    with patch("app.api.v1.internal_ai_chat.settings.INTERNAL_AGENT_TOKEN", "secret"):
        with patch(
            "app.api.v1.internal_ai_chat.finalize_personal_practice_delivery",
            new_callable=AsyncMock,
            return_value=result,
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/internal/ai-chat/personal-practices/finalize",
                    headers={"X-Internal-Agent-Token": "secret"},
                    json={
                        "generation_id": "generation-1",
                        "user_id": "u1",
                        "course_id": "offering-1",
                    },
                )
    assert response.status_code == 200
    assert response.json()["data"] == result


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/internal/ai-chat/code-problem-validations",
        "/internal/ai-chat/choice-quizzes",
    ],
)
async def test_retired_ai_chat_practice_routes_are_not_available(path):
    with patch("app.api.v1.internal_ai_chat.settings.INTERNAL_AGENT_TOKEN", "secret"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                path,
                headers={"X-Internal-Agent-Token": "secret"},
                json={},
            )

    assert response.status_code == 404


def test_personal_practice_prepare_schema_requires_exactly_one_draft():
    schema = PersonalPracticePrepareRequest.model_json_schema()
    properties = schema["properties"]

    assert set(schema["required"]) == {
        "user_id",
        "course_id",
        "conversation_id",
        "run_id",
        "practice_type",
    }
    assert properties["practice_type"]["enum"] == ["choice_quiz", "code_problem"]
    assert properties["run_id"]["maxLength"] == 80

    payload = _choice_prepare_payload()
    payload["code_problem"] = {
        "title": "unexpected",
        "statement": "unexpected",
        "language": "python",
        "starter_code": "",
        "reference_solution": "print(input())",
        "test_inputs": [
            {"stdin": "public", "is_public": True},
            {"stdin": "hidden", "is_public": False},
        ],
    }
    with pytest.raises(ValueError, match="requires only choice_quiz draft"):
        PersonalPracticePrepareRequest.model_validate(payload)
