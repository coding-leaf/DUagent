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
