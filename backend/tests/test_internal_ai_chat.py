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


@pytest.mark.asyncio
async def test_internal_code_problem_returns_stable_validation_reason():
    from app.services.code_problem_service import CodeProblemValidationError

    with patch("app.api.v1.internal_ai_chat.settings.INTERNAL_AGENT_TOKEN", "secret"):
        with patch(
            "app.api.v1.internal_ai_chat.create_validated_personal_problem_from_ai_chat",
            new_callable=AsyncMock,
        ) as mock_service:
            mock_service.side_effect = CodeProblemValidationError(
                "conversation_ownership_check_failed"
            )
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/internal/ai-chat/code-problem-validations",
                    headers={"X-Internal-Agent-Token": "secret"},
                    json={
                        "user_id": "u1",
                        "course_id": "offering-1",
                        "conversation_id": "conv-1",
                        "run_id": "run-1",
                        "draft": {
                            "title": "回显",
                            "statement": "读取并输出输入。",
                            "language": "python",
                            "starter_code": "print(input())",
                            "reference_solution": "print(input())",
                            "test_inputs": [
                                {"stdin": "1\n", "is_public": True},
                                {"stdin": "2\n", "is_public": False},
                            ],
                        },
                    },
                )

    assert response.status_code == 400
    assert response.json()["detail"]["data"]["reason"] == "conversation_ownership_check_failed"


@pytest.mark.asyncio
async def test_internal_code_problem_returns_published_problem_id():
    from types import SimpleNamespace

    created = SimpleNamespace(
        generation=SimpleNamespace(id="generation-1", status="published"),
        problem=SimpleNamespace(id="problem-1", language="python"),
        public_case_count=1,
        hidden_case_count=1,
    )
    with patch("app.api.v1.internal_ai_chat.settings.INTERNAL_AGENT_TOKEN", "secret"):
        with patch(
            "app.api.v1.internal_ai_chat.create_validated_personal_problem_from_ai_chat",
            new_callable=AsyncMock,
            return_value=created,
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/internal/ai-chat/code-problem-validations",
                    headers={"X-Internal-Agent-Token": "secret"},
                    json={
                        "user_id": "u1",
                        "course_id": "offering-1",
                        "conversation_id": "conv-1",
                        "run_id": "run-1",
                        "draft": {
                            "title": "回显",
                            "statement": "读取并输出输入。",
                            "language": "python",
                            "starter_code": "print(input())",
                            "reference_solution": "print(input())",
                            "test_inputs": [
                                {"stdin": "1\n", "is_public": True},
                                {"stdin": "2\n", "is_public": False},
                            ],
                        },
                    },
                )

    assert response.status_code == 200
    assert response.json()["data"] == {
        "generation_id": "generation-1",
        "status": "published",
        "problem_id": "problem-1",
        "language": "python",
        "public_case_count": 1,
        "hidden_case_count": 1,
    }
