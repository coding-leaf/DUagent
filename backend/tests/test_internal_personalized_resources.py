from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_db
from app.main import app


@pytest.mark.asyncio
async def test_internal_personalized_draft_requires_agent_token():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/internal/personalized-resources/drafts",
            json={
                "user_id": "u1",
                "course_id": "c1",
                "source_type": "manual",
                "goal": "复习指针",
                "resource_type": "personal_lesson",
                "draft": {"title": "指针", "content": "# 指针"},
            },
        )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_internal_personalized_publish_delegates_owner_scoped_service():
    resource = MagicMock(id="resource-1", type="personal_lesson")
    with patch(
        "app.api.v1.internal_personalized_resources.settings.INTERNAL_AGENT_TOKEN",
        "secret",
    ), patch(
        "app.api.v1.internal_personalized_resources.PersonalizedResourceGenerationService.publish",
        new_callable=AsyncMock,
        return_value=resource,
    ) as publish:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/internal/personalized-resources/generation-1/publish",
                headers={"X-Internal-Agent-Token": "secret"},
                json={"user_id": "u1", "course_id": "c1"},
            )

    assert response.status_code == 200
    assert response.json()["data"]["resource_id"] == "resource-1"
    assert publish.await_args.kwargs == {"user_id": "u1", "course_id": "c1"}


@pytest.mark.asyncio
async def test_internal_fail_task_endpoint_updates_async_task():
    db = MagicMock()
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    task = MagicMock(id="task-123", status="processing", error_code=None, error_message="", completed_at=None)
    result = MagicMock()
    result.scalar_one_or_none.return_value = task
    db.execute.return_value = result

    async def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with patch(
            "app.api.v1.internal_personalized_resources.settings.INTERNAL_AGENT_TOKEN",
            "secret",
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/internal/personalized-resources/tasks/task-123/fail",
                    headers={"X-Internal-Agent-Token": "secret"},
                    json={"error_code": "llm_timeout", "error_message": "LLM generation timed out"},
                )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json()["data"]["task_id"] == "task-123"
    assert response.json()["data"]["status"] == "failed"
    assert task.status == "failed"
    assert task.error_code == "llm_timeout"
    assert task.error_message == "LLM generation timed out"
    assert task.completed_at is not None


@pytest.mark.asyncio
async def test_internal_fail_task_endpoint_returns_404_when_not_found():
    db = MagicMock()
    db.execute = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result

    async def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with patch(
            "app.api.v1.internal_personalized_resources.settings.INTERNAL_AGENT_TOKEN",
            "secret",
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/internal/personalized-resources/tasks/missing-task/fail",
                    headers={"X-Internal-Agent-Token": "secret"},
                    json={"error_code": "error", "error_message": "fail"},
                )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 404

